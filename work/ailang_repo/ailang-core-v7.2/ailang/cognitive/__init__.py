"""ailang.cognitive — runtime cognitivo de AILang (U1).

FASE P1-2 FINAL: las clases cognitivas ahora viven físicamente en el
paquete modular `ailang/cognitive/`, no solo como fachada. Los módulos:
- brain_engine.py: CognitiveBrainEngine, NexusAIEngine
- brain_store.py: CognitiveBrainStore + knowledge graph dataclasses
- retriever.py: HybridRetriever
- dsl/: compilador del DSL cognitivo (migrado desde ailang/compiler/)

Los imports desde el monolito `ailang_core.py` son perezosos vía
__getattr__ para mantener retrocompatibilidad con código que aún
importa `from ailang.cognitive import X` sin cargar el monolito si no se usa.
"""
from __future__ import annotations

# DSL compiler (físico en ailang.cognitive.dsl)
from ailang.cognitive.dsl import (
    compile_cognitive,
    CompilerPipeline,
    tokenize,
    parse_tokens,
    analyze,
    SemanticError,
    ASTModule,
    ASTStmt,
    Token,
)

from typing import Any

# Brain engine + store + retriever (físicos en ailang.cognitive)
from ailang.cognitive.brain_engine import (
    CognitiveBrainEngine,
    CognitiveBrainStore,
    HybridRetriever,
    SchemaPack,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeEntity,
    KnowledgeRelation,
    Evidence,
    ProvenanceRecord,
    RetrievalResult,
    NexusAIEngine,
    BoundedChannel,
    Metrics,
    LatencyBudget,
    HardLatencyBudget,
    RetryPolicy,
    _AVAILABLE as _BRAIN_AVAILABLE,
)

# Bytecode compiler + transport (fachada perezosa al monolito)
def __getattr__(name: str) -> Any:
    """Re-exporta símbolos del monolito de forma perezosa."""
    _COGNITIVE_SYMBOLS = {
        "CognitiveCompiler", "CognitiveRuntime", "CognitiveIR",
        "CognitiveInstruction", "Extension",
        "AILangCompiler", "DecodedProgram", "decode_bytecode",
        "sign_bytecode", "verify_bytecode_signature",
        "SourceInspector", "strip_comments",
        "TcpTransport", "DistributedNode", "PersistentOutbox", "OutboxItem",
        "OutboxDispatcher", "PersistentSeenStore",
        "derive_outbox_key",
        "stable_msg_id", "parse_address",
        "CompilerError", "IntegrityError", "LatencyBudgetExceeded",
        "TransportError", "OutboxFull",
        "BrainEngine",  # alias histórico
    }
    if name in _COGNITIVE_SYMBOLS:
        try:
            import ailang_core as _core
        except ImportError as e:
            raise ImportError(
                f"ailang.cognitive.{name} requiere el módulo ailang_core. "
                f"Instálalo con `pip install -e .` desde la raíz del repo. "
                f"Causa: {e}"
            ) from e
        if hasattr(_core, name):
            return getattr(_core, name)
        raise AttributeError(
            f"ailang.cognitive no encontró '{name}' en ailang_core. "
            f"Puede que el monolito no exponga este símbolo aún."
        )
    raise AttributeError(f"ailang.cognitive no tiene atributo '{name}'")


__all__ = [
    # DSL compiler
    "compile_cognitive", "CompilerPipeline", "tokenize", "parse_tokens",
    "analyze", "SemanticError", "Token", "ASTModule", "ASTStmt",
    # Brain engine + store + retriever (físicos)
    "CognitiveBrainEngine", "CognitiveBrainStore", "HybridRetriever",
    "SchemaPack", "KnowledgeDocument", "KnowledgeChunk",
    "KnowledgeEntity", "KnowledgeRelation", "Evidence",
    "ProvenanceRecord", "RetrievalResult",
    "NexusAIEngine", "BoundedChannel",
    "Metrics", "LatencyBudget", "HardLatencyBudget", "RetryPolicy",
    # Fachada al monolito (lazy)
    "CognitiveCompiler", "CognitiveRuntime", "CognitiveIR",
    "CognitiveInstruction", "Extension",
    "AILangCompiler", "DecodedProgram", "decode_bytecode",
    "sign_bytecode", "verify_bytecode_signature",
    "SourceInspector", "strip_comments",
    "TcpTransport", "DistributedNode", "PersistentOutbox", "OutboxItem",
    "OutboxDispatcher", "PersistentSeenStore", "derive_outbox_key",
    "stable_msg_id", "parse_address",
    "CompilerError", "IntegrityError", "LatencyBudgetExceeded",
    "TransportError", "OutboxFull", "BrainEngine",
]
