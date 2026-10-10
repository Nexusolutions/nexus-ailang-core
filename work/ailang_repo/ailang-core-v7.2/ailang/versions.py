"""ailang.versions — FUENTE ÚNICA de versionado para AILang.

FASE 1 (P0-1) del prompt maestro. Toda versión del proyecto se declara aquí;
ningún otro módulo debe definir su propia cadena de versión.

Las 7 constantes separadas que exige el prompt maestro:

  LANGUAGE_VERSION        — versión semántica del lenguaje (sintaxis + semántica).
  RUNTIME_VERSION         — versión del runtime (interpreter + VM + bytecode_io).
  BYTECODE_VERSION        — versión del formato .ailc (cableado a FORMAT_VERSION
                            del monolito para retrocompatibilidad).
  IR_VERSION              — versión del IR unificado (Cognitive + Agent + Task +
                            Security). Es el "major" compartido por los IR_*_VERSION.
  ABI_VERSION             — versión de la ABI de las funciones nativas (FFI futuro).
  STDLIB_VERSION          — versión de la stdlib (módulos io/math/strings/...).
  PACKAGE_FORMAT_VERSION  — versión del formato de paquetes (ailang.toml/lock).

`__version__` es la versión agregada del paquete, mostrada por CLI/LSP/README.
Se mantiene alineada con `pyproject.toml`.

Cualquier bump de versión debe:
  1. Actualizar este archivo.
  2. Actualizar CHANGELOG.md con la entrada correspondiente.
  3. Si bump BYTECODE_VERSION, documentar el cambio de formato en BYTECODE.md.
  4. Si bump LANGUAGE_VERSION con breaking change, marcar major release.

Historial:
  5.0.0  — Nivel E (estado pre-auditoría FASE 0).
  5.1.0  — FASE 0 + FASE A + FASE B (auditoría completa, P0 quirúrgicos,
           versionado unificado, bytecode firmado v7).
  5.2.0  — FASE C (VM conformance: closures mutables, generadores,
           enum/interface/record/InterpolatedString, async/await event loop,
           conformance suite interp↔VM).
  5.3.0  — P1 (partitionar monolito: ailang.cognitive + ailang.cognitive.dsl
           migrado desde ailang/compiler/), P2 (LSP ampliado con references/
           rename/documentSymbol/semanticTokens/signatureHelp, formatter AST
           idempotente, linter con reglas E001/W001/W002/W003/W005, ailang
           doctor), P3 (jerarquía AILangError completa, effect checker,
           capability enforcement con --allow/--deny CLI, pipeline HIR/MIR/AIR).
  5.4.0  — P3-9b (capability enforcement integrado en stdlib: io/path/http/
           brain/sys/time llaman a require() antes de operar), P3-1b (HIR/MIR/AIR
           integrado con effect inference + capability mapping + ailang check
           command), P2-10 (property-based testing con hypothesis: 13 properties
           de aritmética/closures/parser/formatter), P2-13 (CI multiplataforma
           GitHub Actions matrix 3 OS × 3 Python versions), P2-14 (benchmark
           suite reproducible con 17 casos + output tabular + save a JSON).
  5.7.0  — S1 (intérprete AIR nativo con --air flag: compila a AIR + verifica
           capabilities + ejecuta via VM), S2 (DAP completo: threads/scopes/
           stepIn/stepOut/evaluate/setExceptionBreakpoints/pause/terminate +
           threading real del debugger con stopped events), S3 (fuzzing con
           atheris/hypothesis: 11 fuzz targets que encontraron y fixearon un
           bug del parser con input "0.."), S4 (PostgreSQL backend real:
           connection pool psycopg_pool, CRUD con UPSERT, transacciones,
           prepared statements, búsqueda lexical ILIKE, búsqueda vectorial
           pgvector cosine <=>, búsqueda FTS to_tsvector+ts_rank), S5 (package
           manager completo: publish/update/remove/search + checksum SHA-256
           verification + firma Ed25519 opcional + formato .ailpkg tar.gz).
"""
from __future__ import annotations

# --- Versión agregada del paquete -------------------------------------------

__version__: str = "5.7.0"

# --- 7 constantes separadas (FASE 1) ----------------------------------------

LANGUAGE_VERSION: str = "5.7.0"
"""Versión semántica del lenguaje: léxico, gramática, AST, sistema de tipos,
semántica de ejecución. Bump major ante breaking changes sintácticos.
Bump minor ante nuevas features del lenguaje. Bump patch ante bugfixes semánticos.
"""

RUNTIME_VERSION: str = "5.7.0"
"""Versión del runtime: interpreter + VM + bytecode_io + closures + scheduler.
Independiente de LANGUAGE_VERSION porque el runtime puede evolucionar
(se añade GC, se cambia el modelo de threads, etc.) sin tocar el lenguaje.
"""

BYTECODE_VERSION: int = 7
"""Versión del formato .ailc. Bump cuando cambia el layout del header o el
encoding del payload. v6 = formato original sin firma. v7 = formato firmado
Ed25519 (P0-11). Decoders viejos deben rechazar versiones desconocidas.
"""

IR_VERSION: int = 1
"""Versión 'major' compartida por los 4 IRs (Cognitive, Agent, Task, Security).
Cada IR tiene además su propia *_VERSION interna; este es el contrato
cross-IR. Bump ante cambios estructurales que afecten al pipeline IR unificado.
"""

ABI_VERSION: int = 1
"""Versión de la ABI para funciones nativas (FFI). Actualmente no hay FFI
real (no hay backend nativo), pero la constante existe para cuando se
implemente (FASE 31 - LLVM).
"""

STDLIB_VERSION: str = "5.7.0"
"""Versión de la stdlib: io, math, strings, json, time, http, path, sys,
random, listops, test_mod, re, brain. Bump cuando se añade/elimina un
módulo o se cambia una API pública de stdlib.
"""

PACKAGE_FORMAT_VERSION: int = 1
"""Versión del formato de package: ailang.toml, ailang.lock, .ailpkg.
Bump cuando cambia el schema de los archivos de manifiesto.
"""

# --- Constantes derivadas ----------------------------------------------------

# Versión canónica que reporta `python -m ailang --version`, `sys.version()`,
# `lsp.serverInfo.version`, README, CHANGELOG. Lee `LANGUAGE_VERSION` porque
# esa es la versión que ve el usuario del lenguaje (no la del runtime interno).
PUBLIC_VERSION: str = LANGUAGE_VERSION

# Identificador canónico para el runtime de AILang expuesto vía `sys.version()`.
RUNTIME_ID: str = f"ailang-{PUBLIC_VERSION}"

# Compatibilidad hacia atrás: código existente hace `from ailang import __version__`.
# Esa variable vive en `ailang/__init__.py` y se importa desde aquí.
