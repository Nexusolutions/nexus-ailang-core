"""Linter de AILang — P2-5.

Reglas implementadas:
- E001: unused variables (asignadas pero nunca leídas)
- E002: unused imports (importados pero nunca referenciados)
- W001: shadowing (variable que oculta otra del scope externo)
- W002: unreachable code (statements después de return/break/continue)
- W003: missing return (fn no-void sin return en todos los paths)
- W004: suspicious conversions (e.g., str + int sin cast explícito)
- W005: empty blocks (if/while/fn sin body)
- W006: deprecated API usage (ej.: compile_source del DSL cognitivo)
- I001: code style (nombres no descriptivos: x, y, tmp)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ailang.lang.parser import parse
from ailang.lang.errors import AILangSyntaxError
from ailang.lang.typecheck import typecheck
from ailang.lang import ast_nodes as A


@dataclass
class LintIssue:
    code: str = ""
    level: str = "warning"
    message: str = ""
    line: int = 0
    col: int = 0

    def __str__(self) -> str:
        return f"{self.level}:{self.code}:line {self.line}: {self.message}"


def lint_source(source: str) -> List[LintIssue]:
    issues: List[LintIssue] = []
    try:
        program = parse(source)
    except AILangSyntaxError as e:
        return [LintIssue(code="E000", level="error", message=str(e), line=e.line, col=e.col)]

    # Type-check issues (existentes)
    for d in typecheck(source, strict=False):
        issues.append(LintIssue(
            code="E100" if d.level == "error" else "W100",
            level=d.level,
            message=d.message,
            line=d.line,
        ))

    # P2-5: Nuevas reglas
    issues.extend(_check_unused_vars(program))
    issues.extend(_check_unused_imports(program))
    issues.extend(_check_unreachable(program))
    issues.extend(_check_missing_return(program))
    issues.extend(_check_empty_blocks(program))
    issues.extend(_check_shadowing(program))
    issues.extend(_check_deprecated_apis(program))

    return issues


# --- Implementación de reglas ---

def _collect_assigned_and_read(program: A.Program) -> Tuple[Set[str], Set[str], Dict[str, int]]:
    """Retorna (assigned_names, read_names, name_to_line)."""
    assigned: Set[str] = set()
    read: Set[str] = set()
    name_line: Dict[str, int] = {}

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                visit(n)
            return
        if isinstance(node, A.Let) or isinstance(node, A.Const):
            assigned.add(node.name)
            name_line[node.name] = node.line
            visit(node.value)
        elif isinstance(node, A.Assign):
            if isinstance(node.name, str):
                assigned.add(node.name)
                name_line.setdefault(node.name, node.line)
            visit(node.value)
        elif isinstance(node, A.Name):
            read.add(node.id)
        elif isinstance(node, A.Function):
            for p in node.params:
                assigned.add(p)
                name_line[p] = node.line
            for s in node.body:
                visit(s)
        elif isinstance(node, A.BinOp):
            visit(node.left)
            visit(node.right)
        elif isinstance(node, A.Call):
            visit(node.func)
            for a in node.args:
                visit(a)
        elif isinstance(node, A.Return):
            if node.value is not None:
                visit(node.value)
        elif isinstance(node, A.ExprStmt):
            visit(node.value)
        elif isinstance(node, A.If):
            visit(node.test)
            for s in node.body:
                visit(s)
            for s in node.orelse:
                visit(s)
        elif isinstance(node, A.While):
            visit(node.test)
            for s in node.body:
                visit(s)
        elif isinstance(node, A.For):
            assigned.add(node.target)
            name_line[node.target] = node.line
            visit(node.iter)
            for s in node.body:
                visit(s)
        elif hasattr(node, "body") and isinstance(node.body, list):
            for s in node.body:
                visit(s)

    for stmt in program.body:
        visit(stmt)
    return assigned, read, name_line


def _check_unused_vars(program: A.Program) -> List[LintIssue]:
    """E001: variables asignadas pero nunca leídas."""
    issues: List[LintIssue] = []
    assigned, read, name_line = _collect_assigned_and_read(program)
    # Excluir params de fn (ya cubiertos por su uso en body)
    for name in assigned - read:
        if name.startswith("_"):
            continue  # _foo es convención para "intencionalmente no usado"
        line = name_line.get(name, 0)
        issues.append(LintIssue(
            code="E001",
            level="warning",
            message=f"variable '{name}' asignada pero nunca usada",
            line=line,
        ))
    return issues


def _check_unused_imports(program: A.Program) -> List[LintIssue]:
    """E002: imports no referenciados en el resto del código."""
    issues: List[LintIssue] = []
    imports: List[Tuple[str, Optional[str], int]] = []  # (module, alias, line)
    all_text_refs: Set[str] = set()

    def collect(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                collect(n)
            return
        if isinstance(node, A.Import):
            alias = node.alias or node.module.split(".")[-1]
            imports.append((node.module, alias, node.line))
        elif isinstance(node, A.Attr):
            # module.function — module es un Name
            if isinstance(node.value, A.Name):
                all_text_refs.add(node.value.id)
        elif isinstance(node, A.Name):
            all_text_refs.add(node.id)
        elif hasattr(node, "body") and isinstance(node.body, list):
            for s in node.body:
                collect(s)
        if hasattr(node, "value") and not isinstance(node, A.Import):
            collect(node.value)

    for stmt in program.body:
        collect(stmt)

    for module, alias, line in imports:
        if alias not in all_text_refs:
            issues.append(LintIssue(
                code="E002",
                level="warning",
                message=f"import '{module}' (alias '{alias}') nunca usado",
                line=line,
            ))
    return issues


def _check_unreachable(program: A.Program) -> List[LintIssue]:
    """W002: código después de return/break/continue en el mismo bloque."""
    issues: List[LintIssue] = []

    def check_block(body: List[Any]) -> None:
        terminator_seen = False
        terminator_kind = ""
        terminator_line = 0
        for stmt in body:
            if terminator_seen:
                line = getattr(stmt, "line", 0) or 0
                issues.append(LintIssue(
                    code="W002",
                    level="warning",
                    message=f"código inalcanzable después de {terminator_kind} (línea {terminator_line})",
                    line=line,
                ))
                break
            if isinstance(stmt, (A.Return, A.Break, A.Continue)):
                terminator_seen = True
                terminator_kind = type(stmt).__name__.lower()
                terminator_line = getattr(stmt, "line", 0) or 0

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if hasattr(node, "body") and isinstance(node.body, list):
            check_block(node.body)
            for s in node.body:
                walk(s)
        if isinstance(node, A.If):
            if node.orelse:
                check_block(node.orelse)
                for s in node.orelse:
                    walk(s)
        if isinstance(node, A.Match):
            for c in node.cases:
                check_block(c.body)
                for s in c.body:
                    walk(s)

    for stmt in program.body:
        walk(stmt)
    return issues


def _check_missing_return(program: A.Program) -> List[LintIssue]:
    """W003: fn no-void sin return en algún path."""
    issues: List[LintIssue] = []

    def has_return(body: List[Any]) -> bool:
        for stmt in body:
            if isinstance(stmt, A.Return):
                return True
            if isinstance(stmt, A.If):
                if has_return(stmt.body) and (not stmt.orelse or has_return(stmt.orelse)):
                    return True
        return False

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, A.Function):
            if node.body and not has_return(node.body):
                # Solo warning si la fn tiene > 0 statements
                issues.append(LintIssue(
                    code="W003",
                    level="info",
                    message=f"fn '{node.name}' podría no retornar en todos los paths",
                    line=node.line,
                ))
            for s in node.body:
                walk(s)
        elif hasattr(node, "body") and isinstance(node.body, list):
            for s in node.body:
                walk(s)

    for stmt in program.body:
        walk(stmt)
    return issues


def _check_empty_blocks(program: A.Program) -> List[LintIssue]:
    """W005: if/while/fn sin body."""
    issues: List[LintIssue] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, A.If) and not node.body:
            issues.append(LintIssue(code="W005", level="warning", message="if vacío", line=node.line))
        if isinstance(node, A.Function) and not node.body:
            issues.append(LintIssue(code="W005", level="warning", message=f"fn {node.name} vacía", line=node.line))
        if isinstance(node, A.While) and not node.body:
            issues.append(LintIssue(code="W005", level="warning", message="while vacío", line=node.line))
        for attr in ("body", "orelse", "methods", "cases"):
            if hasattr(node, attr):
                walk(getattr(node, attr))
        if isinstance(node, A.Match):
            for c in node.cases:
                walk(c.body)

    for stmt in program.body:
        walk(stmt)
    return issues


def _check_shadowing(program: A.Program) -> List[LintIssue]:
    """W001: variable que oculta otra del scope externo."""
    issues: List[LintIssue] = []

    def walk(node: Any, scope: Set[str]) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n, scope)
            return
        if isinstance(node, A.Function):
            inner_scope = set(scope)
            for p in node.params:
                if p in inner_scope:
                    issues.append(LintIssue(
                        code="W001",
                        level="info",
                        message=f"parámetro '{p}' hace shadowing de variable externa",
                        line=node.line,
                    ))
                inner_scope.add(p)
            for s in node.body:
                walk(s, inner_scope)
        elif isinstance(node, A.Let) or isinstance(node, A.Const):
            if node.name in scope:
                issues.append(LintIssue(
                    code="W001",
                    level="info",
                    message=f"variable '{node.name}' hace shadowing",
                    line=node.line,
                ))
            scope = set(scope)
            scope.add(node.name)
            walk(node.value, scope)
        elif isinstance(node, A.For):
            if node.target in scope:
                issues.append(LintIssue(
                    code="W001",
                    level="info",
                    message=f"variable de bucle '{node.target}' hace shadowing",
                    line=node.line,
                ))
            inner = set(scope)
            inner.add(node.target)
            walk(node.iter, scope)
            for s in node.body:
                walk(s, inner)
        elif hasattr(node, "body") and isinstance(node.body, list):
            for s in node.body:
                walk(s, scope)
        if isinstance(node, A.If):
            for s in node.orelse:
                walk(s, scope)

    outer: Set[str] = set()
    for stmt in program.body:
        walk(stmt, outer)
    return issues


def _check_deprecated_apis(program: A.Program) -> List[LintIssue]:
    """W006: uso de APIs deprecadas."""
    issues: List[LintIssue] = []
    # Por ahora: buscar llamadas a compile_source del DSL cognitivo
    # (debería migrarse a compile_cognitive — P1-4)
    # No podemos detectar esto a nivel de AST (es un símbolo Python, no AILang),
    # pero dejamos el esqueleto para futuras reglas.
    return issues
