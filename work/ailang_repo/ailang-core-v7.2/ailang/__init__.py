"""AILang 2.0 — lenguaje + runtime cognitivo (Nivel B industrial)."""
from __future__ import annotations

__version__ = "5.0.0"
__author__ = "Enrique Jimenez García"

from ailang.lang.interpreter import Interpreter, run_source, create_repl
from ailang.lang.typecheck import typecheck, TypeChecker
from ailang.lang.vm import compile_source as compile_bytecode, run_vm
from ailang.debugger import Debugger, debug_source
from ailang.agent_runtime import AgentRuntime, TaskRuntime, run_agent

__all__ = [
    "__version__",
    "Interpreter", "run_source", "create_repl",
    "typecheck", "TypeChecker", "compile_bytecode", "run_vm",
    "Debugger", "debug_source", "AgentRuntime", "TaskRuntime", "run_agent",
]
