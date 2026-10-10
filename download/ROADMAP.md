# ROADMAP.md — AILang

**Generado a partir de:** AUDIT_REPORT.md (FASE 0)
**Cumple:** FASE 43 del prompt maestro
**Convenio de prioridades:** P0 bloqueante · P1 estabilidad · P2 tooling · P3 optimización · P4 IA/hardware avanzado (experimental)
**Estado inicial:** `pending` (cada tarea se inicializa pendiente; al ejecutar el plan, los estados avanzan a `in_progress` → `done` o `blocked`).

---

## Convención por tarea

Cada tarea sigue el formato demandado por la FASE 43:

```
ID | Prioridad | Archivo/módulo | Problema | Solución | Dependencias | Riesgo | Tests | Estado
```

---

## P0 — Bloqueantes (impiden cualquier release)

| ID | Archivo/módulo | Problema | Solución | Dependencias | Riesgo | Tests | Estado |
|---|---|---|---|---|---|---|---|
| P0-1 | `ailang/versions.py` (nuevo), `pyproject.toml:3`, `ailang/__init__.py:4`, `ailang_core.py:118`, `ailang_core.py:3429`, `ailang/lang/stdlib/sys_mod.py:17`, `ailang/lsp.py` serverInfo, `README.md:1`, `CHANGELOG.md:3`, `tests/test_nivel_e.py:15` | Coexisten 9 versiones distintas (1.0.0, 2.0.0, 5.0.0, v7.0, v7.1, 7.1.0, v7.2, 8.0.0, v8.1, v8.3). Test `test_nivel_e.py:15` bloquea bumps. | Crear `ailang/versions.py` con 7 constantes: `LANGUAGE_VERSION`, `RUNTIME_VERSION`, `BYTECODE_VERSION`, `IR_VERSION`, `ABI_VERSION`, `STDLIB_VERSION`, `PACKAGE_FORMAT_VERSION`. `pyproject.toml` lee `__version__` dinámicamente. Todos los demás puntos leen de ahí. Cambiar `assertEqual(__version__, "5.0.0")` por `>= "5.0.0"`. | Ninguna | Bajo — mecánico | `test_version_consistency`: recorre todos los puntos y afirma que leen de `versions.py`. | pending |
| P0-2 | `ailang/lang/stdlib/re_mod.py:6` | `return null if False else None` — `null` no definido en Python → `NameError` en cada búsqueda regex fallida. | Reemplazar `null` por `None`. Mejor aún: `return re.search(pattern, text)`. | Ninguna | Bajo — 1 carácter | `test_re_search_no_match` debe retornar `None`, no lanzar. | pending |
| P0-3 | `ailang_core.py:2908` (`list`), `:2917` (`purge-dead`) | CLI del monolito llama a `PersistentOutbox.list_pending()` y `purge_dead()` — métodos inexistentes → `AttributeError`. | Implementar `list_pending(n)` como wrapper sobre `due(n)`, y `purge_dead()` como wrapper sobre `requeue_dead()` + `mark_dead()`. | Ninguna | Bajo | `test_cli_list_outbox`, `test_cli_purge_dead`. | pending |
| P0-4 | `ailang_core.py:3429` | Test embebido `test_version_and_prometheus` afirma `__version__ == "1.0.0"` pero `__version__ = "2.0.0"` → siempre falla. | Alinear con `__version__` de P0-1, o eliminar la aserción específica. | P0-1 | Bajo | Test pasa. | pending |
| P0-5 | `ailang/lang/vm.py:568-573` (`MAKE_FUNCTION`) | VM captura `clos = dict(self.globals); clos.update(names_local)` — snapshot en tiempo de definición. Mutaciones posteriores a closures capturados no se reflejan. `counter()` devuelve 1 en VM donde el intérprete devuelve 2. | Implementar upvalues mutables compartidas: cada variable capturada se envuelve en una `Cell` (envoltorio mutable). `MAKE_FUNCTION` guarda lista de Cells; `LOAD_NAME`/`STORE_NAME` en closure scope acceden via Cell. | Ninguna | Medio — refactor del modelo de variables | `test_vm_mutable_closure_parity`: `let c = counter(); c(); c(); assert c() == 3` corre en ambos modos. | pending |
| P0-6 | `ailang/lang/vm.py:294` | `raise "VM no soporta Yield"`. Generadores no implementados en VM. | Implementar `GeneratorValue` en VM con pausa/reanudación via `YIELD` opcode + frame stack de generadores. Alternativa aceptable a corto plazo: documentar VM como subset explícito y lanzar error explícito "VM no soporta generadores; usa `--no-vm`". | P0-5 (cells son prerequisito para closures de generadores) | Alto — feature compleja | `test_vm_generator_parity` para yield/yield from. | pending |
| P0-7 | `ailang/lang/vm.py:294, 334` | `raise "VM no soporta {EnumDef,InterfaceDef,RecordDef,Spawn}"` y `"expresión no compilable: {InterpolatedString,Await}"`. | Implementar cada uno: `enum` (const table + tag dispatch), `interface` (runtime type check en `implements`), `record` (dict con schema), `spawn` (integración con scheduler de P0-8), `InterpolatedString` (concatenación compilada). | P0-5, P0-8 (para spawn) | Alto | `test_vm_enum_parity`, `test_vm_interface_parity`, `test_vm_record_parity`, `test_vm_interpolation_parity`. | pending |
| P0-8 | `ailang/lang/interpreter.py:666-670` (`A.Await`), `ailang/lang/vm.py:334` | `await` es no-op (`return val`) en intérprete, error duro en VM. No hay event loop. | Implementar scheduler cooperativo: `spawn` crea `Task`, `await` suspende la task actual, scheduler reanuda cuando la task awaited termina. Modelo similar a asyncio pero con sintaxis nativa. `Channel` ya existe con `queue.Queue`. | P0-6 (generadores son prerrequisito para async/await via coroutines) | Alto — refactor del runtime | `test_async_basic`, `test_spawn_join`, `test_channel_send_recv_concurrent`. | pending |
| P0-9 | `ailang/storage/postgres_backend.py:68-91` | `upsert_document` y `replace_chunks` hacen `raise NotImplementedError`. `list_documents`, `list_chunks`, `search_lexical`, `search_vector` devuelven `[]`. | Reimplementar con `psycopg_pool.ConnectionPool`, prepared statements, transactions (`BEGIN/COMMIT/ROLLBACK`), pgvector cosine query (`<=>` operator). Mantener la schema actual en `_SCHEMA_SQL`. | psycopg[binary,pool] ≥ 3.2, pgvector extensión en servidor | Medio — dependencia externa | `test_postgres_crud`, `test_postgres_transactions`, `test_postgres_prepared`, `test_postgres_vector_search` (skip si no hay servidor). | pending |
| P0-10 | `ailang/debugger.py:73` | Body del `if self.state.paused and line in self.breakpoints:` es `pass`. El debugger nunca pausa. | Implementar pausa real con `threading.Event` + signalling: `_maybe_pause` llama `self._pause_event.wait()` cuando se alcanza un breakpoint activo. `continue()` hace `set()`. `step()` hace `set()` una vez. | Ninguna | Medio — threading | `test_debugger_pause_at_breakpoint`, `test_debugger_step_over`. | pending |
| P0-11 | `ailang_core.py:585-616` (`decode_bytecode`, `sign_bytecode`, `verify_bytecode_signature`), `ailang/lang/bytecode_io.py` | `sign_bytecode` y `verify_bytecode_signature` existen pero `AILangCompiler.compile()` y `decode_bytecode()` no los invocan. Bytecode corrupto/falsificado puede ejecutarse. | En `decode_bytecode`: extraer signature del header, invocar `verify_bytecode_signature(blob, signature, pubkey)`, lanzar `IntegrityError` si falla. En `AILangCompiler.compile`: invocar `sign_bytecode(blob, privkey)` y embeber signature en header. | Ninguna | Medio — cambio de formato de bytecode (bump `FORMAT_VERSION`) | `test_bytecode_signature_roundtrip`, `test_bytecode_tamper_detected`. | pending |

