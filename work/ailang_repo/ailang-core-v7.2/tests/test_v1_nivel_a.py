#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang import __version__
from ailang.lang.interpreter import run_source
from ailang.lang.vm import run_vm
from ailang.lang.errors import AILangRuntimeError


class TestVersion(unittest.TestCase):
    def test_v1(self):
        # 1.0+ (Nivel B puede ser 2.0.0)
        self.assertTrue(__version__.split(".")[0] >= "1")


class TestStackTrace(unittest.TestCase):
    def test_frames_on_error(self):
        with self.assertRaises(AILangRuntimeError) as cm:
            run_source("""
fn inner() { missing }
fn outer() { inner() }
outer()
""")
        msg = str(cm.exception)
        self.assertIn("Traceback", msg)
        self.assertIn("inner", msg)


class TestUnifiedBrain(unittest.TestCase):
    def test_brain_module_global(self):
        # sin import: brain está precargado (fallará sin engine al llamar, pero el nombre existe)
        r = run_source("type(brain)")
        self.assertEqual(r, "module")


class TestStdlibNivelA(unittest.TestCase):
    def test_path(self):
        self.assertTrue(run_source("import path\npath.exists(path.cwd())"))

    def test_random(self):
        r = run_source("import random\nrandom.seed(1)\nrandom.randint(1, 3)")
        self.assertIn(r, (1, 2, 3))

    def test_re(self):
        r = run_source('import re\nre.findall("[0-9]+", "a12b34")')
        self.assertEqual(r, ["12", "34"])


class TestVMParityCore(unittest.TestCase):
    CASES = [
        "let x = 2 + 3 * 4\nx",
        "fn f(a,b){ return a+b }\nf(2,3)",
        "fn fact(n){ if n<=1 { return 1 }\n return n*fact(n-1) }\nfact(5)",
        "class P{ fn init(x){ self.x=x } fn g(){ return self.x } }\nP(9).g()",
        "class A{ fn v(){ return 1 } }\nclass B extends A{ fn v(){ return 2 } }\nB().v()",
        'try { throw "e" } catch e { e }',
        "import math\nmath.sqrt(16)",
        "let s=0\nfor n in [1,2,3] { s = s + n }\ns",
    ]

    def test_parity(self):
        for src in self.CASES:
            with self.subTest(src=src[:40]):
                a = run_source(src, use_vm=False)
                b = run_source(src, use_vm=True)
                self.assertEqual(a, b, f"AST={a!r} VM={b!r} for {src!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
