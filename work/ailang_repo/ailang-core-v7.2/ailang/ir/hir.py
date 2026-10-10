"""ailang.ir.hir — High-level IR (P3-1, T1).

FASE 9 del prompt maestro. HIR es la primera representación intermedia:
tipada, con scopes resueltos, sin syntactic sugar.

T1: Expressions are now decomposed into stack-based instructions
(LOAD_CONST, LOAD_NAME, BINARY_OP, CALL, etc.) that the AIR interpreter
can execute directly without delegating to the VM.

Lowering: AST → HIR (decomposed into executable stack instructions)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Opcode names for HIR (matching VM opcodes for direct execution)
HIR_LOAD_CONST = "LOAD_CONST"
HIR_LOAD_NAME = "LOAD_NAME"
HIR_STORE_NAME = "STORE_NAME"
HIR_DEFINE_NAME = "DEFINE_NAME"
HIR_BINARY_OP = "BINARY_OP"
HIR_UNARY_OP = "UNARY_OP"
HIR_CALL = "CALL"
HIR_RETURN = "RETURN"
HIR_JUMP = "JUMP"
HIR_JUMP_IF_FALSE = "JUMP_IF_FALSE"
HIR_POP = "POP"
HIR_MAKE_FUNCTION = "MAKE_FUNCTION"
HIR_EXPR = "EXPR"  # pop top of stack (expression statement)


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
class HIRInstruction:
    """Instrucción HIR: stack-based, executable.

    T1: opcodes are now LOAD_CONST, LOAD_NAME, BINARY_OP, etc.
    (matching VM opcodes) so the AIR interpreter can execute directly.
    """
    op: str  # HIR_LOAD_CONST, HIR_LOAD_NAME, HIR_BINARY_OP, etc.
    args: List[Any] = field(default_factory=list)
    result: Optional[str] = None  # for STORE_NAME/DEFINE_NAME
    type: Optional[HIRType] = None
    line: int = 0


@dataclass
class HIRBlock:
    """Bloque HIR: secuencia de instrucciones ejecutables."""
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
    """Lowering: AST → HIR con decomposición de expresiones (T1).

    Cada expresión se descompone en instrucciones stack-based:
      1 + 2 * 3 → LOAD_CONST 1, LOAD_CONST 2, LOAD_CONST 3, BINARY_OP *, BINARY_OP +

    Esto permite que el AIR interpreter ejecute directamente sin VM.
    """
    from ailang.lang import ast_nodes as A

    module = HIRModule(name="<main>")

    def lower_expr(node, block: HIRBlock) -> None:
        """Emite instrucciones para evaluar una expresión y dejar el resultado en stack."""
        if isinstance(node, A.Literal):
            block.instructions.append(HIRInstruction(
                op=HIR_LOAD_CONST, args=[node.value], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.Name):
            block.instructions.append(HIRInstruction(
                op=HIR_LOAD_NAME, args=[node.id], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.BinOp):
            lower_expr(node.left, block)
            lower_expr(node.right, block)
            block.instructions.append(HIRInstruction(
                op=HIR_BINARY_OP, args=[node.op], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.UnaryOp):
            lower_expr(node.operand, block)
            block.instructions.append(HIRInstruction(
                op=HIR_UNARY_OP, args=[node.op], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.Call):
            lower_expr(node.func, block)
            for arg in node.args:
                lower_expr(arg, block)
            block.instructions.append(HIRInstruction(
                op=HIR_CALL, args=[len(node.args)], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.Attr):
            lower_expr(node.value, block)
            # LOAD_ATTR is handled by AIR interpreter via LOAD_NAME + property access
            # For now, push attr name as const and use a LOAD_ATTR opcode
            block.instructions.append(HIRInstruction(
                op="LOAD_ATTR", args=[node.attr], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.ListLit):
            for e in node.elts:
                lower_expr(e, block)
            block.instructions.append(HIRInstruction(
                op="BUILD_LIST", args=[len(node.elts)], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.DictLit):
            for k, v in zip(node.keys, node.values):
                lower_expr(k, block)
                lower_expr(v, block)
            block.instructions.append(HIRInstruction(
                op="BUILD_DICT", args=[len(node.keys)], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.Index):
            lower_expr(node.value, block)
            lower_expr(node.index, block)
            block.instructions.append(HIRInstruction(
                op="GET_ITEM", args=[], line=getattr(node, "line", 0),
            ))
        elif isinstance(node, A.Lambda):
            # Lower lambda body as a nested function
            fn_body = HIRBlock()
            for s in node.body:
                lower_stmt(s, fn_body)
            fn_body.instructions.append(HIRInstruction(op=HIR_LOAD_CONST, args=[None]))
            fn_body.instructions.append(HIRInstruction(op=HIR_RETURN))
            # Store the function body as a constant for MAKE_FUNCTION
            block.instructions.append(HIRInstruction(
                op=HIR_LOAD_CONST, args=[("lambda_code", tuple(node.params), fn_body)],
                line=getattr(node, "line", 0),
            ))
            block.instructions.append(HIRInstruction(
                op=HIR_MAKE_FUNCTION, args=["<lambda>", tuple(node.params), False],
                line=getattr(node, "line", 0),
            ))
        else:
            # Fallback: push None for unsupported expression types
            block.instructions.append(HIRInstruction(
                op=HIR_LOAD_CONST, args=[None], line=getattr(node, "line", 0),
            ))

    def lower_stmt(node, block: HIRBlock) -> None:
        if isinstance(node, (A.Let, A.Const)):
            lower_expr(node.value, block)
            block.instructions.append(HIRInstruction(
                op=HIR_DEFINE_NAME, result=node.name, line=node.line,
            ))
        elif isinstance(node, A.Assign):
            lower_expr(node.value, block)
            if isinstance(node.name, str):
                block.instructions.append(HIRInstruction(
                    op=HIR_STORE_NAME, result=node.name, line=node.line,
                ))
            elif isinstance(node.name, A.Attr):
                lower_expr(node.name.value, block)
                block.instructions.append(HIRInstruction(
                    op="STORE_ATTR", args=[node.name.attr], line=node.line,
                ))
        elif isinstance(node, A.Return):
            if node.value is not None:
                lower_expr(node.value, block)
            else:
                block.instructions.append(HIRInstruction(op=HIR_LOAD_CONST, args=[None]))
            block.instructions.append(HIRInstruction(op=HIR_RETURN, line=node.line))
        elif isinstance(node, A.ExprStmt):
            lower_expr(node.value, block)
            # Pop the result (expression statement discards result)
            block.instructions.append(HIRInstruction(op=HIR_POP, line=node.line))
        elif isinstance(node, A.If):
            lower_expr(node.test, block)
            # Placeholder: in a full implementation, we'd use JUMP_IF_FALSE
            # to skip the body. For now, we emit a marker.
            block.instructions.append(HIRInstruction(
                op=HIR_JUMP_IF_FALSE, args=["__else__"], line=node.line,
            ))
            for s in node.body:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(
                op=HIR_JUMP, args=["__end__"], line=node.line,
            ))
            block.instructions.append(HIRInstruction(op="LABEL", args=["__else__"]))
            for s in node.orelse:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(op="LABEL", args=["__end__"]))
        elif isinstance(node, A.While):
            block.instructions.append(HIRInstruction(op="LABEL", args=["__while_start__"]))
            lower_expr(node.test, block)
            block.instructions.append(HIRInstruction(
                op=HIR_JUMP_IF_FALSE, args=["__while_end__"], line=node.line,
            ))
            for s in node.body:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(
                op=HIR_JUMP, args=["__while_start__"], line=node.line,
            ))
            block.instructions.append(HIRInstruction(op="LABEL", args=["__while_end__"]))
        elif isinstance(node, A.For):
            lower_expr(node.iter, block)
            block.instructions.append(HIRInstruction(
                op=HIR_DEFINE_NAME, result="__it", line=node.line,
            ))
            block.instructions.append(HIRInstruction(op="LABEL", args=["__for_start__"]))
            block.instructions.append(HIRInstruction(op=HIR_LOAD_NAME, args=["next"]))
            block.instructions.append(HIRInstruction(op=HIR_LOAD_NAME, args=["__it"]))
            block.instructions.append(HIRInstruction(op=HIR_CALL, args=[1]))
            block.instructions.append(HIRInstruction(
                op=HIR_DEFINE_NAME, result=node.target, line=node.line,
            ))
            for s in node.body:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(op=HIR_JUMP, args=["__for_start__"]))
            block.instructions.append(HIRInstruction(op="LABEL", args=["__for_end__"]))
        elif isinstance(node, A.Function):
            fn_params = [(p, HIRType.any()) for p in node.params]
            fn_body = HIRBlock()
            for s in node.body:
                lower_stmt(s, fn_body)
            # Ensure every function ends with RETURN
            if not fn_body.instructions or fn_body.instructions[-1].op != HIR_RETURN:
                fn_body.instructions.append(HIRInstruction(op=HIR_LOAD_CONST, args=[None]))
                fn_body.instructions.append(HIRInstruction(op=HIR_RETURN))
            module.functions.append(HIRFunction(
                name=node.name,
                params=fn_params,
                return_type=HIRType.any(),
                body=fn_body,
                line=node.line,
                is_async=getattr(node, "is_async", False),
                is_generator=_contains_yield(node.body),
            ))
        elif isinstance(node, A.Yield):
            if node.value is not None:
                lower_expr(node.value, block)
            else:
                block.instructions.append(HIRInstruction(op=HIR_LOAD_CONST, args=[None]))
            block.instructions.append(HIRInstruction(op="YIELD", line=node.line))
        elif isinstance(node, A.Import):
            block.instructions.append(HIRInstruction(
                op="IMPORT_MODULE", args=[node.module, node.alias], line=node.line,
            ))
        elif isinstance(node, A.Throw):
            lower_expr(node.value, block)
            block.instructions.append(HIRInstruction(op="THROW", line=node.line))
        elif isinstance(node, A.Try):
            block.instructions.append(HIRInstruction(
                op="SETUP_CATCH", args=["__catch__"], line=node.line,
            ))
            for s in node.body:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(op="POP_CATCH"))
            block.instructions.append(HIRInstruction(op=HIR_JUMP, args=["__try_end__"]))
            block.instructions.append(HIRInstruction(op="LABEL", args=["__catch__"]))
            block.instructions.append(HIRInstruction(
                op=HIR_DEFINE_NAME, result=node.catch_name, line=node.line,
            ))
            for s in node.catch_body:
                lower_stmt(s, block)
            block.instructions.append(HIRInstruction(op="LABEL", args=["__try_end__"]))
        elif isinstance(node, A.Break):
            block.instructions.append(HIRInstruction(op="BREAK", line=node.line))
        elif isinstance(node, A.Continue):
            block.instructions.append(HIRInstruction(op="CONTINUE", line=node.line))

    def _contains_yield(body):
        from ailang.lang.vm import _contains_yield as _cy
        return _cy(body)

    for stmt in program.body:
        lower_stmt(stmt, module.globals_block)

    # T1: Asegurar que el globals_block retorna el último valor
    # (como hace la VM con __last__)
    if module.globals_block.instructions:
        last = module.globals_block.instructions[-1]
        # Si el último statement fue un ExprStmt (termina en POP),
        # reemplazar el POP con un RETURN del valor.
        if last.op == HIR_POP:
            module.globals_block.instructions.pop()  # remove POP
            module.globals_block.instructions.append(HIRInstruction(op=HIR_RETURN))
        elif last.op != HIR_RETURN:
            # Si no termina en RETURN ni en POP, añadir RETURN None
            module.globals_block.instructions.append(HIRInstruction(op=HIR_LOAD_CONST, args=[None]))
            module.globals_block.instructions.append(HIRInstruction(op=HIR_RETURN))

    return module