**Total P0:** 11 tareas.

---

## P1 — Estabilidad (post-P0, prerequisito para 1.0)

| ID | Archivo/módulo | Problema | Solución | Dependencias | Riesgo | Tests | Estado |
|---|---|---|---|---|---|---|---|
| P1-1 | `ailang/runtime_bridge.py`, `ailang/lang/stdlib/brain.py`, `ailang/lang/interpreter.py` | `ailang/` importa `ailang_core.py` en runtime → paquete no autónomo. | Mover `CognitiveBrainEngine`, `CognitiveBrainStore`, `HybridRetriever` a `ailang/cognitive/`. `runtime_bridge` y `brain.py` importan de ahí. | P1-2 | Alto — refactor arquitectónico | Tests existentes siguen pasando sin `ailang_core.py` en PYTHONPATH. | pending |
| P1-2 | `ailang_core.py:2243-2785` (CognitiveBrainStore, CognitiveBrainEngine, HybridRetriever, NexusAIEngine) | Code cognitivo del monolito debe migrarse al paquete. | Mover a `ailang/cognitive/{brain_store.py, brain_engine.py, retriever.py, latent_engine.py}`. Mantener `ailang_core.py` como thin re-export temporal. | Ninguna | Medio | Tests de `test_formal_ir.py` migrados a importar desde nueva ubicación. | pending |
| P1-3 | `ailang/compiler/` (todo el directorio) | Frontend cognitivo legacy v7.1 duplica `lang/` y colisiona en `compile_source`. | Migrar `memory`/`persist`/Zero-Footprint a un pass semántico sobre AST de `lang/` (nuevo `ailang/semantic/cognitive_pass.py`). Renombrar `compile_source` del frontend cognitivo a `compile_cognitive`. Eliminar `ailang/compiler/`. | P1-1 | Medio | `test_formal_ir.py` migrado; tests de zero-footprint pasan. | pending |
| P1-4 | `ailang/compiler/pipeline.py`, `ailang/lang/vm.py` | Colisión de símbolo público `compile_source`. | Renombrar el cognitivo a `compile_cognitive` (ver P1-3). | P1-3 | Bajo | Test que importa ambos nombres sin colisión. | pending |
| P1-5 | `ailang_core.py:3063-3528` | 44 tests embebidos en módulo de runtime. | Mover a `tests/test_ailang_core.py`. Usar pytest estándar. Eliminar `unittest` import en `ailang_core.py`. | P0-4 | Bajo | Tests pasan bajo `pytest tests/`. | pending |
| P1-6 | `ailang_core.py:2789-3059` | CLI embebido en módulo de runtime. | Mover a `ailang/cli_core.py`. O mover a `ailang/__main__.py` como subcomando `core`. | P0-3 | Bajo | `python -m ailang core --help` funciona. | pending |
| P1-7 | `tests/test_conformance.py` | Suite de conformance solo corre intérprete (`use_vm=False`). No valida `Interpreter == VM`. | Cada caso de conformance se parametriza para correrse con `use_vm=False` y `use_vm=True` y comparar resultados. Añadir casos C11+ para: mutable closures, generators, spawn/channels, enum, interface, record, interpolated strings, async/await. | P0-5, P0-6, P0-7, P0-8 | Medio — descubrir divergencias latentes | `pytest tests/test_conformance.py -k vm` pasa 100%. | pending |
| P1-8 | `ailang/lang/vm.py:680-690` | VM registra solo `print/len/str/int/float/range/true/false/null`. Faltan `type`, `isinstance`, `implements`, `channel`, `brain_*`. | Registrar todos los builtins del intérprete. Para `channel`, instanciar `ChannelValue`. Para `brain_*`, integrar con `ailang/cognitive/`. | P1-1 | Bajo | `test_vm_builtin_type`, `test_vm_builtin_implements`, `test_vm_channel`. | pending |
| P1-9 | `ailang/runtime_bridge.py:43-47` (`execute_unified`), `ailang/agent_runtime.py:60-83` (`TaskRuntime.run`) | `execute_unified` ignora `uir.agent` y `uir.task`. `TaskRuntime.run` marca `PENDING → DONE` sin ejecutar. | Implementar dispatch real: AgentRuntime con tools reales (no stores), TaskRuntime con ejecución real de payloads. Alternativa: deprecar AgentIR/TaskIR y eliminarlos. | P4-7 (agent runtime real) | Alto — semantics no triviales | `test_unified_dispatches_agent`, `test_unified_dispatches_task`. | pending |
| P1-10 | `ailang_core.py:1453-1455, 1523-1741` | `PersistentOutbox` permite cleartext a menos que `require_encryption=True` explícito. Docstring dice "Cifrado obligatorio si hay `secret`". | Default `require_encryption=True` cuando `secret` is not None. Raise si `cryptography` no está instalado. | Ninguna | Medio — puede romper callers existentes | `test_outbox_encrypted_by_default`, `test_outbox_raises_without_crypto`. | pending |
| P1-11 | `ailang_core.py:1196-1201` | `TcpTransport` solo `warnings.warn` cuando no hay auth. | Convertir a `raise TransportError` cuando `require_auth=True` y no haya `secret` ni TLS. | Ninguna | Medio — puede romper callers | `test_tcp_transport_raises_on_no_auth`. | pending |
| P1-12 | `ailang_core.py:1437-1441` (`derive_outbox_key`) | HKDF manual con dos HMAC passes. | Reemplazar con `cryptography.hazmat.primitives.kdf.hkdf.HKDF`. | Ninguna | Bajo | `test_outbox_key_derivation_parity` (antes vs después). | pending |
| P1-13 | `ailang_core.py:1510-1512` (`OutboxItem.payload`) | Si caller olvida `decrypt=`, retorna bytes cifrados reinterpretados como NumPy → garbage silencioso. | Validar: si item está cifrado y `decrypt is None`, lanzar `IntegrityError`. | Ninguna | Bajo | `test_outbox_payload_raises_without_decrypt`. | pending |
| P1-14 | `ailang/hardware/__init__.py:3`, `ailang/hardware/accel.py` | `GPUBackend`, `NPUBackend`, `TPUBackend` exportados como backends reales pero siempre delegan a CPU. | Marcar como `experimental` en `__init__.py` docstring. Renombrar exports: `GPUBackendExperimental`, etc. O eliminar exports hasta que sean reales. | P4-6 | Bajo — cambio de API | `test_hardware_exports_marked_experimental`. | pending |

