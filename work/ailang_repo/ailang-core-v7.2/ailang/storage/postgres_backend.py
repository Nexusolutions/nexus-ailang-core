"""Backend PostgreSQL / pgvector — interfaz lista; requiere psycopg opcional.

Si no hay psycopg, las operaciones lanzan RuntimeError con instrucciones.
El esquema prevé columna vector(N) para embeddings.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from ailang.storage.base import StorageBackend, DocumentRecord, ChunkRecord


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ailang_docs (
    id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    source TEXT NOT NULL,
    path TEXT NOT NULL,
    title TEXT,
    content TEXT,
    doc_type TEXT,
    metadata JSONB DEFAULT '{}',
    UNIQUE(tenant, source, path)
);
CREATE TABLE IF NOT EXISTS ailang_chunks (
    id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    document_id TEXT REFERENCES ailang_docs(id) ON DELETE CASCADE,
    content TEXT,
    ordinal INT,
    embedding vector(384)
);
-- CREATE INDEX ON ailang_chunks USING ivfflat (embedding vector_cosine_ops);
"""


class PostgresStorage(StorageBackend):
    def __init__(self, dsn: str, tenant_id: str = "default", embedding_dim: int = 384):
        self.dsn = dsn
        self.tenant_id = tenant_id
        self.embedding_dim = embedding_dim
        self._conn = None
        try:
            import psycopg  # type: ignore
            self._conn = psycopg.connect(dsn)
            with self._conn.cursor() as cur:
                # vector extension optional
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                except Exception:
                    pass
                cur.execute(_SCHEMA_SQL.replace("vector(384)", f"vector({embedding_dim})"))
            self._conn.commit()
        except ImportError:
            self._conn = None
        except Exception as exc:
            self._conn = None
            self._init_error = exc

    def _require(self):
        if self._conn is None:
            raise RuntimeError(
                "PostgresStorage requiere 'psycopg' y un DSN válido. "
                "pip install psycopg[binary] psycopg-pool; "
                "opcional: pgvector en el servidor."
            )

    def upsert_document(self, doc: DocumentRecord) -> DocumentRecord:
        self._require()
        raise NotImplementedError("Ussa SQLiteStorage en entornos sin Postgres; API reservada.")

    def replace_chunks(self, document_id: str, chunks: Sequence[ChunkRecord]) -> None:
        self._require()
        raise NotImplementedError("API Postgres reservada — esquema listo en _SCHEMA_SQL.")

    def list_documents(self, limit: int = 100) -> List[DocumentRecord]:
        self._require()
        return []

    def list_chunks(self, limit: int = 1000) -> List[ChunkRecord]:
        self._require()
        return []

    def search_lexical(self, query: str, top_k: int = 10) -> List[ChunkRecord]:
        self._require()
        return []

    def search_vector(self, embedding: Sequence[float], top_k: int = 10) -> List[ChunkRecord]:
        self._require()
        # SELECT id FROM ailang_chunks ORDER BY embedding <=> %s::vector LIMIT %s
        return []

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
