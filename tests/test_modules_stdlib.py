#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.interpreter import run_source, Interpreter
from ailang.lang.errors import AILangRuntimeError


class TestTryCatch(unittest.TestCase):
    def test_throw_catch(self):
        r = run_source("""
try {
  throw "boom"
} catch e {
  e
}
""")
        self.assertEqual(r, "boom")

    def test_no_throw(self):
        r = run_source("""
try {
  let x = 1 + 1
  x
} catch e {
  0
}
""")
        self.assertEqual(r, 2)

    def test_catch_runtime(self):
        r = run_source("""
try {
  missing_name
} catch e {
  "caught"
}
""")
        self.assertEqual(r, "caught")


class TestStdlib(unittest.TestCase):
    def test_math(self):
        r = run_source("""
import math
math.sqrt(9) + math.floor(3.7)
""")
        self.assertEqual(r, 6.0)

    def test_listops_map_filter(self):
        r = run_source("""
import listops
fn double(x) { return x * 2 }
fn odd(x) { return x % 2 == 1 }
let xs = [1, 2, 3, 4]
listops.sum(listops.map(double, listops.filter(odd, xs)))
""")
        self.assertEqual(r, 8)

    def test_json(self):
        r = run_source("""
import json
let s = json.dumps({"a": 1, "b": [2, 3]})
let o = json.loads(s)
o["b"][0]
""")
        self.assertEqual(r, 2)

    def test_io(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "t.txt")
            r = run_source(f'''
import io
io.write_text("{path}", "hello")
io.read_text("{path}")
''')
            self.assertEqual(r, "hello")

    def test_import_as(self):
        r = run_source("""
import math as m
m.pow(2, 3)
""")
        self.assertEqual(r, 8.0)


class TestUserModule(unittest.TestCase):
    def test_load_ailang_file(self):
        with tempfile.TemporaryDirectory() as td:
            mod = Path(td) / "mylib.ailang"
            mod.write_text("""
fn greet(name) {
  return "hi " + name
}
let VERSION = 1
""")
            r = run_source("""
import mylib
mylib.greet("Ada")
""", module_path=[td])
            self.assertEqual(r, "hi Ada")


if __name__ == "__main__":
    unittest.main(verbosity=2)
