"""Cobertura de AILang con branch-level tracking (T5 — P2-6).

FASE 28 del prompt maestro. Amplía el coverage tool existente con:
- Statement coverage (existente: qué líneas se ejecutaron)
- Branch coverage: qué branches de if/while se tomaron (true/false)
- Function coverage: qué funciones fueron llamadas
- Loop coverage: cuántas iteraciones ejecutó cada loop
- Reporte HTML/JSON

Uso:
  from ailang.coverage_tool import coverage_source
  report = coverage_source(source)
  print(report["summary"])
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ailang.lang.parser import parse
from ailang.lang.interpreter import Interpreter
from ailang.lang import ast_nodes as A


@dataclass
class BranchInfo:
    """Información de un branch (if/while condition)."""
    line: int
    kind: str  # "if" | "while"
    true_taken: bool = False
    false_taken: bool = False


@dataclass
class FunctionInfo:
    """Información de una función."""
    name: str
    line: int
    called: bool = False
    call_count: int = 0


@dataclass
class LoopInfo:
    """Información de un loop."""
    line: int
    kind: str  # "while" | "for"
    iterations: int = 0


@dataclass
class CoverageReport:
    """Reporte completo de cobertura."""
    lines_declared: Set[int] = field(default_factory=set)
    lines_executed: Set[int] = field(default_factory=set)
    branches: Dict[int, BranchInfo] = field(default_factory=dict)
    functions: Dict[str, FunctionInfo] = field(default_factory=dict)
    loops: Dict[int, LoopInfo] = field(default_factory=dict)
    result: Any = None

    def summary(self) -> Dict[str, Any]:
        total_lines = max(1, len(self.lines_declared))
        line_cov = len(self.lines_executed) / total_lines

        total_branches = len(self.branches)
        branches_covered = sum(
            1 for b in self.branches.values()
            if b.true_taken and b.false_taken
        )
        branch_cov = branches_covered / max(1, total_branches)

        total_fns = len(self.functions)
        fns_called = sum(1 for f in self.functions.values() if f.called)
        fn_cov = fns_called / max(1, total_fns)

        return {
            "line_coverage": round(line_cov, 4),
            "branch_coverage": round(branch_cov, 4),
            "function_coverage": round(fn_cov, 4),
            "lines_total": total_lines,
            "lines_executed": len(self.lines_executed),
            "branches_total": total_branches,
            "branches_covered": branches_covered,
            "functions_total": total_fns,
            "functions_called": fns_called,
            "loops": {
                line: {"kind": l.kind, "iterations": l.iterations}
                for line, l in self.loops.items()
            },
        }


def _collect_branch_points(program) -> Dict[int, BranchInfo]:
    """Recopila todos los puntos de branch (if/while) del programa."""
    branches: Dict[int, BranchInfo] = {}

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, A.If):
            line = getattr(node, "line", 0) or 0
            if line:
                branches[line] = BranchInfo(line=line, kind="if")
            walk(node.body)
            walk(node.orelse)
        elif isinstance(node, A.While):
            line = getattr(node, "line", 0) or 0
            if line:
                branches[line] = BranchInfo(line=line, kind="while")
            walk(node.body)
        elif isinstance(node, A.For):
            line = getattr(node, "line", 0) or 0
            if line:
                branches[line] = BranchInfo(line=line, kind="while")
            walk(node.body)
        elif isinstance(node, A.Function):
            walk(node.body)
        elif hasattr(node, "body") and isinstance(node.body, list):
            walk(node.body)

    for stmt in program.body:
        walk(stmt)
    return branches


def _collect_functions(program) -> Dict[str, FunctionInfo]:
    """Recopila todas las funciones del programa."""
    fns: Dict[str, FunctionInfo] = {}

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, A.Function):
            fns[node.name] = FunctionInfo(name=node.name, line=node.line)
            walk(node.body)
        elif hasattr(node, "body") and isinstance(node.body, list):
            walk(node.body)

    for stmt in program.body:
        walk(stmt)
    return fns


def _collect_loops(program) -> Dict[int, LoopInfo]:
    """Recopila todos los loops del programa."""
    loops: Dict[int, LoopInfo] = {}

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, (A.While, A.For)):
            line = getattr(node, "line", 0) or 0
            if line:
                loops[line] = LoopInfo(line=line, kind=type(node).__name__.lower())
            walk(node.body)
        elif isinstance(node, A.Function):
            walk(node.body)
        elif hasattr(node, "body") and isinstance(node.body, list):
            walk(node.body)

    for stmt in program.body:
        walk(stmt)
    return loops


def coverage_source(source: str) -> Dict[str, Any]:
    """Ejecuta source con tracking de cobertura branch-level.

    Retorna un dict con:
    - result: valor de retorno del programa
    - lines_declared: líneas con código ejecutable
    - lines_executed: líneas que se ejecutaron
    - branches: info de branches tomados
    - functions: info de funciones llamadas
    - loops: info de iteraciones de loops
    - summary: porcentajes de cobertura
    """
    program = parse(source)
    report = CoverageReport()

    # Recopilar puntos estáticos
    report.branches = _collect_branch_points(program)
    report.functions = _collect_functions(program)
    report.loops = _collect_loops(program)

    # Declarar todas las líneas con código
    def collect_lines(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                collect_lines(n)
            return
        ln = getattr(node, "line", 0) or 0
        if ln:
            report.lines_declared.add(ln)
        if hasattr(node, "body") and isinstance(node.body, list):
            collect_lines(node.body)
        if isinstance(node, A.If):
            collect_lines(node.orelse)

    for stmt in program.body:
        collect_lines(stmt)

    # Ejecutar con tracking
    interp = Interpreter()

    # Wrap function calls to track coverage
    original_eval = interp.eval_expr
    def tracked_eval(node, env):
        if isinstance(node, A.Call) and isinstance(node.func, A.Name):
            fn_name = node.func.id
            if fn_name in report.functions:
                report.functions[fn_name].called = True
                report.functions[fn_name].call_count += 1
        return original_eval(node, env)
    interp.eval_expr = tracked_eval

    # Execute statements
    result = None
    for stmt in program.body:
        ln = getattr(stmt, "line", 0) or 0
        if ln:
            report.lines_executed.add(ln)

        # Track branches for if/while
        if isinstance(stmt, A.If):
            test_val = bool(interp.eval_expr(stmt.test, interp.global_env))
            line = getattr(stmt, "line", 0) or 0
            if line in report.branches:
                if test_val:
                    report.branches[line].true_taken = True
                else:
                    report.branches[line].false_taken = True
        elif isinstance(stmt, A.While):
            # Execute while loop with branch tracking
            line = getattr(stmt, "line", 0) or 0
            while True:
                test_val = bool(interp.eval_expr(stmt.test, interp.global_env))
                if line in report.branches:
                    if test_val:
                        report.branches[line].true_taken = True
                        report.loops[line].iterations += 1
                    else:
                        report.branches[line].false_taken = True
                if not test_val:
                    break
                for s in stmt.body:
                    ln2 = getattr(s, "line", 0) or 0
                    if ln2:
                        report.lines_executed.add(ln2)
                    interp.exec_stmt(s, interp.global_env)
            continue  # skip normal exec_stmt for while (already handled)

        result = interp.exec_stmt(stmt, interp.global_env)

    report.result = result
    summary = report.summary()
    return {
        "result": result,
        "lines_declared": sorted(report.lines_declared),
        "lines_executed": sorted(report.lines_executed),
        "branches": {
            str(line): {
                "kind": b.kind,
                "true_taken": b.true_taken,
                "false_taken": b.false_taken,
            }
            for line, b in report.branches.items()
        },
        "functions": {
            name: {"called": f.called, "calls": f.call_count}
            for name, f in report.functions.items()
        },
        "loops": {
            str(line): {"kind": l.kind, "iterations": l.iterations}
            for line, l in report.loops.items()
        },
        "summary": summary,
    }
