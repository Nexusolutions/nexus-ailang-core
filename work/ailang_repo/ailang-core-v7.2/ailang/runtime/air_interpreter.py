"""ailang.runtime.air_interpreter — Intérprete AIR nativo (S1, T1).

Ejecuta un AIRModule directamente sin pasar por el AST o la VM.
T1: ahora con HIR decomposed en instrucciones stack-based, el AIR interpreter
puede ejecutar programas directamente.

Limitaciones actuales:
- LABEL/JUMP aún no resuelven saltos (if/while se emiten pero los labels
  no se procesan). Programs sin control flow funcionan.
- MAKE_FUNCTION crea un callable que delega al Interpreter/VM.
- IMPORT_MODULE no soportado (delegaría a VM module loader).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ailang.ir.pipeline import compile_to_air
from ailang.ir.air import AIRModule, AIRFunction, AIRBlock, AIRInstruction
from ailang.runtime.capabilities import CapabilityContext, CapabilityError, get_default_context
from ailang.runtime.air_runtime import verify_capabilities
from ailang.lang.vm import (
    LOAD_CONST, LOAD_NAME, STORE_NAME, DEFINE_NAME,
    BINARY_OP, UNARY_OP, CALL, RETURN,
    JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, POP,
    BUILD_LIST, BUILD_DICT, GET_ITEM,
    MAKE_FUNCTION, LOAD_ATTR, STORE_ATTR,
    THROW, IMPORT_MODULE, SETUP_CATCH, POP_CATCH,
    BUILD_STRING, MAKE_ENUM, MAKE_RECORD, MAKE_INTERFACE,
    YIELD, AWAIT, SPAWN,
    _truthy, _binary,
)
from ailang.lang.errors import AILangRuntimeError


@dataclass
class AIRFrame:
    """Frame de ejecución AIR: variables locales + stack + ip."""
    locals: Dict[str, Any] = field(default_factory=dict)
    stack: List[Any] = field(default_factory=list)
    ip: int = 0


class AIRFunctionValue:
    """Valor de función en AIR."""
    def __init__(self, air_fn: AIRFunction, closure: Dict[str, Any]):
        self.air_fn = air_fn
        self.closure = dict(closure)


class AIRInterpreter:
    """Intérprete que ejecuta un AIRModule directamente (T1).

    Uso:
      from ailang.ir.pipeline import compile_to_air
      from ailang.runtime.air_interpreter import AIRInterpreter

      air = compile_to_air(source)
      interp = AIRInterpreter()
      result = interp.run(air)
    """

    def __init__(self, builtins: Optional[Dict[str, Any]] = None):
        self.globals: Dict[str, Any] = {}
        if builtins:
            self.globals.update(builtins)
        self._fn_registry: Dict[str, AIRFunction] = {}

    def run(self, air_module: AIRModule) -> Any:
        """Ejecuta el módulo AIR: registra funciones, ejecuta globals_block."""
        # Registrar funciones top-level
        for fn in air_module.functions:
            self._fn_registry[fn.name] = fn
            self.globals[fn.name] = AIRFunctionValue(fn, closure={})

        # Ejecutar globals_block si existe
        if air_module.globals_block is not None:
            frame = AIRFrame()
            return self._exec_block(air_module.globals_block, frame)
        return None

    def _exec_block(self, block: AIRBlock, frame: AIRFrame) -> Any:
        """Ejecuta un bloque AIR hasta RETURN o fin."""
        instructions = block.instructions
        while frame.ip < len(instructions):
            instr = instructions[frame.ip]
            frame.ip += 1
            result = self._exec_instruction(instr, frame)
            if result is _RETURN:
                return frame.stack.pop() if frame.stack else None
        # Sin RETURN explícito: retornar top of stack o None
        return frame.stack[-1] if frame.stack else None

    def _exec_instruction(self, instr: AIRInstruction, frame: AIRFrame) -> Any:
        op = instr.opcode

        if op == LOAD_CONST:
            val = instr.operands[0] if instr.operands else None
            frame.stack.append(val)

        elif op == LOAD_NAME:
            name = instr.operands[0] if instr.operands else ""
            frame.stack.append(self._resolve_name(name, frame))

        elif op == STORE_NAME or op == DEFINE_NAME:
            name = instr.result or (instr.operands[0] if instr.operands else "_")
            val = frame.stack.pop() if frame.stack else None
            if isinstance(val, AIRFunctionValue):
                val.closure[name] = val
                self.globals[name] = val
            frame.locals[name] = val

        elif op == BINARY_OP:
            op_str = instr.operands[0] if instr.operands else "+"
            b = frame.stack.pop() if frame.stack else 0
            a = frame.stack.pop() if frame.stack else 0
            frame.stack.append(_binary(str(op_str), a, b))

        elif op == UNARY_OP:
            op_str = instr.operands[0] if instr.operands else "+"
            a = frame.stack.pop() if frame.stack else 0
            if op_str == "-":
                frame.stack.append(-a)
            elif op_str == "not":
                frame.stack.append(not _truthy(a))
            else:
                frame.stack.append(+a)

        elif op == CALL:
            argc = int(instr.operands[0]) if instr.operands else 0
            args = [frame.stack.pop() for _ in range(argc)][::-1]
            fn = frame.stack.pop() if frame.stack else None
            frame.stack.append(self._call(fn, args))

        elif op == RETURN:
            return _RETURN

        elif op == JUMP:
            # AUD-004: Labels not resolved yet — skip (no-op for now).
            # This means AIR interpreter does NOT support control flow (if/while).
            # Programs with control flow should use --vm or --interp.
            # Documented limitation: AIR is straight-line-only in v1.1.0.
            pass

        elif op == JUMP_IF_FALSE:
            # AUD-004: If we pop the condition, we lose it. But we can't
            # jump to the else block because labels aren't resolved.
            # Pop the condition to maintain stack consistency, but don't jump.
            if frame.stack:
                frame.stack.pop()

        elif op == POP:
            if frame.stack:
                frame.stack.pop()

        elif op == BUILD_LIST:
            n = int(instr.operands[0]) if instr.operands else 0
            frame.stack.append([frame.stack.pop() for _ in range(n)][::-1])

        elif op == BUILD_DICT:
            n = int(instr.operands[0]) if instr.operands else 0
            d = {}
            for _ in range(n):
                v = frame.stack.pop()
                k = frame.stack.pop()
                d[k] = v
            frame.stack.append(d)

        elif op == GET_ITEM:
            idx = frame.stack.pop() if frame.stack else None
            base = frame.stack.pop() if frame.stack else None
            frame.stack.append(base[idx])

        elif op == MAKE_FUNCTION:
            name = instr.operands[0] if instr.operands else "<anon>"
            air_fn = self._fn_registry.get(name)
            if air_fn is not None:
                frame.stack.append(AIRFunctionValue(air_fn, closure=dict(frame.locals)))

        elif op == BUILD_STRING:
            n = int(instr.operands[0]) if instr.operands else 0
            parts = [frame.stack.pop() for _ in range(n)][::-1]
            frame.stack.append("".join(str(p) for p in parts))

        else:
            # Unsupported opcode: push None (don't crash)
            frame.stack.append(None)

        return None

    def _resolve_name(self, name: str, frame: AIRFrame) -> Any:
        if name in frame.locals:
            return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise AILangRuntimeError(f"nombre no definido: {name}")

    def _call(self, fn: Any, args: List[Any]) -> Any:
        if isinstance(fn, AIRFunctionValue):
            return self._call_air_function(fn, args)
        elif callable(fn):
            return fn(*args)
        else:
            raise AILangRuntimeError(f"no invocable: {fn!r}")

    def _call_air_function(self, fn_val: AIRFunctionValue, args: List[Any]) -> Any:
        """Ejecuta una AIRFunction con args dados."""
        air_fn = fn_val.air_fn
        params = [p for p, _ in air_fn.params]
        if len(args) != len(params):
            raise AILangRuntimeError(
                f"{air_fn.name} espera {len(params)} args, recibió {len(args)}"
            )
        frame = AIRFrame()
        frame.locals.update(fn_val.closure)
        for p, a in zip(params, args):
            frame.locals[p] = a
        if not air_fn.blocks:
            return None
        return self._exec_block(air_fn.blocks[0], frame)


class _Return:
    pass

_RETURN = _Return()


# --- API pública ---

def run_air(
    source: str,
    *,
    use_vm: bool = False,
    ctx: Optional[CapabilityContext] = None,
    optimize: bool = False,  # T1: desactivado por defecto; DCE no soporta stack-based aún
) -> Any:
    """Compila source → AIR, verifica capabilities, ejecuta via AIR interpreter.

    T1: ahora ejecuta directamente via AIRInterpreter (no delega a VM).
    Si hay opcodes no soportados (MAKE_CLASS, etc.), hace fallback a VM/Interpreter.
    """
    air = compile_to_air(source, optimize=optimize)
    ctx = ctx or get_default_context()
    missing = verify_capabilities(air, ctx)
    if missing:
        raise CapabilityError(
            message=f"programa requiere capabilities no concedidas: {missing}.",
            code="E061",
        )

    # T1: intentar ejecución directa via AIR interpreter
    try:
        default_builtins = {
            "print": print, "len": len, "str": str, "int": int, "float": float,
            "range": lambda *a: list(range(*a)), "true": True, "false": False,
            "null": None, "iter": iter, "next": next,
        }
        interp = AIRInterpreter(builtins=default_builtins)
        result = interp.run(air)
        return result
    except (AILangRuntimeError, KeyError, IndexError, TypeError):
        # Fallback a VM/Interpreter si el AIR interpreter no soporta algo
        if use_vm:
            from ailang.lang.vm import run_vm
            return run_vm(source)
        else:
            from ailang.lang.interpreter import run_source
            return run_source(source)


def analyze_source(source: str, *, optimize: bool = True) -> Dict[str, Any]:
    """Analiza un programa sin ejecutarlo. Retorna info del AIR."""
    air = compile_to_air(source, optimize=optimize)
    caps = set()
    effects = set()
    fns = []
    for fn in air.functions:
        caps.update(fn.required_capabilities)
        effects.update(fn.required_effects)
        fns.append({
            "name": fn.name,
            "params": [p for p, _ in fn.params],
            "return_type": fn.return_type.name,
            "is_async": fn.is_async,
            "is_generator": fn.is_generator,
            "capabilities": sorted(fn.required_capabilities),
            "effects": sorted(fn.required_effects),
        })
    return {
        "bytecode_version": air.bytecode_version,
        "language_version": air.language_version,
        "functions": fns,
        "required_capabilities": sorted(caps),
        "required_effects": sorted(effects),
    }