**Total P1:** 14 tareas.

---

## P2 — Tooling (post-P1, prerequisito para adopción)

| ID | Archivo/módulo | Problema | Solución | Dependencias | Riesgo | Tests | Estado |
|---|---|---|---|---|---|---|---|
| P2-1 | `ailang/lsp.py` (185 LOC, 0% coverage) | Solo implementa ~7 métodos LSP. Faltan: references, rename, documentSymbol, workspaceSymbol, codeAction, signatureHelp, semanticTokens, formatting, documentHighlight, inlay hints. | Implementar cada método según spec LSP 3.17. Añadir tests de protocolo. | Ninguna | Medio | Tests LSP por método. Cobertura ≥ 80 %. | pending |
| P2-2 | `ailang/dap.py` (126 LOC, 0% coverage) | Solo ~7 métodos DAP. Faltan: threads, scopes, stepIn/Out/Back, evaluate, watch, setExceptionBreakpoints, pause, terminate, restart, loadedSources. continue no pausa. | Implementar completitud DAP 1.55. Integrar con debugger real (P0-10). | P0-10 | Medio | Tests DAP por método. Cobertura ≥ 80 %. | pending |
| P2-3 | `ailang/profiler.py` | Solo mide top-level statements. | Sampling profiler por función con `time.perf_counter()` y call graph. Output JSON + flamegraph (via `py-spy` o standalone). | Ninguna | Bajo | `test_profiler_callgraph`. | pending |
| P2-4 | `ailang/fmt.py:31` | Formatter token-stream; tiene dead code (`if False else`); no idempotente en comments. | Reformatear desde AST (parse → pretty-print). Idempotente. | P1-3 | Medio | `test_fmt_idempotent`, `test_fmt_preserves_comments`. | pending |
| P2-5 | `ailang/lint.py` | Solo typecheck + empty blocks. | Reglas: unused vars/imports, shadowing, unreachable, missing return, suspicious conversions, unsafe effects, missing capabilities, deprecated APIs. | P3-8 (effects) | Medio | Tests por regla. | pending |
| P2-6 | `ailang/coverage_tool.py` | Solo cuenta top-level statements. | Branch coverage + instrumentación bytecode-level + HTML/JSON report. | Ninguna | Medio | `test_coverage_branch`. | pending |
| P2-7 | `ailang/pkg.py` | Solo `init/install/list/run` locales. | `publish`, `update`, `remove`, `search`, version resolution, lock file, checksum/signature verification. | Registry remoto (P4?) | Alto — dependencia de registry | Tests por subcomando. | pending |
| P2-8 | `ailang/__main__.py` (171 LOC, 0% coverage) | CLI sin tests. | Smoke tests por subcomando: cada uno debe exit 0 en happy path, exit ≠ 0 en error. | Ninguna | Bajo | Cobertura ≥ 80 %. | pending |
| P2-9 | `ailang_core.py:3063-3528` | Tests embebidos. | Mover a `tests/` (también P1-5). | P1-5 | Bajo | `pytest tests/` los descubre. | pending |
| P2-10 | `tests/` | Sin property-based testing. | Añadir `hypothesis` strategies para: lexer (random strings → tokens), parser (random token streams → AST o error), typechecker (random programs → soundness), bytecode (random .ailc → round-trip), VM (random ops → same result as interp). | Ninguna | Medio — diseño de strategies | `test_property_lexer.py`, etc. | pending |
| P2-11 | `tests/` | Sin fuzzing. | Fuzz targets para: lexer, parser, typechecker, bytecode loader, VM. Integración con `atheris` o `pythonfuzz`. | Ninguna | Medio | CI corre fuzz smoke tests. | pending |
| P2-12 | `ailang/lsp.py`, `ailang/dap.py` | Sin tests de protocolo. | Tests que simulen cliente LSP/DAP via JSON-RPC mock. | P2-1, P2-2 | Bajo | Cobertura ≥ 80 %. | pending |
| P2-13 | CI | Sin CI multiplataforma. | GitHub Actions matrix: Windows/Linux/macOS × Python 3.11/3.12/3.13. Pasos: lint, typecheck, unit, integration, conformance, security, fuzz smoke, package build, docs validation. | Ninguna | Bajo | CI verde en push. | pending |
| P2-14 | `ailang/bench.py` (3 micro-benchmarks) | Benchmarks limitados. | Suite reproducible: arithmetic, loops, fn calls, closures, classes, strings, lists, dicts, exceptions, modules, JSON, concurrency, startup, compile time, memory, AI ops, tensor ops. Comparar Interpreter vs VM. Publicar resultados. | Ninguna | Bajo | `benchmarks/results/<date>.json` commiteado. | pending |
| P2-15 | CLI | Falta `ailang doctor`. | `ailang doctor` detecta: runtime, compiler, VM, stdlib, database, LSP, debugger, backends, dependencias. Reporta estado. | Ninguna | Bajo | `test_doctor_reports_all_components`. | pending |
| P2-16 | `docs/` | 18 contradicciones docs↔código (AUDIT_REPORT §6). | Reescribir: `GAP_ANALYSIS.md` (limpiar ❌ que ya son ✅), `EBNF.md` (agregar 13+ construcciones), `LANGUAGE_SPEC.md` (alinear stdlib con 13 módulos), `CHANGELOG.md` (entradas 6.x, 7.x, 8.x), `README.md` (versión correcta). | P0-1 | Bajo | CI valida que docs y `__version__` coinciden. | pending |

