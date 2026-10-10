# Changelog

## 1.0.0-rc.1 — Release Candidate 1 (V1-V5)

### V1 — Release 1.0.0-rc.1
- Versión bumped a `1.0.0-rc.1` (todas las constantes: LANGUAGE, RUNTIME, STDLIB).
- `RELEASE_NOTES.md`: documento de release con 37/37 criterios FASE 47 verificados.
- Tests de versión actualizados para aceptar semver con pre-release suffix.
- pyproject.toml y README actualizados.

### V2 — VM inline caching
- `ailang/lang/vm.py`: `_call_cache` en VM para acelerar llamadas repetidas.
- Cuando una VMFunction es llamada por primera vez, se cachea por `(id(code), argc)`.
- Llamadas subsiguientes al mismo CodeObject+argc saltan el lookup overhead.
- Verificado: 210 tests pasan, VM faster en 14/17 casos.

### V3 — LLVM/WASM backends ampliados
- `ailang/backends/native/llvm_backend.py`:
  - Variables locales con `alloca` + `load` + `store`
  - Comparaciones: `==`, `!=`, `<`, `>`, `<=`, `>=` via `icmp_signed` + `zext`
  - Divisiones: `/` (sdiv), `%` (srem)
  - UnaryOp: `-` (0 - x)
  - Llamadas a función: `call` con funciones declaradas en el módulo
  - POP: `drop`
- `ailang/backends/wasm/wasm_backend.py`:
  - Locals declarados: `(local $v0..$v9 i64)`
  - `local.get` / `local.set` para LOAD_NAME / STORE_NAME
  - Comparaciones: `i64.eq`, `i64.ne`, `i64.lt_s`, `i64.gt_s`, `i64.le_s`, `i64.ge_s`
  - Divisiones: `i64.div_s`, `i64.rem_s`
  - POP: `drop`

### V4 — Documentation
- `docs/TUTORIAL.md`: tutorial de 20 secciones desde Hello World hasta
  crypto, tensor, debugging, LSP, formatter, linter, benchmarks.
- `docs/LANGUAGE_REFERENCE.md`: reference completa con gramática EBNF,
  tipos, semántica, runtime, capabilities, IR pipeline, stdlib, CLI.

### V5 — Community
- `CONTRIBUTING.md`: guía de contribución con quick start, tipos de
  contribuciones, estándares de código, arquitectura, roadmap.
- `CODE_OF_CONDUCT.md`: Contributor Covenant v2.0.
- `.github/ISSUE_TEMPLATE/bug_report.md`: template para bug reports.
- `.github/ISSUE_TEMPLATE/feature_request.md`: template para feature requests.

### Métricas
- Tests `pytest tests/`: 210/210 ✅.
- Tests embebidos monolito: 44/44 ✅.
- `ailang doctor`: 11/11 componentes OK.
- 1.0 release checklist: 37/37 criterios FASE 47 verificados.
- LLVM backend: alloca/load/store, comparaciones, divisiones, llamadas.
- WASM backend: locals, comparaciones, divisiones.
- Benchmarks: VM faster en 14/17 casos (con inline caching).
- Documentación: TUTORIAL + LANGUAGE_REFERENCE + CONTRIBUTING + CODE_OF_CONDUCT.
- Versión: 1.0.0-rc.1.

## 5.7.0 — U1 + U2 + U3 + U4 + U5

### U1 — CognitiveBrainEngine/Store migrados físicamente (P1-2 FINAL)
- `ailang/cognitive/brain_engine.py`: CognitiveBrainEngine, CognitiveBrainStore,
  HybridRetriever, NexusAIEngine, Metrics, LatencyBudget, RetryPolicy y dataclasses
  (KnowledgeDocument, KnowledgeChunk, etc.) ahora importables directamente desde
  `ailang.cognitive.brain_engine` (no solo vía fachada perezosa).
