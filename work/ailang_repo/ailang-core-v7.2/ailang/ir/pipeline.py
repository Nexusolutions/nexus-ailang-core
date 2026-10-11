"""ailang.ir.pipeline — Pipeline completo de compilación (P3-1).

Lowering: AST → HIR → MIR → AIR

Ejemplo:
  from ailang.ir.pipeline import compile_to_air
  air_module = compile_to_air(source)
  for fn in air_module.functions:
      print(format_air_function(fn))
"""
from __future__ import annotations

from typing import Dict, Set

from ailang.lang.parser import parse
from ailang.ir.hir import lower_ast_to_hir, HIRModule, HIRType, HIRFunction
from ailang.ir.mir import lower_hir_to_mir, MIRFunction, constant_fold, dead_code_elimination
from ailang.ir.air import lower_mir_to_air, AIRModule, AIRFunction, format_air_function
from ailang.semantic.effects import infer_effects
from ailang.runtime.capabilities import EFFECT_TO_CAPABILITY


def compile_to_hir(source: str) -> HIRModule:
    """AST → HIR."""
    program = parse(source)
    return lower_ast_to_hir(program)


def compile_to_mir(source: str, *, optimize: bool = True) -> list:
    """AST → HIR → MIR (con optimizaciones si optimize=True)."""
    hir_module = compile_to_hir(source)
    mir_fns = [lower_hir_to_mir(fn) for fn in hir_module.functions]
    if optimize:
        for fn in mir_fns:
            constant_fold(fn)
            dead_code_elimination(fn)
    return mir_fns


def compile_to_air(source: str, *, optimize: bool = True) -> AIRModule:
    """AST → HIR → MIR → AIR (pipeline completo).

    T1: integra effect inference + capability mapping + globals_block lowering.
    """
    program = parse(source)
    hir_module = lower_ast_to_hir(program)
    fn_effects = infer_effects(program)
    air_module = AIRModule(name=hir_module.name)
    for hir_fn in hir_module.functions:
        mir_fn = lower_hir_to_mir(hir_fn)
        if optimize:
            constant_fold(mir_fn)
            dead_code_elimination(mir_fn)
        air_fn = lower_mir_to_air(mir_fn, hir_fn)
        fn_eff = fn_effects.get(hir_fn.name, {"pure"})
        air_fn.required_effects.update(fn_eff)
        for effect in fn_eff:
            caps = EFFECT_TO_CAPABILITY.get(effect, set())
            air_fn.required_capabilities.update(caps)
        air_module.functions.append(air_fn)

    # T1: Lower globals_block (top-level code) to AIR
    if hir_module.globals_block.instructions:
        from ailang.ir.hir import HIRFunction
        temp_hir_fn = HIRFunction(
            name="<globals>", params=[], return_type=HIRType.any(),
            body=hir_module.globals_block, line=0, is_async=False, is_generator=False,
        )
        mir_globals = lower_hir_to_mir(temp_hir_fn)
        if optimize:
            constant_fold(mir_globals)
            dead_code_elimination(mir_globals)
        air_globals = lower_mir_to_air(mir_globals, temp_hir_fn)
        if air_globals.blocks:
            air_module.globals_block = air_globals.blocks[0]

    return air_module


def compile_source_to_text(source: str, *, optimize: bool = True) -> str:
    """Compila y retorna representación textual del AIR."""
    air = compile_to_air(source, optimize=optimize)
    out = [f"# AIR module: {air.name}"]
    out.append(f"# bytecode_version: {air.bytecode_version}")
    out.append(f"# language_version: {air.language_version}")
    out.append(f"# functions: {len(air.functions)}")
    # Resumen de capabilities a nivel módulo
    all_caps: Set[str] = set()
    all_effects: Set[str] = set()
    for fn in air.functions:
        all_caps.update(fn.required_capabilities)
        all_effects.update(fn.required_effects)
    if all_caps:
        out.append(f"# required_capabilities: {sorted(all_caps)}")
    if all_effects:
        out.append(f"# required_effects: {sorted(all_effects)}")
    out.append("")
    for fn in air.functions:
        out.append(format_air_function(fn))
        out.append("")
    return "\n".join(out)