**Total P2:** 16 tareas.

---

## P3 — Optimización (post-P2, prerequisito para 1.0 según FASE 47)

| ID | Archivo/módulo | Problema | Solución | Dependencias | Riesgo | Tests | Estado |
|---|---|---|---|---|---|---|---|
| P3-1 | `ailang/ir/hir.py` (nuevo), `mir.py` (nuevo), `air.py` (nuevo), `ailang/compiler/hir_lower.py`, `mir_lower.py`, `air_lower.py` (nuevos) | No existe pipeline HIR→MIR→AIR (FASE 9). Existen 5 manifests IR aislados. | Implementar HIR (AST tipado + scopes), MIR (SSA + CFG), AIR (instrucciones tipadas con efectos, capabilities, source_location). Lowering automático entre etapas. | P1-1 | Alto — refactor mayor | Tests por pass: round-trip AST→HIR→AST, HIR→MIR→HIR, MIR→AIR→MIR. | pending |
| P3-2 | `ailang/compiler/mir_lower.py` | Sin optimizaciones MIR. | Constant folding, dead code elimination, inlining, common subexpression elimination. | P3-1 | Medio | Tests por optimización: input → MIR esperado. | pending |
| P3-3 | `ailang/lang/vm.py` | VM stack-based, sin inline caching. | Inline caching para calls a métodos. Considerar register-based opcodes para hot loops. | P3-1 | Alto — cambia bytecode | Benchmarks muestran ≥ 30 % speedup en call-heavy. | pending |
| P3-4 | `ailang/runtime/memory.py` (nuevo) | Sin memory model formal. | Object model + lifetime + references + cyclic structures + GC (mark-and-sweep o generacional). Memory limits. | Ninguna | Alto — runtime crítico | `test_gc_collects_cycles`, `test_memory_limit_enforced`. | pending |
| P3-5 | `ailang/frontend/source_map.py` (nuevo) | Source maps no preservados end-to-end. | SourceMap dataclass embebida en AST → HIR → MIR → AIR → bytecode → runtime frame. Errores VM reportan línea/columna del source original. | P3-1 | Medio | `test_source_map_vm_error_reports_original_line`. | pending |
| P3-6 | `ailang/frontend/diagnostics.py` (nuevo) | Jerarquía AILangError parcial (solo errors.py con clases básicas). | Implementar jerarquía completa FASE 7: LexError, SyntaxError, ParseError, TypeError, NameError, ImportError, RuntimeError, ValueError, IndexError, AttributeError, SecurityError, CapabilityError, TimeoutError, MemoryError, IOError, ConcurrencyError. Formato visual Rust-style con código, archivo, línea, columna, fragmento, indicador, mensaje, causa, sugerencia. | Ninguna | Bajo | Tests por tipo de error: formato visual correcto. | pending |
| P3-7 | `ailang/frontend/modules.py` (nuevo) | Module system parcial. | Resolución, paths, aliases, circular dependency detection, version constraints, cache, secure loading. | P1-1 | Medio | `test_module_circular_detected`, `test_module_version_constraints`. | pending |
| P3-8 | `ailang/semantic/effects.py` (nuevo) | Sin effect checker. | Inference de effects: pure, io, filesystem, network, ai, hardware, process, unsafe. Cada función declara/effects inferidos. `ailang check` valida. | P3-1 | Medio | `test_effect_inference`, `test_unsafe_effect_rejected`. | pending |
| P3-9 | `ailang/runtime/capabilities.py` (nuevo) | Capabilities declaradas en IR pero no enforced en runtime. | Cada builtin con efecto (`io`, `fs`, `network`, `process`, `ai`, `database`) verifica `runtime.has_capability(name)` antes de ejecutar. Default: deny. CLI: `ailang run app.ailang --allow fs.read --allow ai.query`. | P3-8 | Alto — cambio de UX | `test_capability_denied_by_default`, `test_capability_allowed_explicit`. | pending |

