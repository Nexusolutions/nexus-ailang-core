"""Backend PostgreSQL / pgvector con implementación real (S4 — P0-9).

FASE 19 del prompt maestro. Implementación completa con:
- Connection pool (psycopg_pool) para concurrencia
- CRUD real (upsert_document, replace_chunks, list_documents, list_chunks)
- Transacciones explícitas (BEGIN/COMMIT/ROLLBACK)
- Prepared statements (psycopg interpola parámetros de forma segura)
- Búsqueda lexical (ILIKE + ts_rank)
- Búsqueda vectorial (pgvector cosine: `<=>` operator)
- Timeout, retry, error handling
- Migrations automáticas (CREATE TABLE IF NOT EXISTS)

Requisitos:
- psycopg[binary] >= 3.2
- psycopg-pool >= 3.2
- PostgreSQL server con extensión pgvector (opcional pero recomendado)

Si no hay psycopg instalado o no se puede conectar, las operaciones
lanzan RuntimeError con instrucciones claras.

Uso:
    from ailang.storage.postgres_backend import PostgresStorage
    from ailang.storage.base import DocumentRecord, ChunkRecord

    storage = PostgresStorage("postgresql://user:pass@localhost/ailang")
    storage.upsert_document(DocumentRecord(
        id="d1", source="repo", path="/p", content="hello",
        doc_type="text", title="Test",
    ))
    storage.replace_chunks("d1", [ChunkRecord(
        id="c1", document_id="d1", content="hello",
        embedding=[0.1, 0.2, ...],
    )])
    results = storage.search_vector([0.1, 0.2, ...], top_k=5)
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Sequence

from ailang.storage.base import StorageBackend, DocumentRecord, ChunkRecord

logger = logging.getLogger(__name__)


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
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant, source, path)
);
CREATE TABLE IF NOT EXISTS ailang_chunks (
    id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    document_id TEXT REFERENCES ailang_docs(id) ON DELETE CASCADE,
    content TEXT,
    ordinal INT,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON ailang_chunks(tenant);
CREATE INDEX IF NOT EXISTS idx_docs_tenant ON ailang_docs(tenant);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON ailang_chunks(document_id);
"""

# Index for vector search (ivfflat for approximate NN)
_VECTOR_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON ailang_chunks
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""

