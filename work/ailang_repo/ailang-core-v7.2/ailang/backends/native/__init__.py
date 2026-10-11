"""ailang.backends.native — Native backend (LLVM).

FASE 31 del prompt maestro. Lowering: AIR → LLVM IR → native code.

Estado: experimental. Solo soporta un subset de AIR (integers, +, -, *).
"""
from __future__ import annotations

from ailang.backends.native.llvm_backend import (
    compile_to_llvm_ir,
    compile_to_native,
)

__all__ = ["compile_to_llvm_ir", "compile_to_native"]
