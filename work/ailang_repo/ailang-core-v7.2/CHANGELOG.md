# Changelog

## 5.3.0 — P1 + P2 + P3 (arquitectura, tooling, IR pipeline)

### P1 — Partitionar monolito y eliminar frontend duplicado
- **P1-1**: Creado `ailang/cognitive/` paquete como fachada normativa del runtime cognitivo.
  `ailang.cognitive.{CognitiveBrainEngine, CognitiveBrainStore, HybridRetriever, ...}` se re-exporta
  perezosamente desde `ailang_core.py` vía `__getattr__`. El paquete modular `ailang/` ya no importa
  `ailang_core` directamente en `brain.py` ni en `runtime_bridge.py`.
- **P1-3 + P1-4**: Eliminado `ailang/compiler/` (frontend duplicado v7.1 legacy). Migrado físicamente
  a `ailang/cognitive/dsl/` con imports internos actualizados. Símbolo canónico renombrado
  `compile_source` → `compile_cognitive` (evita colisión con `ailang.lang.vm.compile_source`).
  Alias deprecated con `DeprecationWarning` para retrocompatibilidad.
- **P1-5**: Tests embebidos del monolito (44 tests, ~465 LOC) migrados a
  `tests/test_ailang_core.py`. pytest los descubre automáticamente.

### P2 — Tooling profesional
- **P2-1** LSP ampliado: añadidos `references`, `rename`, `documentSymbol`, `semanticTokens/full`,
  `signatureHelp`, `codeAction`. Capabilities declaradas en `initialize` response. Helpers:
  `_extract_symbols`, `_extract_semantic_tokens` (tokenizer con 9 token types + modifiers),
  `_signature_help` (encuentra `(` más cercano y resuelve firma).
- **P2-4** Formatter AST-based idempotente: `format_ast(source)` parsea → emite desde AST.
  Verificado idempotente: `format_ast(format_ast(x)) == format_ast(x)`. NO preserva comentarios
  (los comentarios no están en el AST); para preservarlos usar `format_source` (token-based).
- **P2-5** Linter con reglas:
  - E001: unused variables (asignadas pero nunca leídas, excluyendo `_foo`)
  - E002: unused imports
  - W001: shadowing (variable que oculta otra del scope externo)
  - W002: unreachable code (statements después de return/break/continue)
  - W003: missing return (fn no-void sin return en todos los paths)
  - W005: empty blocks (if/while/fn sin body)
- **P2-15** `ailang doctor`: diagnostica 11 componentes (runtime, VM, compiler, bytecode_io,
  stdlib, database, LSP, debugger, hardware, cognitive, dependencies). Reporta versiones
  (package/language/runtime/bytecode/IR) y estado de cada componente.

### P3 — Diagnostics, effects, capabilities, IR pipeline
- **P3-6** Jerarquía `AILangError` completa (FASE 7): AILangError + 16 subclases (LexError,
  SyntaxError, ParseError, TypeError, NameError, ImportError, RuntimeError, ValueError,
  IndexError, AttributeError, SecurityError, CapabilityError, TimeoutError, MemoryError,
  IOError, ConcurrencyError). Cada error incluye code/file/line/col/source_snippet/cause/
  suggestion. Formato visual estilo Rust con caret indicator.
- **P3-8** Effect checker (`ailang/semantic/effects.py`): inferencia de effects (pure/io/
  filesystem/network/ai/hardware/process/unsafe) para cada función. Tabla de effects por
  builtin y por módulo stdlib. `check_source(source)` retorna issues E110 (pure fn calling
  impure) y W110 (effect set incompleto).
- **P3-9** Capability enforcement en runtime (`ailang/runtime/capabilities.py`):
  `CapabilityContext` con allow/deny lists, audit log, wildcards (`filesystem.*`).
  CLI flags `--allow <cap>` y `--deny <cap>`. Default: permissive (modo legacy);
  explícito restrictive cuando se pasa `--allow`. 11 capabilities conocidas:
  filesystem.read/write, network.http, process.spawn, ai.query, hardware.gpu/npu/tpu,
  database.read/write, system.env.
