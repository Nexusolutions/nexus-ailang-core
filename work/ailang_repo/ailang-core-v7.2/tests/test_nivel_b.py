#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang import __version__
from ailang.lang.typecheck import typecheck
from ailang.debugger import debug_source
from ailang.pkg import init_package, install_package, list_packages, run_package
from ailang.agent_runtime import run_agent, TaskRuntime
from ailang.ir.task import TaskIR, TaskNode, TaskStatus
from ailang.storage.sqlite_backend import SQLiteStorage
from ailang.storage.base import DocumentRecord, ChunkRecord


class TestNivelB(unittest.TestCase):
    def test_version(self):
        self.assertTrue(int(__version__.split(".")[0]) >= 2)

    def test_narrowing_isinstance(self):
        # no debe explotar; isinstance narrows for inner use
        d = typecheck('''
let x = 1
if isinstance(x, "int") {
  let y: int = x
}
''', strict=True)
        errors = [x for x in d if x.level == "error"]
        self.assertEqual(errors, [])

    def test_debugger(self):
        out = debug_source("let a = 1\nlet b = a + 2\nb", breakpoints=[2])
        self.assertEqual(out["result"], 3)
        self.assertTrue(any("pause" in h for h in out["history"]))

    def test_pkg(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_package("demo_pkg", dest=str(Path(td) / "demo_pkg"))
            info = install_package(str(root))
            self.assertEqual(info["version"], "0.1.0")
            self.assertIn("demo_pkg", list_packages())
            # run prints hello — no exception
            run_package("demo_pkg")

    def test_agent(self):
        out = run_agent("test goal", [
            {"kind": "observe", "name": "o", "args": {"value": 1}},
            {"kind": "think", "name": "t", "args": {"text": "hi"}},
            {"kind": "decide", "name": "d", "args": {"choice": "ok"}},
        ])
        self.assertEqual(out["goal"], "test goal")
        self.assertIn("t", out["memory"])

    def test_task_runtime(self):
        ir = TaskIR(tasks=(
            TaskNode("a", "first"),
            TaskNode("b", "second", depends_on=("a",)),
        )).with_digest()
        out = TaskRuntime().run(ir)
        self.assertTrue(all(t.status == TaskStatus.DONE for t in out.tasks))

    def test_vector_search(self):
        st = SQLiteStorage(":memory:")
        doc = st.upsert_document(DocumentRecord("", "s", "p", "t", "hello"))
        st.replace_chunks(doc.id, [
            ChunkRecord("", doc.id, "hello", 0, [1.0, 0.0, 0.0]),
            ChunkRecord("", doc.id, "world", 1, [0.0, 1.0, 0.0]),
        ])
        hits = st.search_vector([1.0, 0.0, 0.0], top_k=1)
        self.assertTrue(hits)
        self.assertEqual(hits[0].content, "hello")
        st.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
