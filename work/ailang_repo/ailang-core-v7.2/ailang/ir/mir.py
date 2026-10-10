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


@dataclass
class MIRVar:
    """Variable MIR en forma SSA-lite (versionada)."""
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

    Traducción directa con renombrado SSA-lite. Cada `let`/`assign` crea
    una nueva versión de la variable.
    """
    mir_fn = MIRFunction(
        name=hir_fn.name,
        params=[MIRVar(p) for p, _ in hir_fn.params],
    )
    entry = MIRBlock(label="entry")
    mir_fn.blocks.append(entry)

    var_versions = {}  # name → current version

    def get_var(name: str) -> MIRVar:
        if name not in var_versions:
            var_versions[name] = 0
        return MIRVar(name, var_versions[name])

    def new_version(name: str) -> MIRVar:
        v = mir_fn.new_var(name)
        var_versions[name] = v.version
        return v

    for instr in hir_fn.body.instructions:
        if instr.op == "let" or instr.op == "const":
            val = instr.args[0]
            target = new_version(instr.result.name)
            if val.kind == "literal":
                entry.instructions.append(MIRInstruction(
                    op="const", args=[val.value], result=target, line=instr.line,
                ))
            else:
                entry.instructions.append(MIRInstruction(
                    op="copy", args=[get_var(val.name)], result=target, line=instr.line,
                ))
        elif instr.op == "assign":
            val = instr.args[0]
            target = new_version(instr.result.name)
            if val.kind == "literal":
                entry.instructions.append(MIRInstruction(
                    op="const", args=[val.value], result=target, line=instr.line,
                ))
            else:
                entry.instructions.append(MIRInstruction(
                    op="copy", args=[get_var(val.name)], result=target, line=instr.line,
                ))
        elif instr.op == "return":
            if instr.args:
                entry.instructions.append(MIRInstruction(
                    op="ret", args=[instr.args[0]], line=instr.line,
                ))
            else:
                entry.instructions.append(MIRInstruction(op="ret", line=instr.line))
        elif instr.op == "expr":
            entry.instructions.append(MIRInstruction(
                op="expr", args=instr.args, line=instr.line,
            ))
        elif instr.op == "yield":
            entry.instructions.append(MIRInstruction(
                op="yield", args=instr.args, line=instr.line,
            ))
        # else: simplificación — HIR completo requiere más opcodes

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
