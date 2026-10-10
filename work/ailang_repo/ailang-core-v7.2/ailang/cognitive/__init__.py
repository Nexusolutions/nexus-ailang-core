"""ailang.cognitive — runtime cognitivo de AILang.

Este paquete es la **fuente normativa** dentro del paquete modular `ailang/`
para todo lo relacionado con el runtime cognitivo: brain engine, brain store,
retriever híbrido, latent engine, compilador del DSL cognitivo, y los IRs cognitivos.

FASE P1-1/P1-2/P1-3/P1-4 del roadmap:
- `ailang.cognitive.dsl` se migró físicamente desde `ailang/compiler/` (frontend
  duplicado eliminado). El símbolo canónico es `compile_cognitive` (no `compile_source`,
  que colisionaba con `ailang.lang.vm.compile_source`).
- `ailang.cognitive.{CognitiveBrainEngine, CognitiveBrainStore, ...}` re-exporta
  desde el monolito `ailang_core.py` vía __getattr__ perezoso. Esta es una fachada
  temporal: cuando P1-2 se complete, las clases vivirán físicamente aquí.
"""
from __future__ import annotations

# El DSL compiler (compilador cognitivo) SÍ vive físicamente aquí (no en el monolito).
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

# Re-exportación perezosa (lazy) para evitar importar ailang_core si el
# consumidor solo necesita el sub-paquete IR o el DSL compiler.


def __getattr__(name: str) -> Any:
    """Re-exporta símbolos cognitivos desde ailang_core de forma perezosa.

    Cualquier import `from ailang.cognitive import CognitiveBrainEngine`
    se resuelve aquí, cargando ailang_core solo cuando se necesita.
    """
    _COGNITIVE_SYMBOLS = {
        # Compilador cognitivo DSL + IR (monolito-side, fachada)
        "CognitiveCompiler", "CognitiveRuntime", "CognitiveIR",
        "CognitiveInstruction", "Extension",
        # Bytecode compiler (firmado v7)
        "AILangCompiler", "DecodedProgram", "decode_bytecode",
        "sign_bytecode", "verify_bytecode_signature",
        "SourceInspector", "strip_comments",
        # Latent engine
        "NexusAIEngine", "BoundedChannel",
        # Brain engine + store + retriever
        "CognitiveBrainEngine", "CognitiveBrainStore", "HybridRetriever",
        "BrainEngine",  # alias histórico
        # Schema + knowledge graph dataclasses
        "SchemaType", "SchemaPack", "KnowledgeDocument", "KnowledgeChunk",
        "KnowledgeEntity", "KnowledgeRelation", "Evidence",
        "ProvenanceRecord", "RetrievalResult",
        # Transport + outbox
        "TcpTransport", "DistributedNode", "PersistentOutbox", "OutboxItem",
        "OutboxDispatcher", "RetryPolicy", "PersistentSeenStore",
        "derive_outbox_key",
        # Métricas + budget
        "Metrics", "LatencyBudget", "HardLatencyBudget",
        # Utilidades
        "stable_msg_id", "parse_address",
        # Errores
        "CompilerError", "IntegrityError", "LatencyBudgetExceeded",
        "TransportError", "OutboxFull",
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
    # DSL compiler (físico en ailang.cognitive.dsl)
    "compile_cognitive", "CompilerPipeline", "tokenize", "parse_tokens",
    "analyze", "SemanticError", "Token", "ASTModule", "ASTStmt",
    # Fachada al monolito (lazy)
    "CognitiveCompiler", "CognitiveRuntime", "CognitiveIR",
    "CognitiveInstruction", "Extension",
    "AILangCompiler", "DecodedProgram", "decode_bytecode",
    "sign_bytecode", "verify_bytecode_signature",
    "SourceInspector", "strip_comments",
    "NexusAIEngine", "BoundedChannel",
    "CognitiveBrainEngine", "CognitiveBrainStore", "HybridRetriever",
    "BrainEngine",
    "SchemaType", "SchemaPack", "KnowledgeDocument", "KnowledgeChunk",
    "KnowledgeEntity", "KnowledgeRelation", "Evidence",
    "ProvenanceRecord", "RetrievalResult",
    "TcpTransport", "DistributedNode", "PersistentOutbox", "OutboxItem",
    "OutboxDispatcher", "RetryPolicy", "PersistentSeenStore",
    "derive_outbox_key",
    "Metrics", "LatencyBudget", "HardLatencyBudget",
    "stable_msg_id", "parse_address",
    "CompilerError", "IntegrityError", "LatencyBudgetExceeded",
    "TransportError", "OutboxFull",
]
