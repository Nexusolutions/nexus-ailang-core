# CONFORMANCE_MATRIX.md — AILang

**Generado a partir de:** AUDIT_REPORT.md (FASE 0)
**Cumple:** FASE 44 del prompt maestro
**Leyenda de estados:**
- ✅ Implementado y testeado en ambas rutas (Interpreter y VM)
- ⚠️ Implementado solo en Interpreter; VM diverge o no soporta
- ❌ No implementado en ninguna ruta
- 🔴 Stub / mock / fake implementation
- 🟡 Parcial / API sin semántica completa
- N/A No aplica a esta etapa del pipeline

**Criterio de completitud (FASE 44):** Ninguna feature se considera completa si tiene huecos críticos. La presencia de ⚠️ o ❌ en cualquier columna marca la feature como NO CONFORME.

---

## Matriz principal — Features × Etapas del pipeline

| # | Feature | Lexer | Parser | AST | Semantic | Typechecker | HIR | MIR | AIR | Interpreter | Bytecode | VM | Stdlib | LSP | DAP | Tests | Status |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Literals (int, float, string, bool, null) | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 2 | Variables (`let`) | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 3 | Constants (`const`) | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ✅ | ⚠️ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM ignora flag `const` |
| 4 | Assignment | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 5 | Blocks `{ ... }` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 6 | `if` / `else` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 7 | `while` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 8 | `for x in iter` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ⚠️ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM usa index loop, diverge en iterables no indexables (dicts, generators) |
| 9 | Functions (`fn`) | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 10 | Lambdas | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 11 | Closures (inmutables) | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 12 | **Closures mutables** | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ⚠️ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM usa snapshot, mutaciones no visibles |
| 13 | `return` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 14 | `break` / `continue` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 15 | Classes + `init` + `self` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 16 | `extends` + `super` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 17 | Polimorfismo (dispatch dinámico) | N/A | N/A | N/A | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 18 | Imports (builtins) | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 19 | Imports (módulos `.ailang`) | ✅ | ✅ | ✅ | ⚠️ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — Sin circular dependency detection |
| 20 | `try` / `catch` / `throw` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 21 | `match` (literal + binding) | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — Sin wildcard `_`; sin pattern typing |
| 22 | Interpolated strings `"${x}"` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM no compila InterpolatedString |
| 23 | `enum` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM raise |
| 24 | `interface` + `implements()` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM raise; spec no documenta |
| 25 | `record` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM raise; spec no documenta |
| 26 | `yield` / generadores | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM raise |
| 27 | `channel()` + `send`/`recv` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM no registra builtin `channel` |
| 28 | `spawn` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM raise; usa `threading.Thread` sin política |
| 29 | `async fn` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ⚠️ | ❌ | ❌ | ✅ | ✅ | N/A | ⚠️ | ⚠️ NO CONFORME — No hay event loop; flag almacenado pero ignorado |
| 30 | `await` | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | N/A | N/A | N/A | ⚠️ | ❌ | ❌ | ✅ | ✅ | N/A | ⚠️ | ⚠️ NO CONFORME — Interpreter no-op; VM raise |
| 31 | `purge_after(Nms)` directive | ✅ | ✅ | ✅ | ⚠️ | ✅ | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM no reconoce; spec drift en `ms` keyword |
| 32 | `purge_after` múltiple | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | ❌ | ❌ NO CONFORME — Spec permite `{ directive \| stmt }*` pero solo uno se respeta |
| 33 | Type: `Int`, `Float`, `Bool`, `String`, `Null` | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 34 | Type: `List[T]`, `Dict[K,V]`, `Tuple[T...]` | ✅ | ✅ | ✅ | ✅ | ⚠️ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ⚠️ | ⚠️ NO CONFORME — Sin inference completa de colecciones |
| 35 | Type: `Function[A,B]`, `Future[T]`, `Generator[T]`, `Channel[T]`, `Tensor[T]` | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ | N/A | N/A | N/A | ⚠️ | ❌ | ❌ | ⚠️ | ❌ | N/A | ❌ | ❌ NO CONFORME — Tensor no existe |
| 36 | Type: `Union`, `Optional`, `Generic` | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | ❌ | ❌ NO CONFORME — Sin generics |
| 37 | Type inference | N/A | N/A | N/A | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME (parcial) |
| 38 | Type narrowing en `if` | N/A | N/A | N/A | ✅ | ✅ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 39 | `native` type (spec) | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | ❌ | ❌ NO CONFORME — Especificado en LANGUAGE_SPEC pero no implementado |
| 40 | Builtins `print`/`len`/`str`/`int`/`float`/`range` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | ✅ CONFORME |
| 41 | Builtins `type`/`isinstance`/`implements` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ⚠️ | ❌ | ✅ | ✅ | N/A | ✅ | ⚠️ NO CONFORME — VM no registra |
| 42 | Builtins `brain_ingest/query/think/graph` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | ❌ | ❌ | ⚠️ | ⚠️ | N/A | ⚠️ | ⚠️ NO CONFORME — Requiere engine externo; VM no registra |
| 43 | stdlib `io` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 44 | stdlib `math` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 45 | stdlib `strings` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 46 | stdlib `json` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 47 | stdlib `re` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | N/A | ⚠️ | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — `search()` lanza `NameError` por `null` |
| 48 | stdlib `time` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 49 | stdlib `http` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Sin tests reales (solo shape) |
| 50 | stdlib `path` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ⚠️ | ⚠️ Parcialmente testeado |
| 51 | stdlib `sys` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — `version()` retorna string hardcodeado discordante |
| 52 | stdlib `random` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 53 | stdlib `listops` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 54 | stdlib `test_mod` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ⚠️ | ⚠️ Parcialmente testeado |
| 55 | stdlib `brain` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | ❌ | ⚠️ | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Solo puente, requiere engine externo |
| 56 | stdlib `crypto` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | N/A | ❌ | N/A | N/A | ❌ | ❌ NO CONFORME — Módulo inexistente (FASE 35) |
| 57 | stdlib `tensor` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | N/A | ❌ | N/A | N/A | ❌ | ❌ NO CONFORME — Módulo inexistente (FASE 33) |
| 58 | Storage SQLite | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 59 | Storage PostgreSQL | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 🔴 | N/A | N/A | 🔴 | N/A | N/A | 🔴 | 🔴 NO CONFORME — Todos los métodos raise o return [] |
| 60 | Hardware CPU | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 61 | Hardware GPU | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 🔴 | N/A | N/A | 🔴 | N/A | N/A | 🔴 | 🔴 NO CONFORME — Stub que delega a CPU |
| 62 | Hardware NPU | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 🔴 | N/A | N/A | 🔴 | N/A | N/A | 🔴 | 🔴 NO CONFORME — Stub |
| 63 | Hardware TPU | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 🔴 | N/A | N/A | 🔴 | N/A | N/A | 🔴 | 🔴 NO CONFORME — Stub |
| 64 | CognitiveIR | N/A | ✅ | ✅ | ✅ | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | N/A | N/A | N/A | ✅ | ✅ CONFORME |
| 65 | CognitiveBrainEngine (ingest/query/think/graph) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | ⚠️ | ⚠️ | N/A | N/A | ✅ | ⚠️ NO CONFORME — Existe solo en monolito; VM no registra builtins |
| 66 | AgentIR + AgentRuntime | N/A | ✅ | ✅ | ✅ | N/A | N/A | N/A | N/A | 🔴 | N/A | N/A | N/A | N/A | N/A | ✅ | 🔴 NO CONFORME — ACT/DECIDE son stubs; THINK es echo |
| 67 | TaskIR + TaskRuntime | N/A | ✅ | ✅ | ✅ | N/A | N/A | N/A | N/A | 🔴 | N/A | N/A | N/A | N/A | N/A | ✅ | 🔴 NO CONFORME — Marca PENDING→DONE sin ejecutar |
| 68 | SecurityIR (capabilities) | N/A | N/A | ✅ | ✅ | N/A | N/A | N/A | N/A | ⚠️ | N/A | N/A | ⚠️ | N/A | N/A | ✅ | ⚠️ NO CONFORME — Existe pero no se invoca en runtime |
| 69 | `execute_unified` (IR dispatcher) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | N/A | N/A | N/A | N/A | ✅ | ⚠️ NO CONFORME — Solo despacha cognitive; agent y task ignorados |
| 70 | Bytecode `.ailc` (load/save) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ✅ | ✅ | N/A | N/A | N/A | ✅ | ⚠️ NO CONFORME — Sin firma/verificación |
| 71 | Bytecode signature (sign/verify) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — Funciones existen pero no se invocan |
| 72 | Diagnostics (jerarquía AILangError) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ | N/A | ⚠️ | N/A | ✅ | ⚠️ NO CONFORME — Jerarquía parcial; sin formato visual Rust-style |
| 73 | Source maps end-to-end | N/A | N/A | ✅ | ✅ | N/A | N/A | N/A | N/A | ⚠️ | ⚠️ | ⚠️ | N/A | N/A | N/A | ✅ | ⚠️ NO CONFORME — Parciales; no preservados en bytecode |
| 74 | Module system (circular deps, version constraints, cache, secure loading) | N/A | N/A | N/A | ⚠️ | N/A | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ | ⚠️ | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Sin circular dependency detection |
| 75 | Effect checker | N/A | N/A | N/A | ❌ | ❌ | N/A | N/A | N/A | ❌ | N/A | ❌ | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — No existe (FASE 11) |
| 76 | Capability enforcement en runtime | N/A | N/A | N/A | ❌ | ❌ | N/A | N/A | N/A | ❌ | N/A | ❌ | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — Solo se valida en IR, no en runtime |
| 77 | HIR (High-level IR) | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | N/A | ❌ | N/A | ❌ | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — No existe (FASE 9) |
| 78 | MIR (Mid-level IR) | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | ❌ | N/A | ❌ | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — No existe (FASE 9) |
| 79 | AIR (AILang IR) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ | N/A | ❌ | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — No existe (FASE 9) |
| 80 | Native backend (LLVM) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — No existe (FASE 31) |
| 81 | WASM backend | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — No existe (FASE 32) |
| 82 | Concurrency: scheduler, structured concurrency, deadlock diagnostics | N/A | N/A | ✅ | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | ❌ | N/A | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — `threading.Thread` sin política; VM no soporta spawn |
| 83 | Memory model + GC | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ | N/A | N/A | N/A | ❌ | ⚠️ NO CONFORME — Sin GC formal; sin memory limits |
| 84 | LSP: completion, hover, definition, diagnostics | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | ❌ | ⚠️ Parcial |
| 85 | LSP: references, rename, documentSymbol, workspaceSymbol, codeAction, signatureHelp, semanticTokens, formatting, documentHighlight, inlay hints | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | ❌ | ❌ NO CONFORME — Faltan 9+ métodos LSP |
| 86 | DAP: initialize, launch, setBreakpoints, continue, next, stackTrace, variables, disconnect | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ❌ | ⚠️ Parcial — 0% coverage; `continue` no pausa |
| 87 | DAP: threads, scopes, stepIn/Out/Back, evaluate, watch, setExceptionBreakpoints, pause, terminate, restart, loadedSources | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ | ❌ NO CONFORME — Faltan 10+ métodos DAP |
| 88 | Debugger: breakpoints, conditional breakpoints, step over/into/out, continue, pause, locals, call stack, watch, exception breakpoints | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | N/A | N/A | N/A | ⚠️ | ✅ | ⚠️ NO CONFORME — Registra breakpoints pero no pausa |
| 89 | Profiler: startup, parsing, compilation, VM, functions, allocations, memory, tasks, AI calls, database, IO | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ | N/A | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Solo top-level stmt timing |
| 90 | Formatter (desde AST, idempotente, determinista) | N/A | ✅ | ✅ | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | N/A | N/A | ✅ | N/A | ⚠️ | ⚠️ NO CONFORME — Token-stream, no AST; no idempotente en comments |
| 91 | Linter (unused, shadowing, unreachable, missing return, suspicious conversions, unsafe effects, missing capabilities, deprecated APIs) | N/A | N/A | ✅ | N/A | ✅ | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ | N/A | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Solo typecheck + empty blocks |
| 92 | Coverage (branch, instrumentation, HTML/JSON report) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | N/A | N/A | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Solo cuenta statements top-level |
| 93 | Package manager: init, install, list, run | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | N/A | N/A | ✅ | N/A | N/A | ✅ | ✅ CONFORME (local) |
| 94 | Package manager: publish, update, remove, search, version resolution, lock file, checksum/signature verification | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | N/A | ❌ | N/A | N/A | ❌ | ❌ NO CONFORME — Sin remote registry |
| 95 | CLI: run, --repl, --vm, --strict, --version | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | ✅ CONFORME |
| 96 | CLI: build, check, test, fmt, lint, repl, debug, profile, doc, package, publish, install, clean, doctor, version | ⚠️ | ⚠️ | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | ⚠️ | ⚠️ | ⚠️ | N/A | N/A | ❌ | ⚠️ NO CONFORME — Faltan: build, check, clean, doctor, publish, install (subcommand), version inconsistente |
| 97 | Tests count ≥ 1000 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — 153 tests (15% del objetivo) |
| 98 | Property-based testing | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — Cero |
| 99 | Fuzzing (lexer, parser, typechecker, bytecode, VM) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — Cero |
| 100 | CI multiplataforma (Windows/Linux/macOS) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | ❌ NO CONFORME — Sin CI configurado |
| 101 | Benchmarks reproducibles | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⚠️ | N/A | ⚠️ | N/A | N/A | N/A | ⚠️ | ⚠️ NO CONFORME — Solo 3 micro-benchmarks |
| 102 | Documentación coherente con código | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ NO CONFORME — 18 contradicciones catalogadas |

