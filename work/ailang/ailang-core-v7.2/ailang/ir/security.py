"""Security IR — capabilities, políticas y autorización declarativa."""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


SECURITY_SCHEMA = "ailang-security-ir"
SECURITY_VERSION = 1


class Capability(str, enum.Enum):
    KNOWLEDGE_READ = "knowledge.read"
    KNOWLEDGE_WRITE = "knowledge.write"
    GRAPH_TRAVERSE = "graph.traverse"
    MEMORY_WRITE = "memory.write"
    MEMORY_PERSIST = "memory.persist"
    AGENT_EXECUTE = "agent.execute"
    TASK_DISPATCH = "task.dispatch"
    HARDWARE_ACCEL = "hardware.accel"
    ADMIN = "admin"


@dataclass(frozen=True)
class PolicyRule:
    """Regla: effect allow|deny sobre un conjunto de capabilities, con opcional resource pattern."""
    effect: str  # allow | deny
    capabilities: Tuple[str, ...]
    resource: str = "*"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect": self.effect,
            "capabilities": list(self.capabilities),
            "resource": self.resource,
            "reason": self.reason,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "PolicyRule":
        return PolicyRule(
            str(d.get("effect") or "deny"),
            tuple(d.get("capabilities") or ()),
            str(d.get("resource") or "*"),
            str(d.get("reason") or ""),
        )


@dataclass(frozen=True)
class SecurityIR:
    schema: str = SECURITY_SCHEMA
    version: int = SECURITY_VERSION
    granted: Tuple[str, ...] = ()
    rules: Tuple[PolicyRule, ...] = ()
    require_auth: bool = True
    digest: str = ""

    def canonical(self) -> str:
        body = {
            "schema": self.schema,
            "version": self.version,
            "granted": list(self.granted),
            "rules": [r.to_dict() for r in self.rules],
            "require_auth": self.require_auth,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def compute_digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def with_digest(self) -> "SecurityIR":
        return SecurityIR(
            self.schema, self.version, self.granted, self.rules,
            self.require_auth, self.compute_digest(),
        )

    def authorize(self, required: Sequence[str], resource: str = "*") -> None:
        """Deny-by-default si require_auth; aplica rules deny > allow."""
        need = set(required)
        if not need:
            return
        granted = set(self.granted)
        # explicit deny
        for rule in self.rules:
            if rule.effect != "deny":
                continue
            if rule.resource not in ("*", resource) and resource != rule.resource:
                continue
            hit = need.intersection(rule.capabilities)
            if hit:
                raise PermissionError(
                    f"SecurityIR DENY {sorted(hit)} on {resource}: {rule.reason or 'policy'}"
                )
        missing = need - granted
        # explicit allow can grant extra
        for rule in self.rules:
            if rule.effect != "allow":
                continue
            if rule.resource not in ("*", resource) and resource != rule.resource:
                continue
            missing -= set(rule.capabilities)
        if missing and self.require_auth:
            raise PermissionError(
                f"SecurityIR: capabilities insuficientes: {sorted(missing)}"
            )

    def manifest(self) -> Dict[str, Any]:
        return {
            "ir": self.schema,
            "version": self.version,
            "granted": list(self.granted),
            "rules": [r.to_dict() for r in self.rules],
            "require_auth": self.require_auth,
            "digest": self.digest or self.compute_digest(),
        }

    @staticmethod
    def from_capabilities(caps: Sequence[str], require_auth: bool = True) -> "SecurityIR":
        return SecurityIR(granted=tuple(sorted(set(caps))), require_auth=require_auth).with_digest()
