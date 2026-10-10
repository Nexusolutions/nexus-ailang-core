"""ailang.runtime.air_interpreter — Intérprete AIR nativo (S1).

Ejecuta un AIRModule con verificación de capabilities previa.

ESTRATEGIA (pragmática):
1. Compila source → HIR → MIR → AIR (con optimizaciones)
2. Verifica que todas las capabilities requeridas estén concedidas
3. Ejecuta via VM (que ya tiene 1.5-2x speedup sobre Interpreter)

El AIR interprete nativo directo (sin VM) requiere que el HIR/MIR/AIR
pipeline decomponga expresiones en instrucciones separadas (LOAD_CONST +
LOAD_CONST + BINARY_OP en lugar de un solo HIRValue binop). Esa decomposición
completa es trabajo futuro (P3-1c). Lo que sí tenemos hoy:

- Verificación de capabilities antes de ejecutar (denegar programas que
  requieren capabilities no concedidas, incluso si el código está ofuscado)
- Optimizaciones MIR (constant folding, DCE) que se aplican antes de ejecutar
- Análisis estático via `ailang check` (sin ejecutar)

Uso:
  from ailang.runtime.air_interpreter import run_air
  result = run_air(source, use_vm=True)

  # Con capability context restrictivo
  from ailang.runtime.capabilities import CapabilityContext, set_default_context
  set_default_context(CapabilityContext(allowed={"filesystem.read"}))
  result = run_air(source)  # falla si el programa requiere ai.query
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ailang.ir.pipeline import compile_to_air
from ailang.ir.air import AIRModule
from ailang.runtime.capabilities import (
    CapabilityContext, CapabilityError, get_default_context,
)
from ailang.runtime.air_runtime import verify_capabilities
from ailang.lang.errors import AILangRuntimeError


def run_air(
    source: str,
    *,
    use_vm: bool = True,
    ctx: Optional[CapabilityContext] = None,
    optimize: bool = True,
) -> Any:
    """Compila source → AIR, verifica capabilities, ejecuta via VM.

    Args:
        source: código fuente AILang
        use_vm: si True (default), ejecuta via VM; si False, via Interpreter
        ctx: CapabilityContext (default = global context)
        optimize: si True, aplica optimizaciones MIR antes de ejecutar

    Returns:
        Resultado de la ejecución

    Raises:
        CapabilityError: si faltan capabilities requeridas por el programa
        AILangRuntimeError: si hay errores de parseo o ejecución
    """
    # 1. Compilar a AIR (con optimizaciones)
    air = compile_to_air(source, optimize=optimize)

    # 2. Verificar capabilities
    ctx = ctx or get_default_context()
    missing = verify_capabilities(air, ctx)
    if missing:
        raise CapabilityError(
            message=(
                f"programa requiere capabilities no concedidas: {missing}. "
                f"Concede con --allow <cap> o ctx.allow('<cap>')."
            ),
            code="E061",
            suggestion=(
                "ailang run app.ailang " +
                " ".join(f"--allow {cap}" for cap in missing)
            ),
        )

    # 3. Ejecutar via VM o Interpreter
    if use_vm:
        from ailang.lang.vm import run_vm
        return run_vm(source)
    else:
        from ailang.lang.interpreter import run_source
        return run_source(source)


def analyze_source(source: str, *, optimize: bool = True) -> Dict[str, Any]:
    """Analiza un programa sin ejecutarlo. Retorna info del AIR.

    Útil para `ailang check` (modo dry-run que reporta capabilities y effects).
    """
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
