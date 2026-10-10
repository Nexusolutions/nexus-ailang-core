# Nexus AILang-Core

<p align="center">
  <strong>Lenguaje de programación con runtime cognitivo</strong>
</p>

<p align="center">
  <a href="https://github.com/EnriqueJimenezGarcia/nexus-ailang-core/actions"><img src="https://github.com/EnriqueJimenezGarcia/nexus-ailang-core/workflows/CI/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/version-1.1.0-blue" alt="version">
  <img src="https://img.shields.io/badge/tests-258%20passing-green" alt="tests">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
</p>

---

Nexus AILang-Core es un lenguaje de programación con runtime cognitivo, capability enforcement, pipeline HIR/MIR/AIR, y backends LLVM/WASM. Combina la simplicidad de Python con la seguridad de Rust, el pipeline IR de LLVM, y un runtime cognitivo para aplicaciones de IA.

## Instalación

```bash
pip install nexus-ailang-core
```

## Inicio rápido

```bash
# Crear proyecto
python -m ailang new app myapp

# Ejecutar
cd myapp
python -m ailang main.ailang

# Playground web
python -m ailang --serve
```

## Características

- **5 backends**: Interpreter, VM (1.5-2.3x faster), AIR, LLVM JIT, WASM
- **Capability enforcement**: `--allow filesystem.read --allow ai.query`
- **Runtime cognitivo**: `brain.ingest()`, `brain.query()`, `brain.think()`
- **Pipeline HIR/MIR/AIR**: lowering + optimizaciones (constant folding, DCE)
- **15 módulos stdlib**: io, math, json, http, brain, crypto, tensor, etc.
- **Tooling completo**: LSP, DAP, formatter, linter, profiler, package manager
- **258 tests**: unit, conformance, property-based, fuzz, formal verification

## Documentación

- [Tutorial](docs/TUTORIAL.md) — 20 secciones desde Hello World
- [Language Reference](docs/LANGUAGE_REFERENCE.md) — gramática, tipos, semántica
- [Changelog](CHANGELOG.md) — historial completo
- [Release Notes](RELEASE_NOTES.md) — 37/37 criterios FASE 47 verificados

## Autor

**Enrique Jimenez Garcia**

## Licencia

MIT
