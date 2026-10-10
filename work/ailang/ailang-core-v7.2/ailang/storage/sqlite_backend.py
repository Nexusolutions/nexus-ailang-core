"""Backend SQLite (default, sin dependencias extra)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from typing import List, Optional, Sequence

from ailang.storage.base import StorageBackend, DocumentRecord, ChunkRecord


class SQLiteStorage(StorageBackend):
    def __init__(self, path: str = ":memory:", tenant_id: str = "default"):
        self.path = path
        self.tenant_id = tenant_id
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS docs (
            id TEXT PRIMARY KEY, tenant TEXT, source TEXT, path TEXT,
            title TEXT, content TEXT, doc_type TEXT, metadata TEXT,
            UNIQUE(tenant, source, path)
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY, tenant TEXT, document_id TEXT,
            content TEXT, ordinal INTEGER, embedding BLOB
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
        """)

    def upsert_document(self, doc: DocumentRecord) -> DocumentRecord:
        did = doc.id or uuid.uuid4().hex
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM docs WHERE tenant=? AND source=? AND path=?",
                (self.tenant_id, doc.source, doc.path),
            ).fetchone()
            if row:
                did = row["id"]
                self._db.execute(
                    "UPDATE docs SET title=?, content=?, doc_type=?, metadata=? WHERE id=?",
                    (doc.title, doc.content, doc.doc_type, json.dumps(doc.metadata), did),
                )
            else:
                self._db.execute(
                    "INSERT INTO docs VALUES (?,?,?,?,?,?,?,?)",
                    (did, self.tenant_id, doc.source, doc.path, doc.title,
                     doc.content, doc.doc_type, json.dumps(doc.metadata)),
                )
            self._db.commit()
        return DocumentRecord(did, doc.source, doc.path, doc.title, doc.content, doc.doc_type, doc.metadata)

    def replace_chunks(self, document_id: str, chunks: Sequence[ChunkRecord]) -> None:
        with self._lock:
            self._db.execute(
                "DELETE FROM chunks WHERE tenant=? AND document_id=?",
                (self.tenant_id, document_id),
            )
            for i, c in enumerate(chunks):
                cid = c.id or uuid.uuid4().hex
                emb = None
                if c.embedding is not None:
                    emb = json.dumps(list(c.embedding)).encode()
                self._db.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                    (cid, self.tenant_id, document_id, c.content, i, emb),
                )
            self._db.commit()

    def list_documents(self, limit: int = 100) -> List[DocumentRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM docs WHERE tenant=? LIMIT ?",
                (self.tenant_id, limit),
            ).fetchall()
        return [
            DocumentRecord(r["id"], r["source"], r["path"], r["title"], r["content"],
                           r["doc_type"], json.loads(r["metadata"] or "{}"))
            for r in rows
        ]

    def list_chunks(self, limit: int = 1000) -> List[ChunkRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM chunks WHERE tenant=? LIMIT ?",
                (self.tenant_id, limit),
            ).fetchall()
        out = []
        for r in rows:
            emb = json.loads(r["embedding"]) if r["embedding"] else None
            out.append(ChunkRecord(r["id"], r["document_id"], r["content"], r["ordinal"], emb))
        return out

    def search_lexical(self, query: str, top_k: int = 10) -> List[ChunkRecord]:
        q = query.lower()
        scored = []
        for c in self.list_chunks():
            text = c.content.lower()
            score = sum(1 for t in q.split() if t in text)
            if score:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_k]]

    def search_vector(self, embedding, top_k: int = 10):
        """Búsqueda por similitud coseno (NumPy) sobre chunks con embedding."""
        try:
            import numpy as np
        except ImportError:
            return []
        q = np.asarray(list(embedding), dtype=np.float64)
        qn = np.linalg.norm(q) + 1e-12
        scored = []
        for c in self.list_chunks(limit=10000):
            if not c.embedding:
                continue
            v = np.asarray(c.embedding, dtype=np.float64)
            score = float(np.dot(q, v) / (qn * (np.linalg.norm(v) + 1e-12)))
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[: max(1, int(top_k))]]

    def close(self) -> None:
        with self._lock:
            self._db.close()
