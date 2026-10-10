"""AILang — lenguaje + runtime cognitivo.

La versión vive en `ailang.versions` (FASE 1 del prompt maestro).
"""
from __future__ import annotations

from ailang.versions import (
    __version__,
    LANGUAGE_VERSION,
    RUNTIME_VERSION,
    BYTECODE_VERSION,
    IR_VERSION,
    ABI_VERSION,
    STDLIB_VERSION,
    PACKAGE_FORMAT_VERSION,
)
__author__ = "Enrique Jimenez Garcia"

from ailang.lang.interpreter import Interpreter, run_source, create_repl
from ailang.lang.typecheck import typecheck, TypeChecker
from ailang.lang.vm import compile_source as compile_bytecode, run_vm
from ailang.debugger import Debugger, debug_source
from ailang.agent_runtime import AgentRuntime, TaskRuntime, run_agent

__all__ = [
    "__version__",
    "LANGUAGE_VERSION", "RUNTIME_VERSION", "BYTECODE_VERSION",
    "IR_VERSION", "ABI_VERSION", "STDLIB_VERSION", "PACKAGE_FORMAT_VERSION",
    "Interpreter", "run_source", "create_repl",
    "typecheck", "TypeChecker", "compile_bytecode", "run_vm",
    "Debugger", "debug_source", "AgentRuntime", "TaskRuntime", "run_agent",
]