---

## Resumen de conformidad

| Estado | Cantidad | % del total |
|---|---:|---:|
| ✅ CONFORME | 28 | 27.5 % |
| ⚠️ NO CONFORME (parcial/divergente) | 47 | 46.1 % |
| ❌ NO CONFORME (ausente) | 27 | 26.5 % |
| **Total features auditadas** | **102** | 100 % |

### Distribución por área

| Área | Conformes | No conformes | Conformidad |
|---|:---:|:---:|:---:|
| Lenguaje básico (literals, vars, if, while, fn, class, try/catch, match) | 13 | 4 | 76 % |
| Tipos (basic, compuestos, inferencia) | 4 | 3 | 57 % |
| Async/concurrency/yield/spawn/channels | 0 | 6 | 0 % |
| Enum/record/interface | 0 | 3 | 0 % |
| Stdlib (13 módulos) | 7 | 6 | 54 % |
| Storage (SQLite/PostgreSQL) | 1 | 1 | 50 % |
| Hardware (CPU/GPU/NPU/TPU) | 1 | 3 | 25 % |
| IR (cognitive/agent/task/security + dispatcher) | 1 | 4 | 20 % |
| Bytecode + firma | 0 | 2 | 0 % |
| Diagnostics + source maps + modules + effects + capabilities | 0 | 5 | 0 % |
| HIR/MIR/AIR + Native + WASM | 0 | 5 | 0 % |
| Tooling (LSP/DAP/debugger/profiler/fmt/lint/coverage) | 0 | 8 | 0 % |
| Package manager | 1 | 1 | 50 % |
| CLI | 1 | 1 | 50 % |
| Tests/CI/fuzzing/benchmarks/docs | 0 | 5 | 0 % |

