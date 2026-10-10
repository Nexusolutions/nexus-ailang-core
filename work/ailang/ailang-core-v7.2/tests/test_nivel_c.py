#!/usr/bin/env python3
import sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang import __version__
from ailang.lang.interpreter import run_source
from ailang.lang.vm import run_vm
from ailang.lang.errors import AILangRuntimeError
from ailang.fmt import format_source
from ailang.lint import lint_source
from ailang.lang.bytecode_io import save_bytecode, load_and_run
from ailang.profiler import profile_source


class TestNivelC(unittest.TestCase):
    def test_version(self):
        self.assertTrue(int(__version__.split(".")[0]) >= 3)

    def test_match(self):
        self.assertEqual(
            run_source('let x=2\nmatch x { case 1 { "a" } case 2 { "b" } case _ { "c" } }'),
            "b",
        )
        self.assertEqual(
            run_vm('let x=2\nmatch x { case 1 { "a" } case 2 { "b" } case _ { "c" } }'),
            "b",
        )

    def test_const(self):
        self.assertEqual(run_source("const K = 10\nK"), 10)
        with self.assertRaises(AILangRuntimeError):
            run_source("const K = 1\nK = 2")

    def test_fmt(self):
        self.assertIn("let", format_source("let x=1"))

    def test_lint(self):
        issues = lint_source('let x: int = "a"')
        self.assertTrue(len(issues) >= 1)

    def test_bytecode_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "t.ailc")
            save_bytecode("let x = 6 * 7\nx", path)
            self.assertEqual(load_and_run(path), 42)

    def test_profile(self):
        r = profile_source("let a = 1\nlet b = a + 1\nb")
        self.assertEqual(r["result"], 2)
        self.assertIn("counts", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
