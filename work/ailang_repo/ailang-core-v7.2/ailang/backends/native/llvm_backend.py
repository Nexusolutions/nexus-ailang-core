"""ailang.backends.native.llvm_backend — LLVM backend esqueleto (U3 — FASE 31).

FASE 31 del prompt maestro. Lowering: AIR → LLVM IR → native code.

ESTADO: experimental. Implementa el lowering de un subset de AIR a LLVM IR:
- LOAD_CONST → constantes LLVM
- BINARY_OP (+, -, *) → instrucciones LLVM add/sub/mul
- RETURN → ret
- Funciones → LLVM functions con signature void() (placeholder)

Limitaciones actuales:
- Solo enteros (i64)
- Sin control de flujo (if/while → requiere basic blocks + br)
- Sin llamadas a función (require declaring functions + call)
- Sin variables locales (require alloca + store/load)

Uso:
  from ailang.backends.native.llvm_backend import compile_to_llvm_ir, compile_to_native
  llvm_ir = compile_to_llvm_ir(source)  # texto LLVM IR
  native_code = compile_to_native(source)  # bytes del .o (futuro)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ailang.ir.pipeline import compile_to_air
from ailang.ir.air import AIRModule, AIRFunction, AIRInstruction
from ailang.lang.vm import (
    LOAD_CONST, LOAD_NAME, STORE_NAME, DEFINE_NAME,
    BINARY_OP, UNARY_OP, CALL, RETURN,
    JUMP, JUMP_IF_FALSE, POP,
)


def compile_to_llvm_ir(source: str, *, optimize: bool = False) -> str:
    """Compila source → AIR → LLVM IR text.

    Retorna el LLVM IR como string.

    Requiere `llvmlite` instalado: pip install llvmlite
    """
    try:
        from llvmlite import ir
    except ImportError:
        raise RuntimeError(
            "llvmlite no instalado. Instala con: pip install llvmlite"
        )

    air = compile_to_air(source, optimize=optimize)

    # Crear módulo LLVM
    module = ir.Module(name=air.name)
    module.triple = "x86_64-pc-linux-gnu"  # default target

    # Para cada función AIR, crear una LLVM function
    for air_fn in air.functions:
        _lower_function_to_llvm(air_fn, module, ir)

    # Si hay globals_block, crear una función main
    if air.globals_block:
        _lower_globals_to_llvm(air.globals_block, module, ir)

    return str(module)


def _lower_function_to_llvm(air_fn: AIRFunction, module: Any, ir: Any) -> None:
    """Lowering: AIRFunction → LLVM function.

    Crea una LLVM function con signature i64 @<name>() (placeholder: sin params).
    Para params reales, habría que declararlos con tipos LLVM.
    """
    # Tipo de retorno i64 (placeholder)
    func_type = ir.FunctionType(ir.IntType(64), [])
    llvm_fn = ir.Function(module, func_type, name=air_fn.name)

    # Crear basic block de entry
    if not air_fn.blocks:
        return
    entry_block = llvm_fn.append_basic_block("entry")
    builder = ir.IRBuilder(entry_block)

    # Stack virtual: mapear opcodes AIR a instrucciones LLVM
    stack: List[Any] = []
    locals_map: Dict[str, Any] = {}

    for block in air_fn.blocks:
        for instr in block.instructions:
            _lower_instruction(instr, builder, ir, stack, locals_map)

    # Si no terminó con ret, añadir ret 0
    if not builder.block.is_terminated:
        builder.ret(ir.Constant(ir.IntType(64), 0))


def _lower_globals_to_llvm(globals_block: Any, module: Any, ir: Any) -> None:
    """Lowering: globals_block → LLVM main function."""
    func_type = ir.FunctionType(ir.IntType(64), [])
    main_fn = ir.Function(module, func_type, name="main")
    entry_block = main_fn.append_basic_block("entry")
    builder = ir.IRBuilder(entry_block)

    stack: List[Any] = []
    locals_map: Dict[str, Any] = {}

    for instr in globals_block.instructions:
        _lower_instruction(instr, builder, ir, stack, locals_map)

    # ret 0
    if not builder.block.is_terminated:
        builder.ret(ir.Constant(ir.IntType(64), 0))


def _lower_instruction(
    instr: AIRInstruction,
    builder: Any,
    ir: Any,
    stack: List[Any],
    locals_map: Dict[str, Any],
) -> None:
    """Lowering: AIRInstruction → LLVM IR instruction.

    Solo soporta un subset; opcodes no soportados son ignorados (no-op).
    """
    op = instr.opcode

    if op == LOAD_CONST:
        val = instr.operands[0] if instr.operands else 0
        if isinstance(val, bool):
            val = int(val)
        elif isinstance(val, float):
            val = int(val)  # LLVM IR requiere enteros por ahora
        elif isinstance(val, str):
            val = 0  # strings no soportados en este esqueleto
        elif val is None:
            val = 0
        const = ir.Constant(ir.IntType(64), int(val))
        stack.append(const)

    elif op == LOAD_NAME:
        name = instr.operands[0] if instr.operands else ""
        if name in locals_map:
            stack.append(locals_map[name])
        else:
            # Placeholder: push 0
            stack.append(ir.Constant(ir.IntType(64), 0))

    elif op == STORE_NAME or op == DEFINE_NAME:
        # En LLVM IR, variables son SSA. Para simplicidad, mantener un mapping.
        if stack:
            val = stack.pop()
            name = instr.result or (instr.operands[0] if instr.operands else "_")
            locals_map[name] = val

    elif op == BINARY_OP:
        op_str = instr.operands[0] if instr.operands else "+"
        if len(stack) < 2:
            return
        b = stack.pop()
        a = stack.pop()
        if op_str == "+":
            result = builder.add(a, b)
        elif op_str == "-":
            result = builder.sub(a, b)
        elif op_str == "*":
            result = builder.mul(a, b)
        else:
            # Op no soportado: push 0
            result = ir.Constant(ir.IntType(64), 0)
        stack.append(result)

    elif op == RETURN:
        if stack:
            val = stack.pop()
            builder.ret(val)
        else:
            builder.ret(ir.Constant(ir.IntType(64), 0))

    # Otros opcodes (CALL, JUMP, etc.) no soportados en este esqueleto


def compile_to_native(source: str, *, target: str = "x86_64") -> bytes:
    """Compila source → LLVM IR → native object code (.o).

    FASE 31: target final. Requiere LLVM instalado en el sistema.

    Args:
        source: código AILang
        target: "x86_64" o "arm64"

    Returns:
        Bytes del object file

    Raises:
        RuntimeError: si LLVM no está disponible en el sistema
    """
    try:
        from llvmlite import binding as llvm
    except ImportError:
        raise RuntimeError("llvmlite no instalado")

    # Inicializar LLVM
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    # Generar LLVM IR
    llvm_ir = compile_to_llvm_ir(source)

    # Crear módulo LLVM
    mod = llvm.parse_assembly(llvm_ir)
    mod.verify()

    # Crear target machine
    target_triple = {
        "x86_64": "x86_64-pc-linux-gnu",
        "arm64": "arm64-apple-darwin",
    }.get(target, llvm.get_default_triple())

    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine(opt=2)

    # Generar object code
    obj_code = target_machine.emit_object(mod)
    return obj_code
