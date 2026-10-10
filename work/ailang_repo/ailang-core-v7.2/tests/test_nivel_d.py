#!/usr/bin/env python3
import sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang import __version__
from ailang.lang.interpreter import run_source
from ailang.coverage_tool import coverage_source
from ailang.project import init_project, run_project, load_project
from ailang.lang.stdlib import http_mod


class TestNivelD(unittest.TestCase):
    def test_version(self):
        self.assertTrue(int(__version__.split(".")[0]) >= 4)

    def test_enum(self):
        r = run_source("""
enum Color { Red, Green }
Color.Green
""")
        self.assertEqual(str(r), "Color.Green")

    def test_async_await(self):
        self.assertEqual(run_source("async fn f() { return 7 }\nawait f()"), 7)

    def test_http_module_shape(self):
        # offline-safe: just call with invalid host returns error structure
        r = http_mod.get("http://127.0.0.1:1/", timeout=0.2)
        self.assertIn("status", r)

    def test_coverage(self):
        c = coverage_source("let a = 1\nlet b = 2\na + b")
        self.assertGreater(c["coverage"], 0)
        self.assertEqual(c["result"], 3)

    def test_project(self):
        with tempfile.TemporaryDirectory() as td:
            init_project(td, "demo")
            cfg = load_project(td)
            self.assertEqual(cfg["name"], "demo")
            run_project(td)


if __name__ == "__main__":
    unittest.main(verbosity=2)
