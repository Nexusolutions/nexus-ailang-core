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
        # `_pause_event` se clear()a al entrar en pause y set()ea al continuar.
        # `_pause_ack` se set()a cuando el hilo ejecutor ha pausado, para que
        # wait_paused() pueda detectarlo sin busy-wait.
        self._pause_event = threading.Event()
        self._pause_event.set()  # inicialmente libre
        self._pause_ack = threading.Event()
        self._stop_requested = False

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
        self._pause_event.set()  # libera para que avance 1 stmt
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
        return dict(self.interp.global_env.values)

    def _maybe_pause(self, line: int, detail: str = "") -> None:
        should_pause = (line in self.breakpoints) or self._step_mode
        if not should_pause:
            return
        # Entramos en pausa: bloqueamos el hilo ejecutor hasta continue/step.
        self.state = DebugState(True, line, detail or "breakpoint")
        self.history.append(f"pause line={line} {detail}")
        self._pause_event.clear()       # bloqueará el wait() siguiente
        self._pause_ack.set()           # notifica al frontend
        self._pause_event.wait()        # BLOQUEA aquí
        # Al despertar:
        self.state = DebugState(False, line, "resumed")
        if self._step_mode:
            # step ya consumió un stmt; re-armar pausa inmediata en el siguiente
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
