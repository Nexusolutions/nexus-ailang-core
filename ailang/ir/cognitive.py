"""Formal Cognitive IR v1 — schema versionado y canónico."""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


IR_SCHEMA = "ailang-cognitive-ir"
IR_VERSION = 1


class CognitiveOp(str, enum.Enum):
    INGEST = "brain.ingest"
    QUERY = "brain.query"
    THINK = "brain.think"
    GRAPH = "brain.graph"
    MEMORY = "memory"
    PERSIST = "persist"


# op → required capabilities
OP_CAPABILITIES: Dict[CognitiveOp, Tuple[str, ...]] = {
    CognitiveOp.INGEST: ("knowledge.write",),
    CognitiveOp.QUERY: ("knowledge.read",),
    CognitiveOp.THINK: ("knowledge.read",),
    CognitiveOp.GRAPH: ("graph.traverse",),
    CognitiveOp.MEMORY: ("memory.write",),
    CognitiveOp.PERSIST: ("memory.persist",),
}


@dataclass(frozen=True)
class CognitiveInstruction:
    op: CognitiveOp
    args: Dict[str, Any] = field(default_factory=dict)
    line: int = 0
    required_capabilities: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op.value,
            "args": self.args,
            "line": self.line,
            "required_capabilities": list(self.required_capabilities),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CognitiveInstruction":
        op = CognitiveOp(d["op"])
        caps = tuple(d.get("required_capabilities") or OP_CAPABILITIES.get(op, ()))
        return CognitiveInstruction(op, dict(d.get("args") or {}), int(d.get("line") or 0), caps)


@dataclass(frozen=True)
class CognitiveIR:
    """IR cognitiva formal: versionada, digesta-canónica, validable."""
    schema: str = IR_SCHEMA
    version: int = IR_VERSION
    instructions: Tuple[CognitiveInstruction, ...] = ()
    required_capabilities: Tuple[str, ...] = ()
    digest: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> str:
        body = {
            "schema": self.schema,
            "version": self.version,
            "instructions": [i.to_dict() for i in self.instructions],
            "required_capabilities": list(self.required_capabilities),
            "metadata": self.metadata,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def compute_digest(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def with_digest(self) -> "CognitiveIR":
        return CognitiveIR(
            self.schema, self.version, self.instructions,
            self.required_capabilities, self.compute_digest(), dict(self.metadata),
        )

    def validate(self) -> None:
        if self.schema != IR_SCHEMA:
            raise ValueError(f"schema inválido: {self.schema}")
        if self.version != IR_VERSION:
            raise ValueError(f"versión IR no soportada: {self.version}")
        if self.digest and self.digest != self.compute_digest():
            raise ValueError("digest del Cognitive IR no coincide (IR alterado).")
        for ins in self.instructions:
            expected = OP_CAPABILITIES.get(ins.op, ())
            for c in expected:
                if c not in ins.required_capabilities and c not in self.required_capabilities:
                    raise ValueError(f"op {ins.op.value} requiere capability '{c}'")
            if ins.op == CognitiveOp.INGEST:
                for k in ("source", "path", "content"):
                    if k not in ins.args:
                        raise ValueError(f"brain.ingest requiere '{k}'")
            if ins.op in (CognitiveOp.QUERY, CognitiveOp.THINK) and "text" not in ins.args:
                raise ValueError(f"{ins.op.value} requiere 'text'")
            if ins.op == CognitiveOp.GRAPH and "entity" not in ins.args:
                raise ValueError("brain.graph requiere 'entity'")
            if ins.op == CognitiveOp.MEMORY and not {"name", "value"}.issubset(ins.args):
                raise ValueError("memory requiere name y value")
            if ins.op == CognitiveOp.PERSIST and "memory" not in ins.args:
                raise ValueError("persist requiere memory")

    def manifest(self) -> Dict[str, Any]:
        return {
            "ir": self.schema,
            "version": self.version,
            "required_capabilities": list(self.required_capabilities),
            "instructions": [i.to_dict() for i in self.instructions],
            "digest": self.digest or self.compute_digest(),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.manifest(), indent=2, ensure_ascii=False)

    @staticmethod
    def from_manifest(d: Dict[str, Any]) -> "CognitiveIR":
        instr = tuple(CognitiveInstruction.from_dict(x) for x in d.get("instructions") or [])
        caps = tuple(d.get("required_capabilities") or [])
        ir = CognitiveIR(
            schema=d.get("ir") or d.get("schema") or IR_SCHEMA,
            version=int(d.get("version") or IR_VERSION),
            instructions=instr,
            required_capabilities=caps,
            digest=str(d.get("digest") or ""),
            metadata=dict(d.get("metadata") or {}),
        )
        ir.validate()
        return ir
