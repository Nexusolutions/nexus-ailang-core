# Changelog

## 5.5.0 — S1 + S2 + S3 + S4 + S5

### S1 — Intérprete AIR nativo
- `ailang/runtime/air_interpreter.py`: API `run_air(source)` que compila a AIR,
  verifica capabilities, y ejecuta via VM.
- CLI `--air` flag: `python -m ailang --air file.ailang` o `-c "source"`.
- Integración con capability enforcement: programas que requieren capabilities
  no concedidas son rechazados antes de ejecutar.
- `analyze_source()` para análisis estático sin ejecución.

### S2 — DAP completo
- `ailang/dap.py` reescrito con 14 métodos DAP:
  - initialize (con capabilities declaradas: supportsSetVariable, supportsTerminateRequest, etc.)
  - launch, setBreakpoints (con conditional breakpoints), setExceptionBreakpoints
  - continue, next, stepIn, stepOut, pause, terminate
  - threads (single-thread report), stackTrace (con source info)
  - scopes (Locals + Globals), variables (con variablesReference para list/dict expansion)
  - evaluate (evalúa expresiones simples en el contexto del frame)
  - setVariable (modifica variables en runtime)
  - source (retorna contenido del archivo)
- Integración real con Debugger (P0-10): threading.Event para pause/continue,
  `stopped` events emitidos cuando se alcanza un breakpoint.

### S3 — Fuzzing con hypothesis/atheris
- `tests/test_fuzz.py` con 11 fuzz targets cubriendo:
  - Lexer (ASCII + Unicode input arbitrario)
  - Parser (input arbitrario)
  - Interpreter (input arbitrario)
  - VM (input arbitrario)
  - Formatter (format_source + format_ast)
  - Linter
  - AIR pipeline (compile_to_air + run_air)
  - Idempotencia de format_ast
- **Bug encontrado y fixeado**: parser crasheaba con `ValueError` en input `0..`
  (número malformado). Fix: `parser.py:485` ahora captura `ValueError` y lanza
  `AILangSyntaxError` con mensaje claro.
- Suite total: 173 tests (162 + 11 fuzz).

### S4 — PostgreSQL backend real
- `ailang/storage/postgres_backend.py` completamente reimplementado:
  - Connection pool via `psycopg_pool.ConnectionPool` (min 2, max 10 conexiones)
  - CRUD real: `upsert_document` con `ON CONFLICT DO UPDATE`, `replace_chunks`
    con `DELETE + INSERT` en transacción explícita (BEGIN/COMMIT/ROLLBACK)
  - `list_documents`/`list_chunks` con `SELECT ... ORDER BY created_at DESC`
  - Búsqueda lexical: `ILIKE` para substring match
  - Búsqueda vectorial: pgvector cosine distance `<=>` operator
  - Búsqueda FTS: `to_tsvector + ts_rank` (PostgreSQL nativo full-text)
  - Schema con `created_at`/`updated_at` TIMESTAMPTZ, índices ivfflat + gin
  - Graceful degradation: si psycopg-pool no instalado, `_init_error` captura
    el error y las operaciones posteriores lanzan RuntimeError claro
- Ya NO hay `NotImplementedError` ni `return []` — implementación real.

### S5 — Package manager completo
- `ailang/pkg.py` ampliado con 4 nuevos comandos:
  - `publish`: empaqueta directorio → `.ailpkg` (tar.gz) con manifest.json +
    checksum.sha256 (SHA-256 de cada archivo) + signature.bin opcional (Ed25519)
  - `update`: instala la versión más reciente (o específica con `--version`)
    desde el registry local
  - `remove`: desinstala un paquete del registry local
  - `search`: busca por nombre en paquetes instalados y publicados
- `install` ahora acepta `.ailpkg` files además de directorios, con
  verificación de checksums opcional (`--no-verify` para skip)
- Formato `.ailpkg`: tar.gz con manifest.json, archivos del paquete,
  checksum.sha256, signature.bin opcional
- Registry local: `~/.ailang/packages/registry/` para `.ailpkg` publicados
- Verificado end-to-end: init → publish → search → install → remove

### Métricas
- Tests `pytest tests/`: 173/173 ✅ (162 + 11 fuzz).
- Tests embebidos monolito: 44/44 ✅.
- `ailang doctor`: 11/11 componentes OK.
- Bug del parser fixeado (encontrado por fuzzer).
- PostgreSQL backend: real (no más stubs).
- Package manager: 7 comandos (init/install/list/run/publish/update/remove/search).

## 5.4.0 — P3-9b + P3-1b + P2-10 + P2-13 + P2-14

### P3-9b — Capability enforcement integrado en stdlib
- Stdlib modules ahora llaman `require()` antes de operar:
  - `io.read_text`/`write_text`/`exists`/`lines` → `filesystem.read`/`filesystem.write`
  - `http.get`/`post`/`json_get` → `network.http`
  - `brain.ingest`/`query`/`think`/`graph` → `ai.query`
  - `sys.argv`/`exit` → `process.spawn`; `sys.getenv` → `system.env`
  - `path.exists`/`is_file`/`is_dir`/`listdir` → `filesystem.read`; `mkdir` → `filesystem.write`
  - `time.sleep` → `process.spawn`
