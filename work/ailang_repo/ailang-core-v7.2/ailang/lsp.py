"""Language Server Protocol mínimo para AILang.

Soporta: initialize, textDocument/didOpen, didChange,
textDocument/completion, textDocument/hover, textDocument/diagnostic (pull via didOpen).

Uso: python -m ailang --lsp
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from ailang.versions import __version__ as LSP_SERVER_VERSION
from ailang.lang.typecheck import typecheck
from ailang.lang.lexer import tokenize
from ailang.lang.errors import AILangSyntaxError
from ailang.lang.parser import parse


COMPLETIONS = [
    "let", "fn", "if", "else", "while", "for", "in", "return", "class", "extends",
    "import", "try", "catch", "throw", "true", "false", "null", "self", "super",
    "print", "len", "type", "isinstance",
    "math", "io", "json", "listops", "strings", "time", "sys", "test", "path",
    "random", "re", "brain",
]


class AILangLanguageServer:
    def __init__(self):
        self.docs: Dict[str, str] = {}

    def run(self) -> None:
        while True:
            msg = self._read_message()
            if msg is None:
                break
            method = msg.get("method")
            mid = msg.get("id")
            params = msg.get("params") or {}
            if method == "initialize":
                self._reply(mid, {
                    "capabilities": {
                        "textDocumentSync": 1,
                        "completionProvider": {"triggerCharacters": ["."]},
                        "hoverProvider": True,
                        "definitionProvider": True,
                    },
                    "serverInfo": {"name": "ailang-lsp", "version": LSP_SERVER_VERSION},
                })
            elif method == "initialized":
                pass
            elif method == "shutdown":
                self._reply(mid, None)
            elif method == "exit":
                break
            elif method == "textDocument/didOpen":
                doc = params.get("textDocument", {})
                uri = doc.get("uri", "")
                self.docs[uri] = doc.get("text", "")
                self._publish_diags(uri, self.docs[uri])
            elif method == "textDocument/didChange":
                doc = params.get("textDocument", {})
                uri = doc.get("uri", "")
                changes = params.get("contentChanges") or []
                if changes:
                    self.docs[uri] = changes[-1].get("text", self.docs.get(uri, ""))
                    self._publish_diags(uri, self.docs[uri])
            elif method == "textDocument/completion":
                items = [{"label": k, "kind": 14} for k in COMPLETIONS]
                self._reply(mid, {"isIncomplete": False, "items": items})
            elif method == "textDocument/definition":
                uri = params.get("textDocument", {}).get("uri", "")
                pos = params.get("position", {})
                text = self.docs.get(uri, "")
                word = self._word_at(text, pos.get("line", 0), pos.get("character", 0))
                loc = self._find_def(text, word)
                if loc is None:
                    self._reply(mid, None)
                else:
                    self._reply(mid, {
                        "uri": uri,
                        "range": {
                            "start": {"line": loc, "character": 0},
                            "end": {"line": loc, "character": 1},
                        },
                    })
            elif method == "textDocument/hover":
                pos = params.get("position", {})
                uri = params.get("textDocument", {}).get("uri", "")
                text = self.docs.get(uri, "")
                word = self._word_at(text, pos.get("line", 0), pos.get("character", 0))
                body = f"**{word}**\n\nAILang identifier" if word else "AILang"
                self._reply(mid, {"contents": {"kind": "markdown", "value": body}})
            elif method and mid is not None:
                self._reply(mid, None)

    def _find_def(self, text: str, word: str):
        if not word:
            return None
        for i, line in enumerate(text.splitlines()):
            stripped = line.strip()
            for prefix in (f"fn {word}", f"class {word}", f"enum {word}", f"let {word}", f"const {word}"):
                if stripped.startswith(prefix):
                    return i
        return None

    def _word_at(self, text: str, line: int, col: int) -> str:
        lines = text.splitlines() or [""]
        if line >= len(lines):
            return ""
        s = lines[line]
        i = min(col, len(s))
        a = i
        while a > 0 and (s[a - 1].isalnum() or s[a - 1] == "_"):
            a -= 1
        b = i
        while b < len(s) and (s[b].isalnum() or s[b] == "_"):
            b += 1
        return s[a:b]

    def _publish_diags(self, uri: str, text: str) -> None:
        diags = []
        try:
            parse(text)
        except AILangSyntaxError as e:
            diags.append({
                "range": {
                    "start": {"line": max(0, e.line - 1), "character": max(0, e.col - 1)},
                    "end": {"line": max(0, e.line - 1), "character": max(0, e.col)},
                },
                "severity": 1,
                "source": "ailang",
                "message": str(e),
            })
        for d in typecheck(text, strict=False):
            if d.level != "error":
                continue
            diags.append({
                "range": {
                    "start": {"line": max(0, d.line - 1), "character": 0},
                    "end": {"line": max(0, d.line - 1), "character": 1},
                },
                "severity": 1,
                "source": "ailang-typecheck",
                "message": d.message,
            })
        self._notify("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": diags})

    def _read_message(self) -> Optional[Dict[str, Any]]:
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
        length = int(headers.get("content-length", "0"))
        if length <= 0:
            return None
        body = sys.stdin.buffer.read(length).decode("utf-8")
        return json.loads(body)

    def _send(self, obj: Dict[str, Any]) -> None:
        data = json.dumps(obj).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
        sys.stdout.buffer.flush()

    def _reply(self, mid, result) -> None:
        self._send({"jsonrpc": "2.0", "id": mid, "result": result})

    def _notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})


def main():
    AILangLanguageServer().run()


if __name__ == "__main__":
    main()
