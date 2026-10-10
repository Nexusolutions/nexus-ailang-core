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
                        "referencesProvider": True,
                        "renameProvider": True,
                        "documentSymbolProvider": True,
                        "semanticTokensProvider": {
                            "legend": {
                                "tokenTypes": [
                                    "keyword", "function", "class", "variable",
                                    "string", "number", "type", "comment", "enumMember",
                                ],
                                "tokenModifiers": ["declaration", "readonly"],
                            },
                            "full": True,
                        },
                        "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
                        "codeActionProvider": True,
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
            # --- P2-1: Nuevos métodos LSP ---
            elif method == "textDocument/references":
                # Encuentra todas las ocurrencias de un identificador
                uri = params.get("textDocument", {}).get("uri", "")
                pos = params.get("position", {})
                text = self.docs.get(uri, "")
                word = self._word_at(text, pos.get("line", 0), pos.get("character", 0))
                locations = []
                if word:
                    for i, line in enumerate(text.splitlines()):
                        # Buscar la palabra como token aislado
                        col = 0
                        while True:
                            idx = line.find(word, col)
                            if idx < 0:
                                break
                            # Verificar que es un token (no substring)
                            before = line[idx - 1] if idx > 0 else " "
                            after = line[idx + len(word)] if idx + len(word) < len(line) else " "
                            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                                locations.append({
                                    "uri": uri,
                                    "range": {
                                        "start": {"line": i, "character": idx},
                                        "end": {"line": i, "character": idx + len(word)},
                                    },
                                })
                            col = idx + len(word)
                self._reply(mid, locations)
            elif method == "textDocument/rename":
                # Rename simbólico: todas las ocurrencias del word en el documento
                uri = params.get("textDocument", {}).get("uri", "")
                pos = params.get("position", {})
                new_name = params.get("newName", "")
                text = self.docs.get(uri, "")
                word = self._word_at(text, pos.get("line", 0), pos.get("character", 0))
                edits = []
                if word and new_name:
                    for i, line in enumerate(text.splitlines()):
                        col = 0
                        while True:
                            idx = line.find(word, col)
                            if idx < 0:
                                break
                            before = line[idx - 1] if idx > 0 else " "
                            after = line[idx + len(word)] if idx + len(word) < len(line) else " "
                            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                                edits.append({
                                    "range": {
                                        "start": {"line": i, "character": idx},
                                        "end": {"line": i, "character": idx + len(word)},
                                    },
                                    "newText": new_name,
                                })
                            col = idx + len(word)
                self._reply(mid, {
                    "changes": {uri: edits},
                    # P2-1: documentChanges no implementado (requiere versioned edits)
                })
            elif method == "textDocument/documentSymbol":
                # Lista símbolos del documento (fn, class, enum, interface, record, let, const)
                uri = params.get("textDocument", {}).get("uri", "")
                text = self.docs.get(uri, "")
                symbols = self._extract_symbols(text)
                self._reply(mid, symbols)
            elif method == "textDocument/semanticTokens/full":
                # Tokens semánticos para highlighting
                uri = params.get("textDocument", {}).get("uri", "")
                text = self.docs.get(uri, "")
                tokens = self._extract_semantic_tokens(text)
                self._reply(mid, {"data": tokens})
            elif method == "textDocument/signatureHelp":
                # Ayuda de firma para funciones
                uri = params.get("textDocument", {}).get("uri", "")
                pos = params.get("position", {})
                text = self.docs.get(uri, "")
                sig_info = self._signature_help(text, pos.get("line", 0), pos.get("character", 0))
                self._reply(mid, sig_info)
            elif method == "textDocument/codeAction":
                # Acciones rápidas (por ahora: agregar tipo a let)
                self._reply(mid, [])
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

    # --- P2-1: Helpers para nuevos métodos LSP ---

    def _extract_symbols(self, text: str) -> List[Dict[str, Any]]:
        """Extrae símbolos del documento (fn, class, enum, interface, record, let, const).

        Retorna una lista de DocumentSymbol (LSP) con name, kind, range.
        """
        symbols = []
        for i, line in enumerate(text.splitlines()):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            for kw, kind_num in [
                ("fn ", 12),       # Function
                ("class ", 5),     # Class
                ("enum ", 10),     # Enum
                ("interface ", 11),# Interface
                ("record ", 23),   # Struct (closest LSP kind)
                ("let ", 13),      # Variable
                ("const ", 14),    # Constant
            ]:
                if stripped.startswith(kw):
                    # Extraer nombre
                    rest = stripped[len(kw):]
                    name_end = 0
                    while name_end < len(rest) and (rest[name_end].isalnum() or rest[name_end] in "_"):
                        name_end += 1
                    name = rest[:name_end]
                    if name:
                        col_start = len(line) - len(stripped) + len(kw)
                        symbols.append({
                            "name": name,
                            "kind": kind_num,
                            "range": {
                                "start": {"line": i, "character": 0},
                                "end": {"line": i, "character": len(line)},
                            },
                            "selectionRange": {
                                "start": {"line": i, "character": col_start},
                                "end": {"line": i, "character": col_start + len(name)},
                            },
                        })
                    break
        return symbols

    def _extract_semantic_tokens(self, text: str) -> List[int]:
        """Tokens semánticos para highlighting (LSP semanticTokens format).

        Formato: [deltaLine, deltaStart, length, tokenType, tokenModifiers]
        """
        tokens = []
        prev_line = 0
        prev_char = 0
        type_index = {
            "keyword": 0, "function": 1, "class": 2, "variable": 3,
            "string": 4, "number": 5, "type": 6, "comment": 7, "enumMember": 8,
        }
        keywords = {
            "let", "const", "fn", "if", "else", "while", "for", "in", "return",
            "class", "extends", "import", "try", "catch", "throw", "true", "false",
            "null", "self", "super", "break", "continue", "match", "case", "enum",
            "interface", "record", "spawn", "yield", "async", "await", "implements",
            "purge_after",
        }
        for line_num, line in enumerate(text.splitlines()):
            i = 0
            while i < len(line):
                c = line[i]
                # Comments
                if c == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    length = len(line) - i
                    delta_line = line_num - prev_line
                    delta_char = i - prev_char if delta_line == 0 else i
                    tokens.extend([delta_line, delta_char, length, type_index["comment"], 0])
                    prev_line = line_num
                    prev_char = i
                    break
                # Strings
                if c == '"':
                    j = i + 1
                    while j < len(line):
                        if line[j] == "\\":
                            j += 2
                            continue
                        if line[j] == '"':
                            j += 1
                            break
                        j += 1
                    length = j - i
                    delta_line = line_num - prev_line
                    delta_char = i - prev_char if delta_line == 0 else i
                    tokens.extend([delta_line, delta_char, length, type_index["string"], 0])
                    prev_line = line_num
                    prev_char = i
                    i = j
                    continue
                # Numbers
                if c.isdigit():
                    j = i
                    while j < len(line) and (line[j].isdigit() or line[j] == "."):
                        j += 1
                    length = j - i
                    delta_line = line_num - prev_line
                    delta_char = i - prev_char if delta_line == 0 else i
                    tokens.extend([delta_line, delta_char, length, type_index["number"], 0])
                    prev_line = line_num
                    prev_char = i
                    i = j
                    continue
                # Identifiers / keywords
                if c.isalpha() or c == "_":
                    j = i
                    while j < len(line) and (line[j].isalnum() or line[j] == "_"):
                        j += 1
                    word = line[i:j]
                    length = j - i
                    token_type = "variable"
                    modifier = 0
                    if word in keywords:
                        token_type = "keyword"
                    elif i + length < len(line) and line[i + length] == "(":
                        # Function call
                        token_type = "function"
                    elif i > 0 and line[i - 1] == ".":
                        # Attribute / enum member
                        token_type = "enumMember"
                    else:
                        # Check if previous non-space is "fn"/"class"/"enum"/"interface"/"record"
                        prefix = line[:i].strip()
                        if prefix.endswith(("fn", "class", "enum", "interface", "record")):
                            token_type = "type"
                            modifier = 1  # declaration
                        elif prefix.endswith(("let", "const")):
                            token_type = "variable"
                            modifier = 1  # declaration
                    delta_line = line_num - prev_line
                    delta_char = i - prev_char if delta_line == 0 else i
                    tokens.extend([delta_line, delta_char, length, type_index[token_type], modifier])
                    prev_line = line_num
                    prev_char = i
                    i = j
                    continue
                i += 1
        return tokens

    def _signature_help(self, text: str, line: int, char: int) -> Dict[str, Any]:
        """Proporciona ayuda de firma para la función en la posición del cursor."""
        lines = text.splitlines()
        if line >= len(lines):
            return {"signatures": []}
        current = lines[line]
        # Buscar el '(' más cercano a la izquierda del cursor
        depth = 0
        open_paren = -1
        for i in range(min(char, len(current)) - 1, -1, -1):
            if current[i] == ")":
                depth += 1
            elif current[i] == "(":
                if depth == 0:
                    open_paren = i
                    break
                depth -= 1
        if open_paren < 0:
            return {"signatures": []}
        # Extraer nombre de función antes del '('
        j = open_paren - 1
        while j >= 0 and (current[j].isalnum() or current[j] == "_"):
            j -= 1
        fn_name = current[j + 1:open_paren]
        if not fn_name:
            return {"signatures": []}
        # Buscar la definición de la función
        sig = self._find_function_signature(text, fn_name)
        if sig is None:
            return {"signatures": []}
        # Calcular parámetro activo
        active_param = current[j + 1:char].count(",")
        return {
            "signatures": [{
                "label": sig,
                "parameters": [
                    {"label": p.strip()}
                    for p in sig[sig.find("(") + 1: sig.rfind(")")].split(",")
                    if p.strip()
                ],
            }],
            "activeSignature": 0,
            "activeParameter": active_param,
        }

    def _find_function_signature(self, text: str, name: str) -> Optional[str]:
        """Busca la firma de una función por nombre en el texto."""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"fn {name}("):
                # Extraer hasta el cierre de paréntesis
                start = stripped.find("(")
                depth = 0
                for i in range(start, len(stripped)):
                    if stripped[i] == "(":
                        depth += 1
                    elif stripped[i] == ")":
                        depth -= 1
                        if depth == 0:
                            return stripped[:i + 1]
                return stripped
        return None

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
