"""Task / Decision IR — grafos de tareas y registros de decisión."""
from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


TASK_SCHEMA = "ailang-task-ir"
TASK_VERSION = 1


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TaskNode:
    id: str
    name: str
    depends_on: Tuple[str, ...] = ()
    payload: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "depends_on": list(self.depends_on),
            "payload": self.payload,
            "status": self.status.value,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TaskNode":
        return TaskNode(
            str(d["id"]), str(d["name"]),
            tuple(d.get("depends_on") or ()),
            dict(d.get("payload") or {}),
            TaskStatus(d.get("status") or "pending"),
        )


@dataclass(frozen=True)
class DecisionRecord:
    id: str
    question: str
    choice: str
    evidence: Tuple[str, ...] = ()
    confidence: float = 0.0
    ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "choice": self.choice,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "ts": self.ts or time.time(),
        }


@dataclass(frozen=True)
class TaskIR:
    schema: str = TASK_SCHEMA
    version: int = TASK_VERSION
    tasks: Tuple[TaskNode, ...] = ()
    decisions: Tuple[DecisionRecord, ...] = ()
    digest: str = ""

    def canonical(self) -> str:
        body = {
            "schema": self.schema,
            "version": self.version,
            "tasks": [t.to_dict() for t in self.tasks],
            "decisions": [d.to_dict() for d in self.decisions],
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def compute_digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def with_digest(self) -> "TaskIR":
        return TaskIR(self.schema, self.version, self.tasks, self.decisions, self.compute_digest())

    def ready_tasks(self) -> List[TaskNode]:
        done = {t.id for t in self.tasks if t.status == TaskStatus.DONE}
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING and all(d in done for d in t.depends_on)
        ]

    def manifest(self) -> Dict[str, Any]:
        return {
            "ir": self.schema,
            "version": self.version,
            "tasks": [t.to_dict() for t in self.tasks],
            "decisions": [d.to_dict() for d in self.decisions],
            "digest": self.digest or self.compute_digest(),
        }
