# Contributing to AILang

¡Gracias por tu interés en contribuir a AILang! Este documento describe
cómo contribuir al proyecto.

## Quick Start

```bash
# Clone el repositorio
git clone <repo-url>
cd Nexus AILang-Core

# Instala en modo editable
pip install -e .

# Verifica que todo funciona
python -m ailang doctor
python -m pytest tests/

# Ejecuta los tests embebidos del monolito
python ailang_core.py test
```

## Tipos de contribuciones

### Bug reports
- Usa GitHub Issues
- Incluye: versión de AILang, versión de Python, OS, código mínimo reproducible
- Ejecuta `python -m ailang doctor` y pega el output

### Feature requests
- Describe el caso de uso
- Explica por qué las features existentes no son suficientes
- Sugiere una API si es posible

### Pull Requests
1. Fork el repositorio
2. Crea una branch: `git checkout -b feature/my-feature`
3. Haz tus cambios
4. Asegúrate de que los tests pasan: `python -m pytest tests/`
5. Añade tests para tus cambios
6. Actualiza documentación si es necesario
7. Commit con mensaje descriptivo
8. Push y crea Pull Request

## Estándares de código

### Python
- Type hints en todas las funciones públicas
- Docstrings en módulos, clases, y funciones públicas
- Máximo 100 caracteres por línea
- Seguir PEP 8 (con excepciones documentadas)

### Tests
- Todo nuevo feature debe tener tests
- Todo bug fix debe tener un test de regresión
- Categorías: unit, integration, conformance, property-based, fuzz

### Commits
- Formato: `<type>: <description>`
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`
- Ejemplo: `feat: add crypto.sha256 to stdlib`

## Arquitectura

AILang sigue el pipeline:

```
Source → Lexer → Parser → AST → Semantic → HIR → MIR → AIR → {Interpreter, VM, LLVM, WASM}
```

### Estructura del repositorio

```
ailang/
├── lang/           # Frontend: lexer, parser, AST, typecheck, interpreter, VM
├── cognitive/      # Runtime cognitivo: brain_engine, brain_store, retriever, dsl/
├── ir/             # IR pipeline: hir, mir, air, pipeline
├── semantic/       # Effect checker
├── runtime/        # Capability enforcement, AIR interpreter
├── storage/        # SQLite, PostgreSQL backends
├── hardware/       # CPU, GPU, NPU, TPU backends
├── backends/       # Native (LLVM), WASM
├── stdlib/         # 15 módulos stdlib
├── tooling/        # LSP, DAP, formatter, linter, profiler
└── pkg.py          # Package manager
```

## Roadmap

Ver `ROADMAP.md` para el roadmap completo. Resumen:

- ✅ 1.0.0-rc.1 — FASE 47 verificado (37/37 criterios)
- 🚧 1.0.0 — release final
- 🚧 1.x — performance, LLVM/WASM completos, async/await real
- 🚧 2.0 — GPU/NPU/TPU reales, agent runtime

## Contacto

- Issues: GitHub Issues
- Discusiones: GitHub Discussions
- Email: Enrique Jimenez Garcia
