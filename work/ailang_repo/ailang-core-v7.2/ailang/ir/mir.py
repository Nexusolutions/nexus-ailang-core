"""ailang.ir.mir — Mid-level IR (P3-1).

FASE 9 del prompt maestro. MIR es la representación optimizable:
- Forma SSA-lite (cada asignación crea una nueva versión)
- CFG explícito (bloques básicos con sucesores)
- Optimizaciones: constant folding, dead code elimination, copy propagation

Lowering: HIR → MIR
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Set


@dataclass(frozen=True)
class MIRVar:
    """Variable MIR en forma SSA-lite (versionada). frozen=True para hashable."""
    name: str
    version: int = 0
    def __repr__(self): return f"{self.name}.{self.version}"


@dataclass
class MIRInstruction:
    """Instrucción MIR: más baja que HIR, más cerca de SSA."""
    op: str  # "const", "binop", "call", "phi", "br", "ret", "store", "load"
    args: List[Any] = field(default_factory=list)  # MIRVar | literal | str
    result: Optional[MIRVar] = None
    line: int = 0
    dead: bool = False  # marcado por DCE


@dataclass
class MIRBlock:
    """Bloque básico CFG."""
    label: str
    instructions: List[MIRInstruction] = field(default_factory=list)
    successors: List[str] = field(default_factory=list)
    predecessors: Set[str] = field(default_factory=set)


@dataclass
class MIRFunction:
    """Función MIR."""
    name: str
    params: List[MIRVar]
    blocks: List[MIRBlock] = field(default_factory=list)
    next_version: int = 0

    def new_var(self, name: str) -> MIRVar:
        v = MIRVar(name, self.next_version)
        self.next_version += 1
        return v


def lower_hir_to_mir(hir_fn) -> MIRFunction:
    """Lowering: HIRFunction → MIRFunction.

    T1: HIR ahora produce instrucciones stack-based (LOAD_CONST, LOAD_NAME,
    BINARY_OP, etc.). MIR pasa estas instrucciones directamente, aplicando
    SSA versioning solo en STORE_NAME/DEFINE_NAME.
    """
    mir_fn = MIRFunction(
        name=hir_fn.name,
        params=[MIRVar(p) for p, _ in hir_fn.params],
    )
    entry = MIRBlock(label="entry")
    mir_fn.blocks.append(entry)

    # T1: Pass through stack-based HIR instructions directly.
    # MIR optimizations (constant_fold, dead_code_elimination) operate on
    # the const/copy/binop ops that HIR now produces.
    _OP_MAP = {
        "LOAD_CONST": "const",
        "LOAD_NAME": "load",
        "STORE_NAME": "store",
        "DEFINE_NAME": "store",
        "BINARY_OP": "binop",
        "UNARY_OP": "unop",
        "CALL": "call",
        "RETURN": "ret",
        "JUMP": "br",
        "JUMP_IF_FALSE": "br_if",
        "POP": "pop",
        "YIELD": "yield",
        "THROW": "throw",
        "BREAK": "break",
        "CONTINUE": "continue",
        "MAKE_FUNCTION": "make_fn",
        "BUILD_LIST": "build_list",
        "BUILD_DICT": "build_dict",
        "GET_ITEM": "get_item",
        "LOAD_ATTR": "load_attr",
        "STORE_ATTR": "store_attr",
        "IMPORT_MODULE": "import",
        "SETUP_CATCH": "setup_catch",
        "POP_CATCH": "pop_catch",
        "EXPR": "expr",
    }

    for instr in hir_fn.body.instructions:
        mir_op = _OP_MAP.get(instr.op, instr.op.lower())
        mir_args = list(instr.args)
        # AUD-004/023: PRESERVE LABEL pseudo-instructions so AIR interpreter
        # can resolve JUMP/JUMP_IF_FALSE targets. Previously stripped, which
        # made control flow impossible in AIR.
        if mir_op == "label":
            # Emit a LABEL marker (no-op execution-wise but tracked for jumps)
            mir_instr = MIRInstruction(
                op="label",
                args=mir_args,  # [label_name]
                result=None,
                line=instr.line,
            )
            entry.instructions.append(mir_instr)
            continue

        # Para binop/unop, solo el operador string (operands are on stack)

        mir_instr = MIRInstruction(
            op=mir_op,
            args=mir_args,
            result=MIRVar(instr.result) if instr.result else None,
            line=instr.line,
        )
        entry.instructions.append(mir_instr)

    return mir_fn


# --- Optimizaciones MIR -----------------------------------------------------

def constant_fold(fn: MIRFunction) -> int:
    """Pasa de constant folding. Retorna el número de instrucciones simplificadas."""
    folded = 0
    constants = {}  # MIRVar → literal value
    for block in fn.blocks:
        for instr in block.instructions:
            # Trackear constantes
            if instr.op == "const" and instr.result is not None:
                constants[instr.result] = instr.args[0] if instr.args else None
            # Constant fold binops
            elif instr.op == "binop" and len(instr.args) >= 3:
                # args: [left, right, op_str]
                left, right, op = instr.args[0], instr.args[1], instr.args[2]
                if isinstance(left, MIRVar) and left in constants \
                   and isinstance(right, MIRVar) and right in constants:
                    lv, rv = constants[left], constants[right]
                    if op == "+": result = lv + rv
                    elif op == "-": result = lv - rv
                    elif op == "*": result = lv * rv
                    elif op == "/" and rv != 0: result = lv / rv
                    else: continue
                    instr.op = "const"
                    instr.args = [result]
                    folded += 1
    return folded


def dead_code_elimination(fn: MIRFunction) -> int:
    """Pasa de DCE: elimina instrucciones cuyo resultado no se usa."""
    eliminated = 0
    used: Set = set()
    # Primera pasada: recolectar variables usadas
    for block in fn.blocks:
        for instr in block.instructions:
            for arg in instr.args:
                if isinstance(arg, MIRVar):
                    used.add(arg)
    # Segunda pasada: marcar instrucciones con resultado no usado
    for block in fn.blocks:
        new_instrs = []
        for instr in block.instructions:
            if instr.result is not None and instr.result not in used \
               and instr.op not in ("call", "ret", "br", "store", "yield"):
                instr.dead = True
                eliminated += 1
            new_instrs.append(instr)
        block.instructions = new_instrs
    return eliminated
