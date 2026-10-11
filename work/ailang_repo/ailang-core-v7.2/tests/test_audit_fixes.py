#!/usr/bin/env python3
"""Tests for audit fixes (AUD-001 to AUD-015)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailang.lang.interpreter import run_source
from ailang.lang.vm import run_vm
from ailang.lang.lexer import tokenize
from ailang.lang.parser import parse
from ailang.fmt import format_ast
from ailang.lang.bytecode_io import save_bytecode, load_and_run
from ailang.runtime.capabilities import CapabilityContext, set_default_context, reset_default_context, CapabilityError


class TestAuditFixes(unittest.TestCase):
    """Tests for the 15 critical audit findings."""

    def test_aud001_string_escapes(self):
        """AUD-001: String escapes like \\n, \\t, \\\\ work correctly."""
        from ailang.lang.lexer import tokenize
        tokens = tokenize('"hello\\nworld"')
        self.assertEqual(tokens[0].value, "hello\nworld")
        tokens = tokenize('"tab\\there"')
        self.assertEqual(tokens[0].value, "tab\there")
        tokens = tokenize('"back\\\\slash"')
        self.assertEqual(tokens[0].value, "back\\slash")
        tokens = tokenize('"quote\\"inside"')
        self.assertEqual(tokens[0].value, 'quote"inside')

    def test_aud002_try_catches_python_exceptions(self):
        """AUD-002: try/catch catches Python exceptions like ZeroDivisionError."""
        result = run_source('try { 1 / 0 } catch e { "caught" }')
        self.assertEqual(result, "caught")

    def test_aud002_try_catches_keyerror(self):
        """AUD-002: try/catch catches KeyError from dict access."""
        result = run_source('let d = {"a": 1}\ntry { d["missing"] } catch e { "caught" }')
        self.assertEqual(result, "caught")

    def test_aud003_capability_error_catchable(self):
        """AUD-003: CapabilityError is catchable by try/catch."""
        try:
            set_default_context(CapabilityContext.restrictive())
            result = run_source('import io\ntry { io.read_text("/etc/hostname") } catch e { "denied" }')
            self.assertEqual(result, "denied")
        finally:
            reset_default_context()

    def test_aud006_generator_flag_preserved_in_bytecode(self):
        """AUD-006: is_generator flag preserved through bytecode round-trip."""
        import tempfile, os, json
        with tempfile.NamedTemporaryFile(suffix=".ailc", delete=False, mode="w") as f:
            path = f.name
        try:
            save_bytecode("fn g() { yield 1 }", path)
            d = json.loads(open(path).read())
            # The top-level CodeObject may not be is_generator,
            # but nested CodeObjects (functions) should have it
            # Check if any nested code object has is_generator=True
            found_gen = False
            def check_code(c):
                nonlocal found_gen
                if isinstance(c, dict) and c.get("is_generator"):
                    found_gen = True
                if isinstance(c, dict) and "__code__" in c:
                    check_code(c["__code__"])
                if isinstance(c, dict) and "constants" in c:
                    for const in c["constants"]:
                        check_code(const)
            check_code(d)
            self.assertTrue(found_gen, "No CodeObject with is_generator=True found")
        finally:
            os.unlink(path)

    def test_aud007_bytecode_has_iter_next_builtins(self):
        """AUD-007: bytecode round-trip has iter/next builtins for for-loops."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".ailc", delete=False, mode="w") as f:
            path = f.name
        try:
            save_bytecode("let s = 0\nfor x in [1,2,3] { s = s + x }\ns", path)
            # This should not raise "nombre no definido: iter"
            result = load_and_run(path)
            self.assertEqual(result, 6)
        finally:
            os.unlink(path)

    def test_aud008_brain_query_raises_ailang_error(self):
        """AUD-008: brain.query raises AILangRuntimeError, not Python RuntimeError."""
        from ailang.lang.errors import AILangRuntimeError
        with self.assertRaises(AILangRuntimeError):
            run_source("import brain\nbrain.query('test')")

    def test_aud012_format_ast_escapes_strings(self):
        """AUD-012: format_ast properly escapes quotes in string literals."""
        src = 'let s = "hello \\"world\\""\ns'
        formatted = format_ast(src)
        # The formatted output should be parseable
        parse(formatted)
        # And should contain escaped quotes
        self.assertIn('\\"', formatted)

    def test_aud002_vm_catches_python_exceptions(self):
        """AUD-002: VM also catches Python exceptions in try/catch."""
        result = run_vm('try { 1 / 0 } catch e { "caught" }')
        self.assertEqual(result, "caught")

    def test_aud002_vm_catches_capability_error(self):
        """AUD-003: VM catches CapabilityError in try/catch."""
        try:
            set_default_context(CapabilityContext.restrictive())
            result = run_vm('import io\ntry { io.read_text("/etc/hostname") } catch e { "denied" }')
            self.assertEqual(result, "denied")
        finally:
            reset_default_context()

    def test_stdlib_has_19_modules(self):
        """Verify all 19 stdlib modules are registered."""
        from ailang.lang.stdlib import builtin_modules
        mods = builtin_modules()
        expected = {"io", "math", "strings", "json", "time", "http", "path",
                    "sys", "random", "listops", "test", "re", "brain",
                    "crypto", "tensor", "graph", "quantum", "selector", "experiment"}
        for mod in expected:
            self.assertIn(mod, mods, f"Missing stdlib module: {mod}")

    def test_capabilities_has_quantum_and_graph(self):
        """Verify quantum.execute and graph.compute are in KNOWN_CAPABILITIES."""
        from ailang.runtime.capabilities import KNOWN_CAPABILITIES
        self.assertIn("quantum.execute", KNOWN_CAPABILITIES)
        self.assertIn("graph.compute", KNOWN_CAPABILITIES)

    def test_effects_has_quantum_and_graph(self):
        """Verify quantum and graph are in EFFECTS."""
        from ailang.semantic.effects import EFFECTS
        self.assertIn("quantum", EFFECTS)
        self.assertIn("graph", EFFECTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
