# AILang Tutorial

Bienvenido a AILang, un lenguaje de programación con runtime cognitivo.
Este tutorial te guía desde "Hello World" hasta features avanzadas.

## 1. Instalación

```bash
pip install -e .
```

Verifica la instalación:

```bash
python -m ailang --version   # AILang 1.0.0-rc.1
python -m ailang doctor      # 11/11 componentes OK
```

## 2. Hello World

Crea `hello.ailang`:

```ailang
print("hello world")
```

Ejecuta:

```bash
python -m ailang hello.ailang
```

## 3. Variables y tipos

```ailang
let name = "Ada"
let age = 30
let pi = 3.14
let is_admin = true
let nothing = null

print("name: " + name)
print("age: " + str(age))
```

AILang infiere tipos automáticamente. Para declaraciones explícitas:

```ailang
let x: int = 42
let greeting: string = "hello"
```

## 4. Funciones

```ailang
fn add(a, b) {
  return a + b
}

fn greet(name) {
  return "hello " + name
}

print(add(3, 4))           // 7
print(greet("Ada"))         // hello Ada
```

### Lambdas

```ailang
let double = fn(x) { return x * 2 }
print(double(5))            // 10
```

### Closures mutables

```ailang
fn make_counter() {
  let count = 0
  fn inc() {
    count = count + 1
    return count
  }
  return inc
}

let c = make_counter()
print(c())                  // 1
print(c())                  // 2
print(c())                  // 3
```

## 5. Control de flujo

### if/else

```ailang
let x = 10
if x > 5 {
  print("mayor")
} else {
  print("menor")
}
```

### while

```ailang
let i = 0
while i < 5 {
  print(i)
  i = i + 1
}
```

### for

```ailang
for n in [1, 2, 3, 4, 5] {
  print(n)
}

for n in range(10) {
  print(n)
}
```

### match

```ailang
let x = 2
match x {
  1 => { print("uno") }
  2 => { print("dos") }
}
```

## 6. Clases y herencia

```ailang
class Animal {
  fn init(name) {
    self.name = name
  }
  fn speak() {
    return "generic sound"
  }
}

class Dog extends Animal {
  fn speak() {
    return "woof"
  }
}

let d = Dog("Rex")
print(d.name)               // Rex
print(d.speak())            // woof
```

## 7. Records y Enums

### Records

```ailang
record Point { x, y }
let p = Point(3, 4)
print(p.x)                  // 3
print(p.y)                  // 4
```

### Enums

```ailang
enum Color { RED, GREEN, BLUE }
print(Color.RED == Color.RED)   // true
print(Color.RED == Color.BLUE)  // false
```

## 8. Interfaces

```ailang
interface Speaker {
  fn speak()
}

class Dog {
  fn speak() { return "woof" }
}

print(implements(Dog(), Speaker))  // true
```

## 9. Interpolación de strings

```ailang
let name = "Ada"
let age = 30
print("Name: ${name}, Age: ${age}")
```

## 10. Generadores

```ailang
fn counter() {
  yield 1
  yield 2
  yield 3
}

for v in counter() {
  print(v)
}
```

## 11. Concurrency

### Channels

```ailang
let c = channel()
c.send(42)
print(c.recv())             // 42
```

### spawn

```ailang
fn worker() {
  print("working...")
  return 100
}

let result = spawn worker()
print(result)
```

## 12. Excepciones

```ailang
try {
  throw "something went wrong"
} catch e {
  print("caught: " + e)
}
```

## 13. Imports y módulos

```ailang
import math
import json
import strings

print(math.sqrt(16))                    // 4
print(json.loads("[1, 2, 3]"))          // [1, 2, 3]
print(strings.upper("hello"))           // HELLO
```

## 14. Capability enforcement

AILang usa capabilities para restringir operaciones con side effects:

```bash
# Por defecto: permissive (todas concedidas)
python -m ailang app.ailang

# Restrictive: solo las capabilities listadas
python -m ailang app.ailang --allow filesystem.read --allow ai.query
```

### Análisis sin ejecución

```bash
python -m ailang check app.ailang
```

Reporta qué capabilities y effects requiere el programa.

## 15. Crypto

```ailang
import crypto

let hash = crypto.sha256("hello")
print(hash)  // 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824

let kp = crypto.generate_keypair()
let sig = crypto.sign(kp["private"], "message")
let valid = crypto.verify(kp["public"], sig, "message")
print(valid)  // true
```

## 16. Tensor con autograd

```ailang
import tensor

let a = tensor.tensor([[1, 2], [3, 4]], true)
let b = tensor.tensor([[5, 6], [7, 8]], true)
let c = a.matmul(b)
let loss = c.sum()
loss.backward()
print(a.grad.tolist())
```

## 17. Debugging

```bash
python -m ailang --debug app.ailang --bp 5 --bp 10
```

Establece breakpoints en las líneas 5 y 10.

## 18. LSP

AILang tiene un Language Server Protocol para VS Code:

```bash
python -m ailang --lsp
```

Soporta: completion, hover, definition, references, rename, documentSymbol,
semanticTokens, signatureHelp.

## 19. Formatter y linter

```bash
python -m ailang fmt app.ailang    # formatea in-place
python -m ailang lint app.ailang   # reporta issues
```

## 20. Benchmarks

```bash
python -m ailang bench --rounds=10 --save
```

Compara Interpreter vs VM en 17 casos.

---

Para más detalles, consulta:
- `docs/LANGUAGE_SPEC.md` — especificación formal del lenguaje
- `docs/EBNF.md` — gramática EBNF
- `CHANGELOG.md` — historial de cambios
- `RELEASE_NOTES.md` — notas de release 1.0.0-rc.1