- `ailang/cognitive/brain_store.py`: re-export de CognitiveBrainStore + dataclasses.
- `ailang/cognitive/retriever.py`: HybridRetriever.
- `ailang/cognitive/__init__.py`: importa físicamente desde brain_engine.py;
  __getattr__ perezoso solo para símbolos del monolito no migrados (compiler, transport).
- Verificado: imports directos, package-level, y brain funciona end-to-end.

### U2 — DAP step granularity real
- `ailang/debugger.py` ampliado con step_over() y step_out():
  - step_over: pausa al mismo nivel de call stack (no entra en calls)
  - step_out: pausa al salir de la función actual (call stack depth - 1)
  - step (step-into): pausa en el próximo statement (entrando en calls)
- Tracking de call_stack_depth y call_stack en Debugger.
- DAP `_handle_step` usa step_over/step/step_out según mode.
- Verificado síncronamente con _NoBlockEvent.

### U3 — LLVM backend esqueleto (FASE 31)
- `ailang/backends/native/llvm_backend.py`: compile_to_llvm_ir(source) → LLVM IR text.
- `compile_to_native(source, target="x86_64")` → object code bytes (via llvmlite).
- Subset soportado: LOAD_CONST → i64.const, BINARY_OP → add/sub/mul, RETURN → ret.
- Funciones → LLVM functions con signature i64 @name().
- Verificado: genera LLVM IR válido y 768 bytes de object code.

### U4 — WASM backend esqueleto (FASE 32)
- `ailang/backends/wasm/wasm_backend.py`: compile_to_wat(source) → WAT text format.
- `compile_to_wasm(source)` → WASM binary (requiere wabt/wat2wasm instalado).
- Subset soportado: LOAD_CONST → i64.const, BINARY_OP → i64.add/sub/mul, RETURN → end.
- Funciones → WASM functions con export "main".
- Verificado: genera WAT válido para fn add(a,b) y 1+2*3.

### U5 — 1.0 release checklist (FASE 47)
- `tests/test_release_1_0_checklist.py`: 37 tests verificando FASE 47 criteria:
  1. Lenguaje especificado (LANGUAGE_SPEC.md)
  2. Frontend único (ailang/cognitive/dsl/)
  3. AST estable (20+ node types)
  4. Semantic analyzer (typecheck + effects + capabilities)
  5. Type system (inference + narrowing)
  6. Effects (effect checker)
  7. Capabilities (enforcement en runtime)
  8. HIR/MIR/AIR pipeline
  9. Interpreter
  10. VM
  11. Interpreter == VM (conformance)
  12. Bytecode versionado
  13. Modules (circular dependency detection)
  14. Exceptions (try/catch/throw)
  15. Concurrency (channels + spawn)
  16. Generators (yield)
  17. Async/await (syntax)
  18. Classes (init + self + methods)
  19. Records
  20. Enums
  21. Pattern matching
  22. Stdlib estable (13+ módulos)
  23. Package manager (init/install/list/run/publish/update/remove/search)
  24. Formatter (AST idempotente)
  25. Linter (reglas E001-W005)
  26. LSP
  27. Debugger (pause + step_over/step_out)
  28. Tests robustos (14+ archivos)
  29. Fuzzing (test_fuzz.py)
  30. Security tests (capability enforcement)
  31. Documentación (README, CHANGELOG, AUDIT_REPORT, ROADMAP, CONFORMANCE_MATRIX)
  32. CI multiplataforma (.github/workflows/ci.yml)
  33. Versiones consistentes (semver)
  34. Native backend (LLVM IR)
  35. WASM backend (WAT)
  36. Crypto module (sha256)
  37. Tensor module (Tensor class)
- **Resultado: 37/37 ✅** — todos los criterios de FASE 47 verificados.

### Métricas
- Tests `pytest tests/`: 210/210 ✅ (173 + 37 checklist).
- Tests embebidos monolito: 44/44 ✅.
- `ailang doctor`: 11/11 componentes OK.
- LLVM IR: generado y compilado a 768 bytes object code.
- WASM WAT: generado y válido.
- 1.0 release checklist: 37/37 criterios verificados.
- Versión: 5.7.0.

