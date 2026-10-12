"""Abstracción de almacenamiento — SQLite y PostgreSQL/pgvector."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class DocumentRecord:
    id: str
    source: str
    path: str
    title: str
    content: str
    doc_type: str = "note"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    id: str
    document_id: str
    content: str
    ordinal: int = 0
    embedding: Optional[List[float]] = None


class StorageBackend(ABC):
    """Contrato común de persistencia del brain."""

    @abstractmethod
    def upsert_document(self, doc: DocumentRecord) -> DocumentRecord: ...

    @abstractmethod
    def replace_chunks(self, document_id: str, chunks: Sequence[ChunkRecord]) -> None: ...

    @abstractmethod
    def list_documents(self, limit: int = 100) -> List[DocumentRecord]: ...

    @abstractmethod
    def list_chunks(self, limit: int = 1000) -> List[ChunkRecord]: ...

    @abstractmethod
    def search_lexical(self, query: str, top_k: int = 10) -> List[ChunkRecord]: ...

    def search_vector(self, embedding: Sequence[float], top_k: int = 10) -> List[ChunkRecord]:
        """Opcional: backends con pgvector/numpy lo implementan."""
        return []

    @abstractmethod
    def close(self) -> None: ...
