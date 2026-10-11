"""ailang.runtime.event_loop — Event loop para async/await (FIX9).

Event loop cooperativo que permite async/await real.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from collections import deque


class Future:
    """Future para async/await."""

    def __init__(self):
        self._done = False
        self._result: Any = None
        self._error: Optional[BaseException] = None
        self._callbacks: List[Callable] = []

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

    def add_done_callback(self, callback: Callable) -> None:
        if self._done:
            callback(self)
        else:
            self._callbacks.append(callback)

    @property
    def done(self) -> bool:
        return self._done

    def result(self) -> Any:
        if not self._done:
            raise RuntimeError("Future no resuelto")
        if self._error:
            raise self._error
        return self._result


class Task:
    """Task del event loop: wrap una corrutina con su Future."""

    def __init__(self, coro, name: str = "<task>"):
        self.coro = coro
        self.name = name
        self.future = Future()
        self._send_value: Any = None

    def step(self) -> bool:
        """Ejecuta un paso. Retorna True si terminó."""
        try:
            value = self.coro.send(self._send_value)
            self._send_value = None
            if isinstance(value, Future):
                if value.done:
                    self._send_value = value.result()
                    return False
                else:
                    value.add_done_callback(lambda f: self._on_future_done(f))
                    return False
            else:
                self._send_value = value
                return False
        except StopIteration as e:
            self.future.set_result(e.value)
            return True
        except BaseException as e:
            self.future.set_error(e)
            return True

    def _on_future_done(self, future: Future) -> None:
        if future._error:
            self._send_value = None
        else:
            self._send_value = future.result()


class EventLoop:
    """Event loop cooperativo."""

    def __init__(self):
        self._ready: deque = deque()
        self._current_task: Optional[Task] = None

    def create_task(self, coro, name: str = "<task>") -> Future:
        task = Task(coro, name=name)
        self._ready.append(task)
        return task.future

    def run_until_complete(self, main_future: Optional[Future] = None) -> Any:
        while self._ready:
            task = self._ready.popleft()
            self._current_task = task
            done = task.step()
            self._current_task = None
            if not done and not task.future.done:
                self._ready.append(task)
            if main_future and main_future.done:
                return main_future.result()
        if main_future:
            if not main_future.done:
                raise RuntimeError("Event loop terminó sin resolver future")
            return main_future.result()
        return None

    @property
    def running(self) -> bool:
        return self._current_task is not None


def run_async(source: str, *, use_vm: bool = True) -> Any:
    """Ejecuta source. Delega a VM/Interpreter (event loop para futuro)."""
    if use_vm:
        from ailang.lang.vm import run_vm
        return run_vm(source)
    else:
        from ailang.lang.interpreter import run_source
        return run_source(source)
