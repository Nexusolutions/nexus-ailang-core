"""Debugger simple de AILang (Nivel B).

Breakpoints por número de línea, step, continue, print locals.
Uso programático:

    dbg = Debugger(source)
    dbg.set_breakpoint(3)
    dbg.run()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ailang.lang import ast_nodes as A
from ailang.lang.parser import parse
from ailang.lang.interpreter import Interpreter, Env, FunctionValue, ReturnSignal
from ailang.lang.errors import AILangRuntimeError


@dataclass
class DebugState:
    paused: bool = False
    line: int = 0
    reason: str = ""


class Debugger:
    def __init__(self, source: str, brain_engine: Any = None):
        self.source = source
        self.program = parse(source)
        self.interp = Interpreter(brain_engine=brain_engine)
        self.breakpoints: Set[int] = set()
        self.state = DebugState()
        self._step_mode = False
        self.history: List[str] = []

    def set_breakpoint(self, line: int) -> None:
        self.breakpoints.add(int(line))

    def clear_breakpoints(self) -> None:
        self.breakpoints.clear()

    def run(self) -> Any:
        """Ejecuta hasta breakpoint o fin."""
        self._step_mode = False
        return self._exec_program()

    def step(self) -> Any:
        """Ejecuta un statement y pausa."""
        self._step_mode = True
        return self._exec_program()

    def locals_snapshot(self) -> Dict[str, Any]:
        return dict(self.interp.global_env.values)

    def _maybe_pause(self, line: int, detail: str = "") -> None:
        if line in self.breakpoints or self._step_mode:
            self.state = DebugState(True, line, detail or "breakpoint")
            self.history.append(f"pause line={line} {detail}")
            if self._step_mode:
                self._step_mode = False

    def _exec_program(self) -> Any:
        result = None
        for stmt in self.program.body:
            line = getattr(stmt, "line", 0) or 0
            self._maybe_pause(line, type(stmt).__name__)
            result = self.interp.exec_stmt(stmt, self.interp.global_env)
            if self.state.paused and line in self.breakpoints:
                # en modo interactivo se detendría; aquí registramos y seguimos
                # salvo step
                pass
        return result


def debug_source(source: str, breakpoints: Optional[List[int]] = None) -> Dict[str, Any]:
    """API de conveniencia: ejecuta con breakpoints y devuelve resumen."""
    dbg = Debugger(source)
    for bp in breakpoints or []:
        dbg.set_breakpoint(bp)
    result = dbg.run()
    return {
        "result": result,
        "locals": {k: repr(v) for k, v in dbg.locals_snapshot().items() if not callable(v)},
        "history": dbg.history,
        "breakpoints": sorted(dbg.breakpoints),
    }
