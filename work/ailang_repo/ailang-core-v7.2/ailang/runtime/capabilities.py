"""ailang.runtime.capabilities — Capability enforcement en runtime (P3-9).

FASE 11 del prompt maestro. Las capabilities son permisos granulares que
el runtime verifica antes de ejecutar operaciones con efectos.

Capabilities soportadas:
  filesystem.read     — leer archivos
  filesystem.write    — escribir archivos
  network.http        — hacer requests HTTP
  process.spawn       — crear procesos/hilos
  ai.query            — invocar brain.* / llamadas cognitivas
  hardware.gpu        — usar GPU
  hardware.npu        — usar NPU
  hardware.tpu        — usar TPU
  database.read       — leer de base de datos
  database.write      — escribir a base de datos
  system.env          — acceder a variables de entorno

Política por defecto: DENY. Toda capability no explícitamente concedida
es denegada.

Uso desde CLI:
  ailang run app.ailang --allow filesystem.read --allow ai.query

Uso programático:
  from ailang.runtime.capabilities import CapabilityContext, CapabilityError

  ctx = CapabilityContext(allowed={"filesystem.read", "ai.query"})
  ctx.require("filesystem.read")  # OK
  ctx.require("network.http")     # raises CapabilityError
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from ailang.lang.errors import CapabilityError


# --- Catálogo de capabilities -----------------------------------------------

KNOWN_CAPABILITIES: Set[str] = {
    "filesystem.read", "filesystem.write",
    "network.http",
    "process.spawn",
    "ai.query",
    "hardware.gpu", "hardware.npu", "hardware.tpu",
    "database.read", "database.write",
    "system.env",
    "crypto.use",
    "quantum.execute",  # Q5: FASE 35 — operaciones cuánticas
    "graph.compute",    # Q1: cómputo de grafos intensivo
}

# Mapa effect → capability requerida
EFFECT_TO_CAPABILITY: Dict[str, Set[str]] = {
    "io": set(),  # print/stderr no requiere capability
    "filesystem": {"filesystem.read", "filesystem.write"},
    "network": {"network.http"},
    "ai": {"ai.query"},
    "process": {"process.spawn"},
    "hardware": {"hardware.gpu", "hardware.npu", "hardware.tpu"},
    "unsafe": set(),  # unsafe requiere None explícito
    "pure": set(),
    "crypto": {"crypto.use"},  # T2: FASE 35
    "quantum": {"quantum.execute"},  # Q5: operaciones cuánticas
    "graph": {"graph.compute"},  # Q1: cómputo de grafos
}


# --- CapabilityContext -------------------------------------------------------

@dataclass
class CapabilityContext:
    """Contexto de capabilities activo durante la ejecución de un programa.

    Por defecto DENY todo. Solo las capabilities en `allowed` son concedidas.
    """
    allowed: Set[str] = field(default_factory=set)
    denied: Set[str] = field(default_factory=set)
    audit_log: list = field(default_factory=list)

    @classmethod
    def permissive(cls) -> "CapabilityContext":
        """Contexto que permite todo (modo legacy / dev)."""
        return cls(allowed=set(KNOWN_CAPABILITIES))

    @classmethod
    def restrictive(cls) -> "CapabilityContext":
        """Contexto que deniega todo (modo sandbox)."""
        return cls(allowed=set())

    def allow(self, capability: str) -> None:
        """Concede una capability."""
        self.allowed.add(capability)
        self.denied.discard(capability)

    def deny(self, capability: str) -> None:
        """Deniega explícitamente una capability (override del allow)."""
        self.denied.add(capability)
        self.allowed.discard(capability)

    def is_allowed(self, capability: str) -> bool:
        """Verifica si una capability está concedida."""
        if capability in self.denied:
            return False
        if capability in self.allowed:
            return True
        # Wildcard: si "filesystem.*" está en allowed, todos los filesystem.X lo están
        if "." in capability:
            prefix = capability.split(".")[0] + ".*"
            if prefix in self.allowed:
                return True
        return False

    def require(self, capability: str, *, op_desc: str = "") -> None:
        """Requiere una capability. Lanza CapabilityError si no está concedida.

        Args:
            capability: nombre de la capability (ej.: "filesystem.read")
            op_desc: descripción humana de la operación (para mensaje de error)
        """
        if not self.is_allowed(capability):
            self.audit_log.append({
                "capability": capability,
                "op": op_desc,
                "result": "denied",
            })
            raise CapabilityError(
                message=(
                    f"capability requerida no concedida: '{capability}'"
                    + (f" (operación: {op_desc})" if op_desc else "")
                ),
                code="E061",
                suggestion=(
                    f"añade --allow {capability} al comando 'ailang run' "
                    f"o concede '{capability}' programáticamente vía "
                    f"ctx.allow('{capability}')"
                ),
            )
        self.audit_log.append({
            "capability": capability,
            "op": op_desc,
            "result": "allowed",
        })

    def require_for_effect(self, effect: str, op_desc: str = "") -> None:
        """Requiere todas las capabilities asociadas a un effect."""
        required = EFFECT_TO_CAPABILITY.get(effect, set())
        for cap in required:
            # Para effects con múltiples capabilities (filesystem.read|write),
            # aceptamos si alguna está concedida (OR semantics)
            if not self.is_allowed(cap):
                # Verificar si alguna capability del effect está concedida
                if not any(self.is_allowed(c) for c in required):
                    self.require(cap, op_desc=op_desc)
                    return  # raises aquí
                return
            return


# --- Singleton default context ----------------------------------------------

_default_context: Optional[CapabilityContext] = None


def get_default_context() -> CapabilityContext:
    """Retorna el contexto global.

    AUD-030: Por defecto RESTRICTIVE (deny all). Para obtener modo legacy
    (permissive), usar `set_default_context(CapabilityContext.permissive())`
    o pasar `--allow *` en CLI.
    """
    global _default_context
    if _default_context is None:
        _default_context = CapabilityContext.restrictive()
    return _default_context


def set_default_context(ctx: CapabilityContext) -> None:
    """Establece el contexto global."""
    global _default_context
    _default_context = ctx


def reset_default_context() -> None:
    """Resets al contexto por defecto (restrictive)."""
    global _default_context
    _default_context = None


def require(capability: str, *, op_desc: str = "") -> None:
    """API de conveniencia: usa el contexto global."""
    get_default_context().require(capability, op_desc=op_desc)


def parse_cli_capabilities(allow_list: list[str], deny_list: list[str] = None) -> CapabilityContext:
    """Construye un CapabilityContext desde flags CLI.

    AUD-030: Si no se pasa ninguna flag, retorna contexto RESTRICTIVE (deny all).
    El usuario debe conceder capabilities explícitamente con --allow.

    Args:
        allow_list: lista de capabilities concedidas (ej.: ["filesystem.read", "ai.query"])
        deny_list: lista de capabilities explícitamente denegadas

    Returns:
        CapabilityContext configurado.
    """
    ctx = CapabilityContext.restrictive()
    for cap in allow_list:
        if cap not in KNOWN_CAPABILITIES and not cap.endswith(".*"):
            # Capability desconocida: warning pero permitir (puede ser futura)
            pass
        ctx.allow(cap)
    for cap in (deny_list or []):
        ctx.deny(cap)
    return ctx
