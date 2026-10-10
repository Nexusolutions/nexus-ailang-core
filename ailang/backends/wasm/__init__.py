"""ailang.backends.wasm — WASM backend (experimental).

FASE 32 del prompt maestro. Lowering: AIR → WebAssembly.
"""
from __future__ import annotations

from ailang.backends.wasm.wasm_backend import (
    compile_to_wat,
    compile_to_wasm,
)

__all__ = ["compile_to_wat", "compile_to_wasm"]
