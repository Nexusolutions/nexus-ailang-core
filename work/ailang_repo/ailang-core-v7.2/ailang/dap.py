"""Debug Adapter Protocol mínimo (Nivel E).

Subconjunto: initialize, launch, setBreakpoints, continue, next, stackTrace, variables.
Uso: python -m ailang --dap
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from ailang.debugger import Debugger


class DAPServer:
    def __init__(self):
        self.seq = 1
        self.dbg: Optional[Debugger] = None
        self.source = ""

    def run(self) -> None:
        while True:
            msg = self._read()
            if msg is None:
                break
            cmd = msg.get("command")
            mid = msg.get("seq")
            args = msg.get("arguments") or {}
            if cmd == "initialize":
                self._response(mid, {
                    "supportsConfigurationDoneRequest": True,
                    "supportsStepInTargetsRequest": False,
                })
                self._event("initialized", {})
            elif cmd == "launch":
                path = args.get("program") or args.get("path") or ""
                if path:
                    self.source = open(path, encoding="utf-8").read()
                    self.dbg = Debugger(self.source)
                self._response(mid, {})
            elif cmd == "setBreakpoints":
                lines = [bp.get("line") for bp in (args.get("breakpoints") or [])]
                if self.dbg:
                    self.dbg.clear_breakpoints()
                    for ln in lines:
                        if ln:
                            self.dbg.set_breakpoint(int(ln))
                self._response(mid, {
                    "breakpoints": [{"verified": True, "line": ln} for ln in lines if ln]
                })
            elif cmd == "configurationDone":
                self._response(mid, {})
            elif cmd == "continue":
                if self.dbg:
                    self.dbg.run()
                self._response(mid, {"allThreadsContinued": True})
            elif cmd == "next":
                if self.dbg:
                    self.dbg.step()
                self._response(mid, {})
            elif cmd == "stackTrace":
                frames = []
                if self.dbg and self.dbg.state.line:
                    frames.append({
                        "id": 1,
                        "name": "main",
                        "line": self.dbg.state.line,
                        "column": 1,
                        "source": {"name": "main.ailang"},
                    })
                self._response(mid, {"stackFrames": frames, "totalFrames": len(frames)})
            elif cmd == "variables":
                vars_ = []
                if self.dbg:
                    for k, v in self.dbg.locals_snapshot().items():
                        if callable(v):
                            continue
                        vars_.append({"name": k, "value": repr(v), "variablesReference": 0})
                self._response(mid, {"variables": vars_})
            elif cmd == "disconnect":
                self._response(mid, {})
                break
            elif cmd:
                self._response(mid, {})

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

    def _event(self, event: str, body: dict) -> None:
        self._send({"seq": self.seq, "type": "event", "event": event, "body": body})
        self.seq += 1


def main():
    DAPServer().run()


if __name__ == "__main__":
    main()