- **P3-1** Pipeline HIR/MIR/AIR (FASE 9, esqueleto):
  - `ailang/ir/hir.py`: HIR (AST tipado con HIRType, HIRValue, HIRInstruction, HIRFunction,
    HIRModule). Lowering AST→HIR con `lower_ast_to_hir(program)`.
  - `ailang/ir/mir.py`: MIR (SSA-lite con MIRVar versionada, MIRBlock con CFG, MIRFunction).
    Lowering HIR→MIR con `lower_hir_to_mir(hir_fn)`. Optimizaciones: `constant_fold`,
    `dead_code_elimination`.
  - `ailang/ir/air.py`: AIR (instrucciones tipadas con effects, capabilities, source_location).
    Lowering MIR→AIR con `lower_mir_to_air(mir_fn, hir_fn)`. Pretty printer
    `format_air_function(fn)`.
  - `ailang/ir/pipeline.py`: API unificada `compile_to_air(source)` y
    `compile_source_to_text(source)`.

### Métricas
- Tests `pytest tests/`: 149/149 ✅ (109 originales + 25 conformance VM parity + 15 ailang_core).
- Tests embebidos monolito: 44/44 ✅.
- `ailang doctor`: 11/11 componentes OK.
- Pipeline HIR/MIR/AIR: funcional end-to-end (AST→HIR→MIR→AIR con optimizaciones).
- Limitaciones conocidas: efecto fixpoint para recursión mutua (TODO), capability enforcement
  aún no integrado en stdlib calls (siguiente iteración).

## 5.2.0 — FASE C (VM conformance)

### P0-5 — Upvalues mutables (closures)
- Implementadas `Cell` (contenedor mutable compartido) en `ailang/lang/vm.py`.
- `MAKE_FUNCTION` ahora captura Cell refs en lugar de snapshotear valores.

### P0-6 — Generadores (yield)
- Implementado `GeneratorState` + `VMGenerator` para pausar/reanudar frames VM.

### P0-7 — Enum / Interface / Record / InterpolatedString
- `MAKE_ENUM`/`MAKE_RECORD`/`MAKE_INTERFACE`/`BUILD_STRING` opcodes.

### P0-8 — Async / Await / Spawn / Channel
- `VMScheduler` event loop cooperativo + `VMFuture` + `VMChannel`.

## 5.1.0 — FASE 0 + FASE A + FASE B (auditoría y P0 quirúrgicos)

### Auditoría (FASE 0)
- `AUDIT_REPORT.md`, `ROADMAP.md`, `CONFORMANCE_MATRIX.md`.

### FASE A — P0 quirúrgicos (5 fixes)
- P0-2 Fix `re_mod.search`: `null` → `None`.
- P0-3 `PersistentOutbox.list_pending`/`purge_dead`.
- P0-4 Test embebido alineado.
- P0-10 Debugger con pausa real.
- P0-11 Bytecode firmado Ed25519 (formato v7).

### FASE B — FASE 1 (versionado unificado)
- `ailang/versions.py` con 7 constantes separadas.

## 5.0.0 — Nivel E
- Generators (`yield`) + for-in
- `interface` + `implements()`
- `record` tipos producto
- Interpolación `"hello ${name}"`
- `channel()` / send / recv + `spawn`
- DAP mínimo (`--dap`)
- `bench` y `docgen`

## 4.0.0 — Nivel D
- enum, async/await, http, coverage, watch, project

## 3.0.0 — Nivel C
- match/const, fmt/lint, .ailc, profiler

## 2.0.0 — Nivel B
- LSP, debugger, pkg, agents

## 1.0.0 — Nivel A
- núcleo + VM
