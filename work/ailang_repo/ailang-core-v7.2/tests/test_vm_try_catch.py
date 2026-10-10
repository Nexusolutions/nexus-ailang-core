#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.vm import run_vm
from ailang.lang.interpreter import run_source
from ailang.lang.errors import AILangRuntimeError


class TestVMTryCatch(unittest.TestCase):
    def test_throw_catch_value(self):
        self.assertEqual(run_vm('try { throw "boom" } catch e { e }'), "boom")

    def test_try_success(self):
        self.assertEqual(run_vm("try { 1 + 2 } catch e { 0 }"), 3)

    def test_catch_undefined_name(self):
        self.assertEqual(run_vm('try { missing } catch e { "ok" }'), "ok")

    def test_throw_in_method(self):
        self.assertEqual(run_vm("""
class X {
  fn boom() { throw "x" }
}
try { X().boom() } catch e { e }
"""), "x")

    def test_uncatched_throw(self):
        with self.assertRaises(AILangRuntimeError):
            run_vm('throw "fail"')

    def test_use_vm_flag(self):
        self.assertEqual(
            run_source('try { throw 7 } catch e { e }', use_vm=True),
            7,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
