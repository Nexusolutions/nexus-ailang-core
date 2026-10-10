"""ailang.semantic.effects — Effect checker (P3-8).

FASE 11 del prompt maestro: cada función declara o infiere sus effects.

Effects soportados:
  pure        — sin side effects (default)
  io          — entrada/salida estándar (print, readline)
  filesystem  — lee/escribe archivos
  network     — hace llamadas de red (http)
  ai          — invoca brain.* o llamadas cognitivas
  hardware    — usa GPU/NPU/TPU
  process     — spawnea procesos
  unsafe      — operación insegura sin categorizar
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from ailang.lang import ast_nodes as A
from ailang.lang.parser import parse


EFFECTS: Set[str] = {"pure", "io", "filesystem", "network", "ai", "hardware", "process", "unsafe"}

BUILTIN_EFFECTS: Dict[str, Set[str]] = {
    "print": {"io"},
    "range": {"pure"}, "len": {"pure"}, "str": {"pure"}, "int": {"pure"},
    "float": {"pure"}, "type": {"pure"}, "isinstance": {"pure"},
    "implements": {"pure"}, "channel": {"pure"}, "iter": {"pure"}, "next": {"pure"},
}

STD_MODULE_EFFECTS: Dict[str, Dict[str, Set[str]]] = {
    "io": {"read_text": {"filesystem"}, "write_text": {"filesystem"},
            "exists": {"filesystem"}, "lines": {"filesystem"}},
    "math": {"abs": {"pure"}, "min": {"pure"}, "max": {"pure"}, "sqrt": {"pure"},
              "pow": {"pure"}, "floor": {"pure"}, "ceil": {"pure"}},
    "strings": {"upper": {"pure"}, "lower": {"pure"}, "len": {"pure"}, "contains": {"pure"}},
    "json": {"loads": {"pure"}, "dumps": {"pure"}},
    "http": {"get": {"network"}, "post": {"network"}, "json_get": {"network"}},
    "time": {"now": {"io"}, "sleep": {"io"}, "format_ts": {"pure"}, "monotonic": {"io"}},
    "sys": {"argv": {"pure"}, "exit": {"process"}, "getenv": {"pure"},
             "platform": {"pure"}, "version": {"pure"}, "stderr_write": {"io"}},
    "path": {"join": {"pure"}, "exists": {"filesystem"}, "basename": {"pure"}, "dirname": {"pure"}},
    "random": {"seed": {"io"}, "random": {"pure"}, "randint": {"pure"}, "choice": {"pure"}},
    "listops": {"map": {"pure"}, "filter": {"pure"}, "reduce": {"pure"},
                 "sum": {"pure"}, "sorted": {"pure"}},
    "re": {"search": {"pure"}, "match": {"pure"}, "findall": {"pure"},
            "sub": {"pure"}, "split": {"pure"}},
    "brain": {"ingest": {"ai", "filesystem"}, "query": {"ai"},
               "think": {"ai"}, "graph": {"ai"}},
}


@dataclass
class EffectIssue:
    code: str
    level: str
    message: str
    line: int = 0
    fn_name: str = ""


def infer_effects(program: A.Program) -> Dict[str, Set[str]]:
    """Infiere los efectos de cada función del programa."""
    fn_effects: Dict[str, Set[str]] = {}

    def infer_fn(fn: A.Function) -> Set[str]:
        effects: Set[str] = set()
        if getattr(fn, "is_async", False):
            effects.add("process")
        _walk_for_effects(fn.body, effects, fn_effects)
        if not effects:
            effects.add("pure")
        return effects

    def _walk_for_effects(body: List[Any], effects: Set[str],
                          known_fns: Dict[str, Set[str]]) -> None:
        for node in body:
            if isinstance(node, list):
                _walk_for_effects(node, effects, known_fns)
                continue
            if isinstance(node, A.Call):
                _infer_call_effects(node, effects, known_fns)
            if isinstance(node, A.Spawn):
                effects.add("process")
            # Visitar value de Return/Let/Const/Assign/ExprStmt
            if isinstance(node, (A.Return, A.Let, A.Const, A.Assign, A.ExprStmt)):
                if hasattr(node, "value") and node.value is not None:
                    _walk_expr_for_effects(node.value, effects, known_fns)
            if hasattr(node, "body") and isinstance(node.body, list):
                _walk_for_effects(node.body, effects, known_fns)
            if isinstance(node, A.If):
                _walk_for_effects(node.orelse, effects, known_fns)
            if isinstance(node, A.Try):
                _walk_for_effects(node.catch_body, effects, known_fns)

    def _walk_expr_for_effects(expr: Any, effects: Set[str],
                                known_fns: Dict[str, Set[str]]) -> None:
        """Recorre expresiones buscando llamadas a functions/builtins con effects."""
        if isinstance(expr, A.Call):
            _infer_call_effects(expr, effects, known_fns)
            # Visitar args recursivamente (puede haber calls anidadas)
            for arg in expr.args:
                _walk_expr_for_effects(arg, effects, known_fns)
        elif isinstance(expr, A.BinOp):
            _walk_expr_for_effects(expr.left, effects, known_fns)
            _walk_expr_for_effects(expr.right, effects, known_fns)
        elif isinstance(expr, A.UnaryOp):
            _walk_expr_for_effects(expr.operand, effects, known_fns)
        elif isinstance(expr, A.Attr):
            _walk_expr_for_effects(expr.value, effects, known_fns)
        elif isinstance(expr, A.Index):
            _walk_expr_for_effects(expr.value, effects, known_fns)
            _walk_expr_for_effects(expr.index, effects, known_fns)
        elif isinstance(expr, A.ListLit):
            for e in expr.elts:
                _walk_expr_for_effects(e, effects, known_fns)
        elif isinstance(expr, A.DictLit):
            for k, v in zip(expr.keys, expr.values):
                _walk_expr_for_effects(k, effects, known_fns)
                _walk_expr_for_effects(v, effects, known_fns)
        elif isinstance(expr, A.Await):
            _walk_expr_for_effects(expr.value, effects, known_fns)
            effects.add("process")
        elif isinstance(expr, A.InterpolatedString):
            for part in expr.parts:
                if not isinstance(part, str):
                    _walk_expr_for_effects(part, effects, known_fns)

    def _infer_call_effects(call: A.Call, effects: Set[str],
                             known_fns: Dict[str, Set[str]]) -> None:
        if isinstance(call.func, A.Name):
            name = call.func.id
            if name in BUILTIN_EFFECTS:
                effects.update(BUILTIN_EFFECTS[name])
            elif name in known_fns:
                effects.update(known_fns[name])
        elif isinstance(call.func, A.Attr):
            # module.function() o instance.method()
            if isinstance(call.func.value, A.Name):
                mod_name = call.func.value.id
                fn_name = call.func.attr
                if mod_name in STD_MODULE_EFFECTS and fn_name in STD_MODULE_EFFECTS[mod_name]:
                    effects.update(STD_MODULE_EFFECTS[mod_name][fn_name])
                # También: si el "mod_name" es en realidad una variable local
                # que apunta a una fn (raro pero posible), no lo detectamos
                # aquí; se cubre con la 2da pasada de propagación.

    for stmt in program.body:
        if isinstance(stmt, A.Function):
            fn_effects[stmt.name] = infer_fn(stmt)
    return fn_effects


def check_effects(program: A.Program, fn_effects: Dict[str, Set[str]]) -> List[EffectIssue]:
    """Verifica que cada caller declara los efectos de sus callees."""
    issues: List[EffectIssue] = []

    def check_fn(fn: A.Function) -> None:
        my_effects = fn_effects.get(fn.name, {"pure"})
        if my_effects == {"pure"}:
            for callee, callee_effects in _collect_callees(fn.body, fn_effects):
                if callee_effects - {"pure"}:
                    issues.append(EffectIssue(
                        code="E110",
                        level="error",
                        message=(
                            f"fn '{fn.name}' declarada pure pero llama a "
                            f"'{callee}' con efectos {callee_effects - {'pure'}}"
                        ),
                        line=fn.line,
                        fn_name=fn.name,
                    ))
        else:
            for callee, callee_effects in _collect_callees(fn.body, fn_effects):
                missing = callee_effects - my_effects
                if missing:
                    issues.append(EffectIssue(
                        code="W110",
                        level="warning",
                        message=(
                            f"fn '{fn.name}' con efectos {my_effects} llama a "
                            f"'{callee}' con efectos {callee_effects}; "
                            f"missing: {missing}"
                        ),
                        line=fn.line,
                        fn_name=fn.name,
                    ))

    for stmt in program.body:
        if isinstance(stmt, A.Function):
            check_fn(stmt)
    return issues


def _collect_callees(body: List[Any], known_fns: Dict[str, Set[str]]) -> List[tuple]:
    """Retorna lista de (callee_name, callee_effects) para todas las llamadas en body."""
    callees: List[tuple] = []
    seen: Set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                visit(n)
            return
        if isinstance(node, A.Call):
            if isinstance(node.func, A.Name):
                name = node.func.id
                if name in known_fns and name not in seen:
                    seen.add(name)
                    callees.append((name, known_fns[name]))
        if hasattr(node, "body") and isinstance(node.body, list):
            visit(node.body)
        if isinstance(node, A.If):
            visit(node.orelse)
        if isinstance(node, A.Try):
            visit(node.catch_body)

    visit(body)
    return callees


def check_source(source: str) -> List[EffectIssue]:
    """API de conveniencia: parsea + infiere + verifica."""
    try:
        program = parse(source)
    except Exception as e:
        return [EffectIssue(code="E000", level="error", message=f"parse error: {e}")]
    fn_effects = infer_effects(program)
    return check_effects(program, fn_effects)
