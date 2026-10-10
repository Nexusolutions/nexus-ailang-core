"""ailang.backends.wasm — WASM backend esqueleto (U4 — FASE 32).

FASE 32 del prompt maestro. Lowering: AIR → WebAssembly.

ESTADO: experimental. Genera WASM text format (.wat) para un subset de AIR:
- LOAD_CONST → i64.const
- BINARY_OP (+, -, *) → i64.add/sub/mul
- RETURN → end

Limitaciones actuales:
- Solo enteros i64
- Sin control de flujo
- Sin llamadas a función (require declaring functions + call)
- Sin variables locales (require local + set/get)

Uso:
  from ailang.backends.wasm import compile_to_wat
  wat_text = compile_to_wat(source)
"""
from __future__ import annotations

from typing import List

from ailang.ir.pipeline import compile_to_air
from ailang.ir.air import AIRModule, AIRFunction, AIRInstruction
from ailang.lang.vm import (
    LOAD_CONST, LOAD_NAME, STORE_NAME, DEFINE_NAME,
    BINARY_OP, UNARY_OP, CALL, RETURN,
    JUMP, JUMP_IF_FALSE, POP,
)


def compile_to_wat(source: str, *, optimize: bool = False) -> str:
    """Compila source → AIR → WASM text format (.wat).

    Retorna el .wat como string.

    No requiere dependencias externas (genera texto WAT directamente).
    """
    air = compile_to_air(source, optimize=optimize)

    lines: List[str] = ['(module']

    # Para cada función AIR, crear una WASM function
    for air_fn in air.functions:
        lines.append(f'  ;; function: {air_fn.name}')
        fn_lines = _lower_function_to_wat(air_fn)
        lines.extend(fn_lines)

    # Si hay globals_block, crear una función main exportada
    if air.globals_block:
        lines.append('  ;; main (globals block)')
        lines.append(f'  (func $main (export "main") (result i64)')
        lines.append('    ;; body:')
        main_lines = _lower_block_to_wat(air.globals_block)
        for line in main_lines:
            lines.append(f'    {line}')
        lines.append('  )')

    lines.append(')')
    return "\n".join(lines) + "\n"


def _lower_function_to_wat(air_fn: AIRFunction) -> List[str]:
    """Lowering: AIRFunction → WASM function text."""
    lines: List[str] = []
    # Signature: placeholder (i64 → i64)
    lines.append(f'  (func ${air_fn.name} (result i64)')
    lines.append('    ;; body:')

    for block in air_fn.blocks:
        block_lines = _lower_block_to_wat(block)
        for line in block_lines:
            lines.append(f'    {line}')

    # Asegurar que termina con un valor en el stack
    lines.append('    i64.const 0  ;; default return')
    lines.append('  )')
    return lines


def _lower_block_to_wat(block: Any) -> List[str]:
    """Lowering: AIRBlock → WASM instructions text."""
    lines: List[str] = []
    stack_depth = 0
    locals_map = {}

    for instr in block.instructions:
        wat_lines = _lower_instruction_to_wat(instr, stack_depth, locals_map)
        for line in wat_lines:
            lines.append(line)
        # Actualizar stack_depth según el opcode
        stack_depth = _update_stack_depth(instr, stack_depth)

    return lines


def _lower_instruction_to_wat(instr: AIRInstruction, stack_depth: int, locals_map: dict) -> List[str]:
    """Lowering: AIRInstruction → WASM instructions text."""
    op = instr.opcode
    lines: List[str] = []

    if op == LOAD_CONST:
        val = instr.operands[0] if instr.operands else 0
        if isinstance(val, bool):
            val = int(val)
        elif isinstance(val, float):
            val = int(val)
        elif isinstance(val, str):
            val = 0
        elif val is None:
            val = 0
        lines.append(f'i64.const {int(val)}')

    elif op == LOAD_NAME:
        name = instr.operands[0] if instr.operands else ""
        if name in locals_map:
            lines.append(f'local.get ${name}')
        else:
            lines.append(f'i64.const 0  ;; {name} not found')

    elif op == STORE_NAME or op == DEFINE_NAME:
        name = instr.result or (instr.operands[0] if instr.operands else "_")
        lines.append(f'local.set ${name}  ;; store to {name}')

    elif op == BINARY_OP:
        op_str = instr.operands[0] if instr.operands else "+"
        wasm_op = {
            "+": "i64.add",
            "-": "i64.sub",
            "*": "i64.mul",
        }.get(op_str, "i64.add")
        lines.append(wasm_op)

    elif op == UNARY_OP:
        op_str = instr.operands[0] if instr.operands else "+"
        if op_str == "-":
            lines.append('i64.const 0')
            lines.append('i64.sub')  # 0 - x = -x
        else:
            lines.append(';; unop not supported')

    elif op == RETURN:
        lines.append('return')

    elif op == POP:
        lines.append('drop  ;; pop top of stack')

    elif op == CALL:
        argc = instr.operands[0] if instr.operands else 0
        lines.append(f';; call with {argc} args (not lowered)')

    elif op == JUMP:
        lines.append(';; jump (not supported in WASM esqueleto)')

    elif op == JUMP_IF_FALSE:
        lines.append(';; jump_if_false (not supported)')

    # Otros opcodes no soportados → comment
    return lines


def _update_stack_depth(instr: AIRInstruction, depth: int) -> int:
    """Estima el stack depth después de cada instrucción (para debugging)."""
    op = instr.opcode
    if op in (LOAD_CONST, LOAD_NAME):
        return depth + 1
    elif op in (STORE_NAME, DEFINE_NAME):
        return depth - 1
    elif op == BINARY_OP:
        return depth - 1
    elif op == UNARY_OP:
        return depth
    elif op == POP:
        return depth - 1
    elif op == RETURN:
        return 0
    return depth


def compile_to_wasm(source: str, *, optimize: bool = False) -> bytes:
    """Compila source → WAT → WASM binary.

    Requiere `wabt` (WebAssembly Binary Toolkit) instalado en el sistema:
    - wat2wasm tool

    Returns:
        Bytes del .wasm binary

    Raises:
        RuntimeError: si wat2wasm no está disponible
    """
    import subprocess
    import tempfile
    import os

    wat_text = compile_to_wat(source, optimize=optimize)

    with tempfile.NamedTemporaryFile(suffix=".wat", delete=False, mode="w") as f:
        f.write(wat_text)
        wat_path = f.name

    wasm_path = wat_path.replace(".wat", ".wasm")

    try:
        result = subprocess.run(
            ["wat2wasm", wat_path, "-o", wasm_path],
            capture_output=True,
            check=True,
        )
        with open(wasm_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(
            "wat2wasm no encontrado. Instala wabt: apt install wabt / brew install wabt"
        )
    finally:
        if os.path.exists(wat_path):
            os.unlink(wat_path)
        if os.path.exists(wasm_path):
            os.unlink(wasm_path)