### Conformidad por modo de ejecución

| Modo | Conformidad |
|---|---|
| Interpreter (default) | ~70 % de features conformes o parciales (async/await no-op es la excepción notable) |
| VM (`--vm` o `AILANG_VM=1`) | ~25 % de features conformes. Solo core aritmético/fn/class/try/import está verificado |

### Conformidad por etapa del pipeline

| Etapa | Conformidad |
|---|---|
| Lexer | ~85 % |
| Parser | ~80 % |
| AST | ~85 % |
| Semantic | ~50 % (sin effects, sin capabilities en runtime, sin circular dep detection) |
| Typechecker | ~60 % (sin generics, sin union narrowing completo) |
| HIR | 0 % |
| MIR | 0 % |
| AIR | 0 % |
| Interpreter | ~75 % (async/await roto) |
| Bytecode | ~50 % (sin firma/verificación) |
| VM | ~30 % (divergencias en 11 categorías) |
| Stdlib | ~70 % (12/13 reales; re roto; brain es puente; crypto/tensor ausentes) |
| LSP | ~35 % |
| DAP | ~30 % |
| Tests | 15 % del objetivo |

---

## Huecos críticos que bloquean 1.0

Según FASE 44: "Ninguna feature se considera completa si tiene huecos críticos."

### Huecos P0 (bloqueantes inmediatos)

