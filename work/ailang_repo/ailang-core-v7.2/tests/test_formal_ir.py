#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from ailang.ir.cognitive import CognitiveIR, CognitiveOp, CognitiveInstruction
from ailang.ir.security import SecurityIR, PolicyRule
from ailang.ir.unified import UnifiedIR
from ailang.ir.agent import AgentIR, AgentStep, AgentStepKind
from ailang.ir.task import TaskIR, TaskNode, TaskStatus
from ailang.cognitive.dsl import compile_cognitive as compile_source
from ailang.storage.sqlite_backend import SQLiteStorage
from ailang.storage.base import DocumentRecord, ChunkRecord
from ailang.hardware.cpu import CPUBackend
from ailang.hardware.accel import select_backend
from ailang.runtime_bridge import execute_unified


class TestFormalCognitiveIR(unittest.TestCase):
    def test_digest_stable(self):
        ir = CognitiveIR(
            instructions=(
                CognitiveInstruction(CognitiveOp.QUERY, {"text": "x"}, 1, ("knowledge.read",)),
            ),
            required_capabilities=("knowledge.read",),
        ).with_digest()
        ir.validate()
        self.assertEqual(ir.digest, ir.compute_digest())

    def test_pipeline_compile(self):
        src = """purge_after(20ms)
brain.query text="knowledge graph" top_k=3
brain.think text="what is AILang"
"""
        uir = compile_source(src)
        self.assertEqual(uir.cognitive.metadata["budget_ms"], 20)
        self.assertIn("knowledge.read", uir.cognitive.required_capabilities)
        uir.validate()

    def test_zero_footprint_semantic(self):
        src = """purge_after(20ms)
memory volatile name=latent value=1
persist memory=latent
"""
        with self.assertRaises(Exception):
            compile_source(src)

    def test_security_deny(self):
        sec = SecurityIR(
            granted=("knowledge.read",),
            rules=(PolicyRule("deny", ("knowledge.write",), reason="no write"),),
        ).with_digest()
        with self.assertRaises(PermissionError):
            sec.authorize(["knowledge.write"])

    def test_agent_task_ir(self):
        agent = AgentIR(
            goal="answer",
            steps=(AgentStep(AgentStepKind.THINK, "reason"),),
        ).with_digest()
        task = TaskIR(
            tasks=(TaskNode("t1", "ingest"), TaskNode("t2", "query", depends_on=("t1",)),),
        ).with_digest()
        self.assertEqual(len(task.ready_tasks()), 1)
        uir = UnifiedIR(agent=agent, task=task).with_digest()
        self.assertTrue(uir.digest)


class TestStorageHardware(unittest.TestCase):
    def test_sqlite_storage(self):
        st = SQLiteStorage(":memory:")
        doc = st.upsert_document(DocumentRecord("", "repo", "a.md", "A", "hello graph"))
        st.replace_chunks(doc.id, [ChunkRecord("", doc.id, "hello graph")])
        hits = st.search_lexical("graph")
        self.assertTrue(hits)
        st.close()

    def test_cpu_backend(self):
        b = CPUBackend()
        self.assertTrue(b.available())
        scores = b.vector_score([1, 0], [[1, 0], [0, 1]])
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(select_backend("cpu").kind.value, "cpu")


class TestBridge(unittest.TestCase):
    def test_execute_on_monolith(self):
        # P1-1: importar vía ailang.cognitive (fachada modular) en lugar de
        # importar ailang_core directamente. Si ailang.cognitive no puede
        # resolver el engine (porque ailang_core no esté en path), se salta.
        try:
            from ailang.cognitive import CognitiveBrainStore, CognitiveBrainEngine
        except ImportError:
            self.skipTest("ailang.cognitive no disponible (ailang_core no en path)")
        src = """purge_after(20ms)
brain.ingest source="repo" path="Projects/A.md" content="AILang hybrid retrieval"
brain.query text="hybrid" top_k=2
"""
        uir = compile_source(src, capabilities=["knowledge.read", "knowledge.write"])
        store = CognitiveBrainStore(":memory:", tenant_id="formal")
        engine = CognitiveBrainEngine(store)
        self.addCleanup(store.close)
        out = execute_unified(uir, engine)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
