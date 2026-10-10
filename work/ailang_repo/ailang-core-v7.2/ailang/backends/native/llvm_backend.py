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

    V3: ahora soporta variables locales (alloca + load/store) y llamadas
    a función (call). Control de flujo (if/while) requiere basic blocks
    adicionales y queda como TODO.
    """
    func_type = ir.FunctionType(ir.IntType(64), [])
    llvm_fn = ir.Function(module, func_type, name=air_fn.name)

    if not air_fn.blocks:
        return
    entry_block = llvm_fn.append_basic_block("entry")
    builder = ir.IRBuilder(entry_block)

    # Stack virtual + locals map (V3: con alloca para variables persistentes)
    stack: List[Any] = []
    locals_map: Dict[str, Any] = {}
    # V3: allocated slots para variables (alloca + load/store)
    var_slots: Dict[str, Any] = {}

    for block in air_fn.blocks:
        for instr in block.instructions:
            _lower_instruction(instr, builder, ir, stack, locals_map, var_slots, llvm_fn, module)

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
    var_slots: Dict[str, Any] = {}

    for instr in globals_block.instructions:
        _lower_instruction(instr, builder, ir, stack, locals_map, var_slots, main_fn, module)

    if not builder.block.is_terminated:
        builder.ret(ir.Constant(ir.IntType(64), 0))


def _lower_instruction(
    instr: AIRInstruction,
    builder: Any,
    ir: Any,
    stack: List[Any],
    locals_map: Dict[str, Any],
    var_slots: Dict[str, Any] = None,
    current_fn: Any = None,
    module: Any = None,
) -> None:
    """Lowering: AIRInstruction → LLVM IR instruction.

    V3: soporta LOAD_NAME/STORE_NAME con alloca/load/store, CALL con call.
    """
    if var_slots is None:
        var_slots = {}
    op = instr.opcode

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
        const = ir.Constant(ir.IntType(64), int(val))
        stack.append(const)

    elif op == LOAD_NAME:
        name = instr.operands[0] if instr.operands else ""
        # V3: usar alloca slot si existe, sino fallback a 0
        if name in var_slots:
            loaded = builder.load(var_slots[name], name=f"_{name}")
            stack.append(loaded)
        else:
            stack.append(ir.Constant(ir.IntType(64), 0))

    elif op == STORE_NAME or op == DEFINE_NAME:
        if stack:
            val = stack.pop()
            name = instr.result or (instr.operands[0] if instr.operands else "_")
            # V3: alloca + store para variables persistentes
            if name not in var_slots:
                var_slots[name] = builder.alloca(ir.IntType(64), name=name)
            builder.store(val, var_slots[name])
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
        elif op_str == "/":
            # V3: signed division
            result = builder.sdiv(a, b)
        elif op_str == "%":
            result = builder.srem(a, b)
        elif op_str == "==":
            cmp = builder.icmp_signed("==", a, b)
            result = builder.zext(cmp, ir.IntType(64))
        elif op_str == "!=":
            cmp = builder.icmp_signed("!=", a, b)
            result = builder.zext(cmp, ir.IntType(64))
        elif op_str == "<":
            cmp = builder.icmp_signed("<", a, b)
            result = builder.zext(cmp, ir.IntType(64))
        elif op_str == ">":
            cmp = builder.icmp_signed(">", a, b)
            result = builder.zext(cmp, ir.IntType(64))
        elif op_str == "<=":
            cmp = builder.icmp_signed("<=", a, b)
            result = builder.zext(cmp, ir.IntType(64))
        elif op_str == ">=":
            cmp = builder.icmp_signed(">=", a, b)
            result = builder.zext(cmp, ir.IntType(64))
        else:
            result = ir.Constant(ir.IntType(64), 0)
        stack.append(result)

    elif op == UNARY_OP:
        op_str = instr.operands[0] if instr.operands else "+"
        if stack:
            a = stack.pop()
            if op_str == "-":
                result = builder.sub(ir.Constant(ir.IntType(64), 0), a)
            else:
                result = a
            stack.append(result)

    elif op == CALL:
        # V3: soporte básico para llamadas a función declaradas en el módulo
        argc = int(instr.operands[0]) if instr.operands else 0
        args = [stack.pop() for _ in range(argc)][::-1]
        fn_name = instr.result or ""
        # Buscar la función en el módulo LLVM
        if module is not None and fn_name in [f.name for f in module.functions]:
            llvm_fn = next(f for f in module.functions if f.name == fn_name)
            result = builder.call(llvm_fn, args)
            stack.append(result)
        else:
            # Fallback: push 0
            stack.append(ir.Constant(ir.IntType(64), 0))

    elif op == RETURN:
        if stack:
            val = stack.pop()
            builder.ret(val)
        else:
            builder.ret(ir.Constant(ir.IntType(64), 0))

    elif op == POP:
        if stack:
            stack.pop()

    # Otros opcodes no soportados → ignorados (no-op)


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
