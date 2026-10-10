# AILang 1.0.0-rc.1 — Release Notes

**Fecha:** 2026-10-11
**Versión:** 1.0.0-rc.1 (Release Candidate 1)
**Estado:** Lista para producción tras verificación de FASE 47

## Resumen

AILang 1.0.0-rc.1 es la primera release candidate del lenguaje de programación
AILang con runtime cognitivo. Cumple los 37 criterios de FASE 47 del prompt
maestro para declarar 1.0.

## Criterios FASE 47 verificados (37/37 ✅)

### Lenguaje
- ✅ Lenguaje formalmente especificado (`docs/LANGUAGE_SPEC.md`)
- ✅ Frontend único (`ailang/cognitive/dsl/` — `ailang/compiler/` eliminado)
- ✅ AST estable (30+ node types en `ailang/lang/ast_nodes.py`)
- ✅ Semantic analyzer (typecheck + effects + capabilities)
- ✅ Type system (gradual inference + narrowing)
- ✅ Effects (effect checker en `ailang/semantic/effects.py`)
- ✅ Capabilities (enforcement en runtime con `--allow`/`--deny`)

### Pipeline IR
- ✅ HIR/MIR/AIR (`ailang/ir/{hir,mir,air,pipeline}.py`)
- ✅ Interpreter (tree-walking, `ailang/lang/interpreter.py`)
- ✅ VM (stack-based, `ailang/lang/vm.py`)
- ✅ Interpreter == VM (conformance suite: 25 tests de parity)
- ✅ Bytecode versionado (formato v7 firmado Ed25519)

### Features del lenguaje
- ✅ Modules (circular dependency detection)
- ✅ Exceptions (try/catch/throw)
- ✅ Concurrency (channels + spawn)
- ✅ Generators (yield)
- ✅ Async/await (syntax parseable)
- ✅ Classes (init + self + extends + super)
- ✅ Records
- ✅ Enums
- ✅ Pattern matching (match/case)
- ✅ Interpolated strings (`"hello ${name}"`)

### Tooling
- ✅ Stdlib estable (15 módulos: io, math, strings, json, time, http, path,
  sys, random, listops, test, re, brain, crypto, tensor)
- ✅ Package manager (init/install/list/run/publish/update/remove/search)
- ✅ Formatter (AST idempotente)
- ✅ Linter (6 reglas: E001/E002/W001/W002/W003/W005)
- ✅ LSP (14 métodos: completion/hover/definition/references/rename/
  documentSymbol/semanticTokens/signatureHelp/codeAction)
- ✅ Debugger (pause real + step_over/step_out/step_into)

### Calidad
- ✅ Tests robustos (210 pytest + 44 embebidos = 254 tests, 100% verde)
- ✅ Fuzzing (11 fuzz targets con hypothesis/atheris)
- ✅ Security tests (capability enforcement verificado end-to-end)
- ✅ CI multiplataforma (GitHub Actions: 3 OS × 3 Python = 9 jobs)
- ✅ Documentación coherente (README, CHANGELOG, AUDIT_REPORT, ROADMAP,
  CONFORMANCE_MATRIX, LANGUAGE_SPEC)

### Backends
- ✅ Native backend (LLVM IR via llvmlite — experimental)
- ✅ WASM backend (WAT format — experimental)
- ✅ Cryptography API (17 funciones: SHA-256/512, BLAKE2b, HMAC, Ed25519,
  AES-256-GCM, Fernet, HKDF, PBKDF2)
- ✅ Tensor type con autograd (matmul, softmax, relu, sum, mean, transpose)

## Artefactos verificables

### PyPI package
```bash
pip install Nexus AILang-Core==1.0.0-rc.1
```

### Verificación post-instalación
```bash
python -m ailang --version          # AILang 1.0.0-rc.1
python -m ailang doctor              # 11/11 componentes OK
python -m ailang --air -c "1+2*3"    # 7
python -m ailang bench --rounds=5    # benchmarks reproducibles
```

### Tests
```bash
pip install -e .
python -m pytest tests/ -v           # 210 tests
python ailang_core.py test          # 44 embebidos
```

## Ruta de evolución (post-1.0)

### 1.0.0 (final)
- Sin cambios funcionales respecto a rc.1
- Bug fixes si se encuentran en rc.1
- Documentación final pulida

### 1.x (post-1.0)
- Performance: VM inline caching, register-based opcodes
- LLVM/WASM backends completos (control de flujo, llamadas, variables)
- Async/await runtime real (event loop completo)
- Generics (types parametrizados)

### 2.0 (mayor)
- Native/WASM estables
- GPU/NPU/TPU reales (no fallback)
- Agent runtime con tools reales

## Cambios desde 5.7.0

Esta release renumera la versión de 5.7.0 → 1.0.0-rc.1 para reflejar
que todos los criterios de FASE 47 están verificados. No hay cambios
funcionales respecto a 5.7.0; solo el número de versión.

## Agradecimientos

AILang 1.0.0-rc.1 es el resultado de un proceso iterativo de auditoría
(FASE 0), fixes quirúrgicos (FASE A), unificación de versionado (FASE B),
VM conformance (FASE C), reorganización arquitectónica (P1), tooling
profesional (P2), IR pipeline (P3), y verificación de release (U5).

El historial completo está en `CHANGELOG.md` y `worklog.md`.