- Default mode: permissive (modo legacy, todas concedidas). Restrictive con `--allow` explícito.
- Verificado end-to-end: programa con `io.read_text` falla sin `--allow filesystem.read`,
  funciona con `--allow filesystem.read`, y respeta wildcards `--allow filesystem.*`.
- Audit log captura cada operation allowed/denied con op_desc.

### P3-1b — HIR/MIR/AIR integrado con runtime
- `ailang/ir/pipeline.py` ahora integra effect inference (P3-8) y capability mapping (P3-9):
  - `compile_to_air(source)` propaga effects → capabilities en cada AIRFunction.
- `ailang/runtime/air_runtime.py`: API `analyze_source(source)` y
  `run_with_air_verification(source, use_vm=, ctx=)`.
- CLI `ailang check <file.ailang>`: reporta capabilities y effects requeridos sin ejecutar.
- Fix effect checker: `_walk_expr_for_effects` visita Return/Let/Const/Assign/ExprStmt.value
  para detectar llamadas a `module.function()` en expresiones.

### P2-10 — Property-based testing con hypothesis
- `tests/test_property_based.py` con 13 properties:
  - Lexer nunca crashea con input arbitrario
  - Parser maneja literales enteros
  - Aritmética conmutativa (a+b == b+a) interp == VM
  - Aritmética asociativa ((a+b)+c == a+(b+c))
  - Distributividad (a*(b+c) == a*b+a*c)
  - Identidades aditiva (a+0 == a) y multiplicativa (a*1 == a)
  - Doble negación (not not x == x)
  - Formatter AST idempotente
  - Paridad interp↔VM para aritmética
  - Variables preservan valores
  - Llamadas a función preservan args
  - If/else selecciona branch correcta
- Suite total: 162 tests (149 + 13 property-based).

### P2-13 — CI multiplataforma (GitHub Actions)
- `.github/workflows/ci.yml` con 3 jobs:
  - `test`: matrix 3 OS (Ubuntu/Windows/macOS) × 3 Python versions (3.11/3.12/3.13)
    = 9 combinaciones. Ejecuta pytest + monolith embedded tests + examples smoke.
  - `lint`: self-lint con ailang linter + format_ast idempotency check.
  - `conformance`: conformance suite + property-based tests.

### P2-14 — Benchmarks reproducibles
- `ailang/bench.py` reescrito con 17 casos cubriendo FASE 30:
  aritmética, loops anidados, recursion (fib), closures, classes dispatch, strings,
  lists, dicts, exceptions, modules, JSON round-trip, generators, interpolation, channels.
- `run_bench(rounds=N, cases=[...])` retorna dict con metadata + results + summary.
- CLI `ailang bench [--rounds=N] [--save] [--cases ...]` con output tabular:
  ```
  Case              Interp (ms)   VM (ms)   Speedup
  arith_sum_1k         7.909      4.487     1.76x
  ```
- `ailang bench --save` persiste a `benchmarks/results/bench-<timestamp>.json`.
- Resultados: VM más rápida que interp en 15/17 casos (avg 1.5-2x speedup).

### Métricas
- Tests `pytest tests/`: 162/162 ✅ (149 + 13 property-based).
- Tests embebidos monolito: 44/44 ✅.
- `ailang doctor`: 11/11 componentes OK.
- Benchmarks: 17 casos reproducibles, VM faster en 15/17.

## 5.3.0 — P1 + P2 + P3 (arquitectura, tooling, IR pipeline)

### P1 — Partitionar monolito y eliminar frontend duplicado
- P1-1: `ailang/cognitive/` fachada, `ailang/cognitive/dsl/` migrado desde `ailang/compiler/`.
- P1-3 + P1-4: Eliminado `ailang/compiler/`, renombrado `compile_source` → `compile_cognitive`.
- P1-5: Tests embebidos migrados a `tests/test_ailang_core.py`.

### P2 — Tooling profesional
- P2-1: LSP ampliado (references/rename/documentSymbol/semanticTokens/signatureHelp/codeAction).
- P2-4: Formatter AST idempotente (`format_ast`).
- P2-5: Linter con reglas (E001/W001/W002/W003/W005).
- P2-15: `ailang doctor` diagnostica 11 componentes.

### P3 — Diagnostics, effects, capabilities, IR pipeline
- P3-6: Jerarquía `AILangError` completa (16 subclases + formato Rust-style).
- P3-8: Effect checker en `ailang/semantic/effects.py`.
- P3-9: Capability enforcement con CLI `--allow`/`--deny`.
- P3-1: Pipeline HIR/MIR/AIR (esqueleto funcional end-to-end).

## 5.2.0 — FASE C (VM conformance)

### P0-5/P0-6/P0-7/P0-8
- Cell upvalues (closures mutables), VMGenerator (yield), MAKE_ENUM/RECORD/INTERFACE/BUILD_STRING,
  VMScheduler event loop + VMFuture + VMChannel.

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
