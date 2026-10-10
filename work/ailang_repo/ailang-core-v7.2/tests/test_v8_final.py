#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ailang.lang.interpreter import run_source

class TestV8(unittest.TestCase):
    def test_break_continue(self):
        r = run_source("""
let s = 0
let i = 0
while i < 10 {
  i = i + 1
  if i % 2 == 0 { continue }
  if i > 7 { break }
  s = s + i
}
s
""")
        self.assertEqual(r, 1+3+5+7)

    def test_type_isinstance(self):
        r = run_source("""
let a = type(1)
let b = isinstance("x", "string")
let c = type([1,2])
a + ":" + str(b) + ":" + c
""")
        self.assertEqual(r, "int:True:list")

    def test_poly_shapes(self):
        r = run_source("""
class A { fn v() { return 1 } }
class B extends A { fn v() { return 2 } }
fn f(x) { return x.v() }
f(A()) + f(B())
""")
        self.assertEqual(r, 3)

if __name__ == "__main__":
    unittest.main()
