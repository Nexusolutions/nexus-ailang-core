# Contributing to AILang-Core

¡Gracias por tu interés en contribuir a AILang-Core! Este documento te guía a través del proceso.

## Quick start

```bash
# 1. Fork & clone
git clone https://github.com/Nexusolutions/nexus-ailang-core.git
cd nexus-ailang-core

# 2. Instalar dependencias
pip install -e .
pip install numpy cryptography hypothesis pytest pytest-cov

# 3. Verificar que todo funciona
python -m ailang doctor
python -m pytest tests/ -q

# 4. Smoke test completo (replica el CI)
./scripts/smoke_test.sh
```

## Desarrollo

### Estructura del proyecto

```
ailang/                    # Paquete modular
├── lang/                  # Núcleo del lenguaje (lexer, parser, AST, interpreter, VM)
│   ├── stdlib/            # Módulos estándar (io, http, brain, crypto, etc.)
├── ir/                    # IR pipeline (HIR → MIR → AIR)
├── runtime/               # Runtime (capabilities, event_loop, air_interpreter)
├── cognitive/             # Cognitive brain engine
├── hardware/              # Hardware backends (CPU, GPU, NPU, TPU)
├── backends/              # Native backends (LLVM, WASM, JIT)
├── storage/               # Storage backends (SQLite, Postgres)
├── semantic/              # Effect analysis
├── compiler/              # Frontend duplicado (legacy)
├── modules.py             # ModuleResolver con circular detection
├── doctor.py              # Diagnóstico de componentes
├── debugger.py            # Debugger
├── lsp.py                 # Language Server Protocol
├── dap.py                 # Debug Adapter Protocol
├── fmt.py                 # Formatter
├── lint.py                # Linter
└── __main__.py            # CLI
ailang_core.py             # Monolito (legacy, re-exports)
tests/                     # Test suite
examples/                  # Ejemplos .ailang
scripts/                   # Scripts de utilidad
```

### Convenciones

- **Encoding**: todos los `open()` deben especificar `encoding="utf-8"`.
- **Paths**: usar `pathlib.Path` (no string concatenation con `/`).
- **Errors**: usar clases `AILang*` de `ailang.lang.errors` (no shadowear builtins Python).
- **Capabilities**: cualquier operación con side effects debe llamar `require("capability")`.
- **Cross-platform**: no usar imports POSIX-only (`fcntl`, `termios`, `tty`, `resource`, `grp`, `pwd`).

### Tests

- Cada fix debe incluir un test de regresión.
- Tests que ejercitan stdlib functions necesitan capabilities permissive (ver `tests/conftest.py`).
- Usar `pytest` con `--tb=short` para debugging.

### CI

El CI corre en GitHub Actions con matrix:
- OS: ubuntu-latest, windows-latest, macos-latest
- Python: 3.11, 3.12, 3.13

Jobs: test, lint, conformance, cross-platform.

Antes de push, ejecuta `./scripts/smoke_test.sh` para verificar localmente.

## Pull requests

1. Crea un feature branch desde `main`.
2. Escribe tests para tus cambios.
3. Ejecuta `./scripts/smoke_test.sh` — debe pasar 8/8.
4. Asegúrate de que el código sigue las convenciones.
5. Crea un PR con descripción clara.

## Licencia

MIT — ver [LICENSE](LICENSE).
