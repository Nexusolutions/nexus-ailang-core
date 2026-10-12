"""ailang.runtime.air_runtime — Runtime que valida AIR antes de ejecutar (P3-1b).

Conecta el pipeline HIR/MIR/AIR con el runtime existente:
1. Compila source → HIR → MIR → AIR (con optimizaciones)
2. Verifica que todas las capabilities requeridas por el AIR module estén
   concedidas en el CapabilityContext activo.
3. Si alguna capability falta, lanza CapabilityError con la lista completa.
4. Si todas están concedidas, ejecuta via Interpreter o VM (modo legacy).

Esta implementación es un paso intermedio pragmático: el AIR se usa para
verificación de capabilities pero la ejecución aún se hace via AST directo.
Una futura iteración (P3-1c) añadirá un intérprete AIR nativo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from ailang.ir.pipeline import compile_to_air
from ailang.ir.air import AIRModule, AIRFunction
from ailang.runtime.capabilities import (
    CapabilityContext, CapabilityError,
    get_default_context, set_default_context, reset_default_context,
)


def collect_required_capabilities(air_module: AIRModule) -> Set[str]:
    """Recolecta todas las capabilities requeridas por un AIRModule."""
    caps: Set[str] = set()
    for fn in air_module.functions:
        caps.update(fn.required_capabilities)
    return caps


def collect_required_effects(air_module: AIRModule) -> Set[str]:
    """Recolecta todos los effects inferidos por el AIR."""
    effects: Set[str] = set()
    for fn in air_module.functions:
        effects.update(fn.required_effects)
    return effects


def verify_capabilities(air_module: AIRModule,
                         ctx: Optional[CapabilityContext] = None) -> List[str]:
    """Verifica que todas las capabilities requeridas estén concedidas.

    Retorna la lista de capabilities faltantes (vacía si todo OK).
    """
    ctx = ctx or get_default_context()
    required = collect_required_capabilities(air_module)
    missing = [cap for cap in sorted(required) if not ctx.is_allowed(cap)]
    return missing


def run_with_air_verification(
    source: str,
    *,
    use_vm: bool = False,
    ctx: Optional[CapabilityContext] = None,
    optimize: bool = True,
) -> Any:
    """Compila source → AIR, verifica capabilities, y ejecuta.

    Args:
        source: código fuente AILang
        use_vm: si True, ejecuta via VM; si False, via Interpreter
        ctx: CapabilityContext a usar (default = global)
        optimize: si True, aplica optimizaciones MIR (constant_fold, DCE)

    Returns:
        Resultado de la ejecución

    Raises:
        CapabilityError: si faltan capabilities requeridas
    """
    # 1. Compilar a AIR
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

    # 3. Ejecutar via Interpreter o VM (modo legacy, sin AIR-interpreter nativo)
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
    caps = collect_required_capabilities(air)
    effects = collect_required_effects(air)
    fns = []
    for fn in air.functions:
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
