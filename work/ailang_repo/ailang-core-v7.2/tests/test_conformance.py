#!/usr/bin/env python3
"""Suite de conformidad normativa AILang v8.1."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.interpreter import run_source


class TestConformance(unittest.TestCase):
    def test_C01_scopes_let_assign(self):
        self.assertEqual(run_source("let x = 1\nx = x + 2\nx"), 3)

    def test_C02_closure_mutable(self):
        r = run_source("""
fn counter() {
  let n = 0
  return fn() { n = n + 1; return n }
}
let c = counter()
c()
c()
""")
        self.assertEqual(r, 2)

    def test_C03_plus_string_coercion(self):
        self.assertEqual(run_source('1 + "x"'), "1x")
        self.assertEqual(run_source('"x" + 1'), "x1")
        self.assertEqual(run_source("2 + 3"), 5)

    def test_C04_truthy_falsy(self):
        self.assertEqual(run_source("if 0 { 1 } else { 2 }"), 2)
        self.assertEqual(run_source('if "" { 1 } else { 2 }'), 2)
        self.assertEqual(run_source("if [] { 1 } else { 2 }"), 2)
        self.assertEqual(run_source("if null { 1 } else { 2 }"), 2)
        self.assertEqual(run_source("if 1 { 1 } else { 2 }"), 1)

    def test_C05_polymorphism(self):
        r = run_source("""
class A { fn v() { return 1 } }
class B extends A { fn v() { return 2 } }
fn call(o) { return o.v() }
call(A()) + call(B())
""")
        self.assertEqual(r, 3)

    def test_C06_super(self):
        self.assertEqual(run_source("""
class A { fn hi() { return "A" } }
class B extends A { fn hi() { return "B"+super.hi() } }
B().hi()
"""), "BA")

    def test_C07_break_continue(self):
        r = run_source("""
let s = 0
let i = 0
while i < 10 {
  i = i + 1
  if i % 2 == 0 { continue }
  if i > 5 { break }
  s = s + i
}
s
""")
        self.assertEqual(r, 1 + 3 + 5)

    def test_C08_try_throw(self):
        self.assertEqual(run_source('try { throw "e" } catch e { e }'), "e")

    def test_C09_import_math(self):
        self.assertEqual(run_source("import math\nmath.sqrt(9)"), 3.0)

    def test_C10_purge_after(self):
        from ailang.lang.interpreter import Interpreter
        i = Interpreter()
        i.run("purge_after(12ms)\nlet a = 1")
        self.assertEqual(i.budget_ms, 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
