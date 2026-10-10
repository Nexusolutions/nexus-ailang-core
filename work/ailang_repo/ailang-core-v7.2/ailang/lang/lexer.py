"""Lexer del núcleo AILang."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
from ailang.lang.errors import AILangSyntaxError

KEYWORDS = {
    "let", "fn", "if", "else", "while", "for", "in", "return",
    "true", "false", "null", "and", "or", "not", "purge_after",
    "import", "try", "catch", "throw", "as",
    "class", "extends", "self", "super",
    "break", "continue",
    "match", "case", "const",
    "enum", "async", "await",
    "yield", "interface", "record", "spawn",
}

TWO = {
    "==": "EQEQ", "!=": "NE", "<=": "LE", ">=": "GE",
}


@dataclass
class Tok:
    kind: str
    value: str
    line: int
    col: int


def tokenize(source: str) -> List[Tok]:
    tokens: List[Tok] = []
    i, n = 0, len(source)
    line, col = 1, 1

    def adv(k=1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and source[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = source[i]
        if ch in " \t\r":
            adv(); continue
        if ch == "\n":
            tokens.append(Tok("NEWLINE", "\n", line, col)); adv(); continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                adv()
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            adv(2)
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                adv()
            adv(2)
            continue
        if ch in "\"'":
            q, start_l, start_c = ch, line, col
            adv()
            buf = []
            while i < n and source[i] != q:
                if source[i] == "\\" and i + 1 < n:
                    adv(); buf.append(source[i]); adv()
                else:
                    buf.append(source[i]); adv()
            if i >= n:
                raise AILangSyntaxError("string no cerrado", start_l, start_c)
            adv()
            tokens.append(Tok("STRING", "".join(buf), start_l, start_c))
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            start_l, start_c = line, col
            buf = []
            while i < n and (source[i].isdigit() or source[i] == "."):
                buf.append(source[i]); adv()
            tokens.append(Tok("NUMBER", "".join(buf), start_l, start_c))
            continue
        if ch.isalpha() or ch == "_":
            start_l, start_c = line, col
            buf = []
            while i < n and (source[i].isalnum() or source[i] == "_"):
                buf.append(source[i]); adv()
            word = "".join(buf)
            kind = "KEYWORD" if word in KEYWORDS else "IDENT"
            tokens.append(Tok(kind, word, start_l, start_c))
            continue
        if i + 1 < n and source[i:i + 2] in TWO:
            tokens.append(Tok(TWO[source[i:i + 2]], source[i:i + 2], line, col))
            adv(2); continue
        if ch == ";":
            tokens.append(Tok("NEWLINE", ";", line, col)); adv(); continue
        singles = {
            "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "%": "PERCENT",
            "(": "LPAREN", ")": "RPAREN", "{": "LBRACE", "}": "RBRACE",
            "[": "LBRACK", "]": "RBRACK", ",": "COMMA", ":": "COLON",
            "=": "EQ", "<": "LT", ">": "GT", ".": "DOT",
        }
        if ch in singles:
            tokens.append(Tok(singles[ch], ch, line, col)); adv(); continue
        raise AILangSyntaxError(f"carácter inesperado {ch!r}", line, col)
    tokens.append(Tok("EOF", "", line, col))
    return tokens
