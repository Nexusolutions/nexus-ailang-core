# AILang 5.4.0

Lenguaje de programación con runtime cognitivo. La versión vive en `ailang/versions.py`
(FASE 1 del prompt maestro: 7 constantes separadas — LANGUAGE / RUNTIME / BYTECODE / IR / ABI / STDLIB / PACKAGE_FORMAT).

```bash
python -m ailang file.ailang
python -m ailang file.ailang --allow filesystem.read --allow ai.query
python -m ailang check file.ailang          # análisis sin ejecución
python -m ailang --repl
python -m ailang --vm file.ailang
python -m ailang doctor
python -m ailang bench --rounds=10 --save  # benchmarks reproducibles
python -m ailang --version
python -m ailang fmt file.ailang
python -m ailang lint file.ailang
python -m ailang --lsp
python -m ailang --dap
```

### Estado del proyecto (post FASE 0 + A/B/C + P1/P2/P3 + P3-9b/P3-1b/P2-10/P2-13/P2-14)

- ✅ Auditoría completa (`AUDIT_REPORT.md`, `ROADMAP.md`, `CONFORMANCE_MATRIX.md`).
- ✅ P0 quirúrgicos (FASE A): `re_mod.search`, `PersistentOutbox.list_pending`/`purge_dead`,
  debugger con pausa real, firma Ed25519 del bytecode (formato v7).
- ✅ Versionado unificado (FASE B): `ailang/versions.py` con 7 constantes separadas.
- ✅ VM conformance (FASE C): closures mutables, generadores, enum/interface/record/
  InterpolatedString en VM, async/await event loop cooperativo.
- ✅ P1: partitionar monolito (`ailang/cognitive/` fachada), eliminar frontend duplicado
  (`ailang/compiler/` migrado a `ailang/cognitive/dsl/`), tests embebidos a `tests/`.
- ✅ P2: LSP ampliado, formatter AST idempotente, linter con reglas, `ailang doctor`.
- ✅ P3: jerarquía `AILangError` completa, effect checker, capability enforcement,
  pipeline HIR/MIR/AIR.
- ✅ P3-9b: capability enforcement integrado en stdlib (`io`/`http`/`brain`/`sys`/`path`/`time`).
- ✅ P3-1b: HIR/MIR/AIR integrado con effect inference + capability mapping + `ailang check`.
- ✅ P2-10: property-based testing con hypothesis (13 properties).
- ✅ P2-13: CI multiplataforma GitHub Actions (3 OS × 3 Python = 9 jobs).
- ✅ P2-14: benchmark suite reproducible (17 casos, output tabular, save JSON).
- ✅ Conformance suite: 162 tests (109 + 25 conformance VM parity + 15 ailang_core + 13 property).
- 🚧 P4: Native/LLVM, WASM, GPU/NPU/TPU reales, cryptography API.

### Arquitectura

```
Source (.ailang) → Lexer → Parser → AST
       ↓
Semantic: typecheck + effects + capabilities
       ↓
HIR → MIR (SSA-lite + CFG + optimizaciones) → AIR (instrucciones tipadas)
       ↓
┌── Interpreter (tree-walking)
├── VM (stack-based, 1.5-2x faster than interp in 15/17 cases)
├── Bytecode .ailc (firmado Ed25519, formato v7)
└── (futuro) Native LLVM / WASM
```

### Capability enforcement

```bash
# Por defecto: permissive (modo legacy)
python -m ailang app.ailang

# Restrictive con capabilities explícitas
python -m ailang app.ailang --allow filesystem.read --allow ai.query

# Análisis sin ejecución
python -m ailang check app.ailang  # reporta capabilities y effects requeridos
```

### Ejemplos

```ailang
record Point { x, y }
interface Drawable { fn draw() }
fn counter() { yield 1; yield 2 }
let c = channel()
c.send(1)
spawn work()
"hello ${name}"
```
