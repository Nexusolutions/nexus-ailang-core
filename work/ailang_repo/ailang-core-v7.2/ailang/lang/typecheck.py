"""Type checker gradual/estricto de AILang (Nivel B).

- Anotaciones opcionales
- strict=True: errores duros
- Narrowing simple tras isinstance(x, "T")
- Tipos de función y listas List[T] básicos
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ailang.lang import ast_nodes as A
from ailang.lang.parser import parse


PRIMITIVES = {
    "null", "bool", "int", "float", "number", "string",
    "list", "dict", "function", "any", "class", "module",
}


@dataclass
class TypeDiagnostic:
    level: str
    message: str
    line: int = 0

    def __str__(self) -> str:
        loc = f"line {self.line}: " if self.line else ""
        return f"{self.level}: {loc}{self.message}"


@dataclass
class TypeEnv:
    types: Dict[str, str] = field(default_factory=dict)
    parent: Optional["TypeEnv"] = None
    classes: Set[str] = field(default_factory=set)

    def get(self, name: str) -> Optional[str]:
        if name in self.types:
            return self.types[name]
        if self.parent:
            return self.parent.get(name)
        return None

    def define(self, name: str, ty: str) -> None:
        self.types[name] = ty

    def child(self) -> "TypeEnv":
        return TypeEnv(parent=self, classes=set(self.classes))


def _normalize(ty: Optional[str]) -> str:
    if not ty:
        return "any"
    t = ty.strip()
    # List[int] -> list
    if t.startswith("List[") or t.startswith("list["):
        return "list"
    if t.startswith("Dict[") or t.startswith("dict["):
        return "dict"
    t = t.lower()
    if t in ("num", "numeric"):
        return "number"
    if t in ("str", "text"):
        return "string"
    return t


def _compatible(got: str, expected: str) -> bool:
    g, e = _normalize(got), _normalize(expected)
    if e == "any" or g == "any":
        return True
    if g == e:
        return True
    if e == "number" and g in ("int", "float", "number"):
        return True
    if e in ("int", "float") and g == "number":
        return True
    return False


def _infer_expr(node: Any, env: TypeEnv) -> str:
    if isinstance(node, A.Literal):
        v = node.value
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int) and not isinstance(v, bool):
            return "int"
        if isinstance(v, float):
            return "float"
        if isinstance(v, str):
            return "string"
        return "any"
    if isinstance(node, A.Name):
        return env.get(node.id) or "any"
    if isinstance(node, A.ListLit):
        return "list"
    if isinstance(node, A.DictLit):
        return "dict"
    if isinstance(node, A.Lambda):
        return "function"
    if isinstance(node, A.Call):
        # isinstance(x, "T") → bool; type(x) → string
        if isinstance(node.func, A.Name) and node.func.id == "isinstance":
            return "bool"
        if isinstance(node.func, A.Name) and node.func.id == "type":
            return "string"
        return "any"
    if isinstance(node, A.BinOp):
        if node.op in ("==", "!=", "<", "<=", ">", ">=", "and", "or"):
            return "bool"
        if node.op == "+":
            lt, rt = _infer_expr(node.left, env), _infer_expr(node.right, env)
            if lt == "string" or rt == "string":
                return "string"
            if lt in ("int", "float", "number") and rt in ("int", "float", "number"):
                return "float" if "float" in (lt, rt) else "int"
            return "any"
        return "number"
    if isinstance(node, A.UnaryOp):
        return "bool" if node.op == "not" else _infer_expr(node.operand, env)
    return "any"


class TypeChecker:
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.diagnostics: List[TypeDiagnostic] = []

    def _diag(self, level: str, msg: str, line: int = 0) -> None:
        if level == "warning" and self.strict:
            level = "error"
        self.diagnostics.append(TypeDiagnostic(level, msg, line))

    def check_source(self, source: str) -> List[TypeDiagnostic]:
        self.diagnostics = []
        program = parse(source)
        env = TypeEnv()
        for stmt in program.body:
            self._check_stmt(stmt, env)
        return list(self.diagnostics)

    def _narrow_isinstance(self, node: Any, env: TypeEnv) -> Optional[TypeEnv]:
        """Si test es isinstance(name, \"T\"), devuelve env hijo con name: T."""
        if not isinstance(node, A.Call):
            return None
        if not (isinstance(node.func, A.Name) and node.func.id == "isinstance"):
            return None
        if len(node.args) < 2:
            return None
        if not isinstance(node.args[0], A.Name):
            return None
        ty_node = node.args[1]
        if isinstance(ty_node, A.Literal) and isinstance(ty_node.value, str):
            ty = _normalize(ty_node.value)
        elif isinstance(ty_node, A.Name):
            ty = _normalize(ty_node.id)
        else:
            return None
        child = env.child()
        child.define(node.args[0].id, ty)
        return child

    def _check_stmt(self, node: Any, env: TypeEnv) -> None:
        if isinstance(node, A.Let):
            inferred = _infer_expr(node.value, env)
            ann = _normalize(node.type_ann) if node.type_ann else "any"
            if node.type_ann and not _compatible(inferred, ann):
                self._diag(
                    "error",
                    f"'{node.name}' anotado como {ann} pero se infiere {inferred}",
                    node.line,
                )
            env.define(node.name, ann if node.type_ann else inferred)
        elif isinstance(node, A.Assign):
            if isinstance(node.name, str):
                expected = env.get(node.name)
                got = _infer_expr(node.value, env)
                if expected and expected != "any" and not _compatible(got, expected):
                    self._diag(
                        "warning",
                        f"asignación a '{node.name}': se esperaba {expected}, se infiere {got}",
                        node.line,
                    )
        elif isinstance(node, A.Function):
            local = env.child()
            for p in node.params:
                local.define(p, "any")
            for s in node.body:
                self._check_stmt(s, local)
            env.define(node.name, "function")
        elif isinstance(node, A.ClassDef):
            env.classes.add(node.name)
            env.define(node.name, "class")
            local = env.child()
            local.define("self", node.name)
            for m in node.methods:
                self._check_stmt(m, local)
        elif isinstance(node, A.If):
            then_env = self._narrow_isinstance(node.test, env) or env.child()
            for s in node.body:
                self._check_stmt(s, then_env)
            for s in node.orelse:
                self._check_stmt(s, env.child())
        elif isinstance(node, A.While):
            for s in node.body:
                self._check_stmt(s, env.child())
        elif isinstance(node, A.For):
            local = env.child()
            local.define(node.target, "any")
            for s in node.body:
                self._check_stmt(s, local)
        elif isinstance(node, A.Block):
            local = env.child()
            for s in node.body:
                self._check_stmt(s, local)
        elif isinstance(node, A.Return) and node.value is not None:
            _infer_expr(node.value, env)
        elif isinstance(node, A.ExprStmt):
            _infer_expr(node.value, env)
        elif isinstance(node, A.Try):
            for s in node.body:
                self._check_stmt(s, env.child())
            local = env.child()
            local.define(node.catch_name, "any")
            for s in node.catch_body:
                self._check_stmt(s, local)


def typecheck(source: str, *, strict: bool = False) -> List[TypeDiagnostic]:
    return TypeChecker(strict=strict).check_source(source)