1. **VM diverge en 11 categorías** (features 12, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31 de la matriz)
2. **PostgreSQL backend es fake** (feature 59)
3. **Debugger no pausa** (feature 88)
4. **Bytecode sin firma** (feature 71)
5. **`re_mod.search` lanza NameError** (feature 47)
6. **AgentRuntime/TaskRuntime son stubs** (features 66, 67)
7. **`execute_unified` ignora agent/task** (feature 69)
8. **GPU/NPU/TPU exportados como reales** (features 61, 62, 63)
9. **Test embebido del monolito falla garantizadamente** (P0-4)
10. **CLI del monolito crashea en list/purge-dead** (P0-3)
11. **9 versiones distintas coexisten** (P0-1)

### Huecos P1 (estabilidad para 1.0)

12. **HIR/MIR/AIR inexistentes** (features 77, 78, 79)
13. **Effect checker inexistente** (feature 75)
14. **Capability enforcement en runtime inexistente** (feature 76)
15. **Native/WASM backends inexistentes** (features 80, 81)
16. **Async/await sin event loop** (features 29, 30)
17. **Tests < 16 % del objetivo** (feature 97)
18. **Sin property-based testing ni fuzzing** (features 98, 99)
19. **Sin CI** (feature 100)
20. **18 contradicciones docs↔código** (feature 102)

