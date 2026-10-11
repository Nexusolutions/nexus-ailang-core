"""ailang.versions — FUENTE ÚNICA de versionado para Nexus AILang-Core.

FASE 1 del prompt maestro: 7 constantes separadas.
"""
from __future__ import annotations

# --- Versión agregada del paquete -------------------------------------------

__version__: str = "1.1.0"

# --- 7 constantes separadas (FASE 1) ----------------------------------------

LANGUAGE_VERSION: str = "1.1.0"
RUNTIME_VERSION: str = "1.1.0"
BYTECODE_VERSION: int = 7
IR_VERSION: int = 1
ABI_VERSION: int = 1
STDLIB_VERSION: str = "1.1.0"
PACKAGE_FORMAT_VERSION: int = 1

# --- Constantes derivadas ----------------------------------------------------

PUBLIC_VERSION: str = LANGUAGE_VERSION
RUNTIME_ID: str = f"ailang-{PUBLIC_VERSION}"
