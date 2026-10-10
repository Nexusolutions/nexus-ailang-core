"""ailang.ir.air — AILang IR (P3-1).

FASE 9 del prompt maestro. AIR es la representación final antes del backend:
instrucciones tipadas con effects, capabilities y source_location.

Cada instrucción AIR puede ser ejecutada directamente por el intérprete
AIR (futuro), compilada a bytecode (futuro), o lowered a LLVM/WASM (futuro).

Estructura:
  AIRInstruction
  ├── opcode: int
  ├── operands: List[any]
  ├── result: Optional[str]
  ├── type: Optional[HIRType]
  ├── effects: Set[str]
  ├── capabilities: Set[str]
  ├── source_location: Optional[SourceLocation]
  └── metadata: Dict[str, Any]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ailang.ir.hir import HIRType
from ailang.ir.mir import MIRFunction, MIRVar


# --- Opcodes AIR (compatibles con VM opcodes existentes + extensiones) -------

# Reutilizamos los opcodes de VM donde aplica
from ailang.lang.vm import (
    LOAD_CONST, LOAD_NAME, STORE_NAME, DEFINE_NAME,
    BINARY_OP, UNARY_OP, CALL, RETURN,
    JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, POP,
    BUILD_LIST, BUILD_DICT, GET_ITEM,
    MAKE_FUNCTION, LOAD_ATTR, STORE_ATTR,
    THROW, MAKE_CLASS, IMPORT_MODULE,
    SETUP_CATCH, POP_CATCH,
    BUILD_STRING, MAKE_ENUM, MAKE_RECORD, MAKE_INTERFACE,
    YIELD, AWAIT, SPAWN,
)


@dataclass
class SourceLocation:
    """Ubicación en el código fuente para diagnostics."""
    file: str = "<stdin>"
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0


@dataclass
class AIRInstruction:
    """Instrucción AIR: opcode + operands + metadata."""
    opcode: int
    operands: List[Any] = field(default_factory=list)
    result: Optional[str] = None  # nombre del registro/variable resultado
    type: Optional[HIRType] = None
    effects: Set[str] = field(default_factory=set)  # effects inferidos
    capabilities: Set[str] = field(default_factory=set)  # capabilities requeridas
    source: Optional[SourceLocation] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIRBlock:
    """Bloque AIR: secuencia de instrucciones con saltos explícitos."""
    label: str
    instructions: List[AIRInstruction] = field(default_factory=list)


@dataclass
class AIRFunction:
    """Función AIR."""
    name: str
    params: List[Tuple[str, HIRType]]
    return_type: HIRType
    blocks: List[AIRBlock] = field(default_factory=list)
    is_async: bool = False
    is_generator: bool = False
    required_capabilities: Set[str] = field(default_factory=set)
    required_effects: Set[str] = field(default_factory=set)
    source: Optional[SourceLocation] = None


@dataclass
class AIRModule:
    """Módulo AIR."""
    name: str
    functions: List[AIRFunction] = field(default_factory=list)
    globals_block: Optional[AIRBlock] = None
    bytecode_version: int = 7  # FORMAT_VERSION_SIGNED
    language_version: str = "5.2.0"


def lower_mir_to_air(mir_fn: MIRFunction, hir_fn) -> AIRFunction:
    """Lowering: MIRFunction + HIRFunction → AIRFunction.

    T1: no crea un bloque entry vacío — usa los bloques del MIR directamente.
    """
    air_fn = AIRFunction(
        name=mir_fn.name,
        params=[(p.name, HIRType.any()) for p in mir_fn.params],
        return_type=hir_fn.return_type,
        is_async=hir_fn.is_async,
        is_generator=hir_fn.is_generator,
    )

    # T1: Iterate MIR blocks directly (don't create separate empty entry)
    for mir_block in mir_fn.blocks:
        air_block = AIRBlock(label=mir_block.label)
        for mir_instr in mir_block.instructions:
            if mir_instr.dead:
                continue
            opcode = _mir_op_to_air_op(mir_instr.op)
            if opcode is None:
                continue
            air_instr = AIRInstruction(
                opcode=opcode,
                operands=[_mir_arg_to_air_operand(a) for a in mir_instr.args],
                result=mir_instr.result.name if mir_instr.result else None,
                source=SourceLocation(line=mir_instr.line),
            )
            # Effects basados en el opcode
            if opcode in (CALL, MAKE_FUNCTION):
                air_instr.effects.add("io")  # placeholder; real inference vendría de HIR
            elif opcode == YIELD:
                air_instr.effects.add("process")
            elif opcode == SPAWN:
                air_instr.effects.add("process")
                air_instr.capabilities.add("process.spawn")
            elif opcode == IMPORT_MODULE:
                air_instr.effects.add("io")
            air_block.instructions.append(air_instr)
        air_fn.blocks.append(air_block)

    # Agregar capabilities requeridas a la fn
    for block in air_fn.blocks:
        for instr in block.instructions:
            air_fn.required_capabilities.update(instr.capabilities)
            air_fn.required_effects.update(instr.effects)

    return air_fn


def _mir_op_to_air_op(mir_op: str) -> Optional[int]:
    """Mapea opcode MIR (string) a opcode AIR (int). T1: ampliada para stack-based ops."""
    mapping = {
        "const": LOAD_CONST,
        "copy": LOAD_NAME,
        "load": LOAD_NAME,
        "store": STORE_NAME,
        "binop": BINARY_OP,
        "unop": UNARY_OP,
        "call": CALL,
        "ret": RETURN,
        "br": JUMP,
        "br_if": JUMP_IF_FALSE,
        "yield": YIELD,
        "spawn": SPAWN,
        "await": AWAIT,
        "throw": THROW,
        "expr": POP,  # expression statement: pop result
        "pop": POP,
        "break": JUMP,  # break/continue: mapped to JUMP (target resolved later)
        "continue": JUMP,
        "make_fn": MAKE_FUNCTION,
        "build_list": BUILD_LIST,
        "build_dict": BUILD_DICT,
        "get_item": GET_ITEM,
        "load_attr": LOAD_ATTR,
        "store_attr": STORE_ATTR,
        "import": IMPORT_MODULE,
        "setup_catch": SETUP_CATCH,
        "pop_catch": POP_CATCH,
    }
    return mapping.get(mir_op)


def _mir_arg_to_air_operand(arg: Any) -> Any:
    """Convierte un argumento MIR a operando AIR."""
    if isinstance(arg, MIRVar):
        return arg.name
    return arg


# --- Pretty printer para AIR (debugging) ------------------------------------

def format_air_instruction(instr: AIRInstruction) -> str:
    op_name = _OPCODE_NAMES.get(instr.opcode, f"OP{instr.opcode}")
    parts = [op_name]
    if instr.operands:
        parts.append(" ".join(str(o) for o in instr.operands))
    if instr.result:
        parts.append(f"-> {instr.result}")
    extras = []
    if instr.effects:
        extras.append(f"effects={set(instr.effects)}")
    if instr.capabilities:
        extras.append(f"caps={set(instr.capabilities)}")
    if instr.source and instr.source.line:
        extras.append(f"line={instr.source.line}")
    if extras:
        parts.append("  ; " + " ".join(extras))
    return " ".join(parts)


# Tabla inversa opcode → nombre (para debugging)
_OPCODE_NAMES = {
    LOAD_CONST: "LOAD_CONST", LOAD_NAME: "LOAD_NAME", STORE_NAME: "STORE_NAME",
    DEFINE_NAME: "DEFINE_NAME", BINARY_OP: "BINARY_OP", UNARY_OP: "UNARY_OP",
    CALL: "CALL", RETURN: "RETURN", JUMP: "JUMP", JUMP_IF_FALSE: "JUMP_IF_FALSE",
    JUMP_IF_TRUE: "JUMP_IF_TRUE", POP: "POP", BUILD_LIST: "BUILD_LIST",
    BUILD_DICT: "BUILD_DICT", GET_ITEM: "GET_ITEM", MAKE_FUNCTION: "MAKE_FUNCTION",
    LOAD_ATTR: "LOAD_ATTR", STORE_ATTR: "STORE_ATTR", THROW: "THROW",
    MAKE_CLASS: "MAKE_CLASS", IMPORT_MODULE: "IMPORT_MODULE",
    SETUP_CATCH: "SETUP_CATCH", POP_CATCH: "POP_CATCH", BUILD_STRING: "BUILD_STRING",
    MAKE_ENUM: "MAKE_ENUM", MAKE_RECORD: "MAKE_RECORD", MAKE_INTERFACE: "MAKE_INTERFACE",
    YIELD: "YIELD", AWAIT: "AWAIT", SPAWN: "SPAWN",
}


def format_air_function(fn: AIRFunction) -> str:
    out = [f"fn {fn.name}({', '.join(p for p, _ in fn.params)}) -> {fn.return_type.name}"]
    if fn.required_capabilities:
        out.append(f"  ; capabilities: {sorted(fn.required_capabilities)}")
    if fn.required_effects:
        out.append(f"  ; effects: {sorted(fn.required_effects)}")
    if fn.is_async:
        out.append("  ; async")
    if fn.is_generator:
        out.append("  ; generator")
    for block in fn.blocks:
        out.append(f"{block.label}:")
        for instr in block.instructions:
            out.append(f"  {format_air_instruction(instr)}")
    return "\n".join(out)