---

## Próximos pasos inmediatos

1. **Resolver los 11 P0 del ROADMAP.md** — ninguno requiere más de 50 LOC de cambio excepto P0-5, P0-7, P0-8.
2. **Re-ejecutar esta matriz después de P0 completo** — las features 12, 22-31, 47, 59, 71, 88 deberían pasar de ⚠️/❌ a ✅.
3. **Re-ejecutar esta matriz después de P1 completo** — las features 65-69, 76 deberían pasar a ✅.
4. **Re-ejecutar esta matriz después de P3 completo** — las features 75-79 deberían pasar a ✅.
5. **No declarar 1.0 hasta que toda la matriz esté ✅ o explícitamente N/A** (excepto P4 marcado como experimental).

---

## Notas metodológicas

- Esta matriz fue generada a partir de 5 sub-auditorías paralelas cubriendo: monolito `ailang_core.py`, dual frontend, IR + runtime conformance, stdlib/storage/hardware/tooling, versionado/tests/docs.
- Cada celda se justifica con file:line en `worklog.md`.
- La matriz debe regenerarse después de cada hito del ROADMAP para evitar drift.
- La conformidad "✅" requiere evidencia de test que la verifica; la ausencia de test implica ⚠️ o ❌ aunque la feature parezca implementada.