**Total P3:** 9 tareas.

---

## P4 — IA/Hardware avanzado (experimental, post-1.0)

| ID | Archivo/módulo | Problema | Solución | Dependencias | Riesgo | Tests | Estado |
|---|---|---|---|---|---|---|---|
| P4-1 | `ailang/backends/native/` (nuevo) | Sin backend nativo (FASE 31). | AIR → LLVM IR → native code. Targets: x86_64, ARM64. Sistemas: Windows, Linux, macOS. | P3-1, llvmlite | Alto — complejo | `test_native_compile_run_arithmetic`. | pending |
| P4-2 | `ailang/backends/wasm/` (nuevo) | Sin backend WASM (FASE 32). | AIR → WASM. `ailang build --target wasm`. Objetivos: browser, serverless, edge, sandbox. | P3-1, wasmtime | Alto | `test_wasm_compile_run`. | pending |
| P4-3 | `ailang/stdlib/tensor.py` (nuevo) | Sin tipo Tensor (FASE 33). Solo `TensorRef` dataclass. | Tensor con dtype, shape, device, memory layout, ops (matmul, softmax, normalization, embedding). Autograd. nn.Module. | P4-4 | Alto | `test_tensor_matmul`, `test_tensor_autograd`. | pending |
| P4-4 | `ailang/hardware/base.py` (expandir), `cpu.py`, `gpu.py`, `npu.py`, `tpu.py` | HAL skeleton (5 métodos). GPU/NPU/TPU son stubs. | HAL expandido: memory pools, async streams, device events, kernel launch, BLAS handle, profiling counters. GPU/NPU/TPU reales (cupy, torch_npu, openvino, jax, torch_xla). Cada backend marca: implemented / experimental / fallback / unavailable. | Ninguna | Alto | `test_hal_backend_status_reports`. | pending |
| P4-5 | `ailang/stdlib/crypto.py` (nuevo) | Sin API de criptografía (FASE 35). | hash, signature, key exchange, random, identity, secure storage. Separar: Language API / Provider / Backend. Para PQC usar implementaciones auditadas (no inventar). | cryptography lib | Alto — seguridad | Tests por primitiva. Audit criptográfico. | pending |
| P4-6 | `ailang/hardware/{gpu,npu,tpu}.py` | GPU/NPU/TPU actuales son fallbacks CPU. | Implementar paths reales: cupy para GPU CUDA, torch_npu para NPU Huawei, jax/torch_xla para TPU. Cada uno con smoke test en hardware real. | P4-4 | Alto — dependencias hardware | `test_gpu_matmul_real` (skip si no hay GPU). | pending |
| P4-7 | `ailang/ai/agent_runtime.py` (refactor) | AgentRuntime es stub (ACT stores args, DECIDE es relabel, THINK es echo). | Implementar agent runtime con tools reales: cada tool es una callable AILang con capability check. Scheduler integrado con concurrency (P0-8). | P0-8, P3-9 | Alto | `test_agent_observes_acts_decides`, `test_agent_respects_capabilities`. | pending |

