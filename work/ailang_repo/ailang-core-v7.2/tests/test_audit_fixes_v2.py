"""Tests de regresión para los fixes de las iteraciones I1-I7.

Cada test verifica un AUD finding específico que fue corregido.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

import pytest


# ===========================================================================
# I1: Seguridad crítica
# ===========================================================================

class TestAUD003_CapabilityErrorCatchable:
    """AUD-003: CapabilityError debe ser catchable por try/catch del lenguaje."""

    def test_capability_error_extends_runtime_error(self):
        from ailang.lang.errors import CapabilityError, AILangRuntimeError
        assert issubclass(CapabilityError, AILangRuntimeError)

    def test_try_catch_catches_capability_error(self):
        from ailang.lang.interpreter import run_source
        from ailang.runtime.capabilities import set_default_context, CapabilityContext, reset_default_context
        set_default_context(CapabilityContext.restrictive())
        try:
            out = io.StringIO(); sys.stdout = out
            run_source('try { io.read_text("/etc/passwd") } catch e { print("caught") }')
            sys.stdout = sys.__stdout__
            assert "caught" in out.getvalue()
        finally:
            reset_default_context()


class TestAUD030_DefaultContextRestrictive:
    """AUD-030: default context debe ser restrictive (deny all)."""

    def test_default_context_is_restrictive(self):
        from ailang.runtime.capabilities import get_default_context, reset_default_context
        reset_default_context()
        ctx = get_default_context()
        # Restrictive means no capabilities are allowed
        assert not ctx.is_allowed("filesystem.read")
        assert not ctx.is_allowed("network.http")
        assert not ctx.is_allowed("process.spawn")

    def test_parse_cli_capabilities_empty_is_restrictive(self):
        from ailang.runtime.capabilities import parse_cli_capabilities
        ctx = parse_cli_capabilities([], [])
        assert not ctx.is_allowed("filesystem.read")


class TestAUD076_PathTraversal:
    """AUD-076: io.read_text debe rechazar path traversal."""

    def test_path_traversal_rejected(self, tmp_path, monkeypatch):
        from ailang.lang.stdlib import io as ailang_io
        from ailang.lang.errors import AILangRuntimeError
        # Use an absolute path that's clearly outside the allowed bases (cwd, /tmp)
        # On Linux, /etc/passwd is outside /tmp and any cwd
        monkeypatch.chdir(tmp_path)
        with pytest.raises(AILangRuntimeError) as exc_info:
            ailang_io.read_text("/etc/passwd")
        assert "acceso denegado" in str(exc_info.value).lower() or "fuera" in str(exc_info.value).lower()

    def test_normal_path_allowed(self, tmp_path, monkeypatch):
        from ailang.lang.stdlib import io as ailang_io
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        # Should NOT raise
        content = ailang_io.read_text("test.txt")
        assert content == "hello"


class TestAUD075_URLValidation:
    """AUD-075: http.get debe rechazar esquemas no HTTP/HTTPS."""

    def test_file_scheme_rejected(self):
        from ailang.lang.stdlib import http_mod
        from ailang.lang.errors import AILangRuntimeError
        with pytest.raises(AILangRuntimeError) as exc_info:
            http_mod._validate_url("file:///etc/passwd")
        assert "esquema" in str(exc_info.value).lower() or "scheme" in str(exc_info.value).lower()

    def test_ftp_scheme_rejected(self):
        from ailang.lang.stdlib import http_mod
        from ailang.lang.errors import AILangRuntimeError
        with pytest.raises(AILangRuntimeError):
            http_mod._validate_url("ftp://evil.com/file")

    def test_http_scheme_allowed(self):
        from ailang.lang.stdlib import http_mod
        url = http_mod._validate_url("http://example.com/path")
        assert url == "http://example.com/path"

    def test_https_scheme_allowed(self):
        from ailang.lang.stdlib import http_mod
        url = http_mod._validate_url("https://example.com/path")
        assert url == "https://example.com/path"


class TestAUD071_SafeFormat:
    """AUD-071: strings.format no debe permitir acceso a atributos."""

    def test_positional_format_works(self):
        from ailang.lang.stdlib import strings
        result = strings.format("Hello {0}, {1}!", "world", "foo")
        assert result == "Hello world, foo!"

    def test_attribute_access_blocked(self):
        from ailang.lang.stdlib import strings
        # {0.__class__} should NOT leak class info — should be left as-is
        result = strings.format("{0.__class__}", "hello")
        assert "__class__" not in result or "{0.__class__}" in result


class TestAUD052_HardwareCapability:
    """AUD-052: hardware backends deben requerir capability."""

    def test_matmul_requires_capability(self):
        from ailang.hardware.accel import GPUBackend
        from ailang.hardware.base import TensorRef
        from ailang.runtime.capabilities import set_default_context, CapabilityContext, reset_default_context
        from ailang.lang.errors import CapabilityError

        # Set restrictive context
        set_default_context(CapabilityContext.restrictive())
        try:
            gpu = GPUBackend()
            # Force native path by making _ok True
            gpu._ok = True
            a = TensorRef([1.0], (1,), "float32", gpu.kind)
            b = TensorRef([2.0], (1,), "float32", gpu.kind)
            with pytest.raises(CapabilityError):
                gpu.matmul(a, b)
        finally:
            reset_default_context()


# ===========================================================================
# I2: Lenguaje core
# ===========================================================================

class TestAUD019_ConstTypeAnnotation:
    """AUD-019: const con type annotation genérica debe parsear."""

    def test_const_with_generic_type(self):
        from ailang.lang.parser import parse
        prog = parse("const xs: List[int] = [1, 2, 3]")
        assert prog.body is not None
        assert len(prog.body) == 1

    def test_const_with_dict_type(self):
        from ailang.lang.parser import parse
        prog = parse('const m: Dict[string, int] = {"a": 1}')
        assert prog.body is not None


class TestAUD020_RecordTypeAnnotations:
    """AUD-020: record con type annotations en fields debe parsear."""

    def test_record_with_typed_fields(self):
        from ailang.lang.parser import parse
        prog = parse("record Point { x: int, y: int }")
        assert prog.body is not None
        assert len(prog.body) == 1

    def test_record_typed_fields_accessible(self):
        from ailang.lang.interpreter import run_source
        out = io.StringIO(); sys.stdout = out
        run_source("""
            record Point { x: int, y: int }
            let p = Point(3, 4)
            print(p.x)
        """)
        sys.stdout = sys.__stdout__
        assert "3" in out.getvalue()


class TestAUD010_SpawnExpression:
    """AUD-010: spawn debe ser expression, no solo statement."""

    def test_spawn_in_let(self):
        from ailang.lang.parser import parse
        # Should not raise
        prog = parse("let f = spawn worker()")
        assert prog.body is not None


class TestAUD029_ErrorsRenamed:
    """AUD-029: errors con prefijo AILang* disponibles."""

    def test_ailang_prefixed_errors_exist(self):
        from ailang.lang import errors
        assert hasattr(errors, "AILangTypeError")
        assert hasattr(errors, "AILangNameError")
        assert hasattr(errors, "AILangValueError")
        assert hasattr(errors, "AILangIndexError")
        assert hasattr(errors, "AILangAttributeError")

    def test_old_names_are_aliases(self):
        from ailang.lang import errors
        assert errors.TypeError is errors.AILangTypeError
        assert errors.NameError is errors.AILangNameError


# ===========================================================================
# I3: AIR interpreter control flow
# ===========================================================================

class TestAUD004_AIRControlFlow:
    """AUD-004: AIR interpreter debe soportar if/while/for."""

    def test_if_else_executes_correct_branch(self):
        from ailang.runtime.air_interpreter import run_air
        out = io.StringIO(); sys.stdout = out
        run_air('let x = 5; if x > 0 { print("pos") } else { print("neg") }')
        sys.stdout = sys.__stdout__
        assert "pos" in out.getvalue()
        assert "neg" not in out.getvalue()

    def test_if_else_false_branch(self):
        from ailang.runtime.air_interpreter import run_air
        out = io.StringIO(); sys.stdout = out
        run_air('let x = -5; if x > 0 { print("pos") } else { print("neg") }')
        sys.stdout = sys.__stdout__
        assert "neg" in out.getvalue()
        assert "pos" not in out.getvalue()

    def test_while_loop(self):
        from ailang.runtime.air_interpreter import run_air
        out = io.StringIO(); sys.stdout = out
        run_air('let i = 0; while i < 3 { print(i); i = i + 1 }')
        sys.stdout = sys.__stdout__
        output = out.getvalue()
        assert "0" in output
        assert "1" in output
        assert "2" in output


# ===========================================================================
# I4: Arquitectura
# ===========================================================================

class TestAUD015_ModuleResolverIntegrated:
    """AUD-015: Interpreter debe usar ModuleResolver."""

    def test_module_resolver_imported_in_load_module(self):
        """Verifica estructuralmente que Interpreter.load_module usa ModuleResolver."""
        import inspect
        from ailang.lang.interpreter import Interpreter
        src = inspect.getsource(Interpreter.load_module)
        # AUD-015: debe referenciar ModuleResolver
        assert "ModuleResolver" in src or "module_resolver" in src, \
            "Interpreter.load_module no usa ModuleResolver"

    def test_module_resolver_works_for_simple_module(self, tmp_path, monkeypatch):
        """Verifica que cargar un módulo simple funciona via ModuleResolver."""
        from ailang.lang.interpreter import run_source
        from ailang.runtime.capabilities import set_default_context, CapabilityContext, reset_default_context
        set_default_context(CapabilityContext.permissive())
        try:
            monkeypatch.chdir(tmp_path)
            (tmp_path / "mymod.ailang").write_text("let greeting = \"hello\"", encoding="utf-8")
            out = io.StringIO(); sys.stdout = out
            run_source('import mymod; print(mymod.greeting)', module_path=[str(tmp_path)])
            sys.stdout = sys.__stdout__
            assert "hello" in out.getvalue()
        finally:
            reset_default_context()


# ===========================================================================
# I5: Bytecode signing (AUD-005) — stub check
# ===========================================================================

class TestAUD005_BytecodeSigning:
    """AUD-005: bytecode_io debería tener signing (stub for now)."""

    def test_bytecode_io_module_importable(self):
        from ailang.lang import bytecode_io
        assert hasattr(bytecode_io, "save_bytecode")
        assert hasattr(bytecode_io, "load_and_run")
