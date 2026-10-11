"""Intérprete tree-walking del núcleo AILang + builtins cognitivos opcionales."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ailang.lang import ast_nodes as A
from ailang.lang.parser import parse
from ailang.lang.errors import AILangRuntimeError, AILangSyntaxError, StackFrame
from ailang.lang.stdlib import builtin_modules, Module
from ailang.lang.stdlib import brain as brain_mod
from pathlib import Path as _Path


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class ThrowSignal(Exception):
    """Excepción del lenguaje (throw)."""
    def __init__(self, value):
        self.value = value
        super().__init__(repr(value))


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class YieldSignal(Exception):
    def __init__(self, value):
        self.value = value


@dataclass
class FunctionValue:
    name: str
    params: List[str]
    body: List[Any]
    env: "Env"
    is_method: bool = False
    is_async: bool = False


@dataclass
class ClassValue:
    name: str
    base: Optional["ClassValue"]
    methods: Dict[str, FunctionValue]
    env: "Env"

    def mro_methods(self) -> Dict[str, FunctionValue]:
        """Resuelve métodos con herencia (hijo sobrescribe padre)."""
        chain: List[ClassValue] = []
        cur: Optional[ClassValue] = self
        seen = set()
        while cur is not None and cur.name not in seen:
            chain.append(cur)
            seen.add(cur.name)
            cur = cur.base
        merged: Dict[str, FunctionValue] = {}
        for cls in reversed(chain):
            merged.update(cls.methods)
        return merged

    def lookup(self, name: str) -> Optional[FunctionValue]:
        return self.mro_methods().get(name)

    def lookup_with_owner(self, name: str):
        cur: Optional[ClassValue] = self
        while cur is not None:
            if name in cur.methods:
                return cur.methods[name], cur
            cur = cur.base
        return None, None


@dataclass
class Instance:
    cls: ClassValue
    fields: Dict[str, Any]

    def __repr__(self) -> str:
        return f"<{self.cls.name} instance>"


@dataclass
class BoundMethod:
    instance: Instance
    func: FunctionValue
    defining_cls: ClassValue

    def __repr__(self) -> str:
        return f"<bound {self.func.name} of {self.instance.cls.name}>"


@dataclass
class SuperProxy:
    """Permite super.metodo(...) desde un método."""
    instance: Instance
    start_cls: ClassValue  # clase donde se definió el método actual


@dataclass
class EnumType:
    name: str
    variants: Dict[str, "EnumMember"]

    def __repr__(self) -> str:
        return f"<enum {self.name}>"


@dataclass
class EnumMember:
    enum_name: str
    variant: str

    def __repr__(self) -> str:
        return f"{self.enum_name}.{self.variant}"

    def __eq__(self, other):
        if isinstance(other, EnumMember):
            return self.enum_name == other.enum_name and self.variant == other.variant
        return NotImplemented


@dataclass
class GeneratorValue:
    """Generador perezoso basado en yield dentro de fn."""
    fn: FunctionValue
    args: list
    _interp: Any = None
    _exhausted: bool = False
    _gen: Any = field(default=None, repr=False)

    def __iter__(self):
        return self

    def __next__(self):
        if self._exhausted:
            raise StopIteration
        if self._gen is None:
            self._gen = self._start()
        try:
            return next(self._gen)
        except StopIteration:
            self._exhausted = True
            raise

    def _start(self):
        local = Env(parent=self.fn.env)
        for p, a in zip(self.fn.params, self.args):
            local.define(p, a)
        for stmt in self.fn.body:
            try:
                self._interp.exec_stmt(stmt, local)
            except YieldSignal as ys:
                yield ys.value
            except ReturnSignal as rs:
                if rs.value is not None:
                    yield rs.value
                return
        return


@dataclass
class InterfaceType:
    name: str
    methods: list

    def __repr__(self) -> str:
        return f"<interface {self.name}>"


@dataclass
class RecordType:
    name: str
    fields: list

    def __call__(self, *args, **kwargs):
        data = {}
        if len(args) == 1 and isinstance(args[0], dict):
            data = dict(args[0])
        else:
            for i, f in enumerate(self.fields):
                if i < len(args):
                    data[f] = args[i]
        for k, v in kwargs.items():
            data[k] = v
        return RecordInstance(self.name, data)

    def __repr__(self) -> str:
        return f"<record {self.name}>"


@dataclass
class RecordInstance:
    record_name: str
    fields: dict

    def __repr__(self) -> str:
        return f"{self.record_name}({self.fields})"


@dataclass
class ChannelValue:
    q: Any
    name: str = "chan"

    def send(self, value):
        self.q.put(value)
        return None

    def recv(self, timeout=None):
        import queue
        try:
            if timeout is None:
                return self.q.get()
            return self.q.get(timeout=float(timeout))
        except queue.Empty:
            return None

    def __repr__(self) -> str:
        return f"<channel {self.name}>"


@dataclass
class Env:
    values: Dict[str, Any] = field(default_factory=dict)
    parent: Optional["Env"] = None
    constants: set = field(default_factory=set)

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.get(name)
        raise AILangRuntimeError(f"nombre no definido: {name}")

    def set(self, name: str, value: Any) -> None:
        env: Optional[Env] = self
        while env is not None:
            if name in env.values:
                if name in env.constants:
                    raise AILangRuntimeError(f"no se puede reasignar const '{name}'")
                env.values[name] = value
                return
            env = env.parent
        raise AILangRuntimeError(f"asignación a variable no declarada: {name}")

    def define(self, name: str, value: Any, *, const: bool = False) -> None:
        self.values[name] = value
        if const:
            self.constants.add(name)


def _truthy(v: Any) -> bool:
    """Semántica normativa: null/false/0/0.0/""/[]/{} son falsy."""
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return False
    if isinstance(v, str) and v == "":
        return False
    if isinstance(v, (list, dict)) and len(v) == 0:
        return False
    return True


class Interpreter:
    def __init__(self, brain_engine: Any = None, module_path: Optional[list] = None):
        self.global_env = Env()
        self.budget_ms: Optional[int] = None
        self.brain = brain_engine
        self.module_path = list(module_path or [".", "stdlib"])
        self._module_cache: Dict[str, Any] = {}
        self._builtins_mods = builtin_modules()
        self._install_builtins(self.global_env)
        if brain_engine is not None:
            brain_mod.bind_engine(brain_engine)
        # Gramática unificada: módulo brain siempre en el entorno global
        try:
            if "brain" in self._builtins_mods:
                self.global_env.define("brain", self._builtins_mods["brain"])
        except Exception:
            pass

    def _install_builtins(self, env: Env) -> None:
        def _print(*args):
            print(*args)
            return None

        def _len(x):
            return len(x)

        def _str(x):
            return str(x)

        def _int(x):
            return int(x)

        def _float(x):
            return float(x)

        def _range(*a):
            return list(range(*a))

        env.define("print", _print)
        env.define("len", _len)
        env.define("str", _str)
        env.define("int", _int)
        env.define("float", _float)
        env.define("range", _range)
        env.define("true", True)
        env.define("false", False)
        env.define("null", None)

        def _type(x):
            if x is None:
                return "null"
            if isinstance(x, bool):
                return "bool"
            if isinstance(x, int) and not isinstance(x, bool):
                return "int"
            if isinstance(x, float):
                return "float"
            if isinstance(x, str):
                return "string"
            if isinstance(x, list):
                return "list"
            if isinstance(x, dict):
                return "dict"
            if isinstance(x, FunctionValue):
                return "function"
            if isinstance(x, ClassValue):
                return "class"
            if isinstance(x, Instance):
                return x.cls.name
            if isinstance(x, EnumMember):
                return x.enum_name
            if isinstance(x, RecordInstance):
                return x.record_name
            if isinstance(x, GeneratorValue):
                return "generator"
            if isinstance(x, ChannelValue):
                return "channel"
            if isinstance(x, Module):
                return "module"
            return type(x).__name__

        def _isinstance(x, name):
            return _type(x) == str(name)

        env.define("type", _type)
        env.define("isinstance", _isinstance)

        def _channel(name="chan", maxsize=0):
            import queue
            return ChannelValue(queue.Queue(maxsize=int(maxsize) if maxsize else 0), str(name))

        def _implements(obj, iface):
            if not isinstance(iface, InterfaceType):
                return False
            if not isinstance(obj, Instance):
                return False
            for m in iface.methods:
                meth, _ = obj.cls.lookup_with_owner(m)
                if meth is None:
                    return False
            return True

        env.define("implements", _implements)
        env.define("channel", _channel)

        if self.brain is not None:
            eng = self.brain

            def brain_ingest(source, path, content, **kw):
                return eng.ingest(str(source), str(path), str(content), **kw)

            def brain_query(text, top_k=10):
                return eng.search(str(text), top_k=int(top_k))

            def brain_think(text, top_k=8):
                return eng.think(str(text), top_k=int(top_k))

            def brain_graph(entity, depth=2):
                return eng.graph(str(entity), depth=int(depth))

            env.define("brain_ingest", brain_ingest)
            env.define("brain_query", brain_query)
            env.define("brain_think", brain_think)
            env.define("brain_graph", brain_graph)

    def load_module(self, name: str) -> Any:
        if name in self._module_cache:
            return self._module_cache[name]
        if name in self._builtins_mods:
            mod = self._builtins_mods[name]
            self._module_cache[name] = mod
            return mod
        # archivo .ailang en module_path
        rel = name.replace(".", "/") + ".ailang"
        for root in self.module_path:
            candidate = _Path(root) / rel
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
                # Ejecutar en entorno fresco; exportar bindings globales del módulo
                mod_env = Env()
                self._install_builtins(mod_env)
                program = parse(text)
                for stmt in program.body:
                    self.exec_stmt(stmt, mod_env)
                exports = dict(mod_env.values)
                # no reexportar builtins puros si se desea — se dejan por simplicidad
                mod = Module(name, exports)
                self._module_cache[name] = mod
                return mod
        raise AILangRuntimeError(f"módulo no encontrado: {name}")

    def run(self, source: str) -> Any:
        program = parse(source)
        if program.budget_ms is not None:
            self.budget_ms = program.budget_ms
        result = None
        for stmt in program.body:
            result = self.exec_stmt(stmt, self.global_env)
        return result

    def exec_stmt(self, node: Any, env: Env) -> Any:
        if isinstance(node, A.Let):
            env.define(node.name, self.eval_expr(node.value, env))
            return None
        if isinstance(node, A.Const):
            env.define(node.name, self.eval_expr(node.value, env), const=True)
            return None
        if isinstance(node, A.Match):
            subject = self.eval_expr(node.subject, env)
            for case in node.cases:
                matched = False
                if isinstance(case.pattern, A.Name) and case.pattern.id == "_":
                    matched = True
                elif isinstance(case.pattern, A.Literal):
                    matched = subject == case.pattern.value
                elif isinstance(case.pattern, A.Name):
                    # bind name to subject
                    local = Env(parent=env)
                    local.define(case.pattern.id, subject)
                    return self.exec_block(case.body, local)
                if matched:
                    return self.exec_block(case.body, env)
            raise AILangRuntimeError(f"match sin caso para {subject!r}")
        if isinstance(node, A.Assign):
            val = self.eval_expr(node.value, env)
            if isinstance(node.name, str):
                env.set(node.name, val)
            elif isinstance(node.name, A.Attr):
                obj = self.eval_expr(node.name.value, env)
                if isinstance(obj, Instance):
                    obj.fields[node.name.attr] = val
                elif isinstance(obj, dict):
                    obj[node.name.attr] = val
                else:
                    raise AILangRuntimeError(
                        f"no se puede asignar atributo en {type(obj).__name__}"
                    )
            else:
                raise AILangRuntimeError("destino de asignación inválido")
            return None
        if isinstance(node, A.If):
            if _truthy(self.eval_expr(node.test, env)):
                return self.exec_block(node.body, env)
            return self.exec_block(node.orelse, env)
        if isinstance(node, A.While):
            last = None
            while _truthy(self.eval_expr(node.test, env)):
                try:
                    last = self.exec_block(node.body, env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return last
        if isinstance(node, A.For):
            iterable = self.eval_expr(node.iter, env)
            last = None
            for item in iterable:
                local = Env(parent=env)
                local.define(node.target, item)
                try:
                    last = self.exec_block(node.body, local)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return last
        if isinstance(node, A.Function):
            env.define(
                node.name,
                FunctionValue(
                    node.name, node.params, node.body, env,
                    is_async=getattr(node, "is_async", False),
                ),
            )
            return None
        if isinstance(node, A.InterfaceDef):
            env.define(node.name, InterfaceType(node.name, list(node.methods)))
            return None
        if isinstance(node, A.RecordDef):
            env.define(node.name, RecordType(node.name, list(node.fields)))
            return None
        if isinstance(node, A.Spawn):
            import threading
            # spawn call or function invocation
            def _run():
                try:
                    self.eval_expr(node.call, env)
                except Exception as e:
                    print(f"[spawn error] {e}")
            th = threading.Thread(target=_run, daemon=True)
            th.start()
            return th
        if isinstance(node, A.EnumDef):
            variants = {}
            et = EnumType(node.name, variants)
            for v in node.variants:
                variants[v] = EnumMember(node.name, v)
            env.define(node.name, et)
            return et
        if isinstance(node, A.ClassDef):
            base_cls = None
            if node.base:
                base_obj = env.get(node.base)
                if not isinstance(base_obj, ClassValue):
                    raise AILangRuntimeError(f"extends requiere una clase: {node.base}")
                base_cls = base_obj
            methods: Dict[str, FunctionValue] = {}
            for m in node.methods:
                methods[m.name] = FunctionValue(
                    m.name, m.params, m.body, env, is_method=True
                )
            cls = ClassValue(node.name, base_cls, methods, env)
            env.define(node.name, cls)
            return cls
        if isinstance(node, A.Break):
            raise BreakSignal()
        if isinstance(node, A.Continue):
            raise ContinueSignal()
        if isinstance(node, A.Yield):
            val = None if node.value is None else self.eval_expr(node.value, env)
            raise YieldSignal(val)
        if isinstance(node, A.Return):
            val = None if node.value is None else self.eval_expr(node.value, env)
            raise ReturnSignal(val)
        if isinstance(node, A.Import):
            mod = self.load_module(node.module)
            bind = node.alias or node.module.split(".")[-1]
            env.define(bind, mod)
            return mod
        if isinstance(node, A.Try):
            try:
                return self.exec_block(node.body, env)
            except ThrowSignal as ts:
                local = Env(parent=env)
                local.define(node.catch_name, ts.value)
                return self.exec_block(node.catch_body, local)
            except AILangRuntimeError as re:
                local = Env(parent=env)
                local.define(node.catch_name, str(re))
                return self.exec_block(node.catch_body, local)
            except Exception as py_exc:
                # AUD-002: Catch ALL Python exceptions (ZeroDivisionError, KeyError,
                # IndexError, TypeError, CapabilityError, etc.) so try/catch
                # is a true safety net for AILang programs.
                local = Env(parent=env)
                local.define(node.catch_name, str(py_exc))
                return self.exec_block(node.catch_body, local)
        if isinstance(node, A.Throw):
            raise ThrowSignal(self.eval_expr(node.value, env))
        if isinstance(node, A.ExprStmt):
            return self.eval_expr(node.value, env)
        if isinstance(node, A.Block):
            return self.exec_block(node.body, env)
        raise AILangRuntimeError(f"statement desconocido: {type(node)}")

    def exec_block(self, body: List[Any], env: Env) -> Any:
        local = Env(parent=env)
        last = None
        for stmt in body:
            last = self.exec_stmt(stmt, local)
        return last



    def _call_function(
        self,
        fn: FunctionValue,
        args: list,
        *,
        self_obj: Any = None,
        defining_cls: Any = None,
    ) -> Any:
        """Invoca función/método con cierre léxico, self/super y stack frames."""
        expected = list(fn.params)
        if len(args) != len(expected):
            raise AILangRuntimeError(
                f"{fn.name} espera {len(expected)} args, recibió {len(args)}"
            )
        local = Env(parent=fn.env)
        if self_obj is not None:
            local.define("self", self_obj)
            if isinstance(self_obj, Instance):
                owner = defining_cls or self_obj.cls
                local.define("super", SuperProxy(self_obj, owner))
        for p, a in zip(expected, args):
            local.define(p, a)
        # Si el cuerpo tiene yield → generador
        def _has_yield(stmts):
            for s in stmts:
                if isinstance(s, A.Yield):
                    return True
                for attr in ("body", "orelse", "catch_body"):
                    if hasattr(s, attr) and _has_yield(getattr(s, attr) or []):
                        return True
            return False
        if _has_yield(fn.body):
            return GeneratorValue(fn, list(args), _interp=self)
        try:
            self.exec_block(fn.body, local)
        except ReturnSignal as rs:
            return rs.value
        except AILangRuntimeError as exc:
            raise exc.push(fn.name or "<fn>") from None
        return None

    def _py_callable(self, value: Any) -> Any:
        """Envuelve FunctionValue para que stdlib Python pueda invocarla."""
        if not isinstance(value, FunctionValue):
            return value
        fv = value
        interp = self

        def _call(*args):
            local = Env(parent=fv.env)
            if len(args) != len(fv.params):
                raise AILangRuntimeError(
                    f"{fv.name} espera {len(fv.params)} args, recibió {len(args)}"
                )
            for p, a in zip(fv.params, args):
                local.define(p, a)
            try:
                interp.exec_block(fv.body, local)
            except ReturnSignal as rs:
                return rs.value
            return None

        return _call

    def eval_expr(self, node: Any, env: Env) -> Any:
        if isinstance(node, A.InterpolatedString):
            out = []
            for part in node.parts:
                if isinstance(part, A.Literal):
                    out.append(str(part.value))
                else:
                    out.append(str(self.eval_expr(part, env)))
            return "".join(out)
        if isinstance(node, A.Await):
            val = self.eval_expr(node.value, env)
            # await on async function call result: if already value, return
            # if FunctionValue async without call — error
            return val
        if isinstance(node, A.Literal):
            return node.value
        if isinstance(node, A.Lambda):
            return FunctionValue("<lambda>", node.params, node.body, env)
        if isinstance(node, A.Name):
            return env.get(node.id)
        if isinstance(node, A.ListLit):
            return [self.eval_expr(e, env) for e in node.elts]
        if isinstance(node, A.DictLit):
            return {
                self.eval_expr(k, env): self.eval_expr(v, env)
                for k, v in zip(node.keys, node.values)
            }
        if isinstance(node, A.UnaryOp):
            v = self.eval_expr(node.operand, env)
            if node.op == "-":
                return -v
            if node.op == "+":
                return +v
            if node.op == "not":
                return not _truthy(v)
            raise AILangRuntimeError(f"unary {node.op}")
        if isinstance(node, A.BinOp):
            if node.op == "and":
                left = self.eval_expr(node.left, env)
                return self.eval_expr(node.right, env) if _truthy(left) else left
            if node.op == "or":
                left = self.eval_expr(node.left, env)
                return left if _truthy(left) else self.eval_expr(node.right, env)
            l = self.eval_expr(node.left, env)
            r = self.eval_expr(node.right, env)
            if node.op == "+":
                if isinstance(l, str) or isinstance(r, str):
                    return str(l) + str(r)
                return l + r
            ops = {
                "+": lambda a, b: a + b,
                "-": lambda a, b: a - b,
                "*": lambda a, b: a * b,
                "/": lambda a, b: a / b,
                "%": lambda a, b: a % b,
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
                "<": lambda a, b: a < b,
                "<=": lambda a, b: a <= b,
                ">": lambda a, b: a > b,
                ">=": lambda a, b: a >= b,
            }
            if node.op not in ops:
                raise AILangRuntimeError(f"operador {node.op}")
            try:
                return ops[node.op](l, r)
            except TypeError as e:
                raise AILangRuntimeError(str(e)) from e
        if isinstance(node, A.Attr):
            obj = self.eval_expr(node.value, env)
            if isinstance(obj, Module):
                return getattr(obj, node.attr)
            if isinstance(obj, RecordInstance):
                if node.attr in obj.fields:
                    return obj.fields[node.attr]
                raise AILangRuntimeError(f"record sin campo '{node.attr}'")
            if isinstance(obj, ChannelValue):
                if node.attr == "send":
                    return obj.send
                if node.attr == "recv":
                    return obj.recv
            if isinstance(obj, Instance):
                if node.attr in obj.fields:
                    return obj.fields[node.attr]
                meth, owner = obj.cls.lookup_with_owner(node.attr)
                if meth is not None and owner is not None:
                    return BoundMethod(obj, meth, owner)
                raise AILangRuntimeError(
                    f"'{obj.cls.name}' no tiene atributo '{node.attr}'"
                )
            if isinstance(obj, SuperProxy):
                base = obj.start_cls.base
                while base is not None:
                    if node.attr in base.methods:
                        return BoundMethod(obj.instance, base.methods[node.attr], base)
                    base = base.base
                raise AILangRuntimeError(f"super no tiene método '{node.attr}'")
            if isinstance(obj, EnumType):
                if node.attr in obj.variants:
                    return obj.variants[node.attr]
                raise AILangRuntimeError(f"enum {obj.name} no tiene {node.attr}")
            if isinstance(obj, ClassValue):
                meth = obj.lookup(node.attr)
                if meth is not None:
                    return meth
            if isinstance(obj, dict) and node.attr in obj:
                return obj[node.attr]
            if hasattr(obj, node.attr) and not node.attr.startswith("_"):
                return getattr(obj, node.attr)
            raise AILangRuntimeError(f"atributo '{node.attr}' no encontrado en {obj!r}")
        if isinstance(node, A.Call):
            callee = self.eval_expr(node.func, env)
            args = [self.eval_expr(a, env) for a in node.args]
            # constructor: ClassName(args)
            if isinstance(callee, ClassValue):
                inst = Instance(callee, {})
                init = callee.lookup("init")
                if init is not None:
                    self._call_function(init, args, self_obj=inst, defining_cls=callee)
                return inst
            if isinstance(callee, BoundMethod):
                return self._call_function(
                    callee.func, args, self_obj=callee.instance, defining_cls=callee.defining_cls
                )
            if isinstance(callee, FunctionValue):
                return self._call_function(callee, args)
            if callable(callee):
                py_args = [self._py_callable(a) for a in args]
                return callee(*py_args)
            raise AILangRuntimeError(f"no invocable: {callee!r}")
        if isinstance(node, A.Index):
            base = self.eval_expr(node.value, env)
            idx = self.eval_expr(node.index, env)
            return base[idx]
        raise AILangRuntimeError(f"expresión desconocida: {type(node)}")


def run_source(
    source: str,
    *,
    brain_engine: Any = None,
    module_path: Optional[list] = None,
    use_vm: bool = False,
    typecheck_strict: Optional[bool] = None,
) -> Any:
    import os
    if typecheck_strict is not None:
        from ailang.lang.typecheck import typecheck
        diags = typecheck(source, strict=typecheck_strict)
        errors = [d for d in diags if d.level == "error"]
        if errors:
            raise AILangRuntimeError("typecheck: " + "; ".join(str(e) for e in errors))
    # AILANG_VM=1 fuerza VM; use_vm=True también
    if use_vm or os.environ.get("AILANG_VM") == "1":
        from ailang.lang.vm import run_vm
        return run_vm(source, module_path=module_path)
    return Interpreter(brain_engine=brain_engine, module_path=module_path).run(source)


def create_repl(brain_engine: Any = None) -> None:
    """REPL interactivo del núcleo AILang."""
    interp = Interpreter(brain_engine=brain_engine)
    print(f"AILang REPL — núcleo MVP. Ctrl+D / exit para salir.")
    buf: List[str] = []
    while True:
        try:
            prompt = "... " if buf else "ailang> "
            line = input(prompt)
        except EOFError:
            print()
            break
        if line.strip() in ("exit", "quit") and not buf:
            break
        buf.append(line)
        text = "\n".join(buf)
        # continue if block seems open
        if text.count("{") > text.count("}"):
            continue
        buf = []
        try:
            result = interp.run(text)
            if result is not None:
                print(repr(result))
        except (AILangSyntaxError, AILangRuntimeError) as e:
            print(f"! {e}")
        except Exception as e:
            print(f"! {type(e).__name__}: {e}")