**Total P4:** 7 tareas.

---

## Resumen ejecutivo del roadmap

| Prioridad | Tareas | Prerequisito para |
|---|---:|---|
| P0 | 11 | Cualquier release (incluido 0.x bugfix) |
| P1 | 14 | 1.0 |
| P2 | 16 | Adopción / tooling profesional |
| P3 | 9 | Performance / escala |
| P4 | 7 | Experimental / post-1.0 |
| **Total** | **57** | |

### Dependencias críticas (cadena P0)

```
P0-1 (versiones) ──┐
                    ├─→ P0-4 (test embebido) ──┐
                    │                            ├─→ P1-5 (tests a tests/)
                    │                            ├─→ P1-6 (CLI a cli_core.py)
                    │                            └─→ P2-16 (docs alineadas)
P0-5 (cells) ───────┼─→ P0-6 (generadores VM) ──┐
                    │                            ├─→ P0-7 (enum/record/... VM)
                    │                            └─→ P0-8 (async/await scheduler)
P0-2 (re_mod) ──────────────────────────────────── independiente
P0-3 (CLI monolito) ──────────────────────────── independiente
P0-9 (PostgreSQL) ────────────────────────────── independiente
P0-10 (debugger pause) ─→ P2-2 (DAP completo)
P0-11 (firma bytecode) ────────────────────────── independiente
```

