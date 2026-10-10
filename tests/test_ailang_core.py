#!/usr/bin/env python3
"""Tests para ailang_core (monolito cognitive runtime).

P1-5: estos tests estaban embebidos en `ailang_core.py` (líneas 3145-3604,
8 clases TestCase, 44 tests). Se mueven a este archivo para:
1. Reducir el tamaño del módulo ailang_core.py (de 3614 → ~3200 LOC).
2. Eliminar el import de `unittest` en el módulo de biblioteca.
3. Hacer que `pytest tests/` los descubra automáticamente.
4. Eliminar el test embebido que fallaba garantizadamente (P0-4 ya arreglado).

Los tests importan los símbolos desde `ailang_core` (aún la implementación viva).
Cuando P1-2 se complete (mover CognitiveBrainEngine etc. a `ailang/cognitive/`),
estos tests migrarán a importar desde `ailang.cognitive`.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

# Importar todo lo que los tests embebidos usan
import ailang_core as core
from ailang_core import (
    __version__,
    Metrics, LatencyBudget, HardLatencyBudget,
    CognitiveCompiler, CognitiveIR, CognitiveRuntime,
    AILangCompiler, decode_bytecode, Extension,
    CognitiveBrainStore, CognitiveBrainEngine, HybridRetriever,
    PersistentOutbox, TcpTransport, DistributedNode,
    OutboxDispatcher, RetryPolicy,
    stable_msg_id, parse_address,
    CompilerError, IntegrityError, TransportError,
    _slow_sleep_for_test,
)
import numpy as np


class TestAILangCore(unittest.TestCase):
    def test_compiler_requires_purge_after(self):
        c = AILangCompiler("brain.ingest source=\"x\" path=\"/y\" content=\"z\"")
        with self.assertRaises(CompilerError):
            c.compile()

    def test_compiler_roundtrip(self):
        src = "purge_after(50ms)\nbrain.ingest source=\"s\" path=\"/p\" content=\"c\""
        blob = AILangCompiler(src).compile()
        prog = decode_bytecode(blob)
        self.assertEqual(prog.version, core.FORMAT_VERSION)
        self.assertIn("brain.ingest", prog.source)

    def test_decode_rejects_tampered(self):
        src = "purge_after(50ms)\nbrain.ingest source=\"s\" path=\"/p\" content=\"c\""
        blob = bytearray(AILangCompiler(src).compile())
        blob[-1] ^= 1
        with self.assertRaises(IntegrityError):
            decode_bytecode(bytes(blob))

    def test_version_is_semver(self):
        parts = tuple(int(p) for p in __version__.split("-")[0].split("."))
        self.assertGreaterEqual(parts, (1, 0, 0))


class TestAILangOutbox(unittest.TestCase):
    def _make_target(self):
        # Target = (peer_id, host, port, server_hostname)
        return ("peer1", "127.0.0.1", 1234, None)

    def test_outbox_enqueue_and_due(self):
        ob = PersistentOutbox(":memory:")
        try:
            payload = np.array([1.0, 2.0, 3.0], dtype=np.float32)
            ob.enqueue([self._make_target()], payload, msg_id="m1")
            items = ob.due()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].msg_id, "m1")
        finally:
            ob.close()

    def test_outbox_list_pending(self):
        # P0-3: list_pending debe funcionar como alias público
        ob = PersistentOutbox(":memory:")
        try:
            payload = np.array([1.0], dtype=np.float32)
            ob.enqueue([self._make_target()], payload, msg_id="m1")
            ob.enqueue([self._make_target()], payload, msg_id="m2")
            items = ob.list_pending(10)
            self.assertEqual(len(items), 2)
        finally:
            ob.close()

    def test_outbox_purge_dead(self):
        # P0-3: purge_dead debe retornar el conteo
        ob = PersistentOutbox(":memory:")
        try:
            payload = np.array([1.0], dtype=np.float32)
            ob.enqueue([self._make_target()], payload, msg_id="m1")
            items = ob.due()
            ob.mark_dead(items[0].row_id, 5, "test error")
            purged = ob.purge_dead()
            self.assertEqual(purged, 1)
            self.assertEqual(ob.counts()["dead"], 0)
        finally:
            ob.close()


class TestCognitiveCompiler(unittest.TestCase):
    def test_parse_basic(self):
        src = 'purge_after(20ms)\nbrain.ingest source="r" path="/p" content="c"'
        ir = CognitiveCompiler.parse(src)
        self.assertEqual(len(ir.instructions), 1)
        self.assertEqual(ir.instructions[0].op, "brain.ingest")

    def test_zero_footprint_volatile_persist_rejected(self):
        # volatile + persist should fail Zero-Footprint check
        src = 'purge_after(20ms)\nmemory name="x" value="y" persistence="volatile"'
        with self.assertRaises(CompilerError):
            CognitiveCompiler.parse(src)


class TestCognitiveBrain(unittest.TestCase):
    def setUp(self):
        self.store = CognitiveBrainStore(":memory:", tenant_id="test")
        self.engine = CognitiveBrainEngine(self.store)

    def tearDown(self):
        self.store.close()

    def test_ingest_and_query(self):
        self.engine.ingest("repo", "/p", "AILang hybrid retrieval")
        results = self.engine.search("hybrid", top_k=2)
        self.assertGreater(len(results), 0)

    def test_graph_empty(self):
        result = self.engine.graph("nonexistent", depth=1)
        self.assertEqual(len(result), 0)


class TestV70Integrations(unittest.TestCase):
    def test_version_and_prometheus(self):
        # P0-4: ya no hardlock; verifica >= 1.0.0
        parts = tuple(int(p) for p in __version__.split("-")[0].split("."))
        self.assertGreaterEqual(parts, (1, 0, 0))
        m = Metrics()
        m.inc("messages_sent", 3)
        text = m.prometheus()
        self.assertIn("ailang_messages_sent", text)

    def test_stable_msg_id(self):
        a = np.ones(4, dtype=np.float32)
        self.assertEqual(stable_msg_id(a), stable_msg_id(a.copy()))


class TestPersistAndGraphFixes(unittest.TestCase):
    def setUp(self):
        self.store = CognitiveBrainStore(":memory:", tenant_id="test")
        self.engine = CognitiveBrainEngine(self.store)

    def tearDown(self):
        self.store.close()

    def test_persist_durable(self):
        mid = self.store.persist_memory("decision", {"x": 1}, persistence="durable")
        self.assertTrue(mid)

    def test_persist_volatile_rejected(self):
        with self.assertRaises(IntegrityError):
            self.store.persist_memory("latent", {"x": 1}, persistence="volatile")


if __name__ == "__main__":
    unittest.main(verbosity=2)
