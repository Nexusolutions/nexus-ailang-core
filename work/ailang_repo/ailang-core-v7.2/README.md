# AILang 5.3.0

Lenguaje de programación con runtime cognitivo. La versión vive en `ailang/versions.py`
(FASE 1 del prompt maestro: 7 constantes separadas — LANGUAGE / RUNTIME / BYTECODE / IR / ABI / STDLIB / PACKAGE_FORMAT).

```bash
python -m ailang file.ailang
python -m ailang file.ailang --allow filesystem.read --allow ai.query
python -m ailang --repl
python -m ailang --vm file.ailang
python -m ailang doctor
python -m ailang --version
python -m ailang bench
python -m ailang fmt file.ailang
python -m ailang lint file.ailang
python -m ailang --lsp
python -m ailang --dap
```

### Estado del proyecto (post FASE 0 + A/B/C + P1/P2/P3)

- ✅ Auditoría completa (`AUDIT_REPORT.md`, `ROADMAP.md`, `CONFORMANCE_MATRIX.md`).
- ✅ P0 quirúrgicos (FASE A): `re_mod.search`, `PersistentOutbox.list_pending`/`purge_dead`,
  debugger con pausa real, firma Ed25519 del bytecode (formato v7).
- ✅ Versionado unificado (FASE B): `ailang/versions.py` con 7 constantes separadas.
- ✅ VM conformance (FASE C): closures mutables, generadores, enum/interface/record/
  InterpolatedString en VM, async/await event loop cooperativo.
- ✅ P1: partitionar monolito (`ailang/cognitive/` fachada), eliminar frontend duplicado
  (`ailang/compiler/` migrado a `ailang/cognitive/dsl/`), tests embebidos a `tests/`.
- ✅ P2: LSP ampliado (references/rename/documentSymbol/semanticTokens/signatureHelp),
  formatter AST idempotente, linter con reglas (E001/W001/W002/W003/W005), `ailang doctor`.
- ✅ P3: jerarquía `AILangError` completa, effect checker, capability enforcement con
  `--allow`/`--deny` CLI, pipeline HIR/MIR/AIR funcional.
- ✅ Conformance suite: 149 tests (109 originales + 25 conformance VM parity + 15 ailang_core).
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
├── VM (stack-based)
├── Bytecode .ailc (firmado Ed25519, formato v7)
└── (futuro) Native LLVM / WASM
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
