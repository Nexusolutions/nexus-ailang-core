# AILang Language Specification — Core MVP (v7.2)

## 1. Diseño

AILang es un lenguaje **imperativo, dinámicamente tipado**, con:
- Núcleo general (expresiones, control de flujo, funciones).
- Directivas cognitivas y builtins de brain/runtime.
- Presupuesto de latencia (`purge_after`).

## 2. Programa

```
program     := { directive | stmt }
directive   := "purge_after" "(" INT "ms" ")"
stmt        := let_stmt | assign | if_stmt | while_stmt | for_stmt
             | fn_stmt | return_stmt | expr_stmt | block
```

## 3. Lexical

- Identifiers: `[A-Za-z_][A-Za-z0-9_]*`
- Numbers: int / float
- Strings: `"..."` o `'...'`
- Comments: `//` line, `/* */` block
- Keywords: `let`, `fn`, `if`, `else`, `while`, `for`, `in`, `return`,
  `true`, `false`, `null`, `and`, `or`, `not`

## 4. Types (runtime)

`null | bool | number | string | list | dict | function | native`

Anotaciones opcionales: `let x: number = 1` (solo documentales en MVP).

## 5. Expressions

```
expr     := or_expr
or_expr  := and_expr { "or" and_expr }
and_expr := not_expr { "and" not_expr }
not_expr := "not" not_expr | cmp
cmp      := sum { ("=="|"!="|"<"|"<="|">"|">=") sum }
sum      := term { ("+"|"-") term }
term     := unary { ("*"|"/"|"%") unary }
unary    := ("-"|"+") unary | postfix
postfix  := primary { call | index }
call     := "(" [expr { "," expr }] ")"
index    := "[" expr "]"
primary  := NUMBER | STRING | true | false | null | IDENT
          | "[" list "]" | "{" map "}" | "(" expr ")"
```

## 6. Statements

```
let x = expr
x = expr
if expr { ... } else { ... }
while expr { ... }
for x in expr { ... }
fn name(a, b) { ... return expr }
return expr
expr   // expression statement
```

## 7. Builtins

| Nombre | Descripción |
|--------|-------------|
| `print(...)` | stdout |
| `len(x)` | longitud |
| `str/int/float(x)` | coerción |
| `brain_ingest(source, path, content)` | si hay engine |
| `brain_query(text, top_k=10)` | si hay engine |
| `brain_think(text)` | si hay engine |
| `brain_graph(entity, depth=2)` | si hay engine |

## 8. Runtime

- Ámbitos léxicos (global + función).
- Intérprete tree-walking (MVP); bytecode opcional después.
- `purge_after` fija `budget_ms` del contexto de ejecución.

## 9. Errores

- `SyntaxError`, `NameError`, `TypeError`, `RuntimeError`
- Zero-Footprint: no aplica al núcleo; sigue en la DSL cognitiva.

## 10. Módulos (v7.2+)

```
import math
import math as m
import "user_mod"      // busca user_mod.ailang en module_path
```

Stdlib builtin: `math`, `io`, `json`, `listops`.

Acceso: `math.sqrt(9)`, `json.loads(s)`.

## 11. Excepciones

```
try {
  throw "error"
} catch e {
  print(e)
}
```

`catch` captura `throw` y errores de runtime del intérprete.

## 12. Closures y lambdas

```
fn make(k) {
  return fn(x) { return x + k }   // cierra sobre k
}
let f = make(10)
f(5)  // 15
```

Asignación a variables capturadas es visible entre llamadas (cierre mutable).

## 13. Clases, herencia y polimorfismo

```
class Animal {
  fn init(name) { self.name = name }
  fn speak() { return "..." }
}
class Dog extends Animal {
  fn speak() { return "woof" }   // override
}
let d = Dog("Rex")
d.speak()       // polimorfismo por método
super.speak()   // solo dentro de un método
```

- Constructor: `ClassName(args)` invoca `init` si existe.
- `self` y `super` están disponibles en métodos.
- Resolución de métodos: MRO hijo → padre.

## 14. Semántica normativa (v8.1)

### Truthy / Falsy
Falsy: `null`, `false`, `0`, `0.0`, `""`, `[]`, `{}`.
Resto: truthy.

### Operador `+`
- Si `typeof(a)==string` o `typeof(b)==string` → `str(a)+str(b)`.
- Si ambos numéricos → suma aritmética.
- En otro caso → `TypeError` de runtime.

### Tipado gradual
- Sin anotaciones: dinámico.
- Con anotaciones (`let x: int = 1`): el checker gradual verifica literales
  y asignaciones simples cuando `strict=True`.
- Tipos reconocidos: `null`, `bool`, `int`, `float`, `number`, `string`,
  `list`, `dict`, `function`, `any`, nombres de clase.

### Bytecode VM
El flag de ejecución puede usar VM (`run_source(..., use_vm=True)`):
compila a opcodes apilados y ejecuta sin recorrer el AST en caliente.

### VM class/import (v8.2)
La VM compila `class`/`extends`/`import` a `MAKE_CLASS` e `IMPORT_MODULE`.

### VM try/catch (v8.3)
`SETUP_CATCH` / `POP_CATCH` / `THROW` implementan try/catch en la VM.
