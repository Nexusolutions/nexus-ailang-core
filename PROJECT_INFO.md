# Nexus AILang-Core

> Lenguaje de programación con runtime cognitivo

**Autor:** Enrique Jimenez Garcia
**Licencia:** MIT
**Versión:** 1.1.0

## Descripción

Nexus AILang-Core es un lenguaje de programación que combina:
- Simplicidad de Python (sintaxis familiar, type inference gradual)
- Seguridad de Rust (capability enforcement, deny by default)
- Pipeline IR de LLVM (HIR → MIR → AIR con optimizaciones)
- Runtime cognitivo (brain.ingest, brain.query, brain.think)
- 5 backends de ejecución (Interpreter, VM, AIR, LLVM, WASM)

## Estado del proyecto

- ✅ 258 tests (214 pytest + 44 embebidos) — 100% verde
- ✅ 37/37 criterios FASE 47 verificados
- ✅ 15 módulos stdlib (io, math, json, http, brain, crypto, tensor, etc.)
- ✅ 5 backends (Interpreter, VM, AIR, LLVM, WASM)
- ✅ Tooling completo (LSP, DAP, formatter, linter, profiler, package manager)
- ✅ Capability enforcement con `--allow`/`--deny`
- ✅ Pipeline HIR/MIR/AIR con optimizaciones
- ✅ Fuzzing + property-based testing
- ✅ CI multiplataforma (3 OS × 3 Python = 9 jobs)

## Estructura del repositorio

```
nexus-ailang-core/
├── ailang/                    # Paquete principal
│   ├── lang/                  # Frontend: lexer, parser, AST, typecheck, interpreter, VM
│   ├── cognitive/              # Runtime cognitivo: brain_engine, brain_store, dsl/
│   ├── ir/                     # IR pipeline: hir, mir, air, pipeline
│   ├── semantic/               # Effect checker
│   ├── runtime/                # Capability enforcement, AIR interpreter, event loop
│   ├── storage/                # SQLite, PostgreSQL backends
│   ├── hardware/               # CPU, GPU, NPU, TPU backends
│   ├── backends/               # Native (LLVM), WASM
│   ├── lang/stdlib/            # 15 módulos stdlib
│   ├── playground/             # Web playground server
│   ├── __init__.py
│   ├── __main__.py             # CLI
│   ├── versions.py             # Fuente única de versiones
│   ├── doctor.py               # Diagnóstico
│   ├── pkg.py                  # Package manager
│   ├── fmt.py                  # Formatter
│   ├── lint.py                 # Linter
│   ├── lsp.py                  # Language Server Protocol
│   ├── dap.py                  # Debug Adapter Protocol
│   ├── debugger.py             # Debugger con step over/into/out
│   └── project_templates.py    # Scaffolding
├── ailang_core.py              # Monolito cognitivo (CognitiveBrainEngine, transport)
├── tests/                      # 214 tests
├── docs/                       # Tutorial, Language Reference, spec
├── playground/                 # Web playground HTML
├── landing/                    # Landing page
├── vscode-ailang/              # VS Code extension
├── examples/                   # 6 ejemplos .ailang
├── benchmarks/                 # Resultados de benchmarks
├── .github/workflows/          # CI multiplataforma
├── .github/ISSUE_TEMPLATE/     # Bug report + feature request templates
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── RELEASE_NOTES.md
├── LICENSE
└── README.md
```

## Instalación

```bash
pip install nexus-ailang-core
```

## Uso

```bash
# Ejecutar archivo
python -m ailang file.ailang

# Con VM (más rápido)
python -m ailang --vm file.ailang

# Con AIR + capabilities
python -m ailang --air file.ailang --allow filesystem.read

# Playground web
python -m ailang --serve

# Crear proyecto
python -m ailang new app myapp

# Diagnóstico
python -m ailang doctor
```

## Licencia

MIT © Enrique Jimenez Garcia
