# AILang Language Reference

Especificación de referencia del lenguaje AILang 1.0.0-rc.1.

## Léxico

### Comentarios
```
// comentario de línea
/* comentario de bloque */
```

### Literales
- **Enteros**: `42`, `0`, `-7`
- **Floats**: `3.14`, `0.5`, `-1.0`
- **Strings**: `"hello"`, `"with \"escape\""`
- **Booleans**: `true`, `false`
- **Null**: `null`

### Identificadores
```
[a-zA-Z_][a-zA-Z0-9_]*
```

### Keywords
```
let const fn if else while for in return class extends
import try catch throw true false null self super break continue
match case enum interface record spawn yield async await
implements purge_after
```

### Operadores
```
+ - * / %
== != < > <= >=
and or not
= (assignment)
```

### Delimitadores
```
( ) { } [ ] , . : ;
```

## Gramática

### Program
```
program := { directive | statement }
```

### Statements
```
statement := let_stmt | const_stmt | fn_stmt | class_stmt
           | if_stmt | while_stmt | for_stmt | return_stmt
           | break_stmt | continue_stmt | expr_stmt
           | import_stmt | try_stmt | throw_stmt
           | match_stmt | enum_stmt | interface_stmt
           | record_stmt | yield_stmt | spawn_stmt

let_stmt := "let" IDENT [":" type] "=" expression
const_stmt := "const" IDENT [":" type] "=" expression
fn_stmt := ["async"] "fn" IDENT "(" params ")" block
class_stmt := "class" IDENT ["extends" IDENT] block
if_stmt := "if" expression block ["else" block]
while_stmt := "while" expression block
for_stmt := "for" IDENT "in" expression block
return_stmt := "return" [expression]
break_stmt := "break"
continue_stmt := "continue"
expr_stmt := expression
import_stmt := "import" STRING ["as" IDENT]
try_stmt := "try" block "catch" IDENT block
throw_stmt := "throw" expression
match_stmt := "match" expression "{" {case} "}"
case := pattern "=>" block
enum_stmt := "enum" IDENT "{" {IDENT} "}"
interface_stmt := "interface" IDENT "{" {fn_stmt} "}"
record_stmt := "record" IDENT "{" {IDENT} "}"
yield_stmt := "yield" [expression]
spawn_stmt := "spawn" expression
```

### Expressions
```
expression := or_expr
or_expr := and_expr {"or" and_expr}
and_expr := not_expr {"and" not_expr}
not_expr := "not" not_expr | cmp
cmp := sum {("==" | "!=" | "<" | ">" | "<=" | ">=") sum}
sum := term {("+" | "-") term}
term := unary {("*" | "/" | "%") unary}
unary := "-" unary | postfix
postfix := primary {"." IDENT | "(" args ")" | "[" expression "]"}
primary := literal | IDENT | "(" expression ")" | lambda | list_lit | dict_lit
lambda := "fn" "(" params ")" block
list_lit := "[" [expression {"," expression}] "]"
dict_lit := "{" [key ":" value {"," key ":" value}] "}"
```

## Tipos

### Tipos base
- `int` — enteros
- `float` — números de coma flotante
- `bool` — booleanos
- `string` — cadenas de texto
- `null` — valor nulo

### Tipos compuestos
- `List[T]` — listas
- `Dict[K, V]` — diccionarios
- `Tuple[T...]` — tuplas

### Type annotations
```ailang
let x: int = 42
let name: string = "Ada"
```

## Semántica

### Scopes
- Global scope (top-level)
- Function scope (parámetros + locals)
- Block scope (if/while/for bodies)
- Closure scope (variables capturadas)

### Closures
Las closures capturan variables por referencia (Cell), no por valor.
Las mutaciones a variables capturadas son visibles desde la closure.

### Pattern matching
```ailang
match x {
  1 => { ... }      // literal match
  _ => { ... }      // wildcard
  name => { ... }   // bind
}
```

## Runtime

### Ejecución
AILang tiene 3 modos de ejecución:

1. **Interpreter** (default): tree-walking sobre AST
2. **VM** (`--vm`): stack-based bytecode
3. **AIR** (`--air`): compila a AIR + verifica capabilities + VM

### Conformance
Interpreter y VM producen resultados idénticos para todos los programas
válidos (verificado por 25 tests de conformance).

### Bytecode
Formato `.ailc` (binary):
- Header: magic `AUR6` + FORMAT_VERSION
- SHA-256 digest del payload
- Payload: source UTF-8
- Signature (opcional, v7): Ed25519

## Capabilities

### Catálogo
- `filesystem.read` / `filesystem.write`
- `network.http`
- `process.spawn`
- `ai.query`
- `hardware.gpu` / `hardware.npu` / `hardware.tpu`
- `database.read` / `database.write`
- `system.env`
- `crypto.use`

### Política
- Default: permissive (todas concedidas)
- `--allow <cap>`: concede capability explícita
- `--deny <cap>`: deniega capability explícita
- Wildcards: `filesystem.*` concede `filesystem.read` + `filesystem.write`

## IR Pipeline

```
Source → Lexer → Parser → AST
       ↓
Semantic: typecheck + effects + capabilities
       ↓
HIR → MIR (SSA-lite + CFG + optimizaciones) → AIR (instrucciones tipadas)
       ↓
┌── Interpreter (tree-walking)
├── VM (stack-based)
├── AIR mode (capability verification + VM)
├── Bytecode .ailc (firmado Ed25519)
├── Native LLVM (experimental)
└── WASM (experimental)
```

## Stdlib

### Módulos (15)
- `io` — read_text, write_text, exists, lines
- `math` — abs, min, max, sqrt, pow, floor, ceil, pi, e
- `strings` — upper, lower, contains, split, replace
- `json` — loads, dumps
- `time` — now, sleep, format_ts, monotonic
- `http` — get, post, json_get
- `path` — join, exists, is_file, is_dir, mkdir, listdir
- `sys` — argv, exit, getenv, platform, version
- `random` — seed, random, randint, choice, shuffle
- `listops` — map, filter, reduce, sum, sorted
- `test` — assert_true, assert_eq, assert_raises, summary
- `re` — search, match, findall, sub, split
- `brain` — ingest, query, think, graph
- `crypto` — sha256, sha512, blake2b, hmac, Ed25519, AES, Fernet, HKDF, PBKDF2
- `tensor` — Tensor, matmul, softmax, relu, sum, mean, transpose, autograd

## CLI

```bash
python -m ailang file.ailang          # ejecutar
python -m ailang --vm file.ailang     # ejecutar con VM
python -m ailang --air file.ailang    # ejecutar con AIR + capabilities
python -m ailang check file.ailang    # análisis sin ejecución
python -m ailang --repl               # REPL interactivo
python -m ailang doctor               # diagnosticar componentes
python -m ailang bench                # benchmarks
python -m ailang fmt file.ailang      # formatear
python -m ailang lint file.ailang     # linter
python -m ailang --lsp                # Language Server Protocol
python -m ailang --dap                # Debug Adapter Protocol
python -m ailang --version            # versión
python -m ailang pkg init/install/list/run/publish/update/remove/search
```
