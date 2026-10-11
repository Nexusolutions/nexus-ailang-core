"""Módulo brain — puente al CognitiveBrainEngine con capability enforcement (P3-9b).

Cada operación requiere `ai.query` capability:
  ingest → ai.query (+ filesystem.read del content si viene de archivo)
  query  → ai.query
  think  → ai.query
  graph  → ai.query
"""
from __future__ import annotations

from ailang.runtime.capabilities import require

_engine = None


def bind_engine(engine) -> None:
    """Vincula el engine cognitivo. Acepta cualquier objeto con la interfaz
    esperada (ingest/search/think/graph). Típicamente un `CognitiveBrainEngine`
    obtenido desde `ailang.cognitive.CognitiveBrainEngine`."""
    global _engine
    _engine = engine


def _need():
    if _engine is None:
        # AUD-008: Raise AILangRuntimeError instead of Python RuntimeError
        # so that try/catch in AILang programs can catch it properly.
        from ailang.lang.errors import AILangRuntimeError
        raise AILangRuntimeError(
            "brain no vinculado: pasa brain_engine=... a Interpreter "
            "o llama brain.bind_engine(engine). "
            "Engine canónico: from ailang.cognitive import CognitiveBrainEngine"
        )
    return _engine


def ingest(source, path, content):
    """Ingesta documento al brain. Requiere `ai.query` capability."""
    require("ai.query", op_desc=f"brain.ingest({source!r}, {path!r}, ...)")
    return _need().ingest(str(source), str(path), str(content))


def query(text, top_k=10):
    """Busca en el brain. Requiere `ai.query` capability."""
    require("ai.query", op_desc=f"brain.query({text!r}, top_k={top_k})")
    return _need().search(str(text), top_k=int(top_k))


def think(text, top_k=8):
    """Razona sobre el brain. Requiere `ai.query` capability."""
    require("ai.query", op_desc=f"brain.think({text!r}, top_k={top_k})")
    return _need().think(str(text), top_k=int(top_k))


def graph(entity, depth=2):
    """Recorre el knowledge graph. Requiere `ai.query` capability."""
    require("ai.query", op_desc=f"brain.graph({entity!r}, depth={depth})")
    return _need().graph(str(entity), depth=int(depth))