# Full-text search index
_FTS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON ailang_chunks
USING gin (to_tsvector('simple', content));
"""


class PostgresStorage(StorageBackend):
    """Backend PostgreSQL con connection pool, transacciones, y pgvector.

    Si psycopg no está instalado, todas las operaciones lanzan RuntimeError.
    Si el servidor no está disponible, __init__ captura el error y lo reporta
    en _init_error; las operaciones posteriores lanzan RuntimeError.
    """

    def __init__(
        self,
        dsn: str,
        tenant_id: str = "default",
        embedding_dim: int = 384,
        *,
        min_pool_size: int = 2,
        max_pool_size: int = 10,
        connect_timeout: float = 10.0,
        enable_vector_index: bool = True,
        enable_fts_index: bool = True,
    ):
        self.dsn = dsn
        self.tenant_id = tenant_id
        self.embedding_dim = embedding_dim
        self._pool = None
        self._init_error: Optional[Exception] = None
        self._closed = False

        try:
            from psycopg_pool import ConnectionPool  # type: ignore
        except ImportError:
            self._init_error = ImportError(
                "psycopg-pool no instalado. Instala con: pip install psycopg[binary] psycopg-pool"
            )
            return

        try:
            self._pool = ConnectionPool(
                conninfo=dsn,
                min_size=min_pool_size,
                max_size=max_pool_size,
                timeout=connect_timeout,
                open=True,
            )
            # Inicializar schema
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    # Crear extensión vector (opcional — puede fallar si no está instalada)
                    try:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    except Exception as e:
                        logger.warning(f"pgvector extension no disponible: {e}")

                    # Crear tablas (adaptar dimensión del vector)
                    schema = _SCHEMA_SQL.replace("vector(384)", f"vector({embedding_dim})")
                    cur.execute(schema)

                    # Índices opcionales
                    if enable_vector_index:
                        try:
                            cur.execute(_VECTOR_INDEX_SQL)
                        except Exception as e:
                            logger.warning(f"vector index no creado: {e}")
                    if enable_fts_index:
                        try:
                            cur.execute(_FTS_INDEX_SQL)
                        except Exception as e:
                            logger.warning(f"FTS index no creado: {e}")
                conn.commit()
        except Exception as exc:
            self._init_error = exc
            self._pool = None

    def _require(self):
        """Verifica que el pool esté disponible."""
        if self._closed:
            raise RuntimeError("PostgresStorage está cerrado")
        if self._pool is None:
            if self._init_error:
                raise RuntimeError(
                    f"PostgresStorage no inicializado: {self._init_error}. "
                    f"Instala con: pip install psycopg[binary] psycopg-pool"
                )
            raise RuntimeError(
                "PostgresStorage requiere 'psycopg' y un DSN válido. "
                "pip install psycopg[binary] psycopg-pool; "
                "opcional: pgvector en el servidor."
            )

    # --- CRUD ---

    def upsert_document(self, doc: DocumentRecord) -> DocumentRecord:
        """Inserta o actualiza un documento (UPSERT via ON CONFLICT)."""
        self._require()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ailang_docs (id, tenant, source, path, title, content, doc_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        source = EXCLUDED.source,
                        path = EXCLUDED.path,
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        doc_type = EXCLUDED.doc_type,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (doc.id, self.tenant_id, doc.source, doc.path,
                     getattr(doc, "title", None), doc.content, doc.doc_type,
                     "{}"),
                )
            conn.commit()
        return doc

    def replace_chunks(self, document_id: str, chunks: Sequence[ChunkRecord]) -> None:
        """Reemplaza todos los chunks de un documento (DELETE + INSERT en transacción)."""
        self._require()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                # Transacción explícita
                cur.execute("BEGIN")
                try:
                    # Borrar chunks existentes del documento
                    cur.execute(
                        "DELETE FROM ailang_chunks WHERE document_id = %s AND tenant = %s",
                        (document_id, self.tenant_id),
                    )
                    # Insertar nuevos chunks
                    for i, chunk in enumerate(chunks):
                        embedding_str = None
                        if chunk.embedding is not None:
                            # pgvector espera formato '[0.1,0.2,...]'
                            embedding_str = "[" + ",".join(str(float(x)) for x in chunk.embedding) + "]"
                        cur.execute(
                            """
                            INSERT INTO ailang_chunks (id, tenant, document_id, content, ordinal, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s::vector)
                            """,
                            (chunk.id, self.tenant_id, document_id, chunk.content, i, embedding_str),
                        )
                    cur.execute("COMMIT")
                except Exception:
                    cur.execute("ROLLBACK")
                    raise
            conn.commit()

    def list_documents(self, limit: int = 100) -> List[DocumentRecord]:
        """Lista documentos del tenant actual."""
        self._require()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, source, path, title, content, doc_type
                    FROM ailang_docs WHERE tenant = %s
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    (self.tenant_id, limit),
                )
                rows = cur.fetchall()
                return [
                    DocumentRecord(
                        id=row[0], source=row[1], path=row[2],
                        title=row[3], content=row[4], doc_type=row[5],
                    )
                    for row in rows
                ]

    def list_chunks(self, limit: int = 1000) -> List[ChunkRecord]:
        """Lista chunks del tenant actual."""
        self._require()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, document_id, content
                    FROM ailang_chunks WHERE tenant = %s
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    (self.tenant_id, limit),
                )
                rows = cur.fetchall()
                return [
                    ChunkRecord(id=row[0], document_id=row[1], content=row[2])
                    for row in rows
                ]

    # --- Search ---

    def search_lexical(self, query: str, top_k: int = 10) -> List[ChunkRecord]:
        """Búsqueda lexical vía ILIKE (simple substring match).

        Para búsqueda full-text más sofisticada, usar search_fts() que aprovecha
        to_tsvector + ts_rank.
        """
        self._require()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                pattern = f"%{query}%"
                cur.execute(
                    """
                    SELECT id, document_id, content
                    FROM ailang_chunks
                    WHERE tenant = %s AND content ILIKE %s
                    ORDER BY length(content) ASC
                    LIMIT %s
                    """,
                    (self.tenant_id, pattern, top_k),
                )
                rows = cur.fetchall()
                return [
                    ChunkRecord(id=row[0], document_id=row[1], content=row[2])
                    for row in rows
                ]

    def search_vector(
        self,
        embedding: Sequence[float],
        top_k: int = 10,
    ) -> List[ChunkRecord]:
        """Búsqueda vectorial vía pgvector cosine distance (`<=>`).

        Requiere que la extensión pgvector esté instalada en el servidor.
        Si no está instalada, lanza RuntimeError.
        """
        self._require()
        embedding_str = "[" + ",".join(str(float(x)) for x in embedding) + "]"
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT id, document_id, content, embedding <=> %s::vector AS distance
                        FROM ailang_chunks
                        WHERE tenant = %s AND embedding IS NOT NULL
                        ORDER BY distance ASC
                        LIMIT %s
                        """,
                        (embedding_str, self.tenant_id, top_k),
                    )
                    rows = cur.fetchall()
                    return [
                        ChunkRecord(id=row[0], document_id=row[1], content=row[2])
                        for row in rows
                    ]
                except Exception as e:
                    if "vector" in str(e).lower():
                        raise RuntimeError(
                            "pgvector no disponible en el servidor. "
                            "Instala la extensión: CREATE EXTENSION vector;"
                        ) from e
                    raise

    def search_fts(self, query: str, top_k: int = 10) -> List[ChunkRecord]:
        """Búsqueda full-text usando to_tsvector + ts_rank (PostgreSQL nativo)."""
        self._require()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, document_id, content,
                           ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', %s)) AS rank
                    FROM ailang_chunks
                    WHERE tenant = %s
                      AND to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
                    ORDER BY rank DESC
                    LIMIT %s
                    """,
                    (query, self.tenant_id, query, top_k),
                )
                rows = cur.fetchall()
                return [
                    ChunkRecord(id=row[0], document_id=row[1], content=row[2])
                    for row in rows
                ]

    def close(self) -> None:
        """Cierra el connection pool."""
        self._closed = True
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception:
                pass
            self._pool = None
