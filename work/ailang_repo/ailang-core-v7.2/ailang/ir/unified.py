"""Unified IR — contenedor versionado de Cognitive + Security + Agent + Task."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ailang.ir.cognitive import CognitiveIR
from ailang.ir.security import SecurityIR
from ailang.ir.agent import AgentIR
from ailang.ir.task import TaskIR


UNIFIED_SCHEMA = "ailang-unified-ir"
UNIFIED_VERSION = 1


@dataclass(frozen=True)
class UnifiedIR:
    schema: str = UNIFIED_SCHEMA
    version: int = UNIFIED_VERSION
    cognitive: Optional[CognitiveIR] = None
    security: Optional[SecurityIR] = None
    agent: Optional[AgentIR] = None
    task: Optional[TaskIR] = None
    digest: str = ""

    def canonical(self) -> str:
        body = {
            "schema": self.schema,
            "version": self.version,
            "cognitive": self.cognitive.manifest() if self.cognitive else None,
            "security": self.security.manifest() if self.security else None,
            "agent": self.agent.manifest() if self.agent else None,
            "task": self.task.manifest() if self.task else None,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def compute_digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def with_digest(self) -> "UnifiedIR":
        return UnifiedIR(
            self.schema, self.version,
            self.cognitive, self.security, self.agent, self.task,
            self.compute_digest(),
        )

    def validate(self) -> None:
        if self.cognitive:
            self.cognitive.validate()
            if self.security:
                self.security.authorize(self.cognitive.required_capabilities)

    def manifest(self) -> Dict[str, Any]:
        return {
            "ir": self.schema,
            "version": self.version,
            "cognitive": self.cognitive.manifest() if self.cognitive else None,
            "security": self.security.manifest() if self.security else None,
            "agent": self.agent.manifest() if self.agent else None,
            "task": self.task.manifest() if self.task else None,
            "digest": self.digest or self.compute_digest(),
        }

    def to_json(self) -> str:
        return json.dumps(self.manifest(), indent=2, ensure_ascii=False)
