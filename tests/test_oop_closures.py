#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.interpreter import run_source


class TestClosures(unittest.TestCase):
    def test_mutable_closure(self):
        r = run_source("""
fn counter() {
  let n = 0
  fn inc() {
    n = n + 1
    return n
  }
  return inc
}
let c = counter()
c()
c()
c()
""")
        self.assertEqual(r, 3)

    def test_lambda_expression(self):
        r = run_source("""
let double = fn(x) { return x * 2 }
double(21)
""")
        self.assertEqual(r, 42)

    def test_closure_captures_param(self):
        r = run_source("""
fn make_adder(k) {
  return fn(x) { return x + k }
}
let add5 = make_adder(5)
add5(10)
""")
        self.assertEqual(r, 15)


class TestClasses(unittest.TestCase):
    def test_init_and_method(self):
        r = run_source("""
class Point {
  fn init(x, y) {
    self.x = x
    self.y = y
  }
  fn sum() {
    return self.x + self.y
  }
}
Point(3, 4).sum()
""")
        self.assertEqual(r, 7)

    def test_inheritance_and_polymorphism(self):
        r = run_source("""
class Animal {
  fn init(name) { self.name = name }
  fn speak() { return "..." }
}
class Dog extends Animal {
  fn speak() { return "woof " + self.name }
}
class Cat extends Animal {
  fn speak() { return "meow " + self.name }
}
fn say(a) { return a.speak() }
say(Dog("Rex")) + "/" + say(Cat("Mimi"))
""")
        self.assertEqual(r, "woof Rex/meow Mimi")

    def test_inherited_method(self):
        r = run_source("""
class A {
  fn init(v) { self.v = v }
  fn get() { return self.v }
}
class B extends A {}
B(99).get()
""")
        self.assertEqual(r, 99)

    def test_super(self):
        r = run_source("""
class A {
  fn hi() { return "A" }
}
class B extends A {
  fn hi() { return "B+" + super.hi() }
}
B().hi()
""")
        self.assertEqual(r, "B+A")

    def test_field_assign(self):
        r = run_source("""
class Box {
  fn init() { self.n = 0 }
  fn bump() { self.n = self.n + 1; return self.n }
}
let b = Box()
b.bump()
b.bump()
""")
        self.assertEqual(r, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
