"""Formateador simple de AILang (Nivel C).

Reglas: indent 2 espacios, llaves en misma línea del header, espacios alrededor de =.
"""
from __future__ import annotations

from ailang.lang.lexer import tokenize


def format_source(source: str) -> str:
    tokens = tokenize(source)
    out = []
    indent = 0
    i = 0
    newline = True
    while i < len(tokens):
        t = tokens[i]
        if t.kind == "EOF":
            break
        if t.kind == "NEWLINE":
            out.append("\n")
            newline = True
            i += 1
            continue
        if t.kind == "RBRACE":
            indent = max(0, indent - 1)
        if newline:
            out.append("  " * indent)
            newline = False
        if t.kind == "STRING":
            out.append(repr(t.value) if False else f'"{t.value}"')
        elif t.kind == "NUMBER":
            out.append(t.value)
        elif t.kind in ("IDENT", "KEYWORD"):
            out.append(t.value)
        elif t.kind == "LBRACE":
            out.append(" {")
            indent += 1
            out.append("\n")
            newline = True
            i += 1
            continue
        elif t.kind == "RBRACE":
            out.append("}")
            out.append("\n")
            newline = True
            i += 1
            continue
        elif t.kind in ("EQ", "EQEQ", "NE", "LE", "GE", "LT", "GT"):
            op = {"EQ": "=", "EQEQ": "==", "NE": "!=", "LE": "<=", "GE": ">=", "LT": "<", "GT": ">"}.get(t.kind, t.value)
            out.append(f" {op} ")
        elif t.kind == "COMMA":
            out.append(", ")
        else:
            out.append(t.value)
        # space after keywords before ident
        if t.kind == "KEYWORD" and i + 1 < len(tokens) and tokens[i + 1].kind in ("IDENT", "NUMBER", "STRING"):
            out.append(" ")
        i += 1
    text = "".join(out)
    # collapse multiple blank lines
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)
    return "\n".join(cleaned).rstrip() + "\n"


def format_file(path: str) -> str:
    from pathlib import Path
    p = Path(path)
    formatted = format_source(p.read_text(encoding="utf-8"))
    p.write_text(formatted, encoding="utf-8")
    return formatted
