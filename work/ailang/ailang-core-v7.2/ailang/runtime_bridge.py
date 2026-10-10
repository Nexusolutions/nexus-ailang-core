"""Ejecuta UnifiedIR / CognitiveIR sobre el brain engine del monolito."""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

from ailang.ir.cognitive import CognitiveIR, CognitiveOp
from ailang.ir.security import SecurityIR
from ailang.ir.unified import UnifiedIR


def execute_cognitive(
    ir: CognitiveIR,
    engine: Any,
    *,
    security: Optional[SecurityIR] = None,
) -> List[Any]:
    if security is not None:
        security.authorize(ir.required_capabilities)
    results: List[Any] = []
    for ins in ir.instructions:
        a = ins.args
        if ins.op == CognitiveOp.INGEST:
            results.append(engine.ingest(
                a["source"], a["path"], a["content"],
                title=a.get("title"), doc_type=a.get("doc_type"),
                metadata=a.get("metadata"),
            ))
        elif ins.op == CognitiveOp.QUERY:
            results.append(engine.search(str(a["text"]), top_k=int(a.get("top_k", 10))))
        elif ins.op == CognitiveOp.THINK:
            results.append(engine.think(str(a["text"]), top_k=int(a.get("top_k", 8))))
        elif ins.op == CognitiveOp.GRAPH:
            results.append(engine.graph(str(a["entity"]), depth=int(a.get("depth", 2))))
        elif ins.op == CognitiveOp.MEMORY:
            results.append(engine.store.persist_memory(
                str(a["name"]), a["value"], persistence=str(a.get("persistence", "durable"))))
        elif ins.op == CognitiveOp.PERSIST:
            results.append(engine.store.persist_memory(
                str(a["memory"]), a.get("value"), persistence=str(a.get("persistence", "durable"))))
    return results


def execute_unified(uir: UnifiedIR, engine: Any) -> List[Any]:
    uir.validate()
    if not uir.cognitive:
        return []
    return execute_cognitive(uir.cognitive, engine, security=uir.security)
