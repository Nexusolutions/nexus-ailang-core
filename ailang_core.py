#!/usr/bin/env python3
"""
Nexus AILang-Core v7.0 - Runtime cognitivo + transporte TCP/Unix/IPv6 con TLS,
ACK, reintentos, cola persistente cifrada, dedup persistente, brain IR,
retrieval híbrido y presupuesto de latencia.

Cambios v6.9 → v7.0:
  - CognitiveCompiler / CognitiveIR / CognitiveRuntime (DSL brain.*).
  - CognitiveBrainStore + HybridRetriever + CognitiveBrainEngine.
  - SchemaPack, evidencia, proveniencia, Zero-Footprint en memoria.
  - Integración de v6.9: Unix/IPv6, ordered, latencia jerárquica,
    metrics.prometheus(), stable_msg_id, parse_address.

Cambios v6.7 → v6.8:
  - Compresión zlib opcional de payloads.
  - Keep-alive / pool de conexiones TCP.
  - Graceful shutdown con flush del outbox.
  - Métricas (p50/p95) + health().
  - Snapshot/restore del motor latente.
  - Entrega ordenada por peer (opcional).
  - CLI outbox (list/requeue/purge/counts).
  - strip_comments con triple-quotes.
  - Re-validación de purge_after al decodificar.

Previos v6.7 (A+B+C):
  A) Fiabilidad
     - Deduplicación persistente (tabla `seen` en SQLite, sobrevive reinicios).
     - ACK tras procesamiento opcional (`ack_after_process=True`): el ACK
       solo se envía si `on_message` termina sin excepción.
     - HardLatencyBudget con proceso real (`multiprocessing`) y fallback a hilo.
  B) Seguridad
     - `require_auth=True` por defecto.
     - Cifrado del outbox obligatorio si hay `secret` (deriva clave vía HKDF).
     - Rotación de claves Fernet (campo `key_version` en cada fila).
  C) Todo lo anterior unificado + tests ampliados.

Qué hace de verdad:
  - Compilador: quita comentarios (respetando strings), exige purge_after(<n>ms),
    empaqueta cabecera + digest SHA-256 + código fuente.
  - Presupuesto de latencia soft (context manager) y hard (proceso/hilo).
  - Motor latente con validación de forma/dtype/valores y purga real.
  - Canal y nodos con búfer acotado (deque).
  - Transporte TCP: frames con prefijo de longitud, arrays SIN pickle,
    HMAC opcional, TLS >= 1.2, ACK autenticado, reintentos con backoff+jitter,
    deduplicación por msg_id con ventana + TTL + persistencia.
  - Cola persistente (SQLite WAL): broadcast_durable guarda en disco ANTES
    de enviar; despachador reenvía hasta ACK (también tras reinicio).
    Dead letters acotadas. Cifrado del payload (Fernet, con rotación).

Qué NO hace (a propósito):
  - No es verificación formal.
  - No hay NPU: usa NumPy.
  - Sin TLS el transporte NO cifra en tránsito (HMAC = integridad, no
    confidencialidad). Con require_auth=True por defecto se exige secret o TLS.
  - Un SHA-256 no prueba autoría; usa sign_bytecode (Ed25519).
"""

from __future__ import annotations

import base64
import enum
import hashlib
import hmac
import json
import logging
import math
import multiprocessing as mp
import os
import random
import re
import secrets
import socket
import sqlite3
import ssl
import struct
import threading
import tempfile
import time
import unittest
import warnings
import zlib
import argparse
from pathlib import Path
import ast
import shlex
import sys
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeout,
)
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "AILangError", "CompilerError", "IntegrityError", "LatencyBudgetExceeded",
    "TransportError", "TcpTransport", "encode_message", "decode_message",
    "make_server_tls_context", "make_client_tls_context",
    "RetryPolicy", "encode_ack", "decode_ack",
    "PersistentOutbox", "OutboxDispatcher", "OutboxItem", "OutboxFull",
    "PersistentSeenStore",
    "Extension", "AILangCompiler", "CognitiveInstruction", "CognitiveIR",
    "CognitiveCompiler", "CognitiveRuntime", "DecodedProgram", "decode_bytecode",
    "sign_bytecode", "verify_bytecode_signature", "LatencyBudget",
    "SchemaType", "SchemaPack", "KnowledgeDocument", "KnowledgeChunk",
    "KnowledgeEntity", "KnowledgeRelation", "Evidence", "ProvenanceRecord",
    "RetrievalResult", "CognitiveBrainStore", "HybridRetriever",
    "CognitiveBrainEngine", "BrainEngine",
    "HardLatencyBudget", "NexusAIEngine", "BoundedChannel", "DistributedNode",
    "SourceInspector", "derive_outbox_key", "Metrics",
    "stable_msg_id", "parse_address",
]

AUTHOR = "Enrique Jimenez Garcia"
# P0-1 (FASE 1): el monolito reporta la misma versión que el paquete modular.
# Antes tenía __version__ = "2.0.0" discordante con ailang/__init__.py (5.0.0).
try:
    from ailang.versions import __version__ as _ailang_pkg_version
    __version__ = _ailang_pkg_version
except ImportError:
    # Fallback si ailang.versions no está disponible (ej.: tests aislados del monolito)
    __version__ = "5.1.0"
FORMAT_VERSION = 6
FORMAT_VERSION_SIGNED = 7  # P0-11: bytecode firmado Ed25519 (header + digest + payload + signature)
MAGIC = b"AUR6"
DEFAULT_BUDGET_MS = 33.0
DIGEST_SIZE = hashlib.sha256().digest_size  # 32
SIGNATURE_SIZE = 64  # P0-11: Ed25519 signature es siempre 64 bytes
COMPRESS_THRESHOLD = 1024

# =============================================================================
# Excepciones
# =============================================================================

class AILangError(Exception):
    """Base de todos los errores de AILang."""


class CompilerError(AILangError):
    """Fallo al compilar o decodificar un programa."""


class IntegrityError(AILangError):
    """Tensor inválido (forma, dtype, NaN/Inf) o bytecode alterado."""


class LatencyBudgetExceeded(AILangError):
    """Un ciclo superó su presupuesto de latencia."""


class TransportError(AILangError):
    """Fallo de red o mensaje no transportable."""


class OutboxFull(AILangError):
    """La cola persistente de salida alcanzó su límite de mensajes pendientes."""


# =============================================================================
# Métricas
# =============================================================================

@dataclass
class Metrics:
    """Contadores thread-safe simples."""
    messages_sent: int = 0
    messages_received: int = 0
    messages_deduped: int = 0
    acks_ok: int = 0
    send_failures: int = 0
    outbox_enqueued: int = 0
    outbox_delivered: int = 0
    outbox_dead: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    latency_samples_ms: list = None
    _lock: object = None

    def __post_init__(self):
        if self.latency_samples_ms is None:
            self.latency_samples_ms = []
        if self._lock is None:
            object.__setattr__(self, '_lock', threading.Lock())

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            setattr(self, name, getattr(self, name, 0) + n)

    def observe_latency(self, ms: float, max_samples: int = 1000) -> None:
        with self._lock:
            self.latency_samples_ms.append(ms)
            if len(self.latency_samples_ms) > max_samples:
                self.latency_samples_ms = self.latency_samples_ms[-max_samples:]

    def latency_percentile(self, p: float):
        with self._lock:
            if not self.latency_samples_ms:
                return None
            s = sorted(self.latency_samples_ms)
            idx = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
            return s[idx]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            samples = list(self.latency_samples_ms)
        p50 = p95 = None
        if samples:
            s = sorted(samples)
            p50 = s[min(len(s)-1, max(0, int(round(0.50 * (len(s)-1)))))]
            p95 = s[min(len(s)-1, max(0, int(round(0.95 * (len(s)-1)))))]
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "messages_deduped": self.messages_deduped,
            "acks_ok": self.acks_ok,
            "send_failures": self.send_failures,
            "outbox_enqueued": self.outbox_enqueued,
            "outbox_delivered": self.outbox_delivered,
            "outbox_dead": self.outbox_dead,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
        }

    def prometheus(self, prefix: str = "ailang") -> str:
        s = self.snapshot()
        lines = []
        for k, v in s.items():
            if v is None:
                continue
            name = f"{prefix}_{k}".replace(".", "_")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {float(v)}")
        return "\n".join(lines) + "\n"


def stable_msg_id(payload: "np.ndarray", salt: bytes = b"") -> str:
    """msg_id determinista a partir del contenido (idempotencia de aplicación)."""
    h = hashlib.sha256(salt)
    h.update(payload.dtype.name.encode())
    h.update(str(payload.shape).encode())
    h.update(np.ascontiguousarray(payload).tobytes())
    return h.hexdigest()[:16]


def parse_address(addr):
    """Devuelve ("tcp", (host, port)) | ("unix", path)."""
    if isinstance(addr, tuple):
        return "tcp", addr
    if isinstance(addr, str) and addr.startswith("unix://"):
        return "unix", addr[len("unix://"):]
    if isinstance(addr, str) and addr.startswith("/"):
        return "unix", addr
    if isinstance(addr, str) and addr.startswith("["):
        host, _, rest = addr[1:].partition("]")
        return "tcp", (host, int(rest.lstrip(":")))
    if isinstance(addr, str) and ":" in addr:
        host, _, port_s = addr.rpartition(":")
        try:
            return "tcp", (host, int(port_s))
        except ValueError:
            pass
    raise ValueError(f"Dirección no reconocida: {addr!r}")


# =============================================================================
# Compilador
# =============================================================================

class Extension(enum.IntFlag):
    DISTRIBUTED = 1
    VERIFY = 2
    HARDWARE = 4
    AGENT = 8
    LATENT = 16
    ALL = DISTRIBUTED | VERIFY | HARDWARE | AGENT | LATENT


_HEADER = struct.Struct(">4sBBHI")  # magic, versión, flags, presupuesto_ms, len(payload)
_PURGE_CLAUSE = re.compile(r"\bpurge_after\s*\(\s*(\d+)\s*ms\s*\)")


def strip_comments(source: str) -> str:
    """Elimina // y /* */ respetando strings simples, dobles y triple-quotes."""
    result: List[str] = []
    i = 0
    n = len(source)
    in_string: Optional[str] = None
    escape = False
    tq1 = chr(39) * 3
    tq2 = chr(34) * 3
    while i < n:
        ch = source[i]
        if in_string is not None:
            if escape:
                result.append(ch)
                escape = False
                i += 1
                continue
            if ch == "\\" and len(in_string) == 1:
                result.append(ch)
                escape = True
                i += 1
                continue
            if len(in_string) == 3:
                if source[i:i + 3] == in_string:
                    result.append(in_string)
                    i += 3
                    in_string = None
                    continue
                result.append(ch)
                i += 1
                continue
            if ch == in_string:
                result.append(ch)
                in_string = None
                i += 1
                continue
            result.append(ch)
            i += 1
            continue
        if source[i:i + 3] in (tq1, tq2):
            in_string = source[i:i + 3]
            result.append(in_string)
            i += 3
            continue
        if ch in ("'", '"'):
            in_string = ch
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        result.append(ch)
        i += 1
    return "".join(result)

@dataclass(frozen=True)
class CognitiveInstruction:
    """Una instrucción cognitiva ya validada por el compilador."""
    op: str
    args: Dict[str, Any] = field(default_factory=dict)
    line: int = 0
    required_capabilities: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CognitiveIR:
    """IR intermedia entre el parser del lenguaje y CognitiveBrainEngine."""
    version: int
    instructions: Tuple[CognitiveInstruction, ...] = ()
    required_capabilities: Tuple[str, ...] = ()
    digest: str = ""

    def manifest(self) -> Dict[str, Any]:
        return {
            "ir": "ailang-cognitive-ir-v1",
            "version": self.version,
            "required_capabilities": list(self.required_capabilities),
            "instructions": [
                {"op": i.op, "args": i.args, "line": i.line,
                 "required_capabilities": list(i.required_capabilities)}
                for i in self.instructions
            ],
            "digest": self.digest,
        }


