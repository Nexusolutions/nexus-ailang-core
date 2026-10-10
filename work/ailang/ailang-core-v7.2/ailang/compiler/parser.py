"""Parser — tokens → AST superficial (ops + kwargs)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ailang.compiler.lexer import Token


@dataclass
class ASTStmt:
    op: str
    args: Dict[str, Any] = field(default_factory=dict)
    line: int = 0


@dataclass
class ASTModule:
    stmts: List[ASTStmt]
    budget_ms: Optional[int] = None


def parse_tokens(tokens: List[Token]) -> ASTModule:
    stmts: List[ASTStmt] = []
    budget_ms: Optional[int] = None
    i = 0
    n = len(tokens)

    def peek(k=0):
        return tokens[i + k] if i + k < n else tokens[-1]

    while i < n and peek().kind != "EOF":
        if peek().kind == "NEWLINE":
            i += 1
            continue
        if peek().kind != "OP":
            i += 1
            continue
        op_tok = peek()
        op = op_tok.value
        line = op_tok.line
        i += 1
        if op == "purge_after":
            if peek().kind == "VALUE":
                budget_ms = int(peek().value)
                i += 1
            continue
        args: Dict[str, Any] = {}
        # memory persistence qualifier
        if op == "memory" and peek().kind in ("KEY", "VALUE") and peek().value in (
            "volatile", "session", "durable"
        ):
            args["persistence"] = peek().value
            i += 1
        while peek().kind not in ("NEWLINE", "EOF", "OP"):
            if peek().kind in ("KEY", "VALUE"):
                key = peek().value
                i += 1
                if peek().kind == "EQ":
                    i += 1
                if peek().kind == "VALUE":
                    raw = peek().value
                    i += 1
                    # try number
                    try:
                        if "." in raw:
                            args[key] = float(raw)
                        else:
                            args[key] = int(raw)
                    except ValueError:
                        args[key] = raw
                else:
                    args[key] = True
            else:
                i += 1
        stmts.append(ASTStmt(op, args, line))
        if peek().kind == "NEWLINE":
            i += 1
    return ASTModule(stmts, budget_ms)
