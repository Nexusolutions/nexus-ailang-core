# AILang — análisis de huecos hacia un lenguaje completo

## Veredicto del equipo

Nexus AILang-Core v7.1 es un **runtime cognitivo + DSL de conocimiento**, no aún un
lenguaje de programación general. Para serlo hace falta un **núcleo de lenguaje**
(expresiones, control de flujo, funciones, tipos, runtime de evaluación).

## Matriz de cobertura

| Capa | Estado v7.1 | Prioridad |
|------|-------------|-----------|
| Lex/parse cognitivo (brain.*) | ✅ | — |
| IR cognitivo / seguridad / unificado | ✅ formal | — |
| Transporte / outbox / latencia | ✅ | — |
| Brain store + retrieval | ✅ | — |
| **Variables / expresiones** | ❌ → v7.2 | P0 |
| **if / while / for** | ❌ → v7.2 | P0 |
| **Funciones + return** | ❌ → v7.2 | P0 |
| **Intérprete / VM** | ❌ → v7.2 | P0 |
| **REPL** | parcial (CLI) → v7.2 | P0 |
| Sistema de tipos | mínimo (anotaciones opcionales) | P1 |
| Módulos / import | ❌ | P1 |
| Stdlib | ❌ | P1 |
| Excepciones try/catch | ❌ | P1 |
| Spec formal del lenguaje | ❌ → v7.2 | P0 |
| Debugger | ❌ | P2 |
| Package manager | ❌ | P2 |
| GPU/NPU real | stubs | P2 |

## Definición de “terminado” (MVP lenguaje)

1. Programa con `let`, aritmética, `if`, `while`, `fn`, `return`.
2. Llamadas a builtins cognitivos (`brain_query`, etc.) desde el mismo programa.
3. `purge_after` como directiva de presupuesto.
4. REPL interactivo.
5. Spec en `docs/LANGUAGE_SPEC.md`.
6. Tests del núcleo ≥ 15.

v7.2 implementa exactamente ese MVP.
