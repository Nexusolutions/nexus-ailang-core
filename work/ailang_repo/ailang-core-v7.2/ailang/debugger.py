"""Debugger de AILang con pausa real en breakpoints.

Implementa pause/continue/step usando un `threading.Event` como barrera:
cuando se alcanza un breakpoint, el hilo que ejecuta el programa bloquea en
`_pause_event.wait()`. Continúa cuando el frontend invoca `continue_run()`
(que hace `set()`) o `step()` (que hace `set()` una vez y re-arma el modo
step).

Uso programático:

    dbg = Debugger(source)
    dbg.set_breakpoint(3)
    # Hilo aparte:
    t = threading.Thread(target=dbg.run); t.start()
    # En hilo principal:
    dbg.wait_paused()           # bloquea hasta que se alcance un bp
    snap = dbg.locals_snapshot()
    dbg.continue_run()         # libera
    t.join()
"""
from __future__ import annotations

import threading
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
        # --- Pause real (P0-10) ---
        self._pause_event = threading.Event()
        self._pause_event.set()  # inicialmente libre
        self._pause_ack = threading.Event()
        self._stop_requested = False
        # --- U2: Step granularity ---
        # _step_over_depth: si no es None, step-over esperará a volver a esta depth
        self._step_over_depth: Optional[int] = None
        # _call_stack_depth: profundidad actual de llamadas a función
        self._call_stack_depth: int = 0
        # Track de call stack para step granularity
        self._call_stack: List[str] = []

    def set_breakpoint(self, line: int) -> None:
        self.breakpoints.add(int(line))

    def clear_breakpoints(self) -> None:
        self.breakpoints.clear()

    def run(self) -> Any:
        """Ejecuta hasta breakpoint o fin."""
        self._step_mode = False
        self._step_over_depth = None
        return self._exec_program()

    def step(self) -> Any:
        """Step-into: ejecuta un statement y pausa (incluso dentro de calls)."""
        self._step_mode = True
        self._step_over_depth = None
        self._pause_event.set()
        return self._exec_program()

    def step_over(self) -> Any:
        """Step-over: ejecuta hasta el próximo statement al mismo nivel de call stack.

        Si el siguiente statement es una llamada a función, la ejecuta completa
        sin pausar dentro de ella.
        """
        self._step_mode = False
        self._step_over_depth = self._call_stack_depth
        self._pause_ack.clear()
        self._pause_event.set()
        return self._exec_program()

    def step_out(self) -> Any:
        """Step-out: ejecuta hasta salir de la función actual."""
        self._step_mode = False
        # Pausar cuando volvamos al nivel de call stack padre
        self._step_over_depth = self._call_stack_depth - 1
        self._pause_ack.clear()
        self._pause_event.set()
        return self._exec_program()

    def continue_run(self) -> None:
        """Libera el hilo pausado; continúa hasta el próximo breakpoint."""
        self._step_mode = False
        self._pause_ack.clear()
        self._pause_event.set()

    def wait_paused(self, timeout: Optional[float] = None) -> bool:
        """Bloquea hasta que el debugger haya pausado en un breakpoint.

        Retorna True si pausó, False si timeout expiró.
        Útil para tests sincrónicos y para frontends DAP.
        """
        return self._pause_ack.wait(timeout=timeout)

    def request_stop(self) -> None:
        """Solicita detener la ejecución (cooperative)."""
        self._stop_requested = True
        self._pause_event.set()  # liberar si estaba bloqueado

    def locals_snapshot(self) -> Dict[str, Any]:
        # AUD: Return both locals and globals, not just globals.
        # The interpreter's global_env is the main scope, but function
        # locals are in separate Env frames. For the DAP, we return
        # the global_env values (which includes top-level variables).
        # In a future version, we'd track the current function's Env too.
        return dict(self.interp.global_env.values)

    def _maybe_pause(self, line: int, detail: str = "") -> None:
        # Determinar si debemos pausar
        at_breakpoint = line in self.breakpoints
        step_into = self._step_mode
        # U2: step-over solo pausa si estamos al mismo nivel (o menos) de call stack
        step_over_match = (
            self._step_over_depth is not None
            and self._call_stack_depth <= self._step_over_depth
        )

        should_pause = at_breakpoint or step_into or step_over_match
        if not should_pause:
            return
        # Si es step-over y estamos a mayor profundidad, no pausar todavía
        if (self._step_over_depth is not None
            and self._call_stack_depth > self._step_over_depth
            and not at_breakpoint):
            return

        # Entramos en pausa: bloqueamos el hilo ejecutor hasta continue/step.
        self.state = DebugState(True, line, detail or "breakpoint")
        self.history.append(f"pause line={line} {detail} depth={self._call_stack_depth}")
        self._step_over_depth = None  # consumido
        self._pause_event.clear()       # bloqueará el wait() siguiente
        self._pause_ack.set()           # notifica al frontend
        self._pause_event.wait()        # BLOQUEA aquí
        # Al despertar:
        self.state = DebugState(False, line, "resumed")
        if self._step_mode:
            self._step_mode = False

    def _exec_program(self) -> Any:
        result = None
        for stmt in self.program.body:
            if self._stop_requested:
                break
            line = getattr(stmt, "line", 0) or 0
            self._maybe_pause(line, type(stmt).__name__)
            if self._stop_requested:
                break
            result = self.interp.exec_stmt(stmt, self.interp.global_env)
        self._pause_ack.clear()
        return result


def debug_source(source: str, breakpoints: Optional[List[int]] = None) -> Dict[str, Any]:
    """API de conveniencia: ejecuta con breakpoints y devuelve resumen.

    NOTA: este helper ejecuta sincrónicamente SIN pausa real (los breakpoints
    se registran pero la ejecución continúa hasta el final). Para pausa real
    use la clase `Debugger` directamente con `wait_paused()`/`continue_run()`.
    """
    dbg = Debugger(source)
    for bp in breakpoints or []:
        dbg.set_breakpoint(bp)
    # Sin hilos: registraremos los hits pero no bloquearemos
    saved_event = dbg._pause_event
    dbg._pause_event = _NoBlockEvent()  # event que nunca bloquea
    try:
        result = dbg.run()
    finally:
        dbg._pause_event = saved_event
    return {
        "result": result,
        "locals": {k: repr(v) for k, v in dbg.locals_snapshot().items() if not callable(v)},
        "history": dbg.history,
        "breakpoints": sorted(dbg.breakpoints),
    }


class _NoBlockEvent:
    """Mock de threading.Event cuyo wait() retorna inmediatamente sin bloquear.
    Útil para compat con código que asume debug_source no pausa."""
    def set(self): pass
    def clear(self): pass
    def wait(self, timeout=None): return True
    def is_set(self): return True
