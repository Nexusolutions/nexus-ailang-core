#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.interpreter import run_source, Interpreter
from ailang.lang.errors import AILangRuntimeError, AILangSyntaxError


class TestCoreLang(unittest.TestCase):
    def test_arithmetic_and_let(self):
        r = run_source("let x = 2 + 3 * 4\nx")
        self.assertEqual(r, 14)

    def test_if_else(self):
        r = run_source("""
let x = 10
if x > 5 {
  let y = 1
  y
} else {
  0
}
""")
        self.assertEqual(r, 1)

    def test_while(self):
        r = run_source("""
let i = 0
let s = 0
while i < 5 {
  s = s + i
  i = i + 1
}
s
""")
        self.assertEqual(r, 10)

    def test_for(self):
        r = run_source("""
let s = 0
for n in range(1, 4) {
  s = s + n
}
s
""")
        self.assertEqual(r, 6)

    def test_function_return(self):
        r = run_source("""
fn add(a, b) {
  return a + b
}
add(2, 3)
""")
        self.assertEqual(r, 5)

    def test_list_index(self):
        r = run_source("""
let xs = [10, 20, 30]
xs[1]
""")
        self.assertEqual(r, 20)

    def test_string_and_bool(self):
        r = run_source("""
let ok = true and not false
let msg = "hi"
ok
""")
        self.assertTrue(r)

    def test_purge_after_directive(self):
        interp = Interpreter()
        interp.run("purge_after(25ms)\nlet a = 1")
        self.assertEqual(interp.budget_ms, 25)

    def test_name_error(self):
        with self.assertRaises(AILangRuntimeError):
            run_source("foo")

    def test_syntax_error(self):
        with self.assertRaises(AILangSyntaxError):
            run_source("let = 1")

    def test_nested_fn_closure_like(self):
        r = run_source("""
fn make() {
  let x = 7
  fn inner() {
    return x
  }
  return inner
}
let f = make()
f()
""")
        self.assertEqual(r, 7)

    def test_dict(self):
        r = run_source("""
let d = {"a": 1, "b": 2}
d["b"]
""")
        self.assertEqual(r, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
