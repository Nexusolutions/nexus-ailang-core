#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.typecheck import typecheck
from ailang.lang.vm import run_vm
from ailang.lang.interpreter import run_source
from ailang.lang.errors import AILangRuntimeError


class TestTypecheck(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(typecheck("let x: int = 1"), [])

    def test_strict_mismatch(self):
        d = typecheck('let x: int = "a"', strict=True)
        self.assertTrue(any(x.level == "error" for x in d))

    def test_run_source_strict(self):
        with self.assertRaises(AILangRuntimeError):
            run_source('let x: int = "a"', typecheck_strict=True)


class TestVM(unittest.TestCase):
    def test_arith(self):
        self.assertEqual(run_vm("let x = 2 + 3 * 4\nx"), 14)

    def test_fn(self):
        self.assertEqual(run_vm("fn add(a,b) { return a+b }\nadd(2,3)"), 5)

    def test_while(self):
        self.assertEqual(run_vm("""
let s = 0
let i = 0
while i < 4 {
  i = i + 1
  s = s + i
}
s
"""), 10)

    def test_use_vm_flag(self):
        self.assertEqual(run_source("1+2*3", use_vm=True), 7)


class TestNewStdlib(unittest.TestCase):
    def test_strings(self):
        self.assertEqual(run_source('import strings\nstrings.upper("ab")'), "AB")
        self.assertEqual(run_source('import strings\nstrings.contains("hello","ell")'), True)

    def test_time(self):
        r = run_source("import time\ntime.now()")
        self.assertTrue(isinstance(r, float) and r > 0)

    def test_sys(self):
        self.assertEqual(run_source("import sys\nsys.version()"), "ailang-8.1")

    def test_test_mod(self):
        r = run_source("""
import test
test.reset()
test.assert_eq(1+1, 2)
test.summary()
""")
        self.assertEqual(r["passed"], 1)
        self.assertEqual(r["failed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