class CognitiveCompiler:
    """Compila la DSL cognitiva declarativa de Nexus AILang-Core.

    Sintaxis soportada (una instrucción por línea):
      brain.ingest source="repo" path="Projects/A.md" content="..."
      brain.query text="knowledge graph" top_k=5
      brain.think text="..." top_k=5
      brain.graph entity="AILang" depth=2
      memory durable name="decision" value='{"x":1}'
      persist memory="decision"

    No ejecuta nada: solo produce CognitiveIR determinista. Esto permite que
    el compilador haga análisis estático antes de tocar memoria o conocimiento.
    """

    _OPS = {
        "brain.ingest": "knowledge.write",
        "brain.query": "knowledge.read",
        "brain.think": "knowledge.read",
        "brain.graph": "graph.traverse",
        "memory": "memory.write",
        "persist": "memory.persist",
    }

    @staticmethod
    def _literal(value: str, *, line: int, key: str) -> Any:
        # shlex elimina las comillas externas; por eso intentamos JSON/AST y,
        # finalmente, tratamos el token como string declarativo.
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
                return float(value) if "." in value else int(value)
            return value

    @classmethod
    def _parse_kv(cls, tokens: List[str], line: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for token in tokens:
            if "=" not in token:
                raise CompilerError(f"Línea {line}: se esperaba key=value, recibido '{token}'.")
            key, raw = token.split("=", 1)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise CompilerError(f"Línea {line}: clave inválida '{key}'.")
            out[key] = cls._literal(raw, line=line, key=key)
        return out

    @classmethod
    def parse(cls, source: str) -> CognitiveIR:
        clean = strip_comments(source)
        instructions: List[CognitiveInstruction] = []
        caps = set()
        memories: Dict[str, str] = {}

        for line_no, raw in enumerate(clean.splitlines(), 1):
            line = raw.strip()
            if not line or line in {"{", "}"} or line.startswith("purge_after("):
                continue
            if line.startswith("brain {") or line == "brain":
                continue
            # Permitir ';' al final para estilo declarativo.
            line = line.rstrip(";").strip()
            try:
                tokens = shlex.split(line, posix=True)
            except ValueError as exc:
                raise CompilerError(f"Línea {line_no}: sintaxis de strings: {exc}") from exc
            if not tokens:
                continue
            op = tokens[0]
            if op not in cls._OPS:
                # El compilador histórico sigue aceptando instrucciones no
                # cognitivas; solo analizamos las primitivas brain/memory.
                continue

            if op == "memory":
                if len(tokens) < 2 or tokens[1] not in {"volatile", "session", "durable"}:
                    raise CompilerError(f"Línea {line_no}: memory requiere volatile|session|durable.")
                args = cls._parse_kv(tokens[2:], line_no)
                if "name" not in args or "value" not in args:
                    raise CompilerError(f"Línea {line_no}: memory requiere name y value.")
                name = str(args["name"])
                if name in memories:
                    raise CompilerError(f"Línea {line_no}: memoria duplicada '{name}'.")
                memories[name] = tokens[1]
                args["persistence"] = tokens[1]
                required = ("memory.write",)
                instructions.append(CognitiveInstruction(op, args, line_no, required))
                caps.update(required)
                continue

            if op == "persist":
                args = cls._parse_kv(tokens[1:], line_no)
                name = args.get("memory")
                if name is None or str(name) not in memories:
                    raise CompilerError(f"Línea {line_no}: persist referencia memoria no declarada '{name}'.")
                persistence = memories[str(name)]
                if persistence == "volatile":
                    raise CompilerError(
                        f"Línea {line_no}: violación Zero-Footprint; memoria volatile '{name}' no puede persistirse."
                    )
                args["persistence"] = persistence
                required = ("memory.persist",)
                instructions.append(CognitiveInstruction(op, args, line_no, required))
                caps.update(required)
                continue

            args = cls._parse_kv(tokens[1:], line_no)
            required = (cls._OPS[op],)
            if op == "brain.ingest" and not {"source", "path", "content"}.issubset(args):
                raise CompilerError(f"Línea {line_no}: brain.ingest requiere source, path y content.")
            if op in {"brain.query", "brain.think"} and "text" not in args:
                raise CompilerError(f"Línea {line_no}: {op} requiere text.")
            if op == "brain.graph" and "entity" not in args:
                raise CompilerError(f"Línea {line_no}: brain.graph requiere entity.")
            instructions.append(CognitiveInstruction(op, args, line_no, required))
            caps.update(required)

        canonical = _json({
            "version": 1,
            "instructions": [
                {"op": i.op, "args": i.args, "line": i.line}
                for i in instructions
            ],
            "required_capabilities": sorted(caps),
        })
        return CognitiveIR(1, tuple(instructions), tuple(sorted(caps)), hashlib.sha256(canonical.encode()).hexdigest())


class CognitiveRuntime:
    """Puente seguro CognitiveIR -> CognitiveBrainEngine."""

    def __init__(self, engine: Any, *, capabilities: Optional[Sequence[str]] = None):
        self.engine = engine
        self.capabilities = set(capabilities or [])

    def _authorize(self, required: Sequence[str]) -> None:
        missing = [c for c in required if c not in self.capabilities]
        if missing:
            raise IntegrityError("Capacidades cognitivas insuficientes: " + ", ".join(missing))

    def execute(self, ir: CognitiveIR) -> List[Any]:
        results = []
        for instruction in ir.instructions:
            self._authorize(instruction.required_capabilities)
            a = instruction.args
            if instruction.op == "brain.ingest":
                results.append(self.engine.ingest(a["source"], a["path"], a["content"],
                                                   title=a.get("title"), doc_type=a.get("doc_type"),
                                                   metadata=a.get("metadata")))
            elif instruction.op == "brain.query":
                results.append(self.engine.search(str(a["text"]), top_k=int(a.get("top_k", 10))))
            elif instruction.op == "brain.think":
                results.append(self.engine.think(str(a["text"]), top_k=int(a.get("top_k", 8))))
            elif instruction.op == "brain.graph":
                results.append(self.engine.graph(str(a["entity"]), depth=int(a.get("depth", 2))))
            elif instruction.op == "memory":
                results.append(self.engine.store.persist_memory(
                    str(a["name"]), a["value"], persistence=str(a["persistence"])))
            elif instruction.op == "persist":
                # Reutiliza el valor ya declarado si no se reenvía en el IR.
                value = a["value"] if "value" in a else None
                results.append(self.engine.store.persist_memory(
                    str(a["memory"]), value, persistence=str(a["persistence"])))
        return results


class DecodedProgram:
    def __init__(self, version: int, flags: Extension, budget_ms: int, source: str,
                 cognitive_ir: Optional[CognitiveIR] = None):
        self.version = version
        self.flags = flags
        self.budget_ms = budget_ms
        self.source = source
        self.cognitive_ir = cognitive_ir or CognitiveCompiler.parse(source)


class AILangCompiler:
    """Compila fuente + Cognitive IR sin cambiar el formato físico del bytecode v6.

    P0-11: Soporta firma opcional Ed25519. Si se pasa `private_key`, se embebe
    la firma (64 bytes) entre el digest SHA-256 y el payload, y se bumpa
    `FORMAT_VERSION_SIGNED = 7` para distinguir formatos.
    """

    def __init__(self, source_code: str, extensions: Extension = Extension.ALL,
                 private_key: Any = None):
        self.source_code = source_code
        self.extensions = extensions
        self.cognitive_ir: Optional[CognitiveIR] = None
        self.private_key = private_key

    def compile_ir(self) -> CognitiveIR:
        self.cognitive_ir = CognitiveCompiler.parse(self.source_code)
        return self.cognitive_ir

    def compile(self) -> bytes:
        clean = strip_comments(self.source_code)
        match = _PURGE_CLAUSE.search(clean)
        if match is None:
            raise CompilerError("Falta la cláusula obligatoria 'purge_after(<n>ms)'.")
        budget_ms = int(match.group(1))
        if not 0 < budget_ms <= 0xFFFF:
            raise CompilerError("El presupuesto de purga debe estar entre 1 y 65535 ms.")
        # Paso cognitivo obligatorio: falla antes de generar bytecode si la DSL
        # contiene errores semánticos o viola Zero-Footprint.
        self.compile_ir()
        payload = self.source_code.encode("utf-8")
        version = FORMAT_VERSION_SIGNED if self.private_key is not None else FORMAT_VERSION
        header = _HEADER.pack(MAGIC, version, int(self.extensions), budget_ms, len(payload))
        digest = hashlib.sha256(payload).digest()
        body = header + digest + payload
        if self.private_key is not None:
            signature = sign_bytecode(body, self.private_key)
            return body + signature
        return body

    def compile_and_execute(self, engine: Any, *, capabilities: Optional[Sequence[str]] = None) -> List[Any]:
        """Compila, autoriza y ejecuta las primitivas cognitivas del programa."""
        ir = self.compile_ir()
        runtime = CognitiveRuntime(engine, capabilities=capabilities)
        return runtime.execute(ir)

def decode_bytecode(blob: bytes, public_key: Any = None,
                    require_signature: bool = False) -> DecodedProgram:
    """Decodifica y valida bytecode AILang.

    P0-11: Soporta verificación opcional de firma Ed25519. Si el blob es v7
    (firmado) y `public_key` se pasa, verifica la firma. Si el blob es v7 y
    `require_signature=True` pero no se pasa `public_key`, lanza IntegrityError.
    Bloques v6 sin firma son aceptados retroactivamente.
    """
    if len(blob) < _HEADER.size + DIGEST_SIZE:
        raise CompilerError("Bytecode demasiado corto.")
    magic, version, flags, budget_ms, length = _HEADER.unpack_from(blob)
    if magic != MAGIC:
        raise CompilerError("Cabecera mágica inválida.")
    if version not in (FORMAT_VERSION, FORMAT_VERSION_SIGNED):
        raise CompilerError(f"Versión no soportada: {version}.")
    digest = blob[_HEADER.size:_HEADER.size + DIGEST_SIZE]
    payload = blob[_HEADER.size + DIGEST_SIZE:]
    # Si es v7 firmado, los últimos SIGNATURE_SIZE bytes son la firma
    signature: Optional[bytes] = None
    if version == FORMAT_VERSION_SIGNED:
        if len(payload) < length + SIGNATURE_SIZE:
            raise IntegrityError("Bytecode firmado pero signature ausente o truncada.")
        signature = payload[length:length + SIGNATURE_SIZE]
        payload = payload[:length]
    if len(payload) != length:
        raise IntegrityError("Longitud del payload no coincide con la cabecera.")
    if hashlib.sha256(payload).digest() != digest:
        raise IntegrityError("El digest no coincide: bytecode alterado.")
    # Verificación de firma (P0-11)
    if version == FORMAT_VERSION_SIGNED:
        if public_key is None:
            if require_signature:
                raise IntegrityError(
                    "Bytecode firmado pero no se proporcionó public_key "
                    "y require_signature=True."
                )
            # Aceptamos retroactivamente si no se exige verificación
        else:
            assert signature is not None
            signed_body = blob[:_HEADER.size + DIGEST_SIZE + length]
            if not verify_bytecode_signature(signed_body, signature, public_key):
                raise IntegrityError("Firma Ed25519 inválida: bytecode falsificado.")
    elif require_signature:
        raise IntegrityError(
            "require_signature=True pero el bytecode no está firmado (FORMAT_VERSION=6)."
        )
    source = payload.decode("utf-8")
    if _PURGE_CLAUSE.search(strip_comments(source)) is None:
        raise IntegrityError("Bytecode sin cláusula purge_after válida tras decodificar.")
    return DecodedProgram(version, Extension(flags), budget_ms, source)


def sign_bytecode(blob: bytes, private_key: Any) -> bytes:
    """Firma Ed25519 (requiere cryptography). Devuelve 64 bytes de signature."""
    return private_key.sign(blob)


def verify_bytecode_signature(blob: bytes, signature: bytes, public_key: Any) -> bool:
    """Verifica Ed25519. Devuelve True si la firma es válida, False en caso contrario."""
    from cryptography.exceptions import InvalidSignature
    try:
        public_key.verify(signature, blob)
        return True
    except InvalidSignature:
        return False


class SourceInspector:
    def inspect(self, source: str) -> Dict[str, Any]:
        clean = strip_comments(source)
        match = _PURGE_CLAUSE.search(clean)
        return {
            "has_purge_clause": match is not None,
            "budget_ms": int(match.group(1)) if match else None,
            "lines": len(source.strip().splitlines()),
        }


# =============================================================================
# Presupuesto de latencia
# =============================================================================

class LatencyBudget:
    """Soft; soporta anidamiento (sub-presupuestos jerárquicos)."""

    _local = threading.local()

    def __init__(self, limit_ms: float = DEFAULT_BUDGET_MS,
                 clock: Callable[[], float] = time.perf_counter):
        self.limit_ms = limit_ms
        self._clock = clock
        self.elapsed_ms = 0.0
        self._parent = None  # type: Optional["LatencyBudget"]

    def __enter__(self) -> "LatencyBudget":
        stack = getattr(LatencyBudget._local, "stack", None)
        if stack is None:
            stack = []
            LatencyBudget._local.stack = stack
        self._parent = stack[-1] if stack else None
        if self._parent is not None:
            remaining = self._parent.limit_ms - self._parent.elapsed_so_far()
            self.limit_ms = min(self.limit_ms, max(0.0, remaining))
        self._start = self._clock()
        stack.append(self)
        return self

    def elapsed_so_far(self) -> float:
        return (self._clock() - self._start) * 1000.0

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.elapsed_ms = self.elapsed_so_far()
        stack = getattr(LatencyBudget._local, "stack", [])
        if stack and stack[-1] is self:
            stack.pop()
        if exc_type is None and self.elapsed_ms > self.limit_ms:
            raise LatencyBudgetExceeded(
                f"Ciclo de {self.elapsed_ms:.2f} ms excede el límite de {self.limit_ms} ms."
            )
        return False




def _hard_worker(fn: Callable[[], Any], queue: Any) -> None:
    """Ejecuta fn y pone (ok, result|exc) en la cola (usado por proceso)."""
    try:
        queue.put(("ok", fn()))
    except BaseException as exc:
        queue.put(("err", exc))


class HardLatencyBudget:
    """Límite duro de latencia.

    Intenta ejecutar en un proceso hijo (sí se puede matar). Si el entorno
    no permite multiprocessing (p. ej. ya dentro de un daemon), cae a hilo
    (el timeout solo evita esperar; el hilo puede seguir vivo).
    """

    def __init__(self, limit_ms: float = DEFAULT_BUDGET_MS, use_process: bool = True):
        self.limit_ms = limit_ms
        self.use_process = use_process
        self.elapsed_ms = 0.0

    def run(self, fn: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        timeout_s = self.limit_ms / 1000.0

        if self.use_process:
            try:
                return self._run_process(fn, timeout_s, start)
            except (OSError, RuntimeError, AssertionError):
                # fallback a hilo si no se puede crear proceso
                pass
        return self._run_thread(fn, timeout_s, start)

    def _run_process(self, fn: Callable[[], Any], timeout_s: float, start: float) -> Any:
        ctx = mp.get_context("spawn")
        queue: mp.Queue = ctx.Queue(1)
        proc = ctx.Process(target=_hard_worker, args=(fn, queue))
        proc.start()
        proc.join(timeout=timeout_s)
        self.elapsed_ms = (time.perf_counter() - start) * 1000.0
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=0.5)
            raise LatencyBudgetExceeded(
                f"Ciclo superó el límite duro de {self.limit_ms} ms (proceso terminado)."
            )
        if queue.empty():
            raise LatencyBudgetExceeded(
                f"Ciclo superó el límite duro de {self.limit_ms} ms (sin resultado)."
            )
        status, value = queue.get_nowait()
        if status == "err":
            raise value
        return value

    def _run_thread(self, fn: Callable[[], Any], timeout_s: float, start: float) -> Any:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(fn)
            try:
                result = fut.result(timeout=timeout_s)
            except FuturesTimeout:
                self.elapsed_ms = self.limit_ms
                raise LatencyBudgetExceeded(
                    f"Ciclo superó el límite duro de {self.limit_ms} ms (hilo)."
                )
            finally:
                self.elapsed_ms = (time.perf_counter() - start) * 1000.0
        return result


# =============================================================================
# Motor latente
# =============================================================================

class NexusAIEngine:
    """Estado latente continuo con decaimiento. Sin KV-cache."""

    DECAY = 0.95
    GAIN = 0.05

    def __init__(self, latent_dims: int = 512, budget_ms: float = DEFAULT_BUDGET_MS,
                 clock: Callable[[], float] = time.perf_counter, auto_purge: bool = False):
        self.latent_dims = latent_dims
        self.budget_ms = budget_ms
        self.auto_purge = auto_purge
        self._clock = clock
        self._weights = np.linspace(0.1, 1.1, latent_dims, dtype=np.float32)
        self._state = np.zeros(latent_dims, dtype=np.float32)
        self._version = 0

    @property
    def state(self) -> np.ndarray:
        view = self._state.copy()
        view.flags.writeable = False
        return view

    @property
    def version(self) -> int:
        return self._version

    def purge(self) -> None:
        self._state.fill(0.0)
        self._version += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "latent_dims": self.latent_dims,
            "version": self._version,
            "state": self._state.tobytes(),
            "dtype": "float32",
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        if snap["latent_dims"] != self.latent_dims:
            raise IntegrityError("Snapshot con latent_dims distinto.")
        arr = np.frombuffer(snap["state"], dtype=np.float32).copy()
        if arr.shape != (self.latent_dims,):
            raise IntegrityError("Snapshot con forma inválida.")
        self._state = arr
        self._version = int(snap.get("version", 0))

    def _validate(self, x: np.ndarray) -> np.ndarray:
        if not isinstance(x, np.ndarray):
            raise IntegrityError("La entrada debe ser un np.ndarray.")
        if x.shape != (self.latent_dims,):
            raise IntegrityError(f"Forma esperada ({self.latent_dims},), recibida {x.shape}.")
        x = x.astype(np.float32, copy=False)
        if not np.isfinite(x).all():
            raise IntegrityError("Tensor con valores NaN/Inf.")
        return x

    def infer(self, input_data: np.ndarray) -> Dict[str, Any]:
        x = self._validate(input_data)
        try:
            with LatencyBudget(self.budget_ms, self._clock) as budget:
                self._state = self._state * self.DECAY + (x * self._weights) * self.GAIN
                self._version += 1
                magnitude = float(np.sqrt(np.dot(self._state, self._state)))
        except LatencyBudgetExceeded:
            self.purge()
            raise
        result = {
            "status": "OK",
            "latent_magnitude": round(magnitude, 4),
            "latency_ms": round(budget.elapsed_ms, 3),
            "state_bytes": int(self._state.nbytes),
            "version": self._version,
            "author": AUTHOR,
        }
        if self.auto_purge:
            self.purge()
            result["status"] = "OK_PURGED"
        return result


# =============================================================================
# Canal en proceso
# =============================================================================

class BoundedChannel:
    """FIFO acotado y thread-safe. Si se llena, descarta el más antiguo."""

    def __init__(self, capacity: int = 2048):
        self._buffer: Deque[np.ndarray] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def send(self, data: np.ndarray) -> None:
        with self._lock:
            self._buffer.append(data)

    def recv(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._buffer.popleft() if self._buffer else None

    def __len__(self) -> int:
        return len(self._buffer)


logger = logging.getLogger("ailang")

# --- Protocolo de frames ----------------------------------------------------
MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_NDIM = 4
ALLOWED_DTYPES = frozenset({"float32", "float64", "int32", "int64", "uint8"})
_U32 = struct.Struct(">I")
MAC_SIZE = hashlib.sha256().digest_size
MSG_ID_BYTES = 8
MAX_ACK_BYTES = 64
_ACK_OK = 1
_ACK_PROCESSED = 2  # ACK tras procesamiento exitoso


def encode_message(sender: str, payload: np.ndarray, secret: Optional[bytes] = None,
                   msg_id: Optional[str] = None, compress: bool = True) -> bytes:
    arr = np.ascontiguousarray(payload)
    if arr.dtype.name not in ALLOWED_DTYPES or arr.ndim > MAX_NDIM:
        raise TransportError(
            f"Array no transportable (dtype={arr.dtype.name}, ndim={arr.ndim})."
        )
    msg_id = msg_id or secrets.token_hex(MSG_ID_BYTES)
    raw = arr.tobytes()
    compressed = False
    if compress and len(raw) >= COMPRESS_THRESHOLD:
        z = zlib.compress(raw, level=3)
        if len(z) < len(raw):
            raw, compressed = z, True
    meta = json.dumps({
        "sender": sender,
        "dtype": arr.dtype.name,
        "shape": list(arr.shape),
        "timestamp": time.time(),
        "msg_id": msg_id,
        "zlib": compressed,
    }).encode("utf-8")
    body = _U32.pack(len(meta)) + meta + raw
    if secret:
        body += hmac.new(secret, body, hashlib.sha256).digest()
    if len(body) > MAX_FRAME_BYTES:
        raise TransportError("Mensaje mayor que MAX_FRAME_BYTES.")
    return _U32.pack(len(body)) + body


def decode_message(body: bytes, secret: Optional[bytes] = None) -> Dict[str, Any]:
    if secret:
        if len(body) < MAC_SIZE:
            raise IntegrityError("Frame sin MAC.")
        body, mac = body[:-MAC_SIZE], body[-MAC_SIZE:]
        if not hmac.compare_digest(mac, hmac.new(secret, body, hashlib.sha256).digest()):
            raise IntegrityError("MAC inválido: mensaje alterado o secreto distinto.")
    try:
        (meta_len,) = _U32.unpack_from(body)
        if meta_len > len(body) - _U32.size:
            raise ValueError("meta fuera de rango")
        meta = json.loads(body[_U32.size:_U32.size + meta_len])
        dtype, sender, msg_id = meta["dtype"], str(meta["sender"]), meta["msg_id"]
        shape = tuple(meta["shape"])
        if not isinstance(msg_id, str) or len(bytes.fromhex(msg_id)) != MSG_ID_BYTES:
            raise ValueError("msg_id inválido")
        if dtype not in ALLOWED_DTYPES or len(shape) > MAX_NDIM:
            raise ValueError("dtype o dimensiones no permitidos")
        if not all(isinstance(d, int) and 0 <= d <= MAX_FRAME_BYTES for d in shape):
            raise ValueError("forma inválida")
        raw = body[_U32.size + meta_len:]
        if meta.get("zlib"):
            raw = zlib.decompress(raw)
        if len(raw) != math.prod(shape) * np.dtype(dtype).itemsize:
            raise ValueError("tamaño de datos no coincide con la forma")
        data = np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
        return {
            "sender": sender,
            "data": data,
            "timestamp": float(meta["timestamp"]),
            "msg_id": msg_id,
        }
    except (KeyError, TypeError, ValueError, struct.error, zlib.error) as exc:
        raise IntegrityError(f"Frame mal formado: {exc}") from exc


def encode_ack(msg_id: str, secret: Optional[bytes] = None,
               processed: bool = False) -> bytes:
    """ACK: [estado][msg_id] (+ HMAC). estado=1 recibido, 2 procesado."""
    status = _ACK_PROCESSED if processed else _ACK_OK
    body = bytes([status]) + bytes.fromhex(msg_id)
    if secret:
        body += hmac.new(secret, body, hashlib.sha256).digest()
    return _U32.pack(len(body)) + body


def decode_ack(body: bytes, secret: Optional[bytes] = None) -> Tuple[str, bool]:
    """Devuelve (msg_id, processed)."""
    if secret:
        if len(body) < MAC_SIZE:
            raise IntegrityError("ACK sin MAC.")
        body, mac = body[:-MAC_SIZE], body[-MAC_SIZE:]
        if not hmac.compare_digest(mac, hmac.new(secret, body, hashlib.sha256).digest()):
            raise IntegrityError("ACK con MAC inválido.")
    if len(body) != 1 + MSG_ID_BYTES or body[0] not in (_ACK_OK, _ACK_PROCESSED):
        raise IntegrityError("ACK mal formado.")
    return body[1:].hex(), body[0] == _ACK_PROCESSED


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    chunks, remaining = [], n
    while remaining:
        chunk = conn.recv(min(remaining, 65536))
        if not chunk:
            raise ConnectionError("Conexión cerrada por el par.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def make_server_tls_context(certfile: str, keyfile: str,
                            client_cafile: Optional[str] = None) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile, keyfile)
    if client_cafile:
        ctx.load_verify_locations(client_cafile)
        ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def make_client_tls_context(cafile: Optional[str] = None, certfile: Optional[str] = None,
                            keyfile: Optional[str] = None) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if certfile:
        ctx.load_cert_chain(certfile, keyfile)
    return ctx


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 0.1
    factor: float = 2.0
    max_delay: float = 2.0
    jitter: float = 0.1
    ack_timeout: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts debe ser >= 1.")
        if not 0.0 <= self.jitter < 1.0:
            raise ValueError("jitter debe estar en [0, 1).")

    def delay_for(self, attempt: int, rng: Callable[[], float] = random.random) -> float:
        delay = min(self.base_delay * self.factor ** (attempt - 1), self.max_delay)
        return delay * (1.0 + self.jitter * (2.0 * rng() - 1.0))


# =============================================================================
# Deduplicación persistente
# =============================================================================

_SEEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    msg_id TEXT PRIMARY KEY,
    seen_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_at ON seen (seen_at);
"""


class PersistentSeenStore:
    """Ventana de deduplicación que sobrevive a reinicios (SQLite)."""

    def __init__(self, path: str, max_entries: int = 16_384, ttl_s: float = 3600.0,
                 clock: Callable[[], float] = time.time):
        self.path = path
        self.max_entries = max_entries
        self.ttl_s = ttl_s
        self._clock = clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        try:
            self._db.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SEEN_SCHEMA)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def is_duplicate(self, msg_id: str) -> bool:
        now = self._clock()
        with self._lock:
            # expirar
            self._db.execute("DELETE FROM seen WHERE seen_at < ?", (now - self.ttl_s,))
            row = self._db.execute(
                "SELECT 1 FROM seen WHERE msg_id=?", (msg_id,)
            ).fetchone()
            if row:
                self._db.execute(
                    "UPDATE seen SET seen_at=? WHERE msg_id=?", (now, msg_id)
                )
                return True
            self._db.execute(
                "INSERT INTO seen (msg_id, seen_at) VALUES (?, ?)", (msg_id, now)
            )
            # acotar tamaño
            (count,) = self._db.execute("SELECT COUNT(*) FROM seen").fetchone()
            if count > self.max_entries:
                self._db.execute(
                    "DELETE FROM seen WHERE msg_id IN "
                    "(SELECT msg_id FROM seen ORDER BY seen_at ASC LIMIT ?)",
                    (count - self.max_entries,),
                )
            return False

    def close(self) -> None:
        with self._lock:
            self._db.close()


# =============================================================================
# Transporte TCP
# =============================================================================


class _ConnPool:
    """Pool simple de sockets TCP por (host, port) para keep-alive."""

    def __init__(self, max_per_peer: int = 4, idle_timeout: float = 30.0):
        self.max_per_peer = max_per_peer
        self.idle_timeout = idle_timeout
        self._pools: Dict[Tuple[str, int], Deque[Tuple[socket.socket, float]]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, host: str, port: int, timeout: float) -> socket.socket:
        key = (host, port)
        now = time.time()
        with self._lock:
            q = self._pools[key]
            while q:
                sock, ts = q.popleft()
                if now - ts > self.idle_timeout:
                    try:
                        sock.close()
                    except OSError:
                        pass
                    continue
                try:
                    sock.settimeout(timeout)
                    return sock
                except OSError:
                    try:
                        sock.close()
                    except OSError:
                        pass
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except OSError:
            pass
        return sock

    def release(self, host: str, port: int, sock: socket.socket) -> None:
        key = (host, port)
        with self._lock:
            q = self._pools[key]
            if len(q) < self.max_per_peer:
                q.append((sock, time.time()))
                return
        try:
            sock.close()
        except OSError:
            pass

    def close_all(self) -> None:
        with self._lock:
            for q in self._pools.values():
                while q:
                    sock, _ = q.popleft()
                    try:
                        sock.close()
                    except OSError:
                        pass
            self._pools.clear()


class TcpTransport:
    """Servidor TCP (hilos) + cliente, TLS opcional, ACK, reintentos, dedup persistente.

    ack_after_process=True: el ACK solo se envía si on_message termina sin
    excepción (ACK de procesamiento). Por defecto False = ACK de recepción
    (mensaje guardado en el buzón), compatible con v6.5/v6.6.
    """

    def __init__(
        self,
        node_id: str,
        on_message: Callable[[Dict[str, Any]], None],
        secret: Optional[bytes] = None,
        timeout: float = 5.0,
        server_context: Optional[ssl.SSLContext] = None,
        client_context: Optional[ssl.SSLContext] = None,
        retry: Optional[RetryPolicy] = None,
        sleep: Callable[[float], None] = time.sleep,
        dedup_window: int = 16_384,
        dedup_ttl_s: float = 3600.0,
        require_auth: bool = True,  # v6.7: True por defecto
        seen_store: Optional[PersistentSeenStore] = None,
        ack_after_process: bool = False,
        compress: bool = True,
        use_pool: bool = True,
        metrics: Optional[Metrics] = None,
    ):
        self.node_id = node_id
        self.on_message = on_message
        self.secret = secret
        self.timeout = timeout
        self.server_context = server_context
        self.client_context = client_context
        self.retry = retry or RetryPolicy()
        self._sleep = sleep
        self._dedup_window = dedup_window
        self._dedup_ttl = dedup_ttl_s
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        self._seen_lock = threading.Lock()
        self._seen_store = seen_store
        self.ack_after_process = ack_after_process
        self.compress = compress
        self._pool = _ConnPool() if use_pool and client_context is None else None
        self.metrics = metrics or Metrics()
        self._server: Optional[socket.socket] = None
        self._stop = threading.Event()
        self.address: Optional[Tuple[str, int]] = None

        if require_auth and secret is None and server_context is None and client_context is None:
            raise TransportError(
                "require_auth=True (por defecto en v6.7) pero no hay secret ni contexto TLS. "
                "Pasa secret=..., un contexto TLS, o require_auth=False solo en redes de confianza."
            )
        if secret is None and server_context is None:
            warnings.warn(
                f"[{node_id}] Transporte sin secret ni TLS: cualquiera puede inyectar mensajes.",
                RuntimeWarning,
                stacklevel=2,
            )

    def start(self, host: str = "127.0.0.1", port: int = 0):
        """Escucha TCP IPv4/IPv6 o Unix (host='unix:///path' o '/path')."""
        if isinstance(host, str) and (host.startswith("unix://") or host.startswith("/")):
            path = host[7:] if host.startswith("unix://") else host
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            self.address = f"unix://{path}"
        else:
            family = socket.AF_INET6 if (isinstance(host, str) and ":" in host) else socket.AF_INET
            server = socket.socket(family, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if family == socket.AF_INET6:
                try:
                    server.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                except OSError:
                    pass
            server.bind((host, port))
            self.address = server.getsockname()[:2]
        server.listen()
        server.settimeout(0.2)
        self._server = server
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self.address

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _peek_duplicate(self, msg_id: str) -> bool:
        """Consulta si ya se vio, sin insertar."""
        if self._seen_store is not None:
            with self._seen_store._lock:
                row = self._seen_store._db.execute(
                    "SELECT 1 FROM seen WHERE msg_id=?", (msg_id,)
                ).fetchone()
                return row is not None
        with self._seen_lock:
            return msg_id in self._seen

    def _is_duplicate(self, msg_id: str) -> bool:
        """Marca como visto y devuelve True si ya existía."""
        if self._seen_store is not None:
            return self._seen_store.is_duplicate(msg_id)
        now = time.time()
        with self._seen_lock:
            while self._seen:
                oldest_id, ts = next(iter(self._seen.items()))
                if now - ts <= self._dedup_ttl:
                    break
                self._seen.popitem(last=False)
            if msg_id in self._seen:
                self._seen.move_to_end(msg_id)
                self._seen[msg_id] = now
                return True
            self._seen[msg_id] = now
            if len(self._seen) > self._dedup_window:
                self._seen.popitem(last=False)
            return False

    def _serve(self, conn: socket.socket) -> None:
        conn.settimeout(self.timeout)
        if self.server_context is not None:
            try:
                conn = self.server_context.wrap_socket(conn, server_side=True)
            except (ssl.SSLError, OSError) as exc:
                logger.warning("[%s] handshake TLS fallido: %s", self.node_id, exc)
                conn.close()
                return
        with conn:
            while not self._stop.is_set():
                try:
                    (length,) = _U32.unpack(_recv_exact(conn, _U32.size))
                    if length > MAX_FRAME_BYTES:
                        raise IntegrityError("Frame mayor que MAX_FRAME_BYTES.")
                    message = decode_message(_recv_exact(conn, length), self.secret)
                except (ConnectionError, socket.timeout, OSError):
                    return
                except AILangError as exc:
                    logger.warning("[%s] frame descartado: %s", self.node_id, exc)
                    return
                # ack_after_process: solo marcar visto y ACK tras éxito de on_message.
                # Modo recepción: marcar visto antes y ACK siempre (at-least-once clásico).
                if self.ack_after_process:
                    if self._peek_duplicate(message["msg_id"]):
                        try:
                            conn.sendall(encode_ack(message["msg_id"], self.secret, processed=True))
                        except OSError:
                            return
                        continue
                    try:
                        self.on_message(message)
                    except Exception:
                        logger.exception(
                            "[%s] on_message falló para %s", self.node_id, message["msg_id"]
                        )
                        return  # sin ACK ni marca → el emisor reintenta
                    self._is_duplicate(message["msg_id"])  # marcar tras éxito
                    try:
                        conn.sendall(encode_ack(message["msg_id"], self.secret, processed=True))
                    except OSError:
                        return
                else:
                    is_dup = self._is_duplicate(message["msg_id"])
                    if not is_dup:
                        try:
                            self.on_message(message)
                        except Exception:
                            logger.exception(
                                "[%s] on_message falló para %s", self.node_id, message["msg_id"]
                            )
                    try:
                        conn.sendall(encode_ack(message["msg_id"], self.secret, processed=False))
                    except OSError:
                        return

    def _exchange(self, sock: socket.socket, frame: bytes, msg_id: str,
                  ack_timeout: float) -> None:
        sock.sendall(frame)
        sock.settimeout(ack_timeout)
        (length,) = _U32.unpack(_recv_exact(sock, _U32.size))
        if length > MAX_ACK_BYTES:
            raise IntegrityError("ACK demasiado grande.")
        ack_id, _processed = decode_ack(_recv_exact(sock, length), self.secret)
        if ack_id != msg_id:
            raise IntegrityError("ACK de otro mensaje.")

    def _connect(self, host: str, port: int) -> socket.socket:
        if isinstance(host, str) and (host.startswith("unix://") or host.startswith("/")):
            path = host[7:] if host.startswith("unix://") else host
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(path)
            return sock
        family = socket.AF_INET6 if (isinstance(host, str) and ":" in host) else socket.AF_INET
        if family == socket.AF_INET6:
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))
        else:
            sock = socket.create_connection((host, port), timeout=self.timeout)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except OSError:
            pass
        return sock

    def _attempt(self, frame: bytes, msg_id: str, host: str, port: int,
                 server_hostname: Optional[str], ack_timeout: float) -> None:
        is_unix = isinstance(host, str) and (host.startswith("unix://") or host.startswith("/"))
        if self.client_context is not None and not is_unix:
            with self._connect(host, port) as raw:
                with self.client_context.wrap_socket(
                        raw, server_hostname=server_hostname or host) as tls:
                    self._exchange(tls, frame, msg_id, ack_timeout)
            return
        if self._pool is not None and not is_unix:
            sock = self._pool.acquire(host, port, self.timeout)
            try:
                self._exchange(sock, frame, msg_id, ack_timeout)
                self._pool.release(host, port, sock)
            except Exception:
                try:
                    sock.close()
                except OSError:
                    pass
                raise
            return
        with self._connect(host, port) as raw:
            self._exchange(raw, frame, msg_id, ack_timeout)


    def send(self, host: str, port: int, payload: np.ndarray,
             server_hostname: Optional[str] = None, msg_id: Optional[str] = None,
             retry: Optional[RetryPolicy] = None) -> int:
        msg_id = msg_id or secrets.token_hex(MSG_ID_BYTES)
        frame = encode_message(self.node_id, payload, self.secret, msg_id, compress=self.compress)
        policy = retry or self.retry
        last_exc: Optional[Exception] = None
        for attempt in range(1, policy.max_attempts + 1):
            try:
                self._attempt(frame, msg_id, host, port, server_hostname, policy.ack_timeout)
                return attempt
            except ssl.SSLCertVerificationError as exc:
                raise TransportError(
                    f"Certificado de {host}:{port} no verificable (no se reintenta): {exc}"
                ) from exc
            except (OSError, IntegrityError) as exc:
                last_exc = exc
                if attempt < policy.max_attempts:
                    delay = policy.delay_for(attempt)
                    logger.info(
                        "[%s] intento %d/%d a %s:%d falló (%s); reintento en %.2fs",
                        self.node_id, attempt, policy.max_attempts, host, port, exc, delay,
                    )
                    self._sleep(delay)
        raise TransportError(
            f"Sin ACK de {host}:{port} tras {policy.max_attempts} intentos: {last_exc}"
        ) from last_exc

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            path = None
            if isinstance(self.address, str) and self.address.startswith("unix://"):
                path = self.address[7:]
            self._server.close()
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
        if getattr(self, "_pool", None) is not None:
            self._pool.close_all()


# =============================================================================
# Cifrado outbox (HKDF + Fernet + rotación)
# =============================================================================

def derive_outbox_key(secret: bytes, salt: bytes = b"ailang-outbox-v1") -> bytes:
    """Deriva 32 bytes de clave a partir del HMAC secret (HKDF-SHA256)."""
    # HKDF extract + expand mínimo (stdlib)
    prk = hmac.new(salt, secret, hashlib.sha256).digest()
    return hmac.new(prk, b"ailang-outbox-key" + b"\x01", hashlib.sha256).digest()


def _try_fernet(key: Optional[bytes]):
    if key is None:
        return None, None
    try:
        from cryptography.fernet import Fernet
        if len(key) == 32:
            key = base64.urlsafe_b64encode(key)
        return Fernet(key), None
    except ImportError:
        return None, "cryptography no instalado; outbox sin cifrar"
    except Exception as exc:
        return None, f"clave Fernet inválida: {exc}"


# =============================================================================
# Cola persistente de salida
# =============================================================================

_OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT NOT NULL,
    peer_id TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    server_hostname TEXT,
    dtype TEXT NOT NULL,
    shape TEXT NOT NULL,
    data BLOB NOT NULL,
    key_version INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt REAL NOT NULL,
    created REAL NOT NULL,
    last_error TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE (msg_id, peer_id)
);
CREATE INDEX IF NOT EXISTS idx_outbox_due ON outbox (status, next_attempt);
"""

_OUTBOX_COLUMNS = (
    "id, msg_id, peer_id, host, port, server_hostname, dtype, shape, data, "
    "key_version, attempts, next_attempt, created, last_error, status"
)

Target = Tuple[str, str, int, Optional[str]]


@dataclass(frozen=True)
class OutboxItem:
    row_id: int
    msg_id: str
    peer_id: str
    host: str
    port: int
    server_hostname: Optional[str]
    dtype: str
    shape: Tuple[int, ...]
    data: bytes
    key_version: int
    attempts: int
    next_attempt: float
    created: float
    last_error: Optional[str]
    status: str

    def payload(self, decrypt: Optional[Callable[[bytes, int], bytes]] = None) -> np.ndarray:
        raw = decrypt(self.data, self.key_version) if decrypt is not None else self.data
        return np.frombuffer(raw, dtype=self.dtype).reshape(self.shape).copy()


def _row_to_item(row: Tuple[Any, ...]) -> OutboxItem:
    return OutboxItem(
        row[0], row[1], row[2], row[3], row[4], row[5], row[6],
        tuple(json.loads(row[7])), bytes(row[8]), int(row[9]),
        row[10], row[11], row[12], row[13], row[14],
    )


class PersistentOutbox:
    """Cola de salida SQLite con cifrado Fernet y rotación de claves.

    keys: dict[version -> 32 bytes]. La versión activa es `current_key_version`.
    Si se pasa `secret` y no hay keys, se deriva una clave (versión 1).
    """

    def __init__(
        self,
        path: str,
        max_items: int = 10_000,
        max_dead: int = 1_000,
        clock: Callable[[], float] = time.time,
        encryption_key: Optional[bytes] = None,
        secret: Optional[bytes] = None,
        keys: Optional[Dict[int, bytes]] = None,
        current_key_version: int = 1,
        require_encryption: bool = False,
    ):
        self.path = path
        self.max_items = max_items
        self.max_dead = max_dead
        self._clock = clock
        self._lock = threading.Lock()
        self._closed = False

        # Resolver claves
        self._keys: Dict[int, Any] = {}  # version -> Fernet
        self._current_version = current_key_version

        resolved: Dict[int, bytes] = dict(keys or {})
        if encryption_key is not None:
            resolved.setdefault(current_key_version, encryption_key)
        if secret is not None and not resolved:
            resolved[1] = derive_outbox_key(secret)
            self._current_version = 1
        if require_encryption and not resolved:
            raise AILangError(
                "require_encryption=True pero no hay encryption_key, keys ni secret."
            )
        if secret is not None and not resolved and encryption_key is None:
            # ya cubierto arriba
            pass

        for ver, raw_key in resolved.items():
            fernet, err = _try_fernet(raw_key)
            if err:
                warnings.warn(f"[outbox] clave v{ver}: {err}", RuntimeWarning, stacklevel=2)
            if fernet is None and require_encryption:
                raise AILangError(f"No se pudo inicializar Fernet para key_version={ver}: {err}")
            if fernet is not None:
                self._keys[ver] = fernet

        if require_encryption and self._current_version not in self._keys:
            raise AILangError("Clave activa no disponible para cifrar el outbox.")

        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        try:
            self._db.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(_OUTBOX_SCHEMA)
        # migración suave: añadir key_version si la tabla antigua no la tenía
        try:
            self._db.execute("SELECT key_version FROM outbox LIMIT 1")
        except sqlite3.OperationalError:
            self._db.execute("ALTER TABLE outbox ADD COLUMN key_version INTEGER NOT NULL DEFAULT 0")

        try:
            os.chmod(path, 0o600)
            parent = os.path.dirname(os.path.abspath(path)) or "."
            try:
                os.chmod(parent, 0o700)
            except OSError:
                pass
        except OSError:
            pass

    def _encrypt(self, raw: bytes) -> Tuple[bytes, int]:
        fernet = self._keys.get(self._current_version)
        if fernet is None:
            return raw, 0
        return fernet.encrypt(raw), self._current_version

    def _decrypt(self, blob: bytes, key_version: int) -> bytes:
        if key_version == 0:
            return blob
        fernet = self._keys.get(key_version)
        if fernet is None:
            raise AILangError(
                f"No hay clave para key_version={key_version}. "
                "Añádela al dict `keys` al abrir el outbox."
            )
        return fernet.decrypt(blob)

    def rotate_key(self, new_key: bytes, new_version: int) -> None:
        """Registra una nueva versión de clave y la hace activa para encolados futuros.
        Los mensajes antiguos siguen descifrables con las claves previas."""
        fernet, err = _try_fernet(new_key)
        if fernet is None:
            raise AILangError(f"No se pudo cargar la nueva clave: {err}")
        with self._lock:
            self._keys[new_version] = fernet
            self._current_version = new_version

    def enqueue(self, targets: Sequence[Target], payload: np.ndarray,
                msg_id: Optional[str] = None) -> str:
        arr = np.ascontiguousarray(payload)
        msg_id = msg_id or secrets.token_hex(MSG_ID_BYTES)
        encode_message("outbox", arr, None, msg_id)
        if not targets:
            return msg_id
        now = self._clock()
        shape_json = json.dumps(list(arr.shape))
        raw, key_ver = self._encrypt(arr.tobytes())
        rows = [
            (msg_id, pid, host, int(port), hostname, arr.dtype.name, shape_json, raw,
             key_ver, now, now)
            for pid, host, port, hostname in targets
        ]
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                (pending,) = self._db.execute(
                    "SELECT COUNT(*) FROM outbox WHERE status='pending'"
                ).fetchone()
                if pending + len(rows) > self.max_items:
                    raise OutboxFull(
                        f"Cola llena ({pending}/{self.max_items} pendientes)."
                    )
                self._db.executemany(
                    "INSERT OR IGNORE INTO outbox "
                    "(msg_id, peer_id, host, port, server_hostname, dtype, shape, data, "
                    "key_version, attempts, next_attempt, created, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,0,?,?,'pending')",
                    rows,
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return msg_id

    def due(self, now: Optional[float] = None, limit: int = 32) -> List[OutboxItem]:
        now = now if now is not None else self._clock()
        with self._lock:
            rows = self._db.execute(
                f"SELECT {_OUTBOX_COLUMNS} FROM outbox "
                "WHERE status='pending' AND next_attempt <= ? "
                "ORDER BY next_attempt LIMIT ?",
                (now, limit),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def next_due(self) -> Optional[float]:
        with self._lock:
            row = self._db.execute(
                "SELECT MIN(next_attempt) FROM outbox WHERE status='pending'"
            ).fetchone()
        return row[0] if row and row[0] is not None else None

    def mark_sent(self, row_id: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM outbox WHERE id=?", (row_id,))

    def mark_retry(self, row_id: int, attempts: int, next_attempt: float,
                   last_error: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE outbox SET attempts=?, next_attempt=?, last_error=? WHERE id=?",
                (attempts, next_attempt, last_error, row_id),
            )

    def mark_dead(self, row_id: int, attempts: int, last_error: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE outbox SET status='dead', attempts=?, last_error=? WHERE id=?",
                (attempts, last_error, row_id),
            )
            self._db.execute(
                "DELETE FROM outbox WHERE status='dead' AND id NOT IN "
                "(SELECT id FROM outbox WHERE status='dead' ORDER BY id DESC LIMIT ?)",
                (self.max_dead,),
            )

    def dead_letters(self) -> List[OutboxItem]:
        with self._lock:
            rows = self._db.execute(
                f"SELECT {_OUTBOX_COLUMNS} FROM outbox WHERE status='dead' ORDER BY id DESC"
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def list_pending(self, limit: int = 32) -> List[OutboxItem]:
        """Lista los items pendientes (status='pending'), sin consumirlos.

        Alias público de `due()` para uso desde la CLI. Se diferencia de `due()`
        en que NO filtra por `next_attempt <= now` (muestra todos los pendientes
        incluso si su próximo intento es futuro).
        """
        with self._lock:
            rows = self._db.execute(
                f"SELECT {_OUTBOX_COLUMNS} FROM outbox "
                "WHERE status='pending' ORDER BY next_attempt LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def purge_dead(self) -> int:
        """Elimina todos los items muertos (status='dead') del outbox.

        Devuelve el número de filas eliminadas. Útil para mantener el outbox
        acotado sin perder la posibilidad de requeue previo (ver `requeue_dead`).
        """
        with self._lock:
            cur = self._db.execute("DELETE FROM outbox WHERE status='dead'")
            self._db.commit()
            return cur.rowcount

    def requeue_dead(self) -> int:
        now = self._clock()
        with self._lock:
            cur = self._db.execute(
                "UPDATE outbox SET status='pending', next_attempt=?, last_error=NULL "
                "WHERE status='dead'",
                (now,),
            )
            return cur.rowcount

    def counts(self) -> Dict[str, int]:
        with self._lock:
            rows = self._db.execute(
                "SELECT status, COUNT(*) FROM outbox GROUP BY status"
            ).fetchall()
        result = {"pending": 0, "dead": 0}
        for status, n in rows:
            result[status] = n
        return result

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True


class OutboxDispatcher:
    def __init__(
        self,
        outbox: PersistentOutbox,
        transport: TcpTransport,
        policy: Optional[RetryPolicy] = None,
        batch_size: int = 16,
        workers: int = 4,
        idle_poll: float = 0.5,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.outbox = outbox
        self.transport = transport
        self.policy = policy or RetryPolicy()
        self.batch_size = batch_size
        self.workers = workers
        self.idle_poll = idle_poll
        self.clock = clock
        self._sleep = sleep
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _deliver(self, item: OutboxItem) -> str:
        try:
            payload = item.payload(decrypt=self.outbox._decrypt)
            self.transport.send(
                item.host,
                item.port,
                payload,
                server_hostname=item.server_hostname,
                msg_id=item.msg_id,
                retry=RetryPolicy(max_attempts=1, ack_timeout=self.policy.ack_timeout),
            )
        except TransportError as exc:
            attempts = item.attempts + 1
            if attempts >= self.policy.max_attempts:
                self.outbox.mark_dead(item.row_id, attempts, str(exc))
                logger.warning(
                    "[outbox] %s → %s a dead letters tras %d intentos: %s",
                    item.msg_id, item.peer_id, attempts, exc,
                )
                return "dead"
            delay = self.policy.delay_for(attempts)
            next_at = self.clock() + delay
            self.outbox.mark_retry(item.row_id, attempts, next_at, str(exc))
            logger.info(
                "[outbox] %s → %s fallo (%s); reintento en %.2fs",
                item.msg_id, item.peer_id, exc, delay,
            )
            return "failed"
        self.outbox.mark_sent(item.row_id)
        return "sent"

    def run_once(self) -> Dict[str, int]:
        counts = {"sent": 0, "failed": 0, "dead": 0}
        items = self.outbox.due(self.clock(), self.batch_size)
        if items:
            with ThreadPoolExecutor(max_workers=min(self.workers, len(items))) as pool:
                for outcome in pool.map(self._deliver, items):
                    counts[outcome] += 1
        return counts

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            try:
                self.run_once()
            except Exception:
                logger.exception("[outbox] error en la ronda de envío")
            upcoming = self.outbox.next_due()
            delay = self.idle_poll if upcoming is None else min(
                self.idle_poll, max(0.0, upcoming - self.clock())
            )
            self._wake.wait(max(delay, 0.01))

    def flush(self, timeout: float = 30.0) -> Dict[str, int]:
        deadline = time.time() + timeout
        total = {"sent": 0, "failed": 0, "dead": 0}
        while time.time() < deadline:
            c = self.run_once()
            for k in total:
                total[k] += c[k]
            if self.outbox.counts().get("pending", 0) == 0:
                break
            time.sleep(0.05)
        return total

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, daemon=True, name="ailang-outbox"
            )
            self._thread.start()

    def wake(self) -> None:
        self._wake.set()

    def stop(self, flush_timeout: float = 0.0) -> None:
        if flush_timeout > 0:
            self.flush(timeout=flush_timeout)
        self._stop.set()
        self._wake.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)


# =============================================================================
# Nodo distribuido
# =============================================================================

class DistributedNode:
    def __init__(
        self,
        node_id: str,
        mailbox_size: int = 1024,
        secret: Optional[bytes] = None,
        tls_server: Optional[ssl.SSLContext] = None,
        tls_client: Optional[ssl.SSLContext] = None,
        retry: Optional[RetryPolicy] = None,
        outbox_path: Optional[str] = None,
        outbox_policy: Optional[RetryPolicy] = None,
        outbox_max_items: int = 10_000,
        outbox_autostart: bool = True,
        outbox_encryption_key: Optional[bytes] = None,
        outbox_keys: Optional[Dict[int, bytes]] = None,
        require_auth: bool = True,
        require_outbox_encryption: bool = False,
        seen_path: Optional[str] = None,
        ack_after_process: bool = False,
        compress: bool = True,
        ordered: bool = False,
        clock: Callable[[], float] = time.time,
        metrics: Optional[Metrics] = None,
    ):
        self.node_id = node_id
        self.peers: Dict[str, "DistributedNode"] = {}
        self.remote_peers: Dict[str, Tuple[str, int, Optional[str]]] = {}
        self.mailbox: Deque[Dict[str, Any]] = deque(maxlen=mailbox_size)
        self._mailbox_lock = threading.Lock()
        self._ordered = ordered
        self._peer_queues: Dict[str, Deque[Dict[str, Any]]] = defaultdict(deque)
        self.secret = secret
        self.retry = retry or RetryPolicy()
        self.clock = clock
        self.metrics = metrics or Metrics()
        self._seen_store: Optional[PersistentSeenStore] = None

        if seen_path is not None:
            self._seen_store = PersistentSeenStore(seen_path, clock=clock)

        def on_message(msg: Dict[str, Any]) -> None:
            with self._mailbox_lock:
                if self._ordered:
                    self._peer_queues[msg.get("sender", "")].append(msg)
                else:
                    self.mailbox.append(msg)

        self._transport = TcpTransport(
            node_id,
            on_message,
            secret=secret,
            server_context=tls_server,
            client_context=tls_client,
            retry=self.retry,
            require_auth=require_auth,
            seen_store=self._seen_store,
            ack_after_process=ack_after_process,
            compress=compress,
            metrics=self.metrics,
        )
        self.outbox: Optional[PersistentOutbox] = None
        self.dispatcher: Optional[OutboxDispatcher] = None
        if outbox_path is not None:
            self.outbox = PersistentOutbox(
                outbox_path,
                max_items=outbox_max_items,
                clock=clock,
                encryption_key=outbox_encryption_key,
                secret=secret,
                keys=outbox_keys,
                require_encryption=require_outbox_encryption or (secret is not None),
            )
            self.dispatcher = OutboxDispatcher(
                self.outbox,
                self._transport,
                policy=outbox_policy or self.retry,
                clock=clock,
            )
            if outbox_autostart:
                self.dispatcher.start()

    def listen(self, host: str = "127.0.0.1", port: int = 0) -> Tuple[str, int]:
        return self._transport.start(host, port)

    def register_peer(self, other: "DistributedNode") -> None:
        self.peers[other.node_id] = other
        other.peers[self.node_id] = self

    def register_remote_peer(
        self,
        peer_id: str,
        host: str,
        port: int,
        server_hostname: Optional[str] = None,
    ) -> None:
        self.remote_peers[peer_id] = (host, port, server_hostname)

    def _deliver_local(self, payload: np.ndarray) -> int:
        delivered = 0
        for peer in self.peers.values():
            msg = {
                "sender": self.node_id,
                "data": payload.copy(),
                "timestamp": time.time(),
            }
            with peer._mailbox_lock:
                if peer._ordered:
                    peer._peer_queues[self.node_id].append(msg)
                else:
                    peer.mailbox.append(msg)
            delivered += 1
        return delivered

    def broadcast(self, payload: np.ndarray) -> int:
        delivered = self._deliver_local(payload)

        def push(item: Tuple[str, Tuple[str, int, Optional[str]]]) -> bool:
            node_id, (host, port, hostname) = item
            try:
                self._transport.send(host, port, payload, hostname)
                return True
            except TransportError as exc:
                logger.warning("[%s] fallo con %s: %s", self.node_id, node_id, exc)
                return False

        remote = list(self.remote_peers.items())
        if remote:
            with ThreadPoolExecutor(max_workers=min(8, len(remote))) as pool:
                delivered += sum(pool.map(push, remote))
        return delivered

    def broadcast_durable(self, payload: np.ndarray) -> int:
        if self.outbox is None or self.dispatcher is None:
            raise AILangError("Este nodo no tiene cola persistente: pasa outbox_path.")
        targets = [
            (nid, host, port, hostname)
            for nid, (host, port, hostname) in self.remote_peers.items()
        ]
        if targets:
            self.outbox.enqueue(targets, payload)
        self._deliver_local(payload)
        if targets:
            self.dispatcher.wake()
        return len(targets)

    def recv(self, timeout: Optional[float] = None,
             from_peer: Optional[str] = None) -> Optional[Dict[str, Any]]:
        deadline = None if timeout is None else time.time() + timeout
        while True:
            with self._mailbox_lock:
                if self._ordered and from_peer is not None:
                    q = self._peer_queues.get(from_peer)
                    if q:
                        return q.popleft()
                elif self._ordered:
                    for q in self._peer_queues.values():
                        if q:
                            return q.popleft()
                elif self.mailbox:
                    return self.mailbox.popleft()
            if deadline is not None and time.time() >= deadline:
                return None
            time.sleep(0.01)

    def health(self) -> Dict[str, Any]:
        h: Dict[str, Any] = {
            "node_id": self.node_id,
            "version": __version__,
            "address": self._transport.address,
            "peers": list(self.peers.keys()),
            "remote_peers": list(self.remote_peers.keys()),
            "metrics": self.metrics.snapshot(),
        }
        if self.outbox is not None:
            h["outbox"] = self.outbox.counts()
        return h

    def close(self, flush_timeout: float = 5.0) -> None:
        if self.dispatcher is not None:
            self.dispatcher.stop(flush_timeout=flush_timeout)
        self._transport.stop()
        if self.outbox is not None:
            self.outbox.close()
        if self._seen_store is not None:
            self._seen_store.close()


# =============================================================================
# Utilidades de reloj para tests
# =============================================================================

class MutableClock:
    def __init__(self, start: float = 0.0):
        self._t = start
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._t

    def advance(self, dt: float) -> None:
        with self._lock:
            self._t += dt


class FakeClock(MutableClock):
    pass



# =============================================================================
# COGNITIVE BRAIN LAYER — integración inspirada en GBrain
# =============================================================================
# Esta capa adopta los conceptos útiles de GBrain sin acoplar Nexus AILang-Core a
# TypeScript/Bun ni copiar su implementación. El motor conserva su contrato
# Python y usa SQLite como backend local; un adaptador futuro puede apuntar a
# PostgreSQL/pgvector sin cambiar la API cognitiva.

import uuid
from dataclasses import asdict, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


@dataclass(frozen=True)
class SchemaType:
    name: str
    primitive: str = "entity"
    path_prefixes: Tuple[str, ...] = ()
    aliases: Tuple[str, ...] = ()
    extractable: bool = True
    expert_routing: bool = False


@dataclass(frozen=True)
class SchemaPack:
    """Schema dinámico: tipos, alias y verbos de relación."""
    name: str
    version: str = "1.0.0"
    types: Tuple[SchemaType, ...] = ()
    link_types: Tuple[str, ...] = ()
    takes_kinds: Tuple[str, ...] = ("fact", "take", "bet", "hunch")

    def infer_type(self, path: str) -> Optional[str]:
        # Prioridad: prefijo más largo, comportamiento determinista.
        norm = path.replace("\\", "/")
        candidates = []
        for t in self.types:
            for prefix in t.path_prefixes:
                if norm.startswith(prefix):
                    candidates.append((len(prefix), t.name))
        return max(candidates)[1] if candidates else None

    def resolve_alias(self, name: str) -> str:
        low = name.casefold()
        for t in self.types:
            if low == t.name.casefold() or low in {a.casefold() for a in t.aliases}:
                return t.name
        return name

    def expert_types(self) -> Tuple[str, ...]:
        return tuple(t.name for t in self.types if t.expert_routing)

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "api_version": "ailang-schema-pack-v1",
            "name": self.name,
            "version": self.version,
            "page_types": [asdict(t) for t in self.types],
            "link_types": list(self.link_types),
            "takes_kinds": list(self.takes_kinds),
        }

    @classmethod
    def from_manifest(cls, manifest: Dict[str, Any]) -> "SchemaPack":
        if manifest.get("api_version") not in (None, "ailang-schema-pack-v1", "gbrain-schema-pack-v1"):
            raise IntegrityError("Schema pack api_version no soportada.")
        types = []
        for raw in manifest.get("page_types", manifest.get("types", [])):
            types.append(SchemaType(
                name=str(raw["name"]),
                primitive=str(raw.get("primitive", "entity")),
                path_prefixes=tuple(raw.get("path_prefixes", [])),
                aliases=tuple(raw.get("aliases", [])),
                extractable=bool(raw.get("extractable", True)),
                expert_routing=bool(raw.get("expert_routing", False)),
            ))
        return cls(
            name=str(manifest["name"]),
            version=str(manifest.get("version", "1.0.0")),
            types=tuple(types),
            link_types=tuple(manifest.get("link_types", [])),
            takes_kinds=tuple(manifest.get("takes_kinds", ["fact", "take", "bet", "hunch"])),
        )


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    source: str
    path: str
    title: str
    type: str
    content: str
    content_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    document_id: str
    position: int
    content: str
    embedding: Optional[np.ndarray] = None


@dataclass(frozen=True)
class KnowledgeEntity:
    id: str
    name: str
    primitive: str = "entity"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeRelation:
    source_id: str
    target_id: str
    verb: str
    weight: float = 1.0


@dataclass(frozen=True)
class Evidence:
    id: str
    claim_id: str
    source: str
    excerpt: str
    reliability: float = 1.0
    created_at: str = ""


@dataclass(frozen=True)
class ProvenanceRecord:
    id: str
    object_type: str
    object_id: str
    source: str
    actor: str
    operation: str
    timestamp: str
    content_hash: str
    parent_id: Optional[str] = None


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    score: float
    lexical_score: float
    vector_score: float
    graph_score: float
    source: str
    excerpt: str


class CognitiveBrainStore:
    """Backend cognitivo local y persistente.

    La API está deliberadamente separada del transporte TCP y del motor latente.
    Esto permite sustituir SQLite por PostgreSQL/pgvector sin modificar el
    compilador ni los consumidores cognitivos.
    """

    def __init__(self, path: str = ":memory:", *, tenant_id: str = "default"):
        self.path = path
        self.tenant_id = tenant_id
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        if path != ":memory:":
            try:
                self._db.execute("PRAGMA journal_mode=WAL")
                self._db.execute("PRAGMA synchronous=FULL")
                os.chmod(path, 0o600)
            except (sqlite3.DatabaseError, OSError):
                pass
        self._migrate()

    def _migrate(self) -> None:
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS brain_documents (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, source TEXT NOT NULL,
            path TEXT NOT NULL, title TEXT NOT NULL, type TEXT NOT NULL,
            content TEXT NOT NULL, content_hash TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}', deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(tenant_id, source, path)
        );
        CREATE INDEX IF NOT EXISTS idx_brain_documents_type
            ON brain_documents(tenant_id, type);
        CREATE TABLE IF NOT EXISTS brain_chunks (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, document_id TEXT NOT NULL,
            position INTEGER NOT NULL, content TEXT NOT NULL,
            embedding BLOB, dimensions INTEGER, dtype TEXT,
            FOREIGN KEY(document_id) REFERENCES brain_documents(id) ON DELETE CASCADE,
            UNIQUE(document_id, position)
        );
        CREATE INDEX IF NOT EXISTS idx_brain_chunks_doc
            ON brain_chunks(tenant_id, document_id);
        CREATE TABLE IF NOT EXISTS brain_entities (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
            primitive TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}',
            UNIQUE(tenant_id, name)
        );
        CREATE TABLE IF NOT EXISTS brain_aliases (
            tenant_id TEXT NOT NULL, alias TEXT NOT NULL, entity_id TEXT NOT NULL,
            PRIMARY KEY(tenant_id, alias),
            FOREIGN KEY(entity_id) REFERENCES brain_entities(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS brain_relations (
            tenant_id TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
            verb TEXT NOT NULL, weight REAL NOT NULL DEFAULT 1.0,
            PRIMARY KEY(tenant_id, source_id, target_id, verb),
            FOREIGN KEY(source_id) REFERENCES brain_entities(id) ON DELETE CASCADE,
            FOREIGN KEY(target_id) REFERENCES brain_entities(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_brain_relations_source
            ON brain_relations(tenant_id, source_id);
        CREATE TABLE IF NOT EXISTS brain_claims (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, subject_id TEXT,
            predicate TEXT NOT NULL, object_value TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5, status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS brain_evidence (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, claim_id TEXT NOT NULL,
            source TEXT NOT NULL, excerpt TEXT NOT NULL, reliability REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(claim_id) REFERENCES brain_claims(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS brain_provenance (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, object_type TEXT NOT NULL,
            object_id TEXT NOT NULL, source TEXT NOT NULL, actor TEXT NOT NULL,
            operation TEXT NOT NULL, timestamp TEXT NOT NULL, content_hash TEXT NOT NULL,
            parent_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_brain_provenance_object
            ON brain_provenance(tenant_id, object_type, object_id);
        CREATE TABLE IF NOT EXISTS brain_schema_packs (
            tenant_id TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,
            manifest TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(tenant_id, name)
        );
        CREATE TABLE IF NOT EXISTS brain_memories (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL,
            persistence TEXT NOT NULL, content TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS brain_retrieval_runs (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, query TEXT NOT NULL,
            mode TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS brain_retrieval_results (
            run_id TEXT NOT NULL, rank INTEGER NOT NULL, chunk_id TEXT NOT NULL,
            score REAL NOT NULL, lexical_score REAL NOT NULL, vector_score REAL NOT NULL,
            graph_score REAL NOT NULL, PRIMARY KEY(run_id, rank)
        );
        """)

    @staticmethod
    def _pack_embedding(arr: np.ndarray) -> bytes:
        return np.asarray(arr, dtype=np.float32).ravel().tobytes()

    @staticmethod
    def _unpack_embedding(blob: Optional[bytes], dimensions: Optional[int]) -> Optional[np.ndarray]:
        if blob is None:
            return None
        arr = np.frombuffer(blob, dtype=np.float32).copy()
        if dimensions is not None and arr.size != int(dimensions):
            raise IntegrityError("Embedding almacenado con dimensiones inconsistentes.")
        return arr

    def upsert_document(self, source: str, path: str, title: str, content: str,
                        *, doc_type: str = "note", metadata: Optional[Dict[str, Any]] = None,
                        document_id: Optional[str] = None) -> KnowledgeDocument:
        now = _utc_now()
        doc_id = document_id or uuid.uuid4().hex
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        meta = _json(metadata or {})
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM brain_documents WHERE tenant_id=? AND source=? AND path=?",
                (self.tenant_id, source, path),
            ).fetchone()
            if row:
                doc_id = row["id"]
                self._db.execute("""UPDATE brain_documents
                    SET title=?, type=?, content=?, content_hash=?, metadata=?, deleted=0, updated_at=?
                    WHERE id=? AND tenant_id=?""",
                    (title, doc_type, content, digest, meta, now, doc_id, self.tenant_id))
            else:
                self._db.execute("""INSERT INTO brain_documents
                    (id,tenant_id,source,path,title,type,content,content_hash,metadata,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (doc_id,self.tenant_id,source,path,title,doc_type,content,digest,meta,now,now))
        return KnowledgeDocument(doc_id, source, path, title, doc_type, content, digest, metadata or {})

    def replace_chunks(self, document_id: str, chunks: Sequence[str],
                       embeddings: Optional[Sequence[np.ndarray]] = None) -> List[KnowledgeChunk]:
        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError("embeddings debe tener la misma longitud que chunks.")
        out = []
        with self._lock:
            self._db.execute("DELETE FROM brain_chunks WHERE document_id=? AND tenant_id=?",
                             (document_id, self.tenant_id))
            for pos, content in enumerate(chunks):
                cid = uuid.uuid4().hex
                emb = None if embeddings is None else np.asarray(embeddings[pos], dtype=np.float32).ravel()
                self._db.execute("""INSERT INTO brain_chunks
                    (id,tenant_id,document_id,position,content,embedding,dimensions,dtype)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (cid,self.tenant_id,document_id,pos,content,
                     None if emb is None else self._pack_embedding(emb),
                     None if emb is None else int(emb.size),
                     None if emb is None else "float32"))
                out.append(KnowledgeChunk(cid, document_id, pos, content, emb))
        return out

    def upsert_entity(self, name: str, *, primitive: str = "entity",
                      metadata: Optional[Dict[str, Any]] = None,
                      entity_id: Optional[str] = None) -> KnowledgeEntity:
        eid = entity_id or uuid.uuid4().hex
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM brain_entities WHERE tenant_id=? AND name=?",
                (self.tenant_id, name)).fetchone()
            if row:
                eid = row["id"]
                self._db.execute("UPDATE brain_entities SET primitive=?, metadata=? WHERE id=? AND tenant_id=?",
                                 (primitive, _json(metadata or {}), eid, self.tenant_id))
            else:
                self._db.execute("INSERT INTO brain_entities(id,tenant_id,name,primitive,metadata) VALUES(?,?,?,?,?)",
                                 (eid,self.tenant_id,name,primitive,_json(metadata or {})))
        return KnowledgeEntity(eid, name, primitive, metadata or {})

    def add_alias(self, alias: str, entity_id: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO brain_aliases(tenant_id,alias,entity_id) VALUES(?,?,?)",
                             (self.tenant_id, alias, entity_id))

    def add_relation(self, source_id: str, target_id: str, verb: str, *, weight: float = 1.0) -> None:
        with self._lock:
            self._db.execute("""INSERT OR REPLACE INTO brain_relations
                (tenant_id,source_id,target_id,verb,weight) VALUES(?,?,?,?,?)""",
                (self.tenant_id,source_id,target_id,verb,float(weight)))

    def add_claim(self, predicate: str, object_value: str, *, subject_id: Optional[str] = None,
                  confidence: float = 0.5, claim_id: Optional[str] = None) -> str:
        cid = claim_id or uuid.uuid4().hex
        with self._lock:
            self._db.execute("""INSERT INTO brain_claims
                (id,tenant_id,subject_id,predicate,object_value,confidence,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (cid,self.tenant_id,subject_id,predicate,object_value,float(confidence),_utc_now()))
        return cid

    def add_evidence(self, claim_id: str, source: str, excerpt: str, *, reliability: float = 1.0) -> str:
        eid = uuid.uuid4().hex
        with self._lock:
            self._db.execute("""INSERT INTO brain_evidence
                (id,tenant_id,claim_id,source,excerpt,reliability,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (eid,self.tenant_id,claim_id,source,excerpt,float(reliability),_utc_now()))
        return eid

    def record_provenance(self, object_type: str, object_id: str, source: str,
                          *, actor: str = "system", operation: str = "write",
                          content_hash: str = "", parent_id: Optional[str] = None) -> str:
        pid = uuid.uuid4().hex
        with self._lock:
            self._db.execute("""INSERT INTO brain_provenance
                (id,tenant_id,object_type,object_id,source,actor,operation,timestamp,content_hash,parent_id)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (pid,self.tenant_id,object_type,object_id,source,actor,operation,_utc_now(),content_hash,parent_id))
        return pid

    def save_schema_pack(self, pack: SchemaPack, *, activate: bool = False) -> None:
        with self._lock:
            if activate:
                self._db.execute("UPDATE brain_schema_packs SET active=0 WHERE tenant_id=?", (self.tenant_id,))
            self._db.execute("""INSERT OR REPLACE INTO brain_schema_packs
                (tenant_id,name,version,manifest,active) VALUES(?,?,?,?,?)""",
                (self.tenant_id,pack.name,pack.version,_json(pack.to_manifest()),1 if activate else 0))

    def active_schema_pack(self) -> Optional[SchemaPack]:
        row = self._db.execute("""SELECT manifest FROM brain_schema_packs
            WHERE tenant_id=? AND active=1 ORDER BY name LIMIT 1""", (self.tenant_id,)).fetchone()
        return None if row is None else SchemaPack.from_manifest(json.loads(row["manifest"]))

    def get_memory(self, kind: str) -> Optional[Dict[str, Any]]:
        """Obtiene la memoria nombrada más reciente (session/durable)."""
        with self._lock:
            row = self._db.execute(
                "SELECT id, kind, persistence, content, metadata, created_at "
                "FROM brain_memories WHERE tenant_id=? AND kind=? "
                "ORDER BY created_at DESC LIMIT 1",
                (self.tenant_id, kind),
            ).fetchone()
        if not row:
            return None
        content = row["content"]
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            pass
        meta = row["metadata"]
        try:
            meta = json.loads(meta) if isinstance(meta, str) else meta
        except (TypeError, ValueError):
            meta = {}
        return {
            "id": row["id"], "kind": row["kind"], "persistence": row["persistence"],
            "content": content, "metadata": meta, "created_at": row["created_at"],
        }

    def persist_memory(self, kind: str, content: Any = None, *, persistence: str = "durable",
                       metadata: Optional[Dict[str, Any]] = None,
                       allow_volatile_persist: bool = False) -> str:
        """Upsert de memoria nombrada (kind). Zero-Footprint: volatile nunca llega a disco.

        Si content is None y ya existe una fila, se conserva el contenido previo
        (útil para `persist memory=X` sin reenviar el valor).
        """
        persistence = str(persistence)
        if persistence == "volatile":
            raise IntegrityError("La memoria volatile no puede persistirse (Zero-Footprint).")
        if persistence not in {"session", "durable"}:
            raise ValueError("persistence debe ser volatile, session o durable.")
        if kind == "latent" and not allow_volatile_persist:
            raise IntegrityError("Persistencia de estado latente requiere autorización explícita.")

        existing = self.get_memory(kind)
        if content is None:
            if existing is None:
                raise IntegrityError(
                    f"No hay contenido para memoria '{kind}' y no se pasó value."
                )
            content = existing["content"]
        if metadata is None and existing is not None:
            metadata = existing.get("metadata") or {}

        payload = _json(content) if not isinstance(content, str) else content
        meta_s = _json(metadata or {})
        with self._lock:
            if existing is not None:
                self._db.execute(
                    "UPDATE brain_memories SET persistence=?, content=?, metadata=? "
                    "WHERE id=? AND tenant_id=?",
                    (self._persistence_storage(persistence), payload, meta_s,
                     existing["id"], self.tenant_id),
                )
                return existing["id"]
            mid = uuid.uuid4().hex
            self._db.execute(
                """INSERT INTO brain_memories
                   (id,tenant_id,kind,persistence,content,metadata,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (mid, self.tenant_id, kind, self._persistence_storage(persistence),
                 payload, meta_s, _utc_now()),
            )
            return mid


    def _persistence_storage(self, persistence: str) -> str:
        return persistence

    def resolve_entity(self, name_or_id: str) -> Optional[KnowledgeEntity]:
        """Resuelve una entidad por id exacto o por nombre (case-insensitive)."""
        key = str(name_or_id).strip()
        if not key:
            return None
        with self._lock:
            row = self._db.execute(
                "SELECT id, name, primitive, metadata FROM brain_entities "
                "WHERE tenant_id=? AND id=?",
                (self.tenant_id, key),
            ).fetchone()
            if row is None:
                row = self._db.execute(
                    "SELECT id, name, primitive, metadata FROM brain_entities "
                    "WHERE tenant_id=? AND lower(name)=lower(?) LIMIT 1",
                    (self.tenant_id, key),
                ).fetchone()
        if row is None:
            return None
        meta = row["metadata"]
        try:
            meta = json.loads(meta) if isinstance(meta, str) else (meta or {})
        except (TypeError, ValueError):
            meta = {}
        return KnowledgeEntity(row["id"], row["name"], row["primitive"], meta)

    def graph_neighbors(self, entity_id: str, *, depth: int = 1) -> List[Tuple[str, str, float]]:
        """Vecinos del grafo. `entity_id` puede ser UUID o nombre legible."""
        resolved = self.resolve_entity(entity_id)
        if resolved is None:
            return []
        entity_id = resolved.id
        depth = max(1, min(int(depth), 32))
        seen = {entity_id}
        frontier = {entity_id}
        found = []
        for _ in range(depth):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self._db.execute(
                f"SELECT source_id,target_id,verb,weight FROM brain_relations "
                f"WHERE tenant_id=? AND (source_id IN ({placeholders}) OR target_id IN ({placeholders}))",
                (self.tenant_id, *frontier, *frontier)).fetchall()
            nxt = set()
            for r in rows:
                other = r["target_id"] if r["source_id"] in frontier else r["source_id"]
                found.append((other, r["verb"], float(r["weight"])))
                if other not in seen:
                    seen.add(other)
                    nxt.add(other)
            frontier = nxt
        return found


    def all_chunks(self) -> List[KnowledgeChunk]:
        rows = self._db.execute("""SELECT id,document_id,position,content,embedding,dimensions
            FROM brain_chunks WHERE tenant_id=? ORDER BY document_id,position""", (self.tenant_id,)).fetchall()
        return [KnowledgeChunk(r["id"],r["document_id"],int(r["position"]),r["content"],
                                self._unpack_embedding(r["embedding"],r["dimensions"])) for r in rows]

    def document_for_chunk(self, chunk_id: str) -> Optional[KnowledgeDocument]:
        row = self._db.execute("""SELECT d.* FROM brain_documents d JOIN brain_chunks c ON c.document_id=d.id
            WHERE c.id=? AND d.tenant_id=?""", (chunk_id,self.tenant_id)).fetchone()
        if row is None:
            return None
        return KnowledgeDocument(row["id"],row["source"],row["path"],row["title"],row["type"],
                                 row["content"],row["content_hash"],json.loads(row["metadata"]))

    def close(self) -> None:
        with self._lock:
            self._db.close()


class HybridRetriever:
    """Retriever local: lexical + vector opcional + grafo + RRF.

    Sigue la idea de GBrain de no depender de un solo brazo de recuperación.
    El embedding es opcional: si no existe, el brazo vectorial simplemente
    aporta cero. En producción puede conectarse a pgvector mediante un adapter.
    """

    def __init__(self, store: CognitiveBrainStore, *, rrf_k: int = 60):
        self.store = store
        self.rrf_k = max(1, int(rrf_k))

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ_:-]+", text.casefold())

    def _lexical_rank(self, query: str, chunks: Sequence[KnowledgeChunk]) -> List[Tuple[str, float]]:
        q = self._tokens(query)
        if not q:
            return []
        qset = set(q)
        scored = []
        for c in chunks:
            toks = self._tokens(c.content)
            if not toks:
                continue
            counts = defaultdict(int)
            for t in toks:
                counts[t] += 1
            score = sum(min(counts[t], 3) for t in qset) / math.sqrt(len(toks))
            if score > 0:
                scored.append((c.id, float(score)))
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _vector_rank(self, query_embedding: Optional[np.ndarray], chunks: Sequence[KnowledgeChunk]) -> List[Tuple[str, float]]:
        if query_embedding is None:
            return []
        out = []
        for c in chunks:
            if c.embedding is not None and c.embedding.size == np.asarray(query_embedding).size:
                score = _cosine(query_embedding, c.embedding)
                if score > 0:
                    out.append((c.id, score))
        return sorted(out, key=lambda x: x[1], reverse=True)

    def search(self, query: str, *, query_embedding: Optional[np.ndarray] = None,
               top_k: int = 10, mode: str = "balanced") -> List[RetrievalResult]:
        chunks = self.store.all_chunks()
        lex = self._lexical_rank(query, chunks)
        vec = self._vector_rank(query_embedding, chunks)
        lex_rank = {cid: i + 1 for i, (cid, _) in enumerate(lex)}
        vec_rank = {cid: i + 1 for i, (cid, _) in enumerate(vec)}
        lex_score = dict(lex); vec_score = dict(vec)

        # Graph signal: si una entidad nombrada en la consulta aparece en un
        # documento, sus vecinos reciben un pequeño refuerzo, sin dominar RRF.
        graph_ids = set()
        for tok in self._tokens(query):
            row = self.store._db.execute("""SELECT id FROM brain_entities
                WHERE tenant_id=? AND lower(name)=? LIMIT 1""", (self.store.tenant_id,tok)).fetchone()
            if row:
                for eid, _verb, _weight in self.store.graph_neighbors(row["id"], depth=1):
                    graph_ids.add(eid)
        graph_score: Dict[str,float] = {}
        if graph_ids:
            rows = self.store._db.execute("""SELECT DISTINCT c.id,e.name FROM brain_chunks c
                JOIN brain_documents d ON d.id=c.document_id
                JOIN brain_entities e ON lower(d.content) LIKE '%' || lower(e.name) || '%'
                WHERE c.tenant_id=?""", (self.store.tenant_id,)).fetchall()
            for r in rows:
                if r["name"] and any(r["name"].casefold() == x.casefold() for x in graph_ids):
                    graph_score[r["id"]] = 1.0

        ids = set(lex_rank) | set(vec_rank) | set(graph_score)
        fused = []
        for cid in ids:
            rrf = 0.0
            if cid in lex_rank: rrf += 1.0 / (self.rrf_k + lex_rank[cid])
            if cid in vec_rank: rrf += 1.0 / (self.rrf_k + vec_rank[cid])
            if cid in graph_score: rrf += 0.15 * graph_score[cid]
            fused.append((cid, rrf))
        fused.sort(key=lambda x: x[1], reverse=True)
        by_id = {c.id:c for c in chunks}
        results = []
        for cid, score in fused[:max(1,int(top_k))]:
            c = by_id[cid]
            doc = self.store.document_for_chunk(cid)
            results.append(RetrievalResult(
                cid, c.document_id, float(score), float(lex_score.get(cid,0.0)),
                float(vec_score.get(cid,0.0)), float(graph_score.get(cid,0.0)),
                doc.source if doc else "", c.content,
            ))
        return results


class CognitiveBrainEngine:
    """Contrato único para ingestión, retrieval, grafo, evidencia y síntesis."""

    def __init__(self, store: CognitiveBrainStore, *, schema_pack: Optional[SchemaPack] = None):
        self.store = store
        self.schema_pack = schema_pack or store.active_schema_pack() or SchemaPack("ailang-default")
        self.retriever = HybridRetriever(store)

    def ingest(self, source: str, path: str, content: str, *, title: Optional[str] = None,
               doc_type: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
               chunk_size: int = 1200, embedding_fn: Optional[Callable[[str], np.ndarray]] = None) -> KnowledgeDocument:
        inferred = doc_type or self.schema_pack.infer_type(path) or "note"
        doc = self.store.upsert_document(source,path,title or os.path.basename(path) or path,content,
                                         doc_type=inferred,metadata=metadata)
        chunks = [content[i:i+max(128,int(chunk_size))] for i in range(0,len(content),max(128,int(chunk_size)))] or [""]
        embeddings = None if embedding_fn is None else [embedding_fn(x) for x in chunks]
        self.store.replace_chunks(doc.id,chunks,embeddings)
        self.store.record_provenance("document",doc.id,source,actor="cognitive-engine",
                                     operation="ingest",content_hash=doc.content_hash)
        return doc

    def search(self, query: str, *, query_embedding: Optional[np.ndarray] = None,
               top_k: int = 10, mode: str = "balanced") -> List[RetrievalResult]:
        return self.retriever.search(query,query_embedding=query_embedding,top_k=top_k,mode=mode)

    def graph(self, entity: str, *, depth: int = 2) -> List[Dict[str, Any]]:
        """Recorre el grafo desde un id o nombre de entidad.

        Devuelve lista de {id, name, verb, weight} para facilitar el uso
        desde la DSL (`brain.graph entity="AILang"`).
        """
        neighbors = self.store.graph_neighbors(entity, depth=depth)
        out = []
        for eid, verb, weight in neighbors:
            ent = self.store.resolve_entity(eid)
            out.append({
                "id": eid,
                "name": ent.name if ent else eid,
                "verb": verb,
                "weight": weight,
            })
        return out

    def think(self, query: str, *, query_embedding: Optional[np.ndarray] = None,
              top_k: int = 8) -> Dict[str, Any]:
        results = self.search(query,query_embedding=query_embedding,top_k=top_k)
        evidence = [{"source":r.source,"excerpt":r.excerpt,"score":round(r.score,6)} for r in results]
        if not results:
            return {"answer":"No hay evidencia suficiente en el brain.","evidence":[],
                    "gaps":["No se encontraron documentos relevantes."],"confidence":0.0}
        confidence = min(1.0, max(0.0, sum(r.score for r in results[:3]) * 20.0))
        gaps = []
        if len(results) < min(3,top_k): gaps.append("Evidencia escasa para la consulta.")
        sources = {r.source for r in results}
        if len(sources) == 1: gaps.append("La evidencia procede de una sola fuente.")
        answer = "\n\n".join(f"[{i}] {r.excerpt}" for i,r in enumerate(results[:5],1))
        return {"answer":answer,"evidence":evidence,"gaps":gaps,
                "confidence":round(confidence,4),"mode":"hybrid"}


# API compatible con el concepto contract-first de GBrain.
BrainEngine = CognitiveBrainEngine

# =============================================================================
# CLI
# =============================================================================

def _cli(argv: Optional[List[str]] = None) -> int:
    """CLI de Nexus AILang-Core v7.0: outbox, brain, eval DSL y tests."""
    parser = argparse.ArgumentParser(
        prog="ailang_core",
        description=f"Nexus AILang-Core {__version__} — runtime cognitivo + transporte fiable",
    )
    sub = parser.add_subparsers(dest="command")

    # --- Outbox ---
    p = sub.add_parser("counts", help="Contadores del outbox SQLite")
    p.add_argument("db", help="Ruta al fichero .db del outbox")

    p = sub.add_parser("list", help="Listar pendientes del outbox o recursos del brain")
    p.add_argument("db", nargs="?", default=None, help="Ruta outbox.db (modo outbox)")
    p.add_argument("-n", type=int, default=50, help="Máximo de filas")
    p.add_argument("--type", default="outbox",
                   choices=("outbox", "schema", "documents", "entities", "chunks"),
                   help="Tipo de recurso a listar")
    p.add_argument("--brain-db", default=None, help="Ruta al brain store (modo schema/docs/...)")

    p = sub.add_parser("dead", help="Listar dead letters del outbox")
    p.add_argument("db")

    p = sub.add_parser("requeue", help="Reencolar dead letters")
    p.add_argument("db")

    p = sub.add_parser("purge-dead", help="Borrar dead letters")
    p.add_argument("db")

    # --- Runtime / DSL ---
    p = sub.add_parser("run", help="Inicializar runtime cognitivo (nodo + brain)")
    p.add_argument("--config", default="ailang.json", help="Fichero de configuración JSON")
    p.add_argument("--secret", default=None, help="HMAC secret (texto); si se omite se genera")
    p.add_argument("--listen", default="127.0.0.1:0", help="host:port o unix:///path")
    p.add_argument("--brain-db", default=":memory:", help="Ruta al CognitiveBrainStore")
    p.add_argument("--outbox", default=None, help="Ruta outbox.db (opcional)")

    p = sub.add_parser("eval", help="Compilar y ejecutar un script DSL cognitivo")
    p.add_argument("file", help="Fichero .ail / texto con purge_after + brain.*")
    p.add_argument("--brain-db", default=":memory:", help="Ruta al brain store")
    p.add_argument("--capabilities", default="knowledge.read,knowledge.write,memory.write,memory.persist,graph.traverse",
                   help="Capacidades autorizadas separadas por coma")
    p.add_argument("--show-ir", action="store_true", help="Imprimir CognitiveIR antes de ejecutar")

    p = sub.add_parser("ingest", help="Ingestar un documento en el brain")
    p.add_argument("path", help="Ruta del fichero a ingerir")
    p.add_argument("--brain-db", required=True, help="Ruta al brain store")
    p.add_argument("--source", default="cli", help="Etiqueta de origen")
    p.add_argument("--type", default=None, dest="doc_type", help="Tipo de documento (schema)")

    p = sub.add_parser("query", help="Consulta híbrida sobre el brain")
    p.add_argument("text", help="Texto de la consulta")
    p.add_argument("--brain-db", required=True)
    p.add_argument("--top-k", type=int, default=5)

    p = sub.add_parser("think", help="Síntesis con evidencia (brain.think)")
    p.add_argument("text")
    p.add_argument("--brain-db", required=True)
    p.add_argument("--top-k", type=int, default=8)

    p = sub.add_parser("health", help="Mostrar health() de un nodo de prueba")
    p.add_argument("--secret", default="cli-health-secret!!")

    sub.add_parser("version", help="Mostrar versión")
    sub.add_parser("test", help="Ejecutar tests unitarios")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    try:
        return _cli_dispatch(args)
    except KeyboardInterrupt:
        print("\n[!] Operación interrumpida por el usuario.")
        return 130
    except AILangError as exc:
        print(f"[!] Error AILang: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[!] Error: {exc}", file=sys.stderr)
        return 1


def _cli_dispatch(args: argparse.Namespace) -> int:
    cmd = args.command

    if cmd == "version":
        print(f"Nexus AILang-Core {__version__}")
        print(f"Author: {AUTHOR}")
        print(f"Bytecode magic: {MAGIC!r} format={FORMAT_VERSION}")
        return 0

    if cmd == "test":
        ok = unittest.main(module=__name__, argv=["ailang_core"], exit=False).result.wasSuccessful()
        return 0 if ok else 1

    if cmd == "health":
        secret = args.secret.encode() if isinstance(args.secret, str) else args.secret
        node = DistributedNode("cli-health", secret=secret)
        print(json.dumps(node.health(), indent=2, default=str))
        print(node.metrics.prometheus())
        node.close(flush_timeout=0)
        return 0

    # --- Outbox commands ---
    if cmd in ("counts", "dead", "requeue", "purge-dead") or (
        cmd == "list" and getattr(args, "type", "outbox") == "outbox" and args.db
    ):
        if not getattr(args, "db", None):
            print("[!] Se requiere la ruta al outbox.db", file=sys.stderr)
            return 1
        ob = PersistentOutbox(args.db)
        try:
            if cmd == "counts":
                print(json.dumps(ob.counts(), indent=2))
            elif cmd == "list":
                for it in ob.list_pending(args.n):
                    print(f"{it.row_id}\t{it.msg_id}\t{it.peer_id}\t"
                          f"{it.host}:{it.port}\tattempts={it.attempts}")
            elif cmd == "dead":
                for it in ob.dead_letters():
                    print(f"{it.row_id}\t{it.msg_id}\t{it.peer_id}\t{it.last_error}")
            elif cmd == "requeue":
                print(f"requeued={ob.requeue_dead()}")
            elif cmd == "purge-dead":
                print(f"purged={ob.purge_dead()}")
        finally:
            ob.close()
        return 0

    # --- Brain list ---
    if cmd == "list":
        brain_path = args.brain_db or args.db
        if not brain_path:
            print("[!] Indica --brain-db o db", file=sys.stderr)
            return 1
        store = CognitiveBrainStore(brain_path)
        try:
            if args.type == "schema":
                pack = store.active_schema_pack()
                print(json.dumps(pack.__dict__ if pack else {}, indent=2, default=str))
            elif args.type == "documents":
                rows = store._db.execute(
                    "SELECT id, source, path, title, type FROM brain_documents LIMIT ?",
                    (args.n,),
                ).fetchall()
                for r in rows:
                    print(dict(r))
            elif args.type == "entities":
                rows = store._db.execute(
                    "SELECT id, name, primitive FROM brain_entities LIMIT ?",
                    (args.n,),
                ).fetchall()
                for r in rows:
                    print(dict(r))
            elif args.type == "chunks":
                for c in store.all_chunks()[: args.n]:
                    print(f"{c.id}\t{c.document_id}\t{c.content[:80]!r}")
            else:
                print(f"[!] Tipo no soportado en list: {args.type}")
                return 1
        finally:
            store.close()
        return 0

    if cmd == "ingest":
        store = CognitiveBrainStore(args.brain_db)
        engine = CognitiveBrainEngine(store)
        try:
            content = Path(args.path).read_text(encoding="utf-8")
            doc = engine.ingest(args.source, args.path, content, doc_type=args.doc_type)
            print(json.dumps({
                "id": doc.id, "path": doc.path, "type": doc.type,
                "content_hash": doc.content_hash,
            }, indent=2))
        finally:
            store.close()
        return 0

    if cmd == "query":
        store = CognitiveBrainStore(args.brain_db)
        engine = CognitiveBrainEngine(store)
        try:
            results = engine.search(args.text, top_k=args.top_k)
            for r in results:
                print(json.dumps({
                    "score": round(r.score, 4), "source": r.source,
                    "excerpt": r.excerpt[:200],
                }, ensure_ascii=False))
        finally:
            store.close()
        return 0

    if cmd == "think":
        store = CognitiveBrainStore(args.brain_db)
        engine = CognitiveBrainEngine(store)
        try:
            out = engine.think(args.text, top_k=args.top_k)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        finally:
            store.close()
        return 0

    if cmd == "eval":
        path = Path(args.file)
        source = path.read_text(encoding="utf-8")
        compiler = AILangCompiler(source)
        ir = compiler.compile_ir()
        if args.show_ir:
            print(json.dumps(ir.manifest(), indent=2, ensure_ascii=False))
        # Genera bytecode (valida purge_after + IR)
        blob = compiler.compile()
        print(f"[*] Bytecode: {len(blob)} bytes, IR digest={ir.digest[:16]}…")
        caps = [c.strip() for c in args.capabilities.split(",") if c.strip()]
        store = CognitiveBrainStore(args.brain_db)
        engine = CognitiveBrainEngine(store)
        try:
            results = compiler.compile_and_execute(engine, capabilities=caps)
            print(json.dumps(results, indent=2, default=str, ensure_ascii=False))
        finally:
            store.close()
        return 0

    if cmd == "run":
        print(f"[*] Nexus AILang-Core {__version__}")
        config: Dict[str, Any] = {}
        cfg_path = Path(args.config)
        if cfg_path.exists():
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
            print(f"[*] Config cargada: {cfg_path}")
        else:
            print(f"[*] Sin config ({cfg_path}); usando defaults de CLI")

        secret_txt = args.secret or config.get("secret") or secrets.token_hex(16)
        secret = secret_txt.encode() if isinstance(secret_txt, str) else secret_txt
        brain_db = args.brain_db or config.get("brain_db", ":memory:")
        outbox = args.outbox or config.get("outbox")
        listen = args.listen or config.get("listen", "127.0.0.1:0")

        store = CognitiveBrainStore(brain_db)
        engine = CognitiveBrainEngine(store)
        node = DistributedNode(
            config.get("node_id", "ailang-cli"),
            secret=secret,
            outbox_path=outbox,
            require_auth=True,
        )
        if listen.startswith("unix://") or listen.startswith("/"):
            addr = node.listen(listen)
        else:
            host, _, port_s = listen.rpartition(":")
            addr = node.listen(host or "127.0.0.1", int(port_s or "0"))
        print(f"[*] Nodo escuchando en {addr}")
        print(f"[*] Brain store: {brain_db}")
        print(json.dumps(node.health(), indent=2, default=str))
        print("[*] Runtime listo. Ctrl+C para detener.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[*] Cerrando…")
        finally:
            node.close(flush_timeout=5)
            store.close()
        return 0

    print(f"[!] Comando desconocido: {cmd}")
    return 1



# =============================================================================
# Tests
# =============================================================================

def _slow_sleep_for_test() -> None:
    """Función top-level serializable para HardLatencyBudget con proceso."""
    time.sleep(0.3)


class TestAILangCore(unittest.TestCase):
    def test_strip_comments_respects_strings(self):
        src = 'x = "// no es comentario"; y = 1; // sí'
        clean = strip_comments(src)
        self.assertIn('"// no es comentario"', clean)
        self.assertNotIn("// sí", clean)

    def test_compiler_requires_purge(self):
        with self.assertRaises(CompilerError):
            AILangCompiler("x = 1").compile()
        blob = AILangCompiler("purge_after(10ms)\nx=1").compile()
        prog = decode_bytecode(blob)
        self.assertEqual(prog.budget_ms, 10)

    def test_bytecode_integrity(self):
        blob = AILangCompiler("purge_after(5ms)\nok").compile()
        bad = bytearray(blob)
        bad[-1] ^= 0xFF
        with self.assertRaises(IntegrityError):
            decode_bytecode(bytes(bad))

    def test_latency_budget_soft(self):
        with self.assertRaises(LatencyBudgetExceeded):
            with LatencyBudget(1.0):
                time.sleep(0.05)

    def test_hard_latency_budget_thread(self):
        budget = HardLatencyBudget(30.0, use_process=False)
        with self.assertRaises(LatencyBudgetExceeded):
            budget.run(lambda: time.sleep(0.2))

    def test_hard_latency_budget_process(self):
        # función top-level para poder serializar con spawn
        budget = HardLatencyBudget(50.0, use_process=True)
        try:
            with self.assertRaises(LatencyBudgetExceeded):
                budget.run(_slow_sleep_for_test)
        except (OSError, RuntimeError, AttributeError):
            self.skipTest("multiprocessing no disponible o no serializable en este entorno")

    def test_engine_infer_and_purge(self):
        eng = NexusAIEngine(latent_dims=8, budget_ms=100.0, auto_purge=True)
        x = np.ones(8, dtype=np.float32)
        r = eng.infer(x)
        self.assertEqual(r["status"], "OK_PURGED")
        self.assertTrue(np.allclose(eng.state, 0.0))

    def test_engine_rejects_bad_shape(self):
        eng = NexusAIEngine(latent_dims=4)
        with self.assertRaises(IntegrityError):
            eng.infer(np.zeros(3, dtype=np.float32))

    def test_encode_decode_roundtrip(self):
        arr = np.arange(6, dtype=np.float32).reshape(2, 3)
        frame = encode_message("a", arr)
        (length,) = _U32.unpack_from(frame)
        body = frame[4:]
        self.assertEqual(length, len(body))
        msg = decode_message(body)
        np.testing.assert_array_equal(msg["data"], arr)

    def test_hmac_rejects_tamper(self):
        secret = b"supersecret"
        arr = np.ones(4, dtype=np.float32)
        frame = encode_message("a", arr, secret)
        body = bytearray(frame[4:])
        body[10] ^= 0x01
        with self.assertRaises(IntegrityError):
            decode_message(bytes(body), secret)

    def test_bounded_channel(self):
        ch = BoundedChannel(capacity=2)
        ch.send(np.array([1.0]))
        ch.send(np.array([2.0]))
        ch.send(np.array([3.0]))
        self.assertEqual(len(ch), 2)
        a = ch.recv()
        np.testing.assert_array_equal(a, np.array([2.0]))

    def test_local_broadcast(self):
        secret = b"local-test-secret!!"
        a = DistributedNode("a", secret=secret, require_auth=True)
        b = DistributedNode("b", secret=secret, require_auth=True)
        a.register_peer(b)
        payload = np.array([1.0, 2.0], dtype=np.float32)
        n = a.broadcast(payload)
        self.assertEqual(n, 1)
        msg = b.recv(timeout=1.0)
        self.assertIsNotNone(msg)
        np.testing.assert_array_equal(msg["data"], payload)
        a.close()
        b.close()


    def test_engine_snapshot_restore(self):
        eng = NexusAIEngine(latent_dims=8, budget_ms=100.0)
        eng.infer(np.ones(8, dtype=np.float32))
        snap = eng.snapshot()
        eng2 = NexusAIEngine(latent_dims=8)
        eng2.restore(snap)
        np.testing.assert_array_almost_equal(eng.state, eng2.state)

    def test_compress_roundtrip(self):
        arr = np.zeros(2000, dtype=np.float32)
        frame = encode_message("a", arr, compress=True)
        msg = decode_message(frame[4:])
        np.testing.assert_array_equal(msg["data"], arr)

    def test_strip_triple_quotes(self):
        src = "x = " + chr(39)*3 + "// no" + chr(39)*3 + "; // yes"
        clean = strip_comments(src)
        self.assertIn("// no", clean)
        self.assertNotIn("// yes", clean)

    def test_health(self):
        secret = b"health-secret!!!!!!"
        n = DistributedNode("h", secret=secret)
        h = n.health()
        self.assertEqual(h["node_id"], "h")
        self.assertIn("metrics", h)
        n.close(flush_timeout=0)

class TestAILangOutbox(unittest.TestCase):
    def _outbox(self, **kw):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return PersistentOutbox(path, **kw)

    def test_enqueue_and_due(self):
        ob = self._outbox()
        arr = np.ones(3, dtype=np.float32)
        mid = ob.enqueue([("p1", "127.0.0.1", 9999, None)], arr)
        items = ob.due(limit=10)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].msg_id, mid)
        np.testing.assert_array_equal(items[0].payload(decrypt=ob._decrypt), arr)
        ob.mark_sent(items[0].row_id)
        self.assertEqual(ob.counts(), {"pending": 0, "dead": 0})

    def test_encryption_from_secret(self):
        try:
            from cryptography.fernet import Fernet  # noqa: F401
        except ImportError:
            self.skipTest("cryptography no instalado")
        secret = b"hmac-secret-for-derive!!"
        ob = self._outbox(secret=secret, require_encryption=True)
        arr = np.arange(5, dtype=np.float64)
        ob.enqueue([("p", "127.0.0.1", 1, None)], arr)
        item = ob.due()[0]
        self.assertGreater(item.key_version, 0)
        recovered = item.payload(decrypt=ob._decrypt)
        np.testing.assert_array_equal(recovered, arr)

    def test_key_rotation(self):
        try:
            from cryptography.fernet import Fernet  # noqa: F401
        except ImportError:
            self.skipTest("cryptography no instalado")
        k1 = secrets.token_bytes(32)
        k2 = secrets.token_bytes(32)
        ob = self._outbox(keys={1: k1}, current_key_version=1, require_encryption=True)
        arr = np.ones(2, dtype=np.float32)
        ob.enqueue([("p", "127.0.0.1", 1, None)], arr)
        item1 = ob.due()[0]
        self.assertEqual(item1.key_version, 1)
        ob.rotate_key(k2, 2)
        arr2 = np.ones(3, dtype=np.float32)
        ob.enqueue([("p2", "127.0.0.1", 1, None)], arr2)
        items = ob.due(limit=10)
        versions = {it.peer_id: it.key_version for it in items}
        self.assertEqual(versions.get("p"), 1)
        self.assertEqual(versions.get("p2"), 2)
        for it in items:
            it.payload(decrypt=ob._decrypt)  # no debe lanzar

    def test_dead_letters_and_requeue(self):
        ob = self._outbox()
        arr = np.zeros(2, dtype=np.float32)
        ob.enqueue([("p", "127.0.0.1", 1, None)], arr)
        item = ob.due()[0]
        ob.mark_dead(item.row_id, 3, "sin ACK")
        self.assertEqual(ob.counts(), {"pending": 0, "dead": 1})
        self.assertEqual(ob.requeue_dead(), 1)
        self.assertEqual(ob.counts(), {"pending": 1, "dead": 0})

    def test_outbox_full(self):
        ob = self._outbox(max_items=1)
        arr = np.ones(1, dtype=np.float32)
        ob.enqueue([("p1", "127.0.0.1", 1, None)], arr)
        with self.assertRaises(OutboxFull):
            ob.enqueue([("p2", "127.0.0.1", 1, None)], arr)


class TestAILangTransport(unittest.TestCase):
    def test_tcp_roundtrip_with_ack(self):
        received = []

        def on_msg(m):
            received.append(m)

        secret = b"test-secret-key!!"
        srv = TcpTransport("srv", on_msg, secret=secret, require_auth=True)
        host, port = srv.start()
        cli = TcpTransport("cli", lambda m: None, secret=secret, require_auth=True)
        arr = np.linspace(0, 1, 8, dtype=np.float32)
        attempts = cli.send(host, port, arr)
        self.assertGreaterEqual(attempts, 1)
        self.assertEqual(len(received), 1)
        np.testing.assert_array_equal(received[0]["data"], arr)
        srv.stop()
        cli.stop()

    def test_require_auth_default_rejects_insecure(self):
        with self.assertRaises(TransportError):
            TcpTransport("x", lambda m: None)  # require_auth=True por defecto

    def test_ack_after_process_skips_on_failure(self):
        def bad_handler(m):
            raise RuntimeError("fallo de procesamiento")

        secret = b"proc-ack-secret!!!!"
        srv = TcpTransport(
            "srv", bad_handler, secret=secret, require_auth=True, ack_after_process=True
        )
        host, port = srv.start()
        cli = TcpTransport("cli", lambda m: None, secret=secret, require_auth=True)
        arr = np.ones(4, dtype=np.float32)
        with self.assertRaises(TransportError):
            cli.send(host, port, arr, retry=RetryPolicy(max_attempts=2, base_delay=0.05))
        srv.stop()
        cli.stop()

    def test_persistent_seen(self):
        fd, path = tempfile.mkstemp(suffix=".seen.db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        store = PersistentSeenStore(path, max_entries=100, ttl_s=3600)
        self.assertFalse(store.is_duplicate("aaaaaaaaaaaaaaaa"))
        self.assertTrue(store.is_duplicate("aaaaaaaaaaaaaaaa"))
        store.close()
        # reabrir: sigue siendo duplicado
        store2 = PersistentSeenStore(path, max_entries=100, ttl_s=3600)
        self.assertTrue(store2.is_duplicate("aaaaaaaaaaaaaaaa"))
        store2.close()

    def test_dedup_window_memory(self):
        secret = b"dedup-mem-secret!!!"
        t = TcpTransport("t", lambda m: None, secret=secret, dedup_window=2, dedup_ttl_s=60.0)
        self.assertFalse(t._is_duplicate("aaaaaaaaaaaaaaaa"))
        self.assertTrue(t._is_duplicate("aaaaaaaaaaaaaaaa"))
        self.assertFalse(t._is_duplicate("bbbbbbbbbbbbbbbb"))
        self.assertFalse(t._is_duplicate("cccccccccccccccc"))
        self.assertFalse(t._is_duplicate("aaaaaaaaaaaaaaaa"))



class TestCognitiveCompiler(unittest.TestCase):
    def test_compile_produces_cognitive_ir(self):
        src = """purge_after(20ms)
brain.query text="knowledge graph" top_k=3
brain.think text="what is AILang"
"""
        compiler = AILangCompiler(src)
        ir = compiler.compile_ir()
        self.assertEqual([i.op for i in ir.instructions], ["brain.query", "brain.think"])
        self.assertIn("knowledge.read", ir.required_capabilities)
        blob = compiler.compile()
        decoded = decode_bytecode(blob)
        self.assertEqual(decoded.cognitive_ir.digest, ir.digest)

    def test_zero_footprint_is_compile_time_error(self):
        src = """purge_after(20ms)
memory volatile name=latent value='{"x":1}'
persist memory=latent
"""
        with self.assertRaises(CompilerError):
            AILangCompiler(src).compile()

    def test_runtime_requires_capability(self):
        src = """purge_after(20ms)
brain.query text="knowledge graph"
"""
        compiler = AILangCompiler(src)
        store = CognitiveBrainStore(":memory:", tenant_id="compiler")
        engine = CognitiveBrainEngine(store)
        self.addCleanup(store.close)
        with self.assertRaises(IntegrityError):
            compiler.compile_and_execute(engine)
        out = compiler.compile_and_execute(engine, capabilities=["knowledge.read"])
        self.assertIsInstance(out, list)

    def test_durable_memory_can_execute(self):
        src = """purge_after(20ms)
memory durable name=decision value='{"ok":true}'
"""
        store = CognitiveBrainStore(":memory:", tenant_id="compiler")
        engine = CognitiveBrainEngine(store)
        self.addCleanup(store.close)
        out = AILangCompiler(src).compile_and_execute(engine, capabilities=["memory.write"])
        self.assertEqual(len(out), 1)


class TestCognitiveBrain(unittest.TestCase):
    def setUp(self):
        self.store = CognitiveBrainStore(":memory:", tenant_id="t1")
        self.addCleanup(self.store.close)
        pack = SchemaPack(
            "test", "1.0.0",
            types=(
                SchemaType("project", "entity", ("Projects/",), ("proj",), True, True),
                SchemaType("note", "document", ("Notes/",)),
            ),
            link_types=("depends_on", "supports"),
        )
        self.store.save_schema_pack(pack, activate=True)
        self.engine = CognitiveBrainEngine(self.store, schema_pack=pack)

    def test_schema_pack_inference_and_alias(self):
        self.assertEqual(self.engine.schema_pack.infer_type("Projects/AILang.md"), "project")
        self.assertEqual(self.engine.schema_pack.resolve_alias("proj"), "project")

    def test_ingest_persists_chunks_and_provenance(self):
        doc = self.engine.ingest("repo", "Projects/AILang.md", "Nexus AILang-Core uses a cognitive graph.")
        self.assertEqual(doc.type, "project")
        self.assertEqual(len(self.store.all_chunks()), 1)
        row = self.store._db.execute(
            "SELECT COUNT(*) n FROM brain_provenance WHERE object_id=?", (doc.id,)).fetchone()
        self.assertEqual(row["n"], 1)

    def test_hybrid_lexical_search(self):
        self.engine.ingest("repo", "Projects/a.md", "Postgres knowledge graph and retrieval")
        self.engine.ingest("repo", "Projects/b.md", "unrelated compiler parser")
        results = self.engine.search("knowledge graph", top_k=2)
        self.assertTrue(results)
        self.assertIn("knowledge graph", results[0].excerpt)

    def test_graph_and_evidence(self):
        a = self.store.upsert_entity("AILang", primitive="project")
        b = self.store.upsert_entity("GBrain", primitive="project")
        self.store.add_relation(a.id,b.id,"inspired_by")
        self.assertTrue(self.store.graph_neighbors(a.id, depth=1))
        claim = self.store.add_claim("uses", "hybrid retrieval", subject_id=a.id, confidence=.9)
        ev = self.store.add_evidence(claim,"repo","retrieval design",reliability=.95)
        self.assertTrue(ev)

    def test_volatile_memory_cannot_persist(self):
        with self.assertRaises(IntegrityError):
            self.store.persist_memory("latent", {"x":1}, persistence="volatile")
        with self.assertRaises(IntegrityError):
            self.store.persist_memory("latent", {"x":1}, persistence="durable")
        mid = self.store.persist_memory("decision", {"x":1}, persistence="durable")
        self.assertTrue(mid)


class TestV70Integrations(unittest.TestCase):
    def test_version_and_prometheus(self):
        # Versión es un string semver válido >= 2.0.0 (NO hard-locked a un literal,
        # para permitir bumps de versión sin romper el test embebido).
        self.assertGreaterEqual(tuple(int(p) for p in __version__.split(".")),
                                (2, 0, 0))
        m = Metrics()
        m.inc("messages_sent", 3)
        text = m.prometheus()
        self.assertIn("ailang_messages_sent", text)

    def test_stable_msg_id(self):
        a = np.ones(4, dtype=np.float32)
        self.assertEqual(stable_msg_id(a), stable_msg_id(a.copy()))

    def test_unix_socket_roundtrip(self):
        path = tempfile.mktemp(suffix=".sock")
        got = []
        secret = b"unix-socket-secret!"
        srv = TcpTransport("srv", lambda m: got.append(m), secret=secret)
        addr = srv.start(f"unix://{path}")
        self.assertTrue(str(addr).startswith("unix://"))
        cli = TcpTransport("cli", lambda m: None, secret=secret)
        cli.send(f"unix://{path}", 0, np.array([3.0], dtype=np.float32))
        self.assertEqual(len(got), 1)
        srv.stop(); cli.stop()

    def test_ordered_local(self):
        secret = b"ordered-test-secret"
        a = DistributedNode("a", secret=secret, ordered=True)
        b = DistributedNode("b", secret=secret, ordered=True)
        a.register_peer(b)
        a.broadcast(np.array([1.0], dtype=np.float32))
        a.broadcast(np.array([2.0], dtype=np.float32))
        m1 = b.recv(timeout=1, from_peer="a")
        m2 = b.recv(timeout=1, from_peer="a")
        self.assertEqual(float(m1["data"][0]), 1.0)
        self.assertEqual(float(m2["data"][0]), 2.0)
        a.close(flush_timeout=0); b.close(flush_timeout=0)

    def test_nested_latency(self):
        with LatencyBudget(100.0) as outer:
            with LatencyBudget(50.0) as inner:
                time.sleep(0.001)
            self.assertLess(inner.elapsed_ms, 50)



class TestPersistAndGraphFixes(unittest.TestCase):
    def setUp(self):
        self.store = CognitiveBrainStore(":memory:", tenant_id="fix")
        self.addCleanup(self.store.close)
        self.engine = CognitiveBrainEngine(self.store)

    def test_memory_upsert_and_persist_keeps_value(self):
        mid1 = self.store.persist_memory("decision", {"ok": True}, persistence="durable")
        mid2 = self.store.persist_memory("decision", None, persistence="durable")
        self.assertEqual(mid1, mid2)
        mem = self.store.get_memory("decision")
        self.assertEqual(mem["content"], {"ok": True})

    def test_persist_dsl_chain(self):
        src = """purge_after(20ms)
memory durable name=decision value='{"ok":true}'
persist memory=decision
"""
        out = AILangCompiler(src).compile_and_execute(
            self.engine, capabilities=["memory.write", "memory.persist"])
        self.assertEqual(out[0], out[1])  # mismo id (upsert)
        mem = self.store.get_memory("decision")
        self.assertEqual(mem["content"], {"ok": True})

    def test_graph_resolves_by_name(self):
        a = self.store.upsert_entity("AILang", primitive="project")
        b = self.store.upsert_entity("GBrain", primitive="project")
        self.store.add_relation(a.id, b.id, "inspired_by")
        by_name = self.engine.graph("AILang", depth=1)
        by_id = self.engine.graph(a.id, depth=1)
        self.assertEqual(len(by_name), 1)
        self.assertEqual(by_name[0]["name"], "GBrain")
        self.assertEqual(by_name[0]["verb"], "inspired_by")
        self.assertEqual(by_name[0]["id"], by_id[0]["id"])

    def test_graph_dsl_by_name(self):
        a = self.store.upsert_entity("AILang", primitive="project")
        b = self.store.upsert_entity("GBrain", primitive="project")
        self.store.add_relation(a.id, b.id, "inspired_by")
        src = """purge_after(20ms)
brain.graph entity="AILang" depth=1
"""
        out = AILangCompiler(src).compile_and_execute(
            self.engine, capabilities=["graph.traverse"])
        self.assertEqual(len(out[0]), 1)
        self.assertEqual(out[0][0]["name"], "GBrain")


if __name__ == "__main__":
    _CLI_CMDS = {
        "counts", "list", "dead", "requeue", "purge-dead", "test",
        "run", "eval", "ingest", "query", "think", "health", "version",
    }
    # -h/--help o sin args → ayuda de la CLI; subcomando → CLI; resto → tests.
    if len(sys.argv) == 1 or sys.argv[1] in _CLI_CMDS or sys.argv[1] in ("-h", "--help"):
        raise SystemExit(_cli())
    unittest.main(verbosity=2)
