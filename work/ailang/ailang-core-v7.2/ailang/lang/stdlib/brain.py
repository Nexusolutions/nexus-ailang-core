"""Módulo brain — puente opcional al CognitiveBrainEngine del monolito."""
from __future__ import annotations

_engine = None


def bind_engine(engine) -> None:
    global _engine
    _engine = engine


def _need():
    if _engine is None:
        raise RuntimeError(
            "brain no vinculado: pasa brain_engine=... a Interpreter "
            "o llama brain.bind_engine(engine)"
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
