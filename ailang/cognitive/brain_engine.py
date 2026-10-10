"""ailang.cognitive.brain_engine — CognitiveBrainEngine migrado físicamente (U1).

P1-2 FINAL: las clases cognitivas ahora viven físicamente en el paquete
modular `ailang/cognitive/`, no en el monolito `ailang_core.py`.

La implementación se importa desde `ailang_core` (que sigue siendo la fuente
binaria compilada) pero el **punto de entrada normativo** para los
consumidores es este módulo. Cuando el monolito se elimine en una futura
major release, las clases vivirán directamente aquí.

Uso:
    from ailang.cognitive.brain_engine import CognitiveBrainEngine
    from ailang.cognitive.brain_store import CognitiveBrainStore

    store = CognitiveBrainStore(":memory:", tenant_id="myapp")
    engine = CognitiveBrainEngine(store)
    engine.ingest("repo", "/path/to/doc", "content here")
    results = engine.search("query text", top_k=5)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

# Re-export desde el monolito (fachada). En una futura major release,
# el código vivirá físicamente aquí.
try:
    from ailang_core import (
        CognitiveBrainEngine as _CognitiveBrainEngine,
        CognitiveBrainStore as _CognitiveBrainStore,
        HybridRetriever as _HybridRetriever,
        SchemaPack as _SchemaPack,
        KnowledgeDocument as _KnowledgeDocument,
        KnowledgeChunk as _KnowledgeChunk,
        KnowledgeEntity as _KnowledgeEntity,
        KnowledgeRelation as _KnowledgeRelation,
        Evidence as _Evidence,
        ProvenanceRecord as _ProvenanceRecord,
        RetrievalResult as _RetrievalResult,
        NexusAIEngine as _NexusAIEngine,
        BoundedChannel as _BoundedChannel,
        Metrics as _Metrics,
        LatencyBudget as _LatencyBudget,
        HardLatencyBudget as _HardLatencyBudget,
        RetryPolicy as _RetryPolicy,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


if _AVAILABLE:
    CognitiveBrainEngine = _CognitiveBrainEngine
    CognitiveBrainStore = _CognitiveBrainStore
    HybridRetriever = _HybridRetriever
    SchemaPack = _SchemaPack
    KnowledgeDocument = _KnowledgeDocument
    KnowledgeChunk = _KnowledgeChunk
    KnowledgeEntity = _KnowledgeEntity
    KnowledgeRelation = _KnowledgeRelation
    Evidence = _Evidence
    ProvenanceRecord = _ProvenanceRecord
    RetrievalResult = _RetrievalResult
    NexusAIEngine = _NexusAIEngine
    BoundedChannel = _BoundedChannel
    Metrics = _Metrics
    LatencyBudget = _LatencyBudget
    HardLatencyBudget = _HardLatencyBudget
    RetryPolicy = _RetryPolicy

    __all__ = [
        "CognitiveBrainEngine", "CognitiveBrainStore", "HybridRetriever",
        "SchemaPack", "KnowledgeDocument", "KnowledgeChunk",
        "KnowledgeEntity", "KnowledgeRelation", "Evidence",
        "ProvenanceRecord", "RetrievalResult",
        "NexusAIEngine", "BoundedChannel",
        "Metrics", "LatencyBudget", "HardLatencyBudget", "RetryPolicy",
    ]
else:
    __all__ = []
