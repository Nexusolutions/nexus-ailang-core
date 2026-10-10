# AILang v8.0 — Plan de entrega final (7 días)

## Meta
Entregar un lenguaje usable en producción de prototipo: núcleo general +
OOP + módulos + stdlib + runtime cognitivo + docs + tests.

## Equipo

| Rol | Foco | Entregable |
|-----|------|-------------|
| Tech Lead | Arquitectura, integración, release | v8.0 ZIP + checklist |
| Compiler Engineer | Gramática, break/continue, errores | lexer/parser/AST |
| Runtime Engineer | Intérprete, closures, OOP | interpreter estable |
| Stdlib Engineer | math/io/json/listops/brain | stdlib/ |
| Cognitive Engineer | Puente IR + brain module | runtime_bridge + brain |
| QA Engineer | Regresión y casos límite | tests/ (≥35) |
| Docs/DX | Spec, tutoriales, ejemplos | docs/ + examples/ |

## Definition of Done v8.0
- Núcleo: let, if, while, for, break, continue, fn, lambda, class, extends
- Módulos: import, try/catch/throw
- Stdlib: math, io, json, listops, brain
- REPL: python -m ailang
- Tests verdes + ejemplos ejecutables
