"""Runtime ejecutable de Agent IR + Task IR (Nivel B)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ailang.ir.agent import AgentIR, AgentStep, AgentStepKind
from ailang.ir.task import TaskIR, TaskNode, TaskStatus, DecisionRecord
import time
import uuid


@dataclass
class AgentContext:
    goal: str
    memory: Dict[str, Any] = field(default_factory=dict)
    log: List[str] = field(default_factory=list)
    brain: Any = None


class AgentRuntime:
    def __init__(self, brain: Any = None, tools: Optional[Dict[str, Callable]] = None):
        self.brain = brain
        self.tools = tools or {}

    def register_tool(self, name: str, fn: Callable) -> None:
        self.tools[name] = fn

    def run(self, agent: AgentIR) -> AgentContext:
        ctx = AgentContext(goal=agent.goal, brain=self.brain)
        ctx.log.append(f"goal: {agent.goal}")
        for step in agent.steps:
            ctx.log.append(f"step:{step.kind.value}:{step.name}")
            if step.kind == AgentStepKind.OBSERVE:
                ctx.memory[step.name] = step.args.get("value", step.args)
            elif step.kind == AgentStepKind.THINK:
                query = str(step.args.get("text") or step.args.get("query") or ctx.goal)
                if self.brain is not None and hasattr(self.brain, "think"):
                    ctx.memory[step.name] = self.brain.think(query)
                else:
                    ctx.memory[step.name] = {"thought": query, "mode": "echo"}
            elif step.kind == AgentStepKind.ACT:
                ctx.memory[step.name] = step.args
            elif step.kind == AgentStepKind.TOOL:
                tool = step.args.get("tool") or step.name
                fn = self.tools.get(str(tool))
                if fn is None:
                    ctx.memory[step.name] = {"error": f"tool not found: {tool}"}
                else:
                    args = {k: v for k, v in step.args.items() if k != "tool"}
                    ctx.memory[step.name] = fn(**args) if args else fn()
            elif step.kind == AgentStepKind.DECIDE:
                ctx.memory[step.name] = {
                    "decision": step.args.get("choice", "continue"),
                    "reason": step.args.get("reason", ""),
                }
        return ctx


class TaskRuntime:
    def run(self, task_ir: TaskIR) -> TaskIR:
        """Ejecuta tareas en orden topológico (pending → done)."""
        tasks = {t.id: t for t in task_ir.tasks}
        done: set = set()
        results = []
        # max iterations safety
        for _ in range(len(tasks) + 1):
            ready = [
                t for t in tasks.values()
                if t.status == TaskStatus.PENDING and all(d in done for d in t.depends_on)
            ]
            if not ready:
                break
            for t in ready:
                # mark done
                new_t = TaskNode(t.id, t.name, t.depends_on, dict(t.payload), TaskStatus.DONE)
                tasks[t.id] = new_t
                done.add(t.id)
                results.append(t.id)
        return TaskIR(
            tasks=tuple(tasks[i] for i in tasks),
            decisions=task_ir.decisions,
        ).with_digest()


def run_agent(goal: str, steps: List[dict], brain: Any = None, tools: Optional[dict] = None) -> dict:
    from ailang.ir.agent import AgentStep, AgentStepKind, AgentIR
    parsed = []
    for s in steps:
        parsed.append(AgentStep(
            AgentStepKind(s.get("kind", "think")),
            s.get("name", "step"),
            dict(s.get("args") or {}),
        ))
    agent = AgentIR(goal=goal, steps=tuple(parsed)).with_digest()
    ctx = AgentRuntime(brain=brain, tools=tools).run(agent)
    return {"goal": ctx.goal, "memory": ctx.memory, "log": ctx.log, "digest": agent.digest}
