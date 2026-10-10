#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang import __version__
from ailang.lang.interpreter import run_source
from ailang.docgen import docgen_source
from ailang.bench import run_bench


class TestNivelE(unittest.TestCase):
    def test_version(self):
        # P0-1 (FASE 1): __version__ ahora se lee de ailang.versions y permite
        # bumps. Afirmamos >= (5, 0, 0) en lugar de hardlock "5.0.0".
        parts = tuple(int(p) for p in __version__.split("."))
        self.assertGreaterEqual(parts, (5, 0, 0))

    def test_interpolation(self):
        self.assertEqual(run_source('let n = "Ada"\n"hi ${n}"'), "hi Ada")

    def test_record(self):
        self.assertEqual(run_source("record P { x, y }\nP(3, 4).x"), 3)

    def test_generator(self):
        self.assertEqual(run_source("""
fn g() { yield 10\n yield 20 }
let s = 0
for v in g() { s = s + v }
s
"""), 30)

    def test_interface(self):
        self.assertTrue(run_source("""
interface S { fn speak() }
class D { fn speak() { return "x" } }
implements(D(), S)
"""))

    def test_channel(self):
        self.assertEqual(run_source('let c = channel()\nc.send(9)\nc.recv()'), 9)

    def test_docgen(self):
        md = docgen_source("// demo\nfn add(a, b) { return a + b }\n")
        self.assertIn("add", md)

    def test_bench(self):
        # P2-14: run_bench ahora retorna {metadata, results, summary}
        r = run_bench(rounds=1)
        self.assertIn("results", r)
        self.assertIn("summary", r)
        # Al menos un caso "arith" debe existir
        arith_cases = [k for k in r["results"] if k.startswith("arith")]
        self.assertTrue(arith_cases, f"no arith case in {list(r['results'].keys())}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
