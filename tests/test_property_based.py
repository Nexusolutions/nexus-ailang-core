#!/usr/bin/env python3
"""Property-based tests para AILang usando hypothesis (P2-10).

FASE 28 del prompt maestro. Verifica invariantes del lexer, parser,
typechecker y runtime con inputs aleatorios.

Properties verificadas:
- Lexer: cualquier string produce tokens o raise (no crash silencioso)
- Parser: tokens válidos siempre producen AST o raise (no hang)
- Idempotencia del formatter AST: format_ast(format_ast(x)) == format_ast(x)
- Conmutatividad aritmética: a + b == b + a (interp == VM)
- Asociatividad aritmética: (a + b) + c == a + (b + c)
- Distributividad: a * (b + c) == a*b + a*c
- Identity: a + 0 == a, a * 1 == a
- Boolean: not not x == x
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hypothesis import given, strategies as st, settings, assume

from ailang.lang.lexer import tokenize
from ailang.lang.parser import parse
from ailang.lang.errors import AILangSyntaxError
from ailang.lang.interpreter import run_source
from ailang.lang.vm import run_vm
from ailang.fmt import format_ast


# --- Strategies -------------------------------------------------------------

# Identifiers válidos en AILang
identifiers = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_",
        min_codepoint=ord("a"),
        max_codepoint=ord("z"),
    ),
    min_size=1,
    max_size=8,
).map(lambda s: s if not s[0].isdigit() else f"_{s}")

# Integer literals
small_ints = st.integers(min_value=-1000, max_value=1000)

# Boolean literals
booleans = st.booleans()

# String literals (sin escape complejo)
simple_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters=" _-",
        min_codepoint=ord("a"),
        max_codepoint=ord("z"),
    ),
    min_size=0,
    max_size=20,
)


# --- Property 1: Lexer nunca crashea con input arbitrario -------------------

@given(st.text(max_size=200))
@settings(max_examples=200)
def test_lexer_never_crashes(text):
    """El lexer siempre retorna tokens o raise, nunca crash silencioso."""
    try:
        tokens = tokenize(text)
        assert isinstance(tokens, list)
    except AILangSyntaxError:
        pass  # OK: error sintáctico reportado correctamente
    except Exception as e:
        # Solo permitimos AILangSyntaxError; otros exceptions son bugs.
        if not isinstance(e, (RecursionError,)):
            raise


# --- Property 2: Parser nunca crashea con tokens válidos -------------------

@given(small_ints)
@settings(max_examples=100)
def test_parser_handles_int_literals(n):
    """El parser maneja literales enteros sin crashear."""
    src = f"let x = {n}\nx"
    try:
        result = run_source(src)
        assert result == n
    except AILangSyntaxError:
        pass


# --- Property 3: Aritmética conmutativa interp == VM -----------------------

@given(small_ints, small_ints)
@settings(max_examples=100)
def test_arithmetic_commutative(a, b):
    """a + b == b + a (interp y VM)."""
    src1 = f"{a} + {b}"
    src2 = f"{b} + {a}"
    r1 = run_source(src1)
    r2 = run_source(src2)
    assert r1 == r2, f"Conmutatividad interp rota: {a}+{b}={r1} vs {b}+{a}={r2}"
    # También verificar paridad interp↔VM
    rv = run_vm(src1)
    assert rv == r1, f"Paridad interp↔VM rota: interp={r1}, vm={rv}"


# --- Property 4: Aritmética asociativa --------------------------------------

@given(small_ints, small_ints, small_ints)
@settings(max_examples=50)
def test_arithmetic_associative(a, b, c):
    """(a + b) + c == a + (b + c)."""
    src1 = f"({a} + {b}) + {c}"
    src2 = f"{a} + ({b} + {c})"
    r1 = run_source(src1)
    r2 = run_source(src2)
    assert r1 == r2, f"Asociatividad rota: ({a}+{b})+{c}={r1} vs {a}+({b}+{c})={r2}"


# --- Property 5: Distributividad --------------------------------------------

@given(small_ints, small_ints, small_ints)
@settings(max_examples=50)
def test_arithmetic_distributive(a, b, c):
    """a * (b + c) == a*b + a*c."""
    src1 = f"{a} * ({b} + {c})"
    src2 = f"({a} * {b}) + ({a} * {c})"
    r1 = run_source(src1)
    r2 = run_source(src2)
    assert r1 == r2, f"Distributividad rota: {a}*({b}+{c})={r1} vs {a}*{b}+{a}*{c}={r2}"


# --- Property 6: Identity elements ------------------------------------------

@given(small_ints)
@settings(max_examples=100)
def test_additive_identity(a):
    """a + 0 == a."""
    src = f"{a} + 0"
    r = run_source(src)
    assert r == a, f"a+0 != a: {a}+0={r}"


@given(small_ints)
@settings(max_examples=100)
def test_multiplicative_identity(a):
    """a * 1 == a."""
    src = f"{a} * 1"
    r = run_source(src)
    assert r == a, f"a*1 != a: {a}*1={r}"


# --- Property 7: Boolean algebra --------------------------------------------

@given(booleans)
@settings(max_examples=50)
def test_double_negation(x):
    """not not x == x."""
    src = f"not not {'true' if x else 'false'}"
    r = run_source(src)
    assert r == x, f"not not x != x: {x} → {r}"


# --- Property 8: Formatter AST idempotente ----------------------------------

@given(small_ints, small_ints)
@settings(max_examples=50)
def test_format_ast_idempotent(a, b):
    """format_ast(format_ast(src)) == format_ast(src)."""
    src = f"let x = {a}\nlet y = {b}\nx + y"
    out1 = format_ast(src)
    out2 = format_ast(out1)
    assert out1 == out2, f"Formatter no idempotente:\n--- first ---\n{out1}\n--- second ---\n{out2}"


# --- Property 9: Paridad interp↔VM para aritmética básica -------------------

@given(small_ints, small_ints, st.sampled_from(["+", "-", "*"]))
@settings(max_examples=100)
def test_interp_vm_arithmetic_parity(a, b, op):
    """Cualquier operación aritmética produce el mismo resultado en interp y VM."""
    src = f"{a} {op} {b}"
    ri = run_source(src)
    rv = run_vm(src)
    assert ri == rv, f"Paridad rota: interp={ri}, vm={rv} (src={src!r})"


# --- Property 10: Variables preservan valores --------------------------------

@given(small_ints)
@settings(max_examples=100)
def test_variable_preserves_value(n):
    """let x = n; x == n (interp y VM)."""
    src = f"let x = {n}\nx"
    ri = run_source(src)
    rv = run_vm(src)
    assert ri == n, f"Variable no preserva valor interp: {n} → {ri}"
    assert rv == n, f"Variable no preserva valor VM: {n} → {rv}"


# --- Property 11: Llamadas a función preservan args --------------------------

@given(small_ints, small_ints)
@settings(max_examples=50)
def test_function_call_returns_arg(a, b):
    """fn id(x) { return x }; id(a) + id(b) == a + b."""
    src = f"""
fn id(x) {{ return x }}
id({a}) + id({b})
"""
    ri = run_source(src)
    rv = run_vm(src)
    expected = a + b
    assert ri == expected, f"fn call rota interp: {a}+{b}={expected}, got {ri}"
    assert rv == expected, f"fn call rota VM: {a}+{b}={expected}, got {rv}"


# --- Property 12: If/else branch selection ----------------------------------

@given(booleans, small_ints, small_ints)
@settings(max_examples=50)
def test_if_else_selects_correct_branch(cond, a, b):
    """if cond { a } else { b } retorna a si cond, else b."""
    src = f"if {'true' if cond else 'false'} {{ {a} }} else {{ {b} }}"
    ri = run_source(src)
    rv = run_vm(src)
    expected = a if cond else b
    assert ri == expected, f"if/else rota interp: cond={cond}, expected={expected}, got={ri}"
    assert rv == expected, f"if/else rota VM: cond={cond}, expected={expected}, got={rv}"


if __name__ == "__main__":
    # Run with pytest to get hypothesis reports
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"]))
