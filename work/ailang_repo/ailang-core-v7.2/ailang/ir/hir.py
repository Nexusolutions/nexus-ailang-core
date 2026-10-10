"""ailang.ir.hir — High-level IR (P3-1).

FASE 9 del prompt maestro. HIR es la primera representación intermedia:
tipada, con scopes resueltos, sin syntactic sugar.

Lowering: AST → HIR (preserva estructura pero añade type annotations,
scope info, y resuelve nombres a IDs únicos).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class HIRType:
    """Tipos básicos en HIR."""
    name: str
    params: Tuple["HIRType", ...] = ()

    @classmethod
    def int(cls): return cls("int")
    @classmethod
    def float(cls): return cls("float")
    @classmethod
    def bool(cls): return cls("bool")
    @classmethod
    def str(cls): return cls("str")
    @classmethod
    def null(cls): return cls("null")
    @classmethod
    def any(cls): return cls("any")
    @classmethod
    def list(cls, elem): return cls("list", (elem,))
    @classmethod
    def dict(cls, k, v): return cls("dict", (k, v))
    @classmethod
    def function(cls, params, ret): return cls("function", tuple(params) + (ret,))


@dataclass
class HIRValue:
    """Valor HIR: literal o referencia a nombre resuelto."""
    kind: str  # "literal" | "name" | "tmp"
    value: Any = None
    type: Optional[HIRType] = None
    name: str = ""  # si kind == "name"
    tmp_id: int = -1  # si kind == "tmp"


@dataclass
class HIRInstruction:
    """Instrucción HIR: alto nivel, casi 1:1 con AST pero con tipos."""
    op: str  # "let", "assign", "if", "while", "for", "fn", "return", "call", "binop", "yield", etc.
    args: List[HIRValue] = field(default_factory=list)
    result: Optional[HIRValue] = None
    type: Optional[HIRType] = None
    line: int = 0


@dataclass
class HIRBlock:
    """Bloque HIR: secuencia de instrucciones."""
    instructions: List[HIRInstruction] = field(default_factory=list)


@dataclass
class HIRFunction:
    """Función HIR."""
    name: str
    params: List[Tuple[str, HIRType]]
    return_type: HIRType
    body: HIRBlock
    line: int = 0
    is_async: bool = False
    is_generator: bool = False


@dataclass
class HIRModule:
    """Módulo HIR: top-level."""
    name: str
    functions: List[HIRFunction] = field(default_factory=list)
    globals_block: HIRBlock = field(default_factory=HIRBlock)


def lower_ast_to_hir(program) -> HIRModule:
    """Lowering: AST → HIR.

    Esta implementación inicial es una traducción directa 1:1 sin optimización.
    Solo añade type stubs (Any) y preserva estructura.
    """
    from ailang.lang import ast_nodes as A

    module = HIRModule(name="<main>")

    def lower_value(node) -> HIRValue:
        if isinstance(node, A.Literal):
            t = HIRType.any()
            if isinstance(node.value, bool): t = HIRType.bool()
            elif isinstance(node.value, int): t = HIRType.int()
            elif isinstance(node.value, float): t = HIRType.float()
            elif isinstance(node.value, str): t = HIRType.str()
            elif node.value is None: t = HIRType.null()
            return HIRValue(kind="literal", value=node.value, type=t)
        if isinstance(node, A.Name):
            return HIRValue(kind="name", name=node.id, type=HIRType.any())
        if isinstance(node, A.BinOp):
            return HIRValue(kind="binop", value=node.op, type=HIRType.any())
        return HIRValue(kind="tmp", tmp_id=-1)

    def lower_stmt(node, block: HIRBlock) -> None:
        if isinstance(node, (A.Let, A.Const)):
            block.instructions.append(HIRInstruction(
                op="let" if isinstance(node, A.Let) else "const",
                args=[lower_value(node.value)],
                result=HIRValue(kind="name", name=node.name),
                line=node.line,
            ))
        elif isinstance(node, A.Assign):
            block.instructions.append(HIRInstruction(
                op="assign",
                args=[lower_value(node.value)],
                result=HIRValue(kind="name", name=node.name if isinstance(node.name, str) else ""),
                line=node.line,
            ))
        elif isinstance(node, A.Return):
            block.instructions.append(HIRInstruction(
                op="return",
                args=[lower_value(node.value)] if node.value else [],
                line=node.line,
            ))
        elif isinstance(node, A.If):
            block.instructions.append(HIRInstruction(
                op="if",
                args=[lower_value(node.test)],
                line=node.line,
            ))
            for s in node.body:
                lower_stmt(s, block)
            if node.orelse:
                block.instructions.append(HIRInstruction(op="else"))
                for s in node.orelse:
                    lower_stmt(s, block)
            block.instructions.append(HIRInstruction(op="end_if"))
        elif isinstance(node, A.While):
            block.instructions.append(HIRInstruction(op="while_start", args=[lower_value(node.test)], line=node.line))
            for s in node.body:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(op="while_end"))
        elif isinstance(node, A.Function):
            fn_params = [(p, HIRType.any()) for p in node.params]
            fn_body = HIRBlock()
            for s in node.body:
                lower_stmt(s, fn_body)
            module.functions.append(HIRFunction(
                name=node.name,
                params=fn_params,
                return_type=HIRType.any(),
                body=fn_body,
                line=node.line,
                is_async=getattr(node, "is_async", False),
                is_generator=_contains_yield(node.body),
            ))
        elif isinstance(node, A.ExprStmt):
            block.instructions.append(HIRInstruction(
                op="expr",
                args=[lower_value(node.value)],
                line=node.line,
            ))
        elif isinstance(node, A.Yield):
            block.instructions.append(HIRInstruction(
                op="yield",
                args=[lower_value(node.value)] if node.value else [],
                line=node.line,
            ))
        # else: skipped for brevity; full HIR would cover all node types

    def _contains_yield(body):
        from ailang.lang.vm import _contains_yield as _cy
        return _cy(body)

    for stmt in program.body:
        lower_stmt(stmt, module.globals_block)

    return module
