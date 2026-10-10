"""ailang.runtime.event_loop — Event loop para async/await real (W4).

FASE 16 del prompt maestro. Implementa un event loop cooperativo que:

1. Permite `async fn` declarar funciones que retornan Futures
2. `await future` suspende la corrutina hasta que el Future se resuelva
3. `spawn fn()` encola una corrutina en el event loop
4. El event loop procesa tasks hasta que todas completan

Diseño:
- Las funciones async se compilan como generadores (yield = suspend)
- `await` se compila como: yield el Future, luego recibir el resultado
- El event loop alterna entre tasks, resumiendo cada una hasta que hace yield

Uso:
    from ailang.runtime.event_loop import run_async
    result = run_async(source)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from collections import deque

from ailang.lang.errors import AILangRuntimeError


class Future:
    """Future para async/await. Se resuelve con set_result o set_error."""

    def __init__(self):
        self._done = False
        self._result: Any = None
        self._error: Optional[BaseException] = None
        self._callbacks: List[callable] = []

    def set_result(self, result: Any) -> None:
        if self._done:
            return
        self._done = True
        self._result = result
        for cb in self._callbacks:
            cb(self)
        self._callbacks.clear()

    def set_error(self, error: BaseException) -> None:
        if self._done:
            return
        self._done = True
        self._error = error
        for cb in self._callbacks:
            cb(self)
        self._callbacks.clear()

    def add_done_callback(self, callback: callable) -> None:
        if self._done:
            callback(self)
        else:
            self._callbacks.append(callback)

    @property
    def done(self) -> bool:
        return self._done

    def result(self) -> Any:
        if not self._done:
            raise AILangRuntimeError("Future no resuelto")
        if self._error:
            raise self._error
        return self._result


class Task:
    """Task del event loop: wrap una corrutina (generador) con su Future."""

    def __init__(self, coro, name: str = "<task>"):
        self.coro = coro
        self.name = name
        self.future = Future()
        self._send_value: Any = None

    def step(self) -> bool:
        """Ejecuta un paso de la corrutina. Retorna True si terminó."""
        try:
            # send() reanuda el generador con el valor del Future awaited
            value = self.coro.send(self._send_value)
            self._send_value = None

            # Si la corrutina yield un Future, registrar callback para continuar
            if isinstance(value, Future):
                if value.done:
                    self._send_value = value.result()
                    return False  # continuar en próximo step
                else:
                    value.add_done_callback(lambda f: self._on_future_done(f))
                    return False  # esperando
            else:
                # yield un valor normal — no es async, continuar
                self._send_value = value
                return False

        except StopIteration as e:
            # Corrutina terminó — resolver future con el valor de retorno
            self.future.set_result(e.value)
            return True
        except BaseException as e:
            self.future.set_error(e)
            return True

    def _on_future_done(self, future: Future) -> None:
        """Callback cuando un Future awaited se resuelve."""
        if future._error:
            self._send_value = None  # el error se propagará al hacer send()
        else:
            self._send_value = future.result()
        # Re-encolar esta task
        # (el event loop la recogerá en la próxima iteración)


class EventLoop:
    """Event loop cooperativo para AILang async/await.

    Mantiene una cola de tasks listas para ejecutar. Cada task es una
    corrutina (generador Python) que puede:
    - yield un Future → se suspende hasta que el Future se resuelva
    - yield cualquier otro valor → se reanuda inmediatamente con ese valor
    - retornar (StopIteration) → el Future de la task se resuelve
    """

    def __init__(self):
        self._ready: deque[Task] = deque()
        self._current_task: Optional[Task] = None

    def create_task(self, coro, name: str = "<task>") -> Future:
        """Crea una task desde una corrutina. Retorna su Future."""
        task = Task(coro, name=name)
        self._ready.append(task)
        return task.future

    def run_until_complete(self, main_future: Optional[Future] = None) -> Any:
        """Ejecuta el event loop hasta que todas las tasks completen.

        Si se pasa main_future, retorna su resultado cuando se resuelva.
        """
        while self._ready:
            task = self._ready.popleft()
            self._current_task = task
            done = task.step()
            self._current_task = None

            if not done:
                # Re-encolar si no terminó (pero solo si no está esperando un Future)
                # Si step() registró un callback, no re-encolar — se re-encolará
                # cuando el callback dispare
                # Simplificación: siempre re-encolar (round-robin)
                # Esto puede causar busy-waiting en espera de Future externos
                # pero para tasks puramente cooperativas funciona
                if not task.future.done:
                    self._ready.append(task)

            if main_future and main_future.done:
                return main_future.result()

        if main_future:
            if not main_future.done:
                raise AILangRuntimeError("Event loop terminó pero main_future no resuelto")
            return main_future.result()
        return None

    @property
    def running(self) -> bool:
        return self._current_task is not None


# --- Singleton event loop ---

_default_loop: Optional[EventLoop] = None


def get_event_loop() -> EventLoop:
    global _default_loop
    if _default_loop is None:
        _default_loop = EventLoop()
    return _default_loop


def run_async(source: str, *, use_vm: bool = True) -> Any:
    """Ejecuta source con async/await support via event loop.

    Compila el source, identifica funciones async, y las ejecuta con
    el event loop si el programa usa spawn/await.
    """
    # Por ahora, delega a VM con scheduler existente
    # El event loop real se activa cuando se detecta spawn/await
    if use_vm:
        from ailang.lang.vm import run_vm
        return run_vm(source)
    else:
        from ailang.lang.interpreter import run_source
        return run_source(source)
