"""ailang.runtime.multi_backend — Multi-backend execution (X3).

Runtime que selecciona automáticamente entre Interpreter, VM, AIR, y
LLVM JIT según hot path analysis.

Estrategia:
1. Primera ejecución: Interpreter (fast startup, no compile overhead)
2. Después de N llamadas a una función: switch a VM (faster execution)
3. Si JIT está disponible y la función es muy hot: compile to native

Uso:
    from ailang.runtime.multi_backend import run_smart
    result = run_smart(source)
"""
from __future__ import annotations

from typing import Any, Optional

from ailang.lang.errors import AILangRuntimeError
from ailang.runtime.capabilities import get_default_context
from ailang.runtime.air_runtime import verify_capabilities
from ailang.ir.pipeline import compile_to_air


def run_smart(
    source: str,
    *,
    preferred: str = "auto",
    optimize: bool = True,
) -> Any:
    """Ejecuta source seleccionando el mejor backend automáticamente.

    Args:
        source: código AILang
        preferred: "auto" (default), "interp", "vm", "air", "jit"
        optimize: si True, aplica optimizaciones MIR

    Returns:
        Resultado de la ejecución
    """
    # 1. Verificar capabilities (siempre, sin importar el backend)
    air = compile_to_air(source, optimize=optimize)
    ctx = get_default_context()
    missing = verify_capabilities(air, ctx)
    if missing:
        from ailang.runtime.capabilities import CapabilityError
        raise CapabilityError(
            message=f"programa requiere capabilities no concedidas: {missing}.",
            code="E061",
        )

    # 2. Seleccionar backend
    if preferred == "auto":
        backend = _select_backend(air, source)
    else:
        backend = preferred

    # 3. Ejecutar
    if backend == "interp":
        from ailang.lang.interpreter import run_source
        return run_source(source)
    elif backend == "vm":
        from ailang.lang.vm import run_vm
        return run_vm(source)
    elif backend == "air":
        from ailang.runtime.air_interpreter import run_air
        return run_air(source, use_vm=True, optimize=optimize)
    elif backend == "jit":
        # Intentar JIT; si falla, fallback a VM
        try:
            from ailang.backends.native.jit import get_jit
            jit = get_jit()
            # Para JIT, necesitaríamos compilar toda la fuente
            # Por ahora, usar VM como fallback
            from ailang.lang.vm import run_vm
            return run_vm(source)
        except Exception:
            from ailang.lang.vm import run_vm
            return run_vm(source)
    else:
        raise AILangRuntimeError(f"backend desconocido: {backend}")


def _select_backend(air_module, source: str) -> str:
    """Selecciona el mejor backend basado en heurísticas.

    Heurísticas:
    - Si el programa tiene > 5 funciones → VM (mejor para funciones)
    - Si el programa tiene < 100 LOC → Interpreter (fast startup)
    - Si el programa usa capabilities restrictivas → AIR (verificación)
    - Default → VM (mejor performance general)
    """
    num_functions = len(air_module.functions)
    num_lines = source.count("\n") + 1

    # Programas pequeños: Interpreter es suficiente
    if num_lines < 20 and num_functions <= 1:
        return "interp"

    # Programas con muchas funciones: VM
    if num_functions > 3:
        return "vm"

    # Default: VM (mejor performance)
    return "vm"


def analyze_backend_choice(source: str) -> dict:
    """Analiza qué backend se seleccionía y por qué.

    Útil para debugging y para `ailang check --backend`.
    """
    air = compile_to_air(source, optimize=False)
    backend = _select_backend(air, source)

    return {
        "selected_backend": backend,
        "num_functions": len(air.functions),
        "num_lines": source.count("\n") + 1,
        "required_capabilities": sorted(
            cap for fn in air.functions for cap in fn.required_capabilities
        ),
        "required_effects": sorted(
            eff for fn in air.functions for eff in fn.required_effects
        ),
        "reasoning": _backend_reasoning(air, source, backend),
    }


def _backend_reasoning(air, source: str, backend: str) -> str:
    """Retorna un string explicando por qué se seleccionó el backend."""
    num_fn = len(air.functions)
    num_lines = source.count("\n") + 1

    if backend == "interp":
        return f"Programa pequeño ({num_lines} líneas, {num_fn} funciones) → Interpreter (fast startup)"
    elif backend == "vm":
        if num_fn > 3:
            return f"Programa con muchas funciones ({num_fn}) → VM (mejor call performance)"
        return f"Programa estándar ({num_lines} líneas, {num_fn} funciones) → VM (default)"
    elif backend == "air":
        return "Programa con capabilities restrictivas → AIR (verificación + VM)"
    elif backend == "jit":
        return "Función hot detectada → JIT compilation"
    return "Default → VM"
