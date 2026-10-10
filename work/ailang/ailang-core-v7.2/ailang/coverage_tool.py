"""Cobertura de statements AILang."""
from __future__ import annotations
from typing import Any, Dict, Set
from ailang.lang.parser import parse
from ailang.lang.interpreter import Interpreter


def coverage_source(source: str) -> Dict[str, Any]:
    program = parse(source)
    lines: Set[int] = set()
    for stmt in program.body:
        ln = getattr(stmt, "line", 0) or 0
        if ln:
            lines.add(ln)
    executed: Set[int] = set()
    interp = Interpreter()
    result = None
    for stmt in program.body:
        ln = getattr(stmt, "line", 0) or 0
        if ln:
            executed.add(ln)
        result = interp.exec_stmt(stmt, interp.global_env)
    total = max(1, len(lines))
    return {
        "result": result,
        "lines_declared": sorted(lines),
        "lines_executed": sorted(executed),
        "coverage": len(executed) / total,
    }