### Estimación de esfuerzo

| Fase | Esfuerzo estimado | Comentario |
|---|---|---|
| P0 completo | 5-10 días-persona | Mayoría quirúrgica; P0-5, P0-7, P0-8 son los más grandes |
| P1 completo | 15-25 días-persona | P1-1, P1-2, P1-3 son refactor arquitectónico |
| P2 completo | 20-30 días-persona | Tests + tooling |
| P3 completo | 30-50 días-persona | P3-1 (HIR/MIR/AIR) es el más grande |
| P4 completo | 60-90+ días-persona | Cada backend (native, WASM, GPU real) es un proyecto en sí mismo |

### Criterios de avance por fase

Antes de pasar a la siguiente fase, **todos** los tests de la fase actual deben pasar y la conformance suite no debe tener regresiones:

- P0 done = los 11 P0-XXXX en `Estado: done` + `pytest tests/` verde + monolito `python ailang_core.py test` verde.
- P1 done = los 14 P1-XXXX en `Estado: done` + `ailang/` funciona sin `ailang_core.py` en PYTHONPATH.
- P2 done = los 16 P2-XXXX en `Estado: done` + cobertura ≥ 80 % global + CI multiplataforma verde.
- P3 done = los 9 P3-XXXX en `Estado: done` + HIR→MIR→AIR pipeline operativo + capabilities enforced en runtime.
- P4 done = los 7 P4-XXXX en `Estado: done` + cada backend marcado `implemented` o `experimental` con tests reales o skip condicional.