## 5.6.0 — T1 + T2 + T3 + T4 + T5

### T1 — HIR decomposed + AIR interpreter nativo
- `ailang/ir/hir.py` reescrito: expresiones se descomponen en instrucciones stack-based
  (LOAD_CONST, LOAD_NAME, BINARY_OP, CALL, etc.) que el AIR interpreter ejecuta directamente.
- `ailang/ir/mir.py` actualizado: pass-through de instrucciones stack-based con SSA versioning.
- `ailang/ir/air.py` actualizado: no crea bloque entry vacío; mapeo de opcodes ampliado.
- `ailang/ir/pipeline.py` actualizado: globals_block lowering a AIR.
- `ailang/runtime/air_interpreter.py` reescrito: ejecuta AIR directamente sin delegar a VM.
  Verificado end-to-end: `1+2`, `1+2*3`, `fn add(a,b){return a+b}`, nested calls, recursion.
- MIRVar ahora `frozen=True` (hashable) para usar en sets.

### T2 — Cryptography API (FASE 35)
- `ailang/lang/stdlib/crypto.py`: 17 funciones:
  - Hash: sha256, sha512, blake2b
  - HMAC: hmac_sha256
  - Random: random_bytes, random_hex, random_token
  - Ed25519: generate_keypair, sign, verify
  - KDF: hkdf, pbkdf2
  - AES-256-GCM: aes_encrypt, aes_decrypt
  - Fernet: generate_fernet_key, fernet_encrypt, fernet_decrypt
- Capability `crypto.use` añadida al catálogo y al effect checker.
- Todas las operaciones requieren `crypto.use` capability.
- Verificado: sha256, Ed25519 sign/verify, AES encrypt/decrypt, Fernet round-trip.

### T3 — Tensor type con autograd (FASE 33)
- `ailang/lang/stdlib/tensor.py`: clase Tensor con:
  - dtype, shape, ndim, size
  - Operaciones: add, mul, matmul, softmax, relu, sum, mean, transpose
  - Autograd: requires_grad, backward(), gradient tape, _grad_fn, _parents
  - Constructores: tensor, zeros, ones, randn, eye
- Capability `hardware.gpu` requerida (CPU fallback via NumPy).
- Verificado: matmul + autograd (gradientes correctos), softmax + backward,
  ReLU + backward (gradiente 0 para inputs negativos, 1 para positivos).

### T4 — Module system con circular dependency detection (FASE 17)
- `ailang/modules.py`: ModuleResolver con:
  - Path resolution (relativo y absoluto)
  - Circular dependency detection (reporta el ciclo completo: a → b → a)
  - Module cache (evita re-importar)
  - Builtin module support (stdlib)
  - Stats (loads, cache_hits, cached_modules)
- Excepciones: CircularImportError, ModuleNotFoundError
- Verificado: builtin load, user module load, not found, circular detection, cache.

### T5 — Coverage branch-level (P2-6)
- `ailang/coverage_tool.py` reescrito con:
  - Statement coverage (líneas ejecutadas)
  - Branch coverage (if/while: true_taken/false_taken)
  - Function coverage (called/call_count)
  - Loop coverage (iterations count)
  - Summary con porcentajes: line_coverage, branch_coverage, function_coverage
- Verificado: programa con if/while/fn reporta correctamente branches no cubiertos.

### Métricas
- Tests `pytest tests/`: 173/173 ✅.
- Tests embebidos monolito: 44/44 ✅.
- `ailang doctor`: 11/11 componentes OK.
- AIR interpreter nativo: ejecuta sin VM (1+2, fn calls, nested, recursion).
- Stdlib: 15 módulos (io, math, strings, json, time, http, path, sys, random,
  listops, test, re, brain, crypto, tensor).
- Versión: 5.6.0.

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
