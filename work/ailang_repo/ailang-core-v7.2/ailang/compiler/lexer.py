"""Lexer — tokeniza la DSL cognitiva AILang."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Token:
    kind: str  # OP | KEY | EQ | VALUE | NEWLINE | EOF
    value: str
    line: int
    col: int


_OP = re.compile(r"^(brain\.(?:ingest|query|think|graph)|memory|persist|purge_after)\b")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?")
_WS = re.compile(r"^[ \t]+")


def _strip_line_comments(line: str) -> str:
    # simple // outside quotes handled by caller context; per-line approx
    out, in_s, esc, q = [], None, False, None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_s:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_s:
                in_s = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_s = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = _strip_line_comments(raw).strip()
        if not line or line in ("{", "}") or line.startswith("brain {") or line == "brain":
            continue
        line = line.rstrip(";").strip()
        col = 1
        # purge_after(Nms)
        m = re.match(r"purge_after\s*\(\s*(\d+)\s*ms\s*\)", line)
        if m:
            tokens.append(Token("OP", "purge_after", line_no, col))
            tokens.append(Token("VALUE", m.group(1), line_no, col))
            tokens.append(Token("NEWLINE", "\n", line_no, col))
            continue
        rest = line
        first = True
        while rest:
            wm = _WS.match(rest)
            if wm:
                rest = rest[wm.end():]
                col += wm.end()
                continue
            if first:
                om = _OP.match(rest)
                if om:
                    tokens.append(Token("OP", om.group(1), line_no, col))
                    rest = rest[om.end():]
                    col += om.end()
                    first = False
                    continue
                # memory volatile|session|durable
                if rest.startswith("memory"):
                    tokens.append(Token("OP", "memory", line_no, col))
                    rest = rest[6:].lstrip()
                    col += 6
                    first = False
                    continue
            if rest.startswith("="):
                tokens.append(Token("EQ", "=", line_no, col))
                rest = rest[1:]
                col += 1
                continue
            if rest[0] in ("'", '"'):
                q = rest[0]
                j = 1
                esc = False
                while j < len(rest):
                    if esc:
                        esc = False
                    elif rest[j] == "\\":
                        esc = True
                    elif rest[j] == q:
                        break
                    j += 1
                val = rest[1:j]
                tokens.append(Token("VALUE", val, line_no, col))
                rest = rest[j + 1:] if j < len(rest) else ""
                col += j + 1
                continue
            im = _IDENT.match(rest)
            if im:
                tokens.append(Token("KEY" if not first else "VALUE", im.group(0), line_no, col))
                rest = rest[im.end():]
                col += im.end()
                first = False
                continue
            nm = _NUMBER.match(rest)
            if nm:
                tokens.append(Token("VALUE", nm.group(0), line_no, col))
                rest = rest[nm.end():]
                col += nm.end()
                continue
            # skip unknown char
            rest = rest[1:]
            col += 1
        tokens.append(Token("NEWLINE", "\n", line_no, col))
    tokens.append(Token("EOF", "", len(source.splitlines()) + 1, 1))
    return tokens
