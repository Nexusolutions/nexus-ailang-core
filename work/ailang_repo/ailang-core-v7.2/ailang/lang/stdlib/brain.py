"""Módulo brain — puente al CognitiveBrainEngine.

FASE P1-1: ahora importa desde `ailang.cognitive` (paquete modular) en lugar
de referenciar el monolito directamente. El monolito sigue siendo la
implementación viva, pero `ailang.cognitive` es la fachada canónica.
"""
from __future__ import annotations

_engine = None


def bind_engine(engine) -> None:
    """Vincula el engine cognitivo. Acepta cualquier objeto con la interfaz
    esperada (ingest/search/think/graph). Típicamente un `CognitiveBrainEngine`
    obtenido desde `ailang.cognitive.CognitiveBrainEngine`."""
    global _engine
    _engine = engine


def _need():
    if _engine is None:
        raise RuntimeError(
            "brain no vinculado: pasa brain_engine=... a Interpreter "
            "o llama brain.bind_engine(engine). "
            "Engine canónico: from ailang.cognitive import CognitiveBrainEngine"
        )
    return _engine


def ingest(source, path, content):
    return _need().ingest(str(source), str(path), str(content))


def query(text, top_k=10):
    return _need().search(str(text), top_k=int(top_k))


def think(text, top_k=8):
    return _need().think(str(text), top_k=int(top_k))


def graph(entity, depth=2):
    return _need().graph(str(entity), depth=int(depth))
