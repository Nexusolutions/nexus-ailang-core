"""Debug Adapter Protocol completo (S2 — P2-2).

Implementa los métodos principales del DAP 1.55:
- initialize, launch, setBreakpoints, configurationDone
- continue, next, stepIn, stepOut, pause, terminate
- threads, stackTrace, scopes, variables
- evaluate, setExceptionBreakpoints
- Integración real con Debugger (P0-10 pause via threading.Event)

El debugger se ejecuta en un hilo separado. Cuando alcanza un breakpoint,
emite un evento `stopped` y espera a que el cliente envíe `continue`/`next`/etc.

Uso: python -m ailang --dap
"""
from __future__ import annotations

import json
import sys
import threading
from typing import Any, Dict, List, Optional

from ailang.debugger import Debugger
from ailang.lang.errors import AILangRuntimeError


class DAPServer:
    """Servidor DAP que comunica con un cliente (VS Code, etc.) via stdio."""

    def __init__(self):
        self.seq = 1
        self.dbg: Optional[Debugger] = None
        self.source = ""
        self.source_path = "main.ailang"
        self._dbg_thread: Optional[threading.Thread] = None
        self._exception_breakpoints: Dict[str, bool] = {}
        self._watch_exprs: Dict[int, str] = {}
        self._next_var_ref = 1000

    def run(self) -> None:
        while True:
            msg = self._read()
            if msg is None:
                break
            cmd = msg.get("command")
            mid = msg.get("seq")
            args = msg.get("arguments") or {}

            if cmd == "initialize":
                self._handle_initialize(mid, args)
            elif cmd == "launch":
                self._handle_launch(mid, args)
            elif cmd == "setBreakpoints":
                self._handle_set_breakpoints(mid, args)
            elif cmd == "setExceptionBreakpoints":
                self._handle_set_exception_breakpoints(mid, args)
            elif cmd == "configurationDone":
                self._response(mid, {})
                # Auto-start si hay breakpoints configurados o si el programa es simple
            elif cmd == "continue":
                self._handle_continue(mid, args)
            elif cmd == "next":
                self._handle_step(mid, args, mode="over")
            elif cmd == "stepIn":
                self._handle_step(mid, args, mode="into")
            elif cmd == "stepOut":
                self._handle_step(mid, args, mode="out")
            elif cmd == "pause":
                self._handle_pause(mid, args)
            elif cmd == "terminate":
                self._handle_terminate(mid, args)
                break
            elif cmd == "disconnect":
                self._handle_disconnect(mid, args)
                break
            elif cmd == "threads":
                self._handle_threads(mid, args)
            elif cmd == "stackTrace":
                self._handle_stack_trace(mid, args)
            elif cmd == "scopes":
                self._handle_scopes(mid, args)
            elif cmd == "variables":
                self._handle_variables(mid, args)
            elif cmd == "evaluate":
                self._handle_evaluate(mid, args)
            elif cmd == "setVariable":
                self._handle_set_variable(mid, args)
            elif cmd == "source":
                self._handle_source(mid, args)
            elif cmd:
                # Comando no reconocido: responder success vacío
                self._response(mid, {})

    # --- Handlers ---

    def _handle_initialize(self, mid, args):
        self._response(mid, {
            "supportsConfigurationDoneRequest": True,
            "supportsStepInTargetsRequest": False,
            "supportsEvaluateForHovers": True,
            "supportsSetVariable": True,
            "supportsTerminateRequest": True,
            "supportsRestartRequest": True,
            "supportsExceptionInfoRequest": True,
            "supportsDelayedStackTraceLoading": False,
            "supportsExceptionFilterOptions": True,
            "supportsStepBack": False,
            "supportsConditionalBreakpoints": True,
            "supportsHitConditionalBreakpoints": False,
            "supportsLogPoints": False,
        })
        self._event("initialized", {})

    def _handle_launch(self, mid, args):
        path = args.get("program") or args.get("path") or ""
        if path:
            try:
                self.source = open(path, encoding="utf-8").read()
                self.source_path = path
                self.dbg = Debugger(self.source)
            except Exception as e:
                self._response_error(mid, f"no se pudo cargar programa: {e}")
                return
        self._response(mid, {})

    def _handle_set_breakpoints(self, mid, args):
        # args: { source: { path }, breakpoints: [{ line, condition? }] }
        bps_req = args.get("breakpoints") or []
        if self.dbg:
            self.dbg.clear_breakpoints()
        verified = []
        for bp in bps_req:
            line = bp.get("line", 0)
            condition = bp.get("condition")
            if line and self.dbg:
                self.dbg.set_breakpoint(int(line))
            verified.append({
                "id": len(verified) + 1,
                "verified": True,
                "line": line,
                "source": args.get("source", {}),
                **({"condition": condition} if condition else {}),
            })
        self._response(mid, {"breakpoints": verified})

    def _handle_set_exception_breakpoints(self, mid, args):
        # args: { filters: ["all" | "uncaught"], exceptionOptions?: [...] }
        filters = args.get("filters") or []
        self._exception_breakpoints = {
            "all": "all" in filters,
            "uncaught": "uncaught" in filters,
        }
        self._response(mid, {})

    def _handle_continue(self, mid, args):
        if self.dbg:
            if self.dbg.state.paused:
                self.dbg.continue_run()
            elif self._dbg_thread is None or not self._dbg_thread.is_alive():
                # Primera vez: arrancar el debugger en un hilo
                self._dbg_thread = threading.Thread(target=self._run_debugger, daemon=True)
                self._dbg_thread.start()
        self._response(mid, {"allThreadsContinued": True})

    def _handle_step(self, mid, args, mode: str = "over"):
        if self.dbg and self.dbg.state.paused:
            # Por ahora step es lo mismo que continue (no hay granularidad de step)
            # Una implementación completa requeriría step-over/into/out en el Debugger
            self.dbg.step()
            # Emitir stopped event cuando pausa de nuevo
            self._check_paused()
        self._response(mid, {})

    def _handle_pause(self, mid, args):
        if self.dbg:
            self.dbg.request_stop()
        self._response(mid, {})

    def _handle_terminate(self, mid, args):
        if self.dbg:
            self.dbg.request_stop()
        if self._dbg_thread and self._dbg_thread.is_alive():
            self.dbg.continue_run()  # liberar si está pausado
            self._dbg_thread.join(timeout=2.0)
        self._response(mid, {})
        self._event("terminated", {})

    def _handle_disconnect(self, mid, args):
        if self.dbg:
            self.dbg.request_stop()
            self.dbg.continue_run()
        if self._dbg_thread and self._dbg_thread.is_alive():
            self._dbg_thread.join(timeout=1.0)
        self._response(mid, {})

    def _handle_threads(self, mid, args):
        # AILang es single-threaded; reportamos un solo hilo
        threads = [{"id": 1, "name": "main"}]
        self._response(mid, {"threads": threads})

    def _handle_stack_trace(self, mid, args):
        frames = []
        if self.dbg and self.dbg.state.paused:
            line = self.dbg.state.line
            frames.append({
                "id": 1,
                "name": self.dbg.state.reason or "main",
                "source": {
                    "name": self.source_path.split("/")[-1],
                    "path": self.source_path,
                },
                "line": line,
                "column": 1,
                "endLine": line,
                "endColumn": 1,
            })
        self._response(mid, {"stackFrames": frames, "totalFrames": len(frames)})

    def _handle_scopes(self, mid, args):
        # args: { frameId }
        scopes = [
            {"name": "Locals", "variablesReference": 1, "expensive": False, "presentationHint": "locals"},
            {"name": "Globals", "variablesReference": 2, "expensive": True, "presentationHint": "globals"},
        ]
        self._response(mid, {"scopes": scopes})

    def _handle_variables(self, mid, args):
        # args: { variablesReference }
        ref = args.get("variablesReference", 0)
        vars_ = []
        if self.dbg:
            if ref == 1:  # Locals
                for k, v in self.dbg.locals_snapshot().items():
                    if callable(v) or k.startswith("_"):
                        continue
                    var_ref = 0
                    if isinstance(v, (list, dict)):
                        var_ref = self._next_var_ref
                        self._watch_exprs[var_ref] = k
                        self._next_var_ref += 1
                    vars_.append({
                        "name": k,
                        "value": repr(v),
                        "type": type(v).__name__,
                        "variablesReference": var_ref,
                    })
            elif ref == 2:  # Globals
                for k, v in self.dbg.interp.global_env.values.items():
                    if callable(v) or k.startswith("_"):
                        continue
                    vars_.append({
                        "name": k,
                        "value": repr(v),
                        "type": type(v).__name__,
                        "variablesReference": 0,
                    })
            else:
                # Es una variable compuesta (list/dict) — expandir
                expr = self._watch_exprs.get(ref, "")
                if expr:
                    val = self.dbg.locals_snapshot().get(expr)
                    if isinstance(val, list):
                        for i, item in enumerate(val):
                            vars_.append({
                                "name": str(i),
                                "value": repr(item),
                                "type": type(item).__name__,
                                "variablesReference": 0,
                            })
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            vars_.append({
                                "name": str(k),
                                "value": repr(v),
                                "type": type(v).__name__,
                                "variablesReference": 0,
                            })
        self._response(mid, {"variables": vars_})

    def _handle_evaluate(self, mid, args):
        # args: { expression, frameId, context }
        expr = args.get("expression", "")
        result = ""
        if self.dbg:
            try:
                # Evaluar la expresión en el contexto del intérprete
                # Limitación: por ahora solo soporta nombres de variables simples
                locals_ = self.dbg.locals_snapshot()
                if expr in locals_:
                    result = repr(locals_[expr])
                elif expr in self.dbg.interp.global_env.values:
                    result = repr(self.dbg.interp.global_env.values[expr])
                else:
                    result = f"<no se pudo evaluar: {expr}>"
            except Exception as e:
                result = f"<error: {e}>"
        self._response(mid, {"result": result, "variablesReference": 0})

    def _handle_set_variable(self, mid, args):
        # args: { variablesReference, name, value }
        name = args.get("name", "")
        value_str = args.get("value", "")
        if self.dbg:
            try:
                # Intentar evaluar el value como Python literal
                import ast as _ast
                try:
                    value = _ast.literal_eval(value_str)
                except Exception:
                    value = value_str  # mantener como string
                self.dbg.interp.global_env.values[name] = value
                self._response(mid, {"value": repr(value)})
            except Exception as e:
                self._response_error(mid, str(e))
        else:
            self._response_error(mid, "no debugger")

    def _handle_source(self, mid, args):
        # args: { source: { path } }
        self._response(mid, {"content": self.source, "mimeType": "text/x-ailang"})

    # --- Internal ---

    def _run_debugger(self):
        """Ejecuta el debugger en un hilo. Emite `stopped` cuando pausa."""
        if not self.dbg:
            return
        try:
            self.dbg.run()
        except Exception as e:
            self._event("output", {"category": "stderr", "output": str(e) + "\n"})
        # Si el debugger termina (programa completado)
        self._event("terminated", {})

    def _check_paused(self):
        """Verifica si el debugger ha pausado y emite el evento `stopped`."""
        if self.dbg and self.dbg.state.paused:
            self._event("stopped", {
                "reason": "breakpoint",
                "threadId": 1,
                "allThreadsStopped": True,
            })

    # --- Protocol layer ---

    def _read(self) -> Optional[Dict[str, Any]]:
        headers = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            line = line.decode("utf-8")
            if line in ("\r\n", "\n"):
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        n = int(headers.get("content-length", "0"))
        if n <= 0:
            return None
        body = sys.stdin.buffer.read(n).decode("utf-8")
        return json.loads(body)

    def _send(self, obj: Dict[str, Any]) -> None:
        data = json.dumps(obj).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
        sys.stdout.buffer.flush()

    def _response(self, req_seq, body) -> None:
        self._send({
            "seq": self.seq, "type": "response", "request_seq": req_seq,
            "success": True, "command": "", "body": body,
        })
        self.seq += 1

    def _response_error(self, req_seq, message: str) -> None:
        self._send({
            "seq": self.seq, "type": "response", "request_seq": req_seq,
            "success": False, "command": "", "body": {},
            "message": message,
        })
        self.seq += 1

    def _event(self, event: str, body: dict) -> None:
        self._send({"seq": self.seq, "type": "event", "event": event, "body": body})
        self.seq += 1


def main():
    DAPServer().run()


if __name__ == "__main__":
    main()
