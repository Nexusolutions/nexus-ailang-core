# AILang 5.0.0

```bash
python -m ailang file.ailang
python -m ailang bench
python -m ailang docgen file.ailang
python -m ailang --dap
python -m ailang --lsp
```

### Nivel E
```ailang
record Point { x, y }
interface Drawable { fn draw() }
fn counter() { yield 1; yield 2 }
let c = channel()
c.send(1)
spawn work()
"hello ${name}"
```
