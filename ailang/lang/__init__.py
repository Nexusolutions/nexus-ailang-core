"""Núcleo del lenguaje AILang (v8.1)."""
from ailang.lang.interpreter import Interpreter, run_source, create_repl
from ailang.lang.errors import AILangSyntaxError, AILangRuntimeError
from ailang.lang.typecheck import typecheck, TypeChecker
from ailang.lang.vm import compile_source as compile_bytecode, run_vm

__all__ = [
    "Interpreter", "run_source", "create_repl",
    "AILangSyntaxError", "AILangRuntimeError",
    "typecheck", "TypeChecker", "compile_bytecode", "run_vm",
]
