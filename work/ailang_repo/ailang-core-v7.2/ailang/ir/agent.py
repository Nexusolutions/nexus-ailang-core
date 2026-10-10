"""Agent IR — plan de pasos de agente."""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


AGENT_SCHEMA = "ailang-agent-ir"
AGENT_VERSION = 1


class AgentStepKind(str, enum.Enum):
    OBSERVE = "observe"
    THINK = "think"
    ACT = "act"
    TOOL = "tool"
    DECIDE = "decide"


@dataclass(frozen=True)
class AgentStep:
    kind: AgentStepKind
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    requires: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "args": self.args,
            "requires": list(self.requires),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AgentStep":
        return AgentStep(
            AgentStepKind(d["kind"]),
            str(d["name"]),
            dict(d.get("args") or {}),
            tuple(d.get("requires") or ()),
        )


@dataclass(frozen=True)
class AgentIR:
    schema: str = AGENT_SCHEMA
    version: int = AGENT_VERSION
    goal: str = ""
    steps: Tuple[AgentStep, ...] = ()
    digest: str = ""

    def canonical(self) -> str:
        body = {
            "schema": self.schema,
            "version": self.version,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def compute_digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def with_digest(self) -> "AgentIR":
        return AgentIR(self.schema, self.version, self.goal, self.steps, self.compute_digest())

    def manifest(self) -> Dict[str, Any]:
        return {
            "ir": self.schema,
            "version": self.version,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "digest": self.digest or self.compute_digest(),
        }
