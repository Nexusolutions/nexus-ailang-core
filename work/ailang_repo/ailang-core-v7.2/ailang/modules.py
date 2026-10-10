"""ailang.modules — Module system con circular dependency detection (T4 — FASE 17).

FASE 17 del prompt maestro. Formaliza la resolución de módulos con:
- Path resolution (paths relativos y absolutos)
- Circular dependency detection (reporta el ciclo claramente)
- Module cache (evita re-importar módulos ya cargados)
- Version constraints (placeholder para futuro registry con versiones)
- Secure loading (solo archivos .ailang desde paths autorizados)

Uso desde el Interpreter/VM:
  from ailang.modules import ModuleResolver
  resolver = ModuleResolver(module_path=[".", "stdlib"])
  resolver.load("math")  # → módulo stdlib
  resolver.load("my_module")  # → busca en paths
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class CircularImportError(Exception):
    """Detectada dependencia circular entre módulos.

    El mensaje incluye el ciclo completo para diagnóstico:
      Circular import: a → b → c → a
    """

    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        chain = " → ".join(cycle)
        super().__init__(f"Circular import detected: {chain}")


class ModuleNotFoundError(Exception):
    """Módulo no encontrado en ningún path autorizado."""

    def __init__(self, module: str, searched: List[str]):
        self.module = module
        self.searched = searched
        paths = ", ".join(str(p) for p in searched)
        super().__init__(f"Module '{module}' not found. Searched: [{paths}]")


class ModuleResolver:
    """Resolvedor de módulos con cache y circular dependency detection.

    Mantiene una pila de módulos en proceso de carga. Si un módulo aparece
    dos veces en la pila, hay dependencia circular.
    """

    def __init__(self, module_path: Optional[List[str]] = None):
        self.module_path = [Path(p) for p in (module_path or [".", "stdlib"])]
        self._cache: Dict[str, Any] = {}
        self._loading: List[str] = []  # pila de módulos en proceso de carga
        self._load_count: int = 0
        self._cache_hits: int = 0

    def find_module_file(self, name: str) -> Optional[Path]:
        """Busca el archivo .ailang correspondiente al módulo.

        Soporta:
        - Módulos builtin (math, io, etc.) → None (cargados desde stdlib)
        - Módulos de usuario: busca en module_path
        - Submódulos: name.sub → name/sub.ailang
        """
        rel = name.replace(".", "/") + ".ailang"
        for root in self.module_path:
            candidate = root / rel
            if candidate.is_file():
                return candidate
        return None

    def is_builtin(self, name: str) -> bool:
        """Verifica si un módulo es builtin (cargado desde stdlib package)."""
        try:
            from ailang.lang.stdlib import builtin_modules
            return name in builtin_modules()
        except Exception:
            return False

    def load_builtin(self, name: str) -> Any:
        """Carga un módulo builtin desde el paquete stdlib."""
        from ailang.lang.stdlib import builtin_modules
        mods = builtin_modules()
        if name not in mods:
            raise ModuleNotFoundError(name, [str(p) for p in self.module_path])
        return mods[name]

    def load_user_module(self, name: str) -> Tuple[Any, Optional[Path]]:
        """Carga un módulo de usuario desde filesystem.

        Retorna (module_exports, file_path).
        Lanza CircularImportError si se detecta dependencia circular.
        Lanza ModuleNotFoundError si no se encuentra.
        """
        # Circular dependency detection
        if name in self._loading:
            cycle = self._loading[self._loading.index(name):] + [name]
            raise CircularImportError(cycle)

        # Cache check
        if name in self._cache:
            self._cache_hits += 1
            return self._cache[name], None

        # Find file
        file_path = self.find_module_file(name)
        if file_path is None:
            searched = [str(p) for p in self.module_path]
            raise ModuleNotFoundError(name, searched)

        # Load
        self._loading.append(name)
        self._load_count += 1
        try:
            source = file_path.read_text(encoding="utf-8")
            # Parse and execute the module
            from ailang.lang.parser import parse
            from ailang.lang.interpreter import Interpreter
            program = parse(source)
            interp = Interpreter(module_path=[str(p) for p in self.module_path])
            for stmt in program.body:
                interp.exec_stmt(stmt, interp.global_env)
            # Collect exports (all top-level names, excluding private)
            exports = {
                k: v for k, v in interp.global_env.values.items()
                if not k.startswith("_")
            }
            self._cache[name] = exports
            return exports, file_path
        finally:
            self._loading.pop()

    def load(self, name: str) -> Any:
        """Carga cualquier módulo (builtin o de usuario).

        Builtin modules se cargan desde el paquete stdlib.
        User modules se cargan desde filesystem con circular dep detection.
        """
        if self.is_builtin(name):
            return self.load_builtin(name)
        exports, _ = self.load_user_module(name)
        from ailang.lang.stdlib import Module
        return Module(name, exports)

    def clear_cache(self) -> None:
        """Limpia la cache de módulos cargados."""
        self._cache.clear()
        self._loading.clear()

    def stats(self) -> Dict[str, int]:
        """Retorna estadísticas de carga."""
        return {
            "loads": self._load_count,
            "cache_hits": self._cache_hits,
            "cached_modules": len(self._cache),
        }
