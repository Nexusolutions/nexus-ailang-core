#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.vm import run_vm
from ailang.lang.interpreter import run_source


class TestVMClassImport(unittest.TestCase):
    def test_class_init_method(self):
        self.assertEqual(run_vm("""
class Point {
  fn init(x, y) { self.x = x; self.y = y }
  fn sum() { return self.x + self.y }
}
Point(3, 4).sum()
"""), 7)

    def test_inheritance_poly(self):
        self.assertEqual(run_vm("""
class Animal {
  fn init(name) { self.name = name }
  fn speak() { return "..." }
}
class Dog extends Animal {
  fn speak() { return "woof " + self.name }
}
Dog("Rex").speak()
"""), "woof Rex")

    def test_super(self):
        self.assertEqual(run_vm("""
class A { fn hi() { return "A" } }
class B extends A { fn hi() { return "B" + super.hi() } }
B().hi()
"""), "BA")

    def test_import_builtin(self):
        self.assertEqual(run_vm("import math\nmath.floor(3.9)"), 3)

    def test_import_as(self):
        self.assertEqual(run_vm("import math as m\nm.pow(2, 3)"), 8.0)

    def test_user_module(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "util.ailang").write_text("fn double(x) { return x * 2 }\n")
            self.assertEqual(
                run_vm("import util\nutil.double(21)", module_path=[td]),
                42,
            )

    def test_use_vm_flag_class(self):
        self.assertEqual(run_source("""
class C { fn v() { return 9 } }
C().v()
""", use_vm=True), 9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
