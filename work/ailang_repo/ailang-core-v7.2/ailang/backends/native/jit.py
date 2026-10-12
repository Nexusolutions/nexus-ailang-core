"""ailang.backends.native.jit — JIT compilation via LLVM (X2).

FASE 31 del prompt maestro. Compila funciones hot a native code via LLVM JIT.

Diseño:
1. El runtime profilea qué funciones se llaman más frecuentemente
2. Cuando una función supera un threshold (ej: 100 llamadas), se compila
   a LLVM IR y luego a native code via llvmlite's JIT
3. Las llamadas subsiguientes usan el código nativo en lugar de la VM

Uso:
    from ailang.backends.native.jit import JITCompiler
    jit = JITCompiler(threshold=100)
    jit.maybe_compile(fn_name, air_module)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set

from ailang.lang.errors import AILangRuntimeError


@dataclass
class HotFunction:
    """Tracking de una función hot (candidata a JIT)."""
    name: str
    call_count: int = 0
    compiled: bool = False
    native_fn: Optional[Callable] = None
    compile_time_s: float = 0.0


class JITCompiler:
    """JIT compiler que compila funciones hot a native code via LLVM.

    Mantiene un profile de llamadas por función. Cuando una función
    supera `threshold` llamadas, se compila a LLVM IR → native code.
    """

    def __init__(self, threshold: int = 100, enabled: bool = True):
        self.threshold = threshold
        self.enabled = enabled
        self._profiles: Dict[str, HotFunction] = {}
        self._llvm_available = self._check_llvm()

    def _check_llvm(self) -> bool:
        """Verifica si llvmlite está disponible."""
        try:
            import llvmlite
            return True
        except ImportError:
            return False

    def record_call(self, fn_name: str) -> bool:
        """Registra una llamada a función. Retorna True si debe compilarse.

        Args:
            fn_name: nombre de la función llamada

        Returns:
            True si la función superó el threshold y debe compilarse.
            El compilador posteriromente intentará compilarla; si LLVM no
            está disponible, compile_function() retornará False pero el
            profiling sigue funcionando.

        Note:
            El profiling SIEMPRE se ejecuta (no requiere llvmlite).
            Solo la compilación requiere llvmlite.
        """
        if not self.enabled:
            return False

        # Profiling SIEMPRE se ejecuta (no requiere LLVM)
        if fn_name not in self._profiles:
            self._profiles[fn_name] = HotFunction(name=fn_name)

        prof = self._profiles[fn_name]
        prof.call_count += 1

        # Si superó threshold y no está compilada, marcar para compilación
        # (la compilación posterior fallará graciosamente si no hay LLVM)
        if prof.call_count >= self.threshold and not prof.compiled:
            return True
        return False

    def is_compiled(self, fn_name: str) -> bool:
        """Verifica si una función ya está compilada a native code."""
        prof = self._profiles.get(fn_name)
        return prof is not None and prof.compiled

    def get_native(self, fn_name: str) -> Optional[Callable]:
        """Retorna la función nativa compilada, o None si no está compilada."""
        prof = self._profiles.get(fn_name)
        if prof and prof.compiled and prof.native_fn:
            return prof.native_fn
        return None

    def compile_function(self, fn_name: str, source: str) -> bool:
        """Compila una función a native code via LLVM JIT.

        Args:
            fn_name: nombre de la función a compilar
            source: código fuente AILang completo

        Returns:
            True si la compilación fue exitosa
        """
        if not self._llvm_available:
            return False

        import time
        t0 = time.perf_counter()

        try:
            from ailang.backends.native.llvm_backend import compile_to_llvm_ir
            from llvmlite import binding as llvm

            # Inicializar LLVM
            llvm.initialize()
            llvm.initialize_native_target()
            llvm.initialize_native_asmprinter()

            # Compilar source a LLVM IR
            llvm_ir = compile_to_llvm_ir(source)

            # Parsear y verificar
            mod = llvm.parse_assembly(llvm_ir)
            mod.verify()

            # Crear target machine y JIT
            target = llvm.Target.from_default_triple()
            target_machine = target.create_target_machine(opt=2)

            # Crear execution engine
            backing_mod = llvm.parse_assembly("")
            engine = llvm.create_mcjit_compiler(backing_mod, target_machine)

            # Añadir nuestro módulo
            engine.add_module(mod)
            engine.finalize_object()
            engine.run_static_constructors()

            # Obtener function pointer
            fn_ptr = engine.get_function_address(fn_name)
            if fn_ptr == 0:
                # Intentar con "main" si es globals_block
                fn_ptr = engine.get_function_address("main")

            if fn_ptr == 0:
                return False

            # Crear callable Python via ctypes
            import ctypes
            cfunc_type = ctypes.CFUNCTYPE(ctypes.c_int64)
            native_fn = cfunc_type(fn_ptr)

            # Guardar en profile
            if fn_name not in self._profiles:
                self._profiles[fn_name] = HotFunction(name=fn_name)
            prof = self._profiles[fn_name]
            prof.compiled = True
            prof.native_fn = native_fn
            prof.compile_time_s = time.perf_counter() - t0

            return True

        except Exception:
            # JIT compilation falló — continuar con VM
            return False

    def stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del JIT."""
        total = len(self._profiles)
        compiled = sum(1 for p in self._profiles.values() if p.compiled)
        hot = sum(1 for p in self._profiles.values()
                  if p.call_count >= self.threshold and not p.compiled)
        return {
            "enabled": self.enabled,
            "llvm_available": self._llvm_available,
            "threshold": self.threshold,
            "total_functions": total,
            "compiled_functions": compiled,
            "hot_pending": hot,
            "total_calls": sum(p.call_count for p in self._profiles.values()),
            "functions": {
                name: {
                    "calls": p.call_count,
                    "compiled": p.compiled,
                    "compile_time_s": round(p.compile_time_s, 4),
                }
                for name, p in self._profiles.items()
            },
        }

    def reset(self) -> None:
        """Limpia todos los profiles y compilaciones."""
        self._profiles.clear()


# --- Singleton ---

_default_jit: Optional[JITCompiler] = None


def get_jit() -> JITCompiler:
    global _default_jit
    if _default_jit is None:
        _default_jit = JITCompiler()
    return _default_jit


def set_jit(jit: JITCompiler) -> None:
    global _default_jit
    _default_jit = jit


def reset_jit() -> None:
    global _default_jit
    _default_jit = None
