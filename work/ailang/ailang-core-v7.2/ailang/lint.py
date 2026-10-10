"""Linter de AILang (Nivel C)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ailang.lang.parser import parse
from ailang.lang.errors import AILangSyntaxError
from ailang.lang.typecheck import typecheck
from ailang.lang import ast_nodes as A


@dataclass
class LintIssue:
    level: str
    message: str
    line: int = 0

    def __str__(self) -> str:
        return f"{self.level}:line {self.line}: {self.message}"


def lint_source(source: str) -> List[LintIssue]:
    issues: List[LintIssue] = []
    try:
        program = parse(source)
    except AILangSyntaxError as e:
        return [LintIssue("error", str(e), e.line)]

    for d in typecheck(source, strict=False):
        issues.append(LintIssue(d.level, d.message, d.line))

    # unused? simple: assign never read — skip
    # empty blocks
    def walk(node, line=0):
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, A.If) and not node.body:
            issues.append(LintIssue("warning", "if vacío", node.line))
        if isinstance(node, A.Function) and not node.body:
            issues.append(LintIssue("warning", f"fn {node.name} vacía", node.line))
        if isinstance(node, A.While) and not node.body:
            issues.append(LintIssue("warning", "while vacío", node.line))
        for attr in ("body", "orelse", "methods", "cases"):
            if hasattr(node, attr):
                walk(getattr(node, attr))
        if isinstance(node, A.Match):
            for c in node.cases:
                walk(c.body)

    for stmt in program.body:
        walk(stmt)
    return issues
