# AILang Conformance Suite

Tests normativos del lenguaje. Un runtime conforme debe pasar
`tests/test_conformance.py`.

## Reglas normativas (resumen)

1. **Scopes:** `let` introduce binding en el entorno actual; asignación
   (`x = …`) muta el binding existente más cercano en la cadena léxica.
2. **Closures:** funciones capturan el `Env` donde se crearon; mutaciones
   a variables capturadas son visibles entre invocaciones.
3. **Coerción `+`:** si algún operando es `string`, ambos se convierten a
   string y se concatenan; en caso contrario aritmética numérica.
4. **Truthy:** `null`, `false`, `0`, `0.0`, `""`, `[]`, `{}` son falsy;
   el resto truthy.
5. **Métodos:** `obj.m(args)` enlaza `self`; override en subclase gana;
   `super.m` busca desde el padre de la clase que define el método actual.
6. **break/continue:** solo en `while`/`for`; no cruzan límites de función.
7. **throw/catch:** `catch` captura `throw` y errores de runtime del lenguaje.
8. **import:** módulos builtin (`math`, `io`, `json`, `listops`, `brain`,
   `strings`, `time`, `sys`, `test`) o ficheros `.ailang` en `module_path`.
9. **purge_after(Nms):** fija `budget_ms` del intérprete; no interrumpe solo.
10. **Tipado gradual:** anotaciones son opcionales; con `--strict` o
    `typecheck(strict=True)` se reportan conflictos.
