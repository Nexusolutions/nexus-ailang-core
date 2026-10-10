# AILang 5.2.0

Lenguaje de programación con runtime cognitivo. La versión vive en `ailang/versions.py`
(FASE 1 del prompt maestro: 7 constantes separadas — LANGUAGE / RUNTIME / BYTECODE / IR / ABI / STDLIB / PACKAGE_FORMAT).

```bash
python -m ailang file.ailang
python -m ailang bench
python -m ailang docgen file.ailang
python -m ailang --dap
python -m ailang --lsp
python -m ailang --version
```

### Estado del proyecto (post FASE 0 + FASE A + B + C)

- ✅ Auditoría completa (`AUDIT_REPORT.md`).
- ✅ Roadmap P0-P4 (`ROADMAP.md`).
- ✅ Matriz de conformidad (`CONFORMANCE_MATRIX.md`).
- ✅ P0 quirúrgicos: `re_mod.search`, `PersistentOutbox.list_pending`/`purge_dead`,
  debugger con pausa real, firma Ed25519 del bytecode (formato v7).
- ✅ FASE 1: versionado unificado en `ailang/versions.py`.
- ✅ FASE C: VM conformance — closures mutables (Cell upvalues), generadores
  (yield + GeneratorState), enum/interface/record/InterpolatedString en VM,
  async/await event loop cooperativo (VMScheduler + VMFuture + VMChannel).
- ✅ Conformance suite: 134 tests (109 originales + 25 nuevos de parity interp↔VM).
- 🚧 P1: partitionar monolito `ailang_core.py`, eliminar frontend duplicado `ailang/compiler/`.
- 🚧 P2: tooling (LSP/DAP completos, formatter desde AST, linter con reglas).
- 🚧 P3: HIR/MIR/AIR pipeline, effect checker, capability enforcement en runtime.
- 🚧 P4: Native/LLVM, WASM, GPU/NPU/TPU reales, cryptography API.

### Ejemplos (Nivel E)

```ailang
record Point { x, y }
interface Drawable { fn draw() }
fn counter() { yield 1; yield 2 }
let c = channel()
c.send(1)
spawn work()
"hello ${name}"
```
