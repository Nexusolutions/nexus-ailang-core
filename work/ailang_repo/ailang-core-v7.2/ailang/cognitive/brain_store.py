"""ailang.cognitive.brain_store — CognitiveBrainStore migrado (U1).

Re-export de CognitiveBrainStore y dataclasses del knowledge graph.
Vive físicamente aquí (no en el monolito) — ver brain_engine.py para detalles.
"""
from __future__ import annotations

from ailang.cognitive.brain_engine import (
    CognitiveBrainStore,
    SchemaPack,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeEntity,
    KnowledgeRelation,
    Evidence,
    ProvenanceRecord,
    RetrievalResult,
    _AVAILABLE,
)

__all__ = [
    "CognitiveBrainStore", "SchemaPack",
    "KnowledgeDocument", "KnowledgeChunk", "KnowledgeEntity",
    "KnowledgeRelation", "Evidence", "ProvenanceRecord", "RetrievalResult",
]