### Hitos sugeridos

| Hito | Cuándo | Criterio |
|---|---|---|
| **0.9.0-rc.1** | P0 + P1 done | Lenguaje coherente, autónomo, sin falsos claims |
| **0.9.5** | P2 done | Tooling profesional, 1000+ tests, CI verde |
| **1.0.0** | P3 done + FASE 47 cumplido | Pipeline HIR→MIR→AIR, capabilities enforced, docs alineadas |
| **1.x** | P4 parcial | Native/WASM como experimentales |
| **2.0** | P4 done | Native/WASM estables, GPU real |

---

## Notas operativas

- **No marcar `done` sin test que lo verifique.** Cada tarea debe tener al menos un test nombrado en su columna "Tests".
- **No pasar a P1 sin P0 completo.** Inversión estricta de dependencias.
- **Cada cambio de versión bump en `ailang/versions.py`** debe actualizarse simultáneamente en CHANGELOG.md.
- **Cualquier modificación de bytecode format** bump `BYTECODE_VERSION` y `FORMAT_VERSION` sincronizadamente.
- **Cualquier feature nueva al lenguaje** requiere: AST + parser + typecheck + effect + capability + HIR + MIR + AIR + interp + VM + bytecode + tests + spec + EBNF + ejemplo. Si falta alguno, la feature está incompleta (FASE 3).
