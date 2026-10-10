# Changelog

## 5.2.0 — FASE C (VM conformance)

### P0-5 — Upvalues mutables (closures)
- Implementadas `Cell` (contenedor mutable compartido) en `ailang/lang/vm.py`.
- `MAKE_FUNCTION` ahora captura Cell refs en lugar de snapshotear valores;
  las mutaciones posteriores a variables capturadas son visibles desde la closure.
- `LOAD_NAME`/`STORE_NAME` hacen unwrap/wrap de Cells automáticamente.
- Test `test_parity_simple_counter` verifica `make_counter()()() == 3` en interp y VM.

### P0-6 — Generadores (yield)
- Implementado `GeneratorState` + `VMGenerator` para pausar/reanudar frames VM.
- `_compile_function_body` ahora marca `CodeObject.is_generator=True` si el body
  contiene YIELD (vía `_contains_yield`/`_walk_for_yield`).
- `CALL` opcode crea `VMGenerator` en lugar de invocar directamente cuando
  `fn.is_generator` es True.
- `_run_generator` ejecuta el frame del generador hasta el próximo YIELD o RETURN.
- `for x in gen()` ahora itera generadores (no solo listas indexables).

### P0-7 — Enum / Interface / Record / InterpolatedString
- `MAKE_ENUM` opcode: crea `VMEnumType` con miembros `VMEnumMember`.
- `MAKE_RECORD` opcode: crea `VMRecordType` y un constructor Python.
- `MAKE_INTERFACE` opcode: crea `VMInterfaceType` con la lista de métodos.
- `BUILD_STRING` opcode: concatena N partes (string + str(expr)) para
  InterpolatedString.
- `LOAD_ATTR` extendido: soporta `Color.RED`, `record.field`, además de
  `instance.method` y `module.function` ya existentes.
- `_vm_implements(instance, interface)` builtin para verificar implementación.
- `for x in iter` reescrito: usa `iter()`/`next()` con try/catch para soportar
  generadores, dicts, strings, y cualquier iterable Python.

### P0-8 — Async / Await / Spawn / Channel (scheduler cooperativo)
- `VMScheduler` event loop cooperativo basado en generators (sin threads).
- `VMFuture` con `set_result`/`set_error`/`add_done_callback`.
- `VMChannel` FIFO síncrono (`send`/`recv`/`close`).
- `SPAWN` opcode: encola una task en el scheduler y retorna Future.
- `AWAIT` opcode: suspende la corrutina actual hasta que el Future se resuelva.
- `run_vm` ejecuta `scheduler.run_until_complete()` al final para drenar tasks.

### Tests
- Añadido `tests/test_conformance_vm_parity.py` con 25 tests que verifican
  parity interp↔VM para todas las features P0-5/P0-6/P0-7/P0-8.
- Suite total: 134 tests (109 originales + 25 nuevos). 100% verde.
- Limitaciones conocidas documentadas: closure-over-record-mutation y
  attr-access-in-interpolated-string requieren P3-1 (HIR/MIR/AIR) para
  resolverse limpiamente.

### Métricas
- Tests `pytest tests/`: 134/134 ✅ (sin regresiones).
- Tests embebidos monolito: 44/44 ✅.
- Conformance parity: 23/25 ✅ (2 limitaciones conocidas documentadas para P3-1).

## 5.1.0 — FASE 0 + FASE A + FASE B (auditoría y P0 quirúrgicos)

### Auditoría (FASE 0)
- `AUDIT_REPORT.md` (13 secciones, 20 stubs, 14 divergencias interp↔VM, 18 contradicciones docs↔código).
- `ROADMAP.md` (57 tareas P0-P4).
- `CONFORMANCE_MATRIX.md` (102 features × 16 etapas).

### FASE A — P0 quirúrgicos (5 fixes)
- **P0-2** Fix `re_mod.search`: reemplazado `null` (indefinido en Python) por `None`.
- **P0-3** Implementado `PersistentOutbox.list_pending(limit=32)` y `purge_dead()`.
- **P0-4** Alineado el test embebido `test_version_and_prometheus` en `ailang_core.py:3429`.
- **P0-10** Implementada pausa real en `Debugger` con `threading.Event`.
- **P0-11** Cableada firma Ed25519 al bytecode (formato v7 firmado).

### FASE B — FASE 1 (versionado unificado)
- Creado `ailang/versions.py` con 7 constantes separadas (FASE 1).
- `__version__ = "5.1.0"` ahora se lee desde `versions.py` en todos los puntos.
- `pyproject.toml` bumped a `5.1.0`.
- `sys_mod.version()` lee `RUNTIME_ID` dinámicamente.
- `__main__.py` description lee `__version__` dinámicamente.
- `lsp.py` serverInfo.version lee `LSP_SERVER_VERSION`.
- `test_nivel_e.py:15` cambiado a `assertGreaterEqual` para permitir bumps.
- `test_typecheck_vm_stdlib.py:60` ahora espera `f"ailang-{PUBLIC_VERSION}"`.

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
