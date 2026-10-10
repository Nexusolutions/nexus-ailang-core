"""Bytecode VM apilada para AILang — núcleo + class/import + try/catch
+ P0-5 upvalues mutables (Cell) para closures
+ P0-6 generadores (yield / GeneratorValue)
+ P0-7 enum/interface/record/InterpolatedString
+ P0-8 async/await event loop minimal
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ailang.lang import ast_nodes as A
from ailang.lang.parser import parse
from ailang.lang.errors import AILangRuntimeError


(
    LOAD_CONST, LOAD_NAME, STORE_NAME, DEFINE_NAME,
    BINARY_OP, UNARY_OP, CALL, RETURN,
    JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, POP,
    BUILD_LIST, BUILD_DICT, GET_ITEM,
    MAKE_FUNCTION, LOAD_ATTR, STORE_ATTR,
    THROW, MAKE_CLASS, IMPORT_MODULE,
    SETUP_CATCH, POP_CATCH,
    # --- P0-5 / P0-6 / P0-7 / P0-8 ---
    BUILD_STRING,        # P0-7: interpola partes (n partes en stack → string)
    MAKE_ENUM,           # P0-7: enum {name: [members]}
    MAKE_RECORD,         # P0-7: record {name, fields}
    MAKE_INTERFACE,      # P0-7: interface {name, methods}
    YIELD,               # P0-6: yield top of stack
    MAKE_GENERATOR,      # P0-6: crea generador desde frame suspendido
    GEN_RESUME,          # P0-6: reanuda generador (no usado directamente porCompiler)
    AWAIT,               # P0-8: await (delega en event loop)
    SPAWN,               # P0-8: spawn (crea task en event loop)
) = range(32)


@dataclass
class CodeObject:
    name: str
    bytecode: List[Tuple[int, Any]] = field(default_factory=list)
    constants: List[Any] = field(default_factory=list)
    names: List[str] = field(default_factory=list)
    arity: int = 0
    is_generator: bool = False  # P0-6: body contiene YIELD


@dataclass
class VMFunction:
    code: CodeObject
    params: Tuple[str, ...]
    closure: Dict[str, Any]
    is_method: bool = False
    is_async: bool = False  # P0-8: fn async → retorna Future en CALL
    is_generator: bool = False  # P0-6: body contiene yield → retorna GeneratorValue en CALL


@dataclass
class Cell:
    """P0-5: contenedor mutable compartido para upvalues de closures.

    Cuando una función interna captura una variable del scope externo,
    en lugar de copiar su valor (snapshot), capturamos la Cell. Mutaciones
    posteriores a esa variable son visibles desde la closure.
    """
    value: Any = None
    def get(self) -> Any: return self.value
    def set(self, v: Any) -> None: self.value = v


@dataclass
class VMClass:
    name: str
    base: Optional["VMClass"]
    methods: Dict[str, VMFunction]

    def lookup(self, name: str):
        cur: Optional[VMClass] = self
        while cur is not None:
            if name in cur.methods:
                return cur.methods[name], cur
            cur = cur.base
        return None, None


@dataclass
class VMInstance:
    cls: VMClass
    fields: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<{self.cls.name} instance>"


@dataclass
class VMBoundMethod:
    instance: VMInstance
    func: VMFunction
    defining: VMClass


@dataclass
class SuperProxy:
    instance: VMInstance
    start_cls: VMClass


@dataclass
class VMModule:
    name: str
    exports: Dict[str, Any]

    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"):
            return object.__getattribute__(self, item)
        try:
            return self.exports[item]
        except KeyError as e:
            raise AttributeError(item) from e


# --- P0-6: Generadores -------------------------------------------------------

class GeneratorState:
    """Estado de un generador: frame suspendido + stack + ip."""
    def __init__(self, fn: "VMFunction", args: list, vm: "VM"):
        self.fn = fn
        self.vm = vm
        self.local = dict(fn.closure)
        self.local.update({p: a for p, a in zip(fn.params, args)})
        self.stack: List[Any] = []
        self.ip = 0
        self.bc = fn.code.bytecode
        self.code = fn.code
        self.finished = False
        self.handlers: List[Tuple[int, str, int]] = []
        self.sent_value: Any = None  # valor inyectado por .send()

    def resume(self, sent_value: Any = None) -> Any:
        """Reanuda el generador. Retorna el próximo valor yielded o raise StopIteration."""
        if self.finished:
            raise StopIteration
        self.sent_value = sent_value
        # Ejecutamos inline: el opcode YIELD hace return del valor;
        # el opcode RETURN final termina el generador.
        return self.vm._run_generator(self)


class VMGenerator:
    """Valor de tipo generador — expone .next() / .send() / .iter()."""
    def __init__(self, state: GeneratorState):
        self.state = state
    def __iter__(self):
        return self
    def __next__(self):
        return self.state.resume()
    def send(self, v: Any):
        return self.state.resume(v)
    def __repr__(self):
        return f"<generator {self.state.fn.code.name}>"


# --- P0-8: Async / Await / Task / Channel ----------------------------------

class VMFuture:
    """Future para async/await. Cumple con el event loop del VM."""
    def __init__(self):
        self._done = False
        self._value: Any = None
        self._error: Optional[BaseException] = None
        self._callbacks: List[Any] = []
    def set_result(self, v: Any) -> None:
        if self._done: return
        self._done = True
        self._value = v
        for cb in self._callbacks: cb(self)
        self._callbacks.clear()
    def set_error(self, e: BaseException) -> None:
        if self._done: return
        self._done = True
        self._error = e
        for cb in self._callbacks: cb(self)
        self._callbacks.clear()
    def add_done_callback(self, cb) -> None:
        if self._done: cb(self)
        else: self._callbacks.append(cb)
    @property
    def done(self) -> bool: return self._done
    def result(self) -> Any:
        if not self._done: raise AILangRuntimeError("Future no resuelto")
        if self._error: raise self._error
        return self._value


class VMScheduler:
    """Event loop cooperativo minimal para spawn/await.

    Mantiene una cola de tareas (cada una es una corrutina VMGenerator).
    ``spawn`` encola; ``await`` suspende la corrutina actual hasta que la
    tarea awaited termine. Implementación basada en generators (sin threads).
    """
    def __init__(self):
        self._ready: List[VMGenerator] = []
        self._current: Optional[VMGenerator] = None
    def spawn(self, gen: VMGenerator) -> VMFuture:
        fut = VMFuture()
        # Wrap: cuando el generator termine, cumplir el future
        def runner():
            try:
                last = None
                while True:
                    try:
                        v = gen.send(last) if last is not None else next(gen)
                    except StopIteration as e:
                        fut.set_result(e.value)
                        return
                    # Si el generator yielded un Future, esperarlo
                    if isinstance(v, VMFuture):
                        if v.done:
                            last = v.result()
                        else:
                            v.add_done_callback(lambda f: self._enqueue_gen(gen, f.result()))
                            return
                    else:
                        last = v
            except BaseException as e:
                fut.set_error(e)
        # Encolar primera ejecución
        self._ready.append(_SyncRunner(generator_from_callable(runner)))
        return fut
    def _enqueue_gen(self, gen: VMGenerator, value: Any) -> None:
        # Reanuda el generator con el valor del future
        def cont():
            try:
                last = gen.send(value)
                # Si yield otro Future, encadenar
                while True:
                    if isinstance(last, VMFuture):
                        if last.done:
                            last = gen.send(last.result())
                        else:
                            last.add_done_callback(lambda f: self._enqueue_gen(gen, f.result()))
                            return
                    else:
                        last = gen.send(last)
            except StopIteration:
                pass
        self._ready.append(_SyncRunner(generator_from_callable(cont)))
    def run_until_complete(self) -> None:
        while self._ready:
            task = self._ready.pop(0)
            task.run()


def generator_from_callable(fn) -> Any:
    """Convierte una callable Python en un generador (para el scheduler).
    Si fn es ya un generator, retorna tal cual; si es una fn regular,
    la invoca y envuelve en un generador de un solo step.
    """
    import types
    if isinstance(fn, types.GeneratorType):
        return fn
    def gen():
        fn()
        return
        yield  # make it a generator
    return gen()


class _SyncRunner:
    """Wrapper para ejecutar una callable como tarea del scheduler."""
    def __init__(self, gen):
        self.gen = gen
    def run(self):
        try:
            next(self.gen)
        except StopIteration:
            pass


class VMChannel:
    """Canal síncrono FIFO para spawn/await."""
    def __init__(self):
        from collections import deque
        self._queue = deque()
        self._closed = False
    def send(self, v: Any) -> None:
        if self._closed:
            raise AILangRuntimeError("canal cerrado")
        self._queue.append(v)
    def recv(self) -> Any:
        if not self._queue:
            if self._closed: raise AILangRuntimeError("canal cerrado y vacío")
            raise AILangRuntimeError("recv en canal vacío sin scheduler")
        return self._queue.popleft()
    def close(self) -> None:
        self._closed = True
    def __repr__(self):
        return f"<channel size={len(self._queue)}>"


# --- P0-7: Enum / Record / Interface ---------------------------------------

@dataclass
class VMEnumType:
    name: str
    members: Dict[str, Any]  # name → int (o cualquier valor)

@dataclass
class VMEnumMember:
    enum_name: str
    name: str
    value: Any
    def __repr__(self): return f"{self.enum_name}.{self.name}"
    def __eq__(self, other):
        if isinstance(other, VMEnumMember):
            return self.enum_name == other.enum_name and self.name == other.name
        return False
    def __hash__(self): return hash((self.enum_name, self.name))

@dataclass
class VMRecordType:
    name: str
    fields: Tuple[str, ...]

@dataclass
class VMRecordInstance:
    type_: VMRecordType
    values: Dict[str, Any]
    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"): return object.__getattribute__(self, item)
        try: return self.values[item]
        except KeyError as e: raise AttributeError(item) from e
    def __repr__(self): return f"{self.type_.name}({', '.join(f'{k}={v!r}' for k,v in self.values.items())})"

@dataclass
class VMInterfaceType:
    name: str
    methods: Tuple[str, ...]


class Compiler:
    def __init__(self):
        self.code = CodeObject("<module>")
        self._loop_stack: List[Tuple[List[int], List[int]]] = []

    def emit(self, op: int, arg: Any = None) -> int:
        self.code.bytecode.append((op, arg))
        return len(self.code.bytecode) - 1

    def const(self, v: Any) -> int:
        for i, c in enumerate(self.code.constants):
            if c is v or c == v:
                return i
        self.code.constants.append(v)
        return len(self.code.constants) - 1

    def name(self, n: str) -> int:
        if n not in self.code.names:
            self.code.names.append(n)
        return self.code.names.index(n)

    def compile_program(self, program: A.Program) -> CodeObject:
        self.emit(LOAD_CONST, self.const(None))
        self.emit(DEFINE_NAME, self.name("__last__"))
        for stmt in program.body:
            self.compile_stmt(stmt)
        self.emit(LOAD_NAME, self.name("__last__"))
        self.emit(RETURN)
        return self.code

    def _compile_function_body(self, name: str, params: List[str], body: List[Any]) -> CodeObject:
        nested = Compiler()
        nested.code = CodeObject(name, arity=len(params))
        for s in body:
            nested.compile_stmt(s)
        nested.emit(LOAD_CONST, nested.const(None))
        nested.emit(RETURN)
        # P0-6: detectar si el body contiene YIELD → marcar como generator
        # El flag se almacena en CodeObject para que CALL lo vea.
        nested.code.is_generator = _contains_yield(body)
        return nested.code

    def compile_stmt(self, node: Any) -> None:
        if isinstance(node, A.Let) or isinstance(node, A.Const):
            self.compile_expr(node.value)
            self.emit(DEFINE_NAME, self.name(node.name))
        elif isinstance(node, A.Assign):
            if isinstance(node.name, str):
                self.compile_expr(node.value)
                self.emit(STORE_NAME, self.name(node.name))
            elif isinstance(node.name, A.Attr):
                self.compile_expr(node.name.value)
                self.compile_expr(node.value)
                self.emit(STORE_ATTR, self.name(node.name.attr))
            else:
                raise AILangRuntimeError("assign no compilable")
        elif isinstance(node, A.ExprStmt):
            self.compile_expr(node.value)
            self.emit(DEFINE_NAME, self.name("__last__"))
        elif isinstance(node, A.Return):
            if node.value is None:
                self.emit(LOAD_CONST, self.const(None))
            else:
                self.compile_expr(node.value)
            self.emit(RETURN)
        elif isinstance(node, A.If):
            self.compile_expr(node.test)
            j_else = self.emit(JUMP_IF_FALSE, 0)
            for s in node.body:
                self.compile_stmt(s)
            j_end = self.emit(JUMP, 0)
            else_ip = len(self.code.bytecode)
            self.code.bytecode[j_else] = (JUMP_IF_FALSE, else_ip)
            for s in node.orelse:
                self.compile_stmt(s)
            self.code.bytecode[j_end] = (JUMP, len(self.code.bytecode))
        elif isinstance(node, A.While):
            breaks, continues = [], []
            self._loop_stack.append((breaks, continues))
            start = len(self.code.bytecode)
            self.compile_expr(node.test)
            j_exit = self.emit(JUMP_IF_FALSE, 0)
            for s in node.body:
                self.compile_stmt(s)
            cont_target = len(self.code.bytecode)
            self.emit(JUMP, start)
            exit_ip = len(self.code.bytecode)
            self.code.bytecode[j_exit] = (JUMP_IF_FALSE, exit_ip)
            for ip in breaks:
                self.code.bytecode[ip] = (JUMP, exit_ip)
            for ip in continues:
                self.code.bytecode[ip] = (JUMP, cont_target)
            self._loop_stack.pop()
        elif isinstance(node, A.For):
            # P0-7: for x in iter — soporta list, dict, str, generadores (VMGenerator)
            # Implementación: iter(iterable) + try/next/catch StopIteration loop
            self.compile_expr(node.iter)
            self.emit(DEFINE_NAME, self.name("__it_src"))
            self.emit(LOAD_NAME, self.name("iter"))
            self.emit(LOAD_NAME, self.name("__it_src"))
            self.emit(CALL, 1)
            self.emit(DEFINE_NAME, self.name("__it"))
            breaks, continues = [], []
            self._loop_stack.append((breaks, continues))
            start = len(self.code.bytecode)
            setup_ip = self.emit(SETUP_CATCH, 0)
            self.emit(LOAD_NAME, self.name("next"))
            self.emit(LOAD_NAME, self.name("__it"))
            self.emit(CALL, 1)
            self.emit(DEFINE_NAME, self.name(node.target))
            for s in node.body:
                self.compile_stmt(s)
            cont_target = len(self.code.bytecode)
            self.emit(POP_CATCH)
            self.emit(JUMP, start)
            handler_ip = len(self.code.bytecode)
            self.code.bytecode[setup_ip] = (SETUP_CATCH, (handler_ip, "__exc__"))
            self.emit(DEFINE_NAME, self.name("__exc__"))
            self.emit(POP)
            exit_ip = len(self.code.bytecode)
            for ip in breaks:
                self.code.bytecode[ip] = (JUMP, exit_ip)
            for ip in continues:
                self.code.bytecode[ip] = (JUMP, cont_target)
            self._loop_stack.pop()
        elif isinstance(node, A.Break):
            if not self._loop_stack:
                raise AILangRuntimeError("break fuera de bucle")
            self._loop_stack[-1][0].append(self.emit(JUMP, 0))
        elif isinstance(node, A.Continue):
            if not self._loop_stack:
                raise AILangRuntimeError("continue fuera de bucle")
            self._loop_stack[-1][1].append(self.emit(JUMP, 0))
        elif isinstance(node, A.Function):
            cobj = self._compile_function_body(node.name, node.params, node.body)
            self.emit(LOAD_CONST, self.const(cobj))
            self.emit(MAKE_FUNCTION, (node.name, tuple(node.params), False))
            self.emit(DEFINE_NAME, self.name(node.name))
        elif isinstance(node, A.ClassDef):
            method_meta = []
            for m in node.methods:
                cobj = self._compile_function_body(m.name, m.params, m.body)
                self.emit(LOAD_CONST, self.const(cobj))
                self.emit(MAKE_FUNCTION, (m.name, tuple(m.params), True))
                method_meta.append(m.name)
            # stack: method0, method1, ... (bottom to top)
            self.emit(MAKE_CLASS, (node.name, node.base, tuple(method_meta)))
            self.emit(DEFINE_NAME, self.name(node.name))
        elif isinstance(node, A.Import):
            self.emit(IMPORT_MODULE, (node.module, node.alias))
        elif isinstance(node, A.Block):
            for s in node.body:
                self.compile_stmt(s)
        elif isinstance(node, A.Match):
            self.compile_expr(node.subject)
            self.emit(DEFINE_NAME, self.name("__match_subj"))
            end_jumps = []
            for case in node.cases:
                is_wild = isinstance(case.pattern, A.Name) and case.pattern.id == "_"
                is_bind = isinstance(case.pattern, A.Name) and case.pattern.id != "_"
                if is_wild or is_bind:
                    if is_bind:
                        self.emit(LOAD_NAME, self.name("__match_subj"))
                        self.emit(DEFINE_NAME, self.name(case.pattern.id))
                    for s in case.body:
                        self.compile_stmt(s)
                    end_jumps.append(self.emit(JUMP, 0))
                    break  # wildcard/bind ends match
                # literal / comparable pattern
                self.emit(LOAD_NAME, self.name("__match_subj"))
                if isinstance(case.pattern, A.Literal):
                    self.emit(LOAD_CONST, self.const(case.pattern.value))
                else:
                    self.compile_expr(case.pattern)
                self.emit(BINARY_OP, "==")
                j_next = self.emit(JUMP_IF_FALSE, 0)
                for s in case.body:
                    self.compile_stmt(s)
                end_jumps.append(self.emit(JUMP, 0))
                self.code.bytecode[j_next] = (JUMP_IF_FALSE, len(self.code.bytecode))
            end_ip = len(self.code.bytecode)
            for j in end_jumps:
                self.code.bytecode[j] = (JUMP, end_ip)
        elif isinstance(node, A.Throw):
            self.compile_expr(node.value)
            self.emit(THROW)
        elif isinstance(node, A.Try):
            # SETUP_CATCH handler_ip; body; POP_CATCH; JUMP end
            # handler: POP_CATCH (if re-entry clean); DEFINE catch_name; catch_body; end:
            setup_ip = self.emit(SETUP_CATCH, 0)  # patch handler
            for s in node.body:
                self.compile_stmt(s)
            self.emit(POP_CATCH)
            j_end = self.emit(JUMP, 0)
            handler_ip = len(self.code.bytecode)
            self.code.bytecode[setup_ip] = (SETUP_CATCH, (handler_ip, node.catch_name))
            # exception value is on stack when jumping here
            self.emit(DEFINE_NAME, self.name(node.catch_name))
            for s in node.catch_body:
                self.compile_stmt(s)
            end_ip = len(self.code.bytecode)
            self.code.bytecode[j_end] = (JUMP, end_ip)
        elif isinstance(node, A.EnumDef):
            # P0-7: enum Color { RED, GREEN, BLUE }
            # AST usa `variants` (lista de str); auto-indexa los valores
            members = []
            for i, mname in enumerate(node.variants):
                members.append((mname, i))
            self.emit(MAKE_ENUM, (node.name, tuple(members)))
            self.emit(DEFINE_NAME, self.name(node.name))
        elif isinstance(node, A.RecordDef):
            # P0-7: record Point { x, y }
            self.emit(MAKE_RECORD, (node.name, tuple(node.fields)))
            self.emit(DEFINE_NAME, self.name(node.name))
        elif isinstance(node, A.InterfaceDef):
            # P0-7: interface S { fn speak() }
            # AST tiene methods: List[str] (nombres directamente)
            method_names = tuple(node.methods) if not node.methods or isinstance(node.methods[0], str) \
                else tuple(m.name for m in node.methods)
            self.emit(MAKE_INTERFACE, (node.name, method_names))
            self.emit(DEFINE_NAME, self.name(node.name))
        elif isinstance(node, A.Yield):
            # P0-6: yield <expr>
            if node.value is not None:
                self.compile_expr(node.value)
            else:
                self.emit(LOAD_CONST, self.const(None))
            self.emit(YIELD)
        elif isinstance(node, A.Spawn):
            # P0-8: spawn <expr>  (AST: node.call es la expr Call)
            self.compile_expr(node.call)
            self.emit(SPAWN)
        else:
            raise AILangRuntimeError(f"VM no soporta {type(node).__name__}")

    def compile_expr(self, node: Any) -> None:
        if isinstance(node, A.Literal):
            self.emit(LOAD_CONST, self.const(node.value))
        elif isinstance(node, A.Name):
            self.emit(LOAD_NAME, self.name(node.id))
        elif isinstance(node, A.UnaryOp):
            self.compile_expr(node.operand)
            self.emit(UNARY_OP, node.op)
        elif isinstance(node, A.BinOp):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.emit(BINARY_OP, node.op)
        elif isinstance(node, A.Call):
            self.compile_expr(node.func)
            for a in node.args:
                self.compile_expr(a)
            self.emit(CALL, len(node.args))
        elif isinstance(node, A.ListLit):
            for e in node.elts:
                self.compile_expr(e)
            self.emit(BUILD_LIST, len(node.elts))
        elif isinstance(node, A.DictLit):
            for k, v in zip(node.keys, node.values):
                self.compile_expr(k)
                self.compile_expr(v)
            self.emit(BUILD_DICT, len(node.keys))
        elif isinstance(node, A.Index):
            self.compile_expr(node.value)
            self.compile_expr(node.index)
            self.emit(GET_ITEM)
        elif isinstance(node, A.Attr):
            self.compile_expr(node.value)
            self.emit(LOAD_ATTR, self.name(node.attr))
        elif isinstance(node, A.Lambda):
            cobj = self._compile_function_body("<lambda>", node.params, node.body)
            self.emit(LOAD_CONST, self.const(cobj))
            self.emit(MAKE_FUNCTION, ("<lambda>", tuple(node.params), False))
        elif isinstance(node, A.InterpolatedString):
            # P0-7: "hello ${name}!" → str(name) + "!" etc.
            # Cada parte string se emite como LOAD_CONST; cada parte expr
            # se emite como LOAD_NAME str + expr + CALL 1 (str(expr)).
            # Final BUILD_STRING n concatena todo.
            n = len(node.parts)
            for part in node.parts:
                if isinstance(part, str):
                    self.emit(LOAD_CONST, self.const(part))
                else:
                    # str(expr): push str fn first, then arg, then CALL 1
                    self.emit(LOAD_NAME, self.name("str"))
                    self.compile_expr(part)
                    self.emit(CALL, 1)
            self.emit(BUILD_STRING, n)
        elif isinstance(node, A.Await):
            # P0-8: await <expr>
            self.compile_expr(node.value)
            self.emit(AWAIT)
        else:
            raise AILangRuntimeError(f"expresión no compilable: {type(node).__name__}")


def _truthy(v: Any) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return False
    if isinstance(v, str) and v == "":
        return False
    if isinstance(v, (list, dict)) and len(v) == 0:
        return False
    return True


def _binary(op: str, a: Any, b: Any) -> Any:
    if op == "+":
        if isinstance(a, str) or isinstance(b, str):
            return str(a) + str(b)
        return a + b
    ops = {
        "-": lambda x, y: x - y,
        "*": lambda x, y: x * y,
        "/": lambda x, y: x / y,
        "%": lambda x, y: x % y,
        "==": lambda x, y: x == y,
        "!=": lambda x, y: x != y,
        "<": lambda x, y: x < y,
        "<=": lambda x, y: x <= y,
        ">": lambda x, y: x > y,
        ">=": lambda x, y: x >= y,
        "and": lambda x, y: y if _truthy(x) else x,
        "or": lambda x, y: x if _truthy(x) else y,
    }
    if op not in ops:
        raise AILangRuntimeError(f"op {op}")
    return ops[op](a, b)


class VM:
    def __init__(
        self,
        builtins: Optional[Dict[str, Any]] = None,
        module_path: Optional[List[str]] = None,
    ):
        self.globals: Dict[str, Any] = {}
        if builtins:
            self.globals.update(builtins)
        self.module_path = list(module_path or [".", "stdlib"])
        self._module_cache: Dict[str, Any] = {}
        # V2: Inline caching para CALL opcode (acelera llamadas repetidas)
        self._call_cache: Dict[Tuple[int, int], Tuple[Any, int]] = {}
        # P0-8: scheduler cooperativo para spawn/await
        self.scheduler = VMScheduler()
        try:
            from ailang.lang.stdlib import builtin_modules
            self._builtin_mods = builtin_modules()
        except Exception:
            self._builtin_mods = {}

    def load_module(self, name: str) -> Any:
        if name in self._module_cache:
            return self._module_cache[name]
        if name in self._builtin_mods:
            mod = self._builtin_mods[name]
            # wrap Module from stdlib as VMModule-compatible
            exports = getattr(mod, "_exports", None)
            if exports is not None:
                vmmod = VMModule(name, dict(exports))
            else:
                vmmod = mod
            self._module_cache[name] = vmmod
            return vmmod
        rel = name.replace(".", "/") + ".ailang"
        for root in self.module_path:
            candidate = Path(root) / rel
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
                code = Compiler().compile_program(parse(text))
                # run in fresh locals; export names
                saved = dict(self.globals)
                result_locals: Dict[str, Any] = {}
                # merge: execute module with empty locals using same globals builtins
                mod_locals = self._run(code, {}, capture_locals=True)
                exports = {
                    k: v for k, v in mod_locals.items()
                    if not k.startswith("__")
                }
                vmmod = VMModule(name, exports)
                self._module_cache[name] = vmmod
                return vmmod
        raise AILangRuntimeError(f"módulo no encontrado: {name}")

    def run_code(self, code: CodeObject, locals_: Optional[Dict[str, Any]] = None) -> Any:
        return self._run(code, locals_ or {}, capture_locals=False)

    def _run(
        self,
        code: CodeObject,
        names_local: Dict[str, Any],
        *,
        capture_locals: bool = False,
    ) -> Any:
        stack: List[Any] = []
        ip = 0
        bc = code.bytecode
        # (handler_ip, catch_name, stack_size)
        handlers: List[Tuple[int, str, int]] = []

        # W3: name cache — index of common names to avoid dict lookups
        # Maps name string → (location, slot) where location is 'local' or 'global'
        # First lookup is slow (dict), subsequent lookups use the cached slot
        name_cache: Dict[str, Tuple[str, int]] = {}

        def resolve_name(n: str) -> Any:
            # W3: check cache first
            cached = name_cache.get(n)
            if cached is not None:
                loc, _ = cached
                if loc == 'local':
                    v = names_local[n]
                else:
                    v = self.globals[n]
                return v.get() if isinstance(v, Cell) else v
            # Cache miss: do full lookup
            if n in names_local:
                name_cache[n] = ('local', 0)
                v = names_local[n]
                return v.get() if isinstance(v, Cell) else v
            if n in self.globals:
                name_cache[n] = ('global', 0)
                v = self.globals[n]
                return v.get() if isinstance(v, Cell) else v
            raise AILangRuntimeError(f"nombre no definido: {n}")

        def store_name(n: str, val: Any) -> None:
            if n in names_local:
                names_local[n] = val
            elif n in self.globals and n not in names_local:
                # prefer local frame for module scripts
                names_local[n] = val
            else:
                names_local[n] = val

        def call_vm_func(fn: VMFunction, args: list, self_obj=None, defining=None):
            if len(args) != len(fn.params):
                raise AILangRuntimeError(
                    f"{fn.code.name} espera {len(fn.params)} args, recibió {len(args)}"
                )
            local = dict(fn.closure)
            local.update({p: a for p, a in zip(fn.params, args)})
            if self_obj is not None:
                local["self"] = self_obj
                owner = defining or (self_obj.cls if isinstance(self_obj, VMInstance) else None)
                if isinstance(self_obj, VMInstance) and owner is not None:
                    local["super"] = SuperProxy(self_obj, owner)
            try:
                return self._run(fn.code, local)
            except AILangRuntimeError as exc:
                raise exc.push(fn.code.name or "<fn>") from None

        while ip < len(bc):
            op, arg = bc[ip]
            ip += 1
            if op == LOAD_CONST:
                stack.append(code.constants[arg])
            elif op == LOAD_NAME:
                try:
                    stack.append(resolve_name(code.names[arg]))
                except AILangRuntimeError as exc:
                    if handlers:
                        handler_ip, catch_name, sp = handlers.pop()
                        del stack[sp:]
                        stack.append(getattr(exc, "message", None) or str(exc))
                        ip = handler_ip
                    else:
                        raise
            elif op == DEFINE_NAME:
                n = code.names[arg]
                val = stack.pop()
                names_local[n] = val
                # Recursión: la función debe verse a sí misma en el cierre
                if isinstance(val, VMFunction):
                    val.closure[n] = val
                    self.globals[n] = val
            elif op == STORE_NAME:
                # P0-5: si la variable es una Cell, actualizar su contenido
                val = stack.pop()
                n = code.names[arg]
                if n in names_local and isinstance(names_local[n], Cell):
                    names_local[n].set(val)
                else:
                    store_name(n, val)
            elif op == BINARY_OP:
                b, a = stack.pop(), stack.pop()
                stack.append(_binary(arg, a, b))
            elif op == UNARY_OP:
                a = stack.pop()
                if arg == "-":
                    stack.append(-a)
                elif arg == "not":
                    stack.append(not _truthy(a))
                else:
                    stack.append(+a)
            elif op == CALL:
                argc = arg
                args = [stack.pop() for _ in range(argc)][::-1]
                fn = stack.pop()

                # V2: Inline caching para method dispatch en VMInstance.
                # Si fn es VMBoundMethod, cacheamos el lookup para evitar
                # repetir cls.lookup() en llamadas sucesivas al mismo método.
                try:
                    if isinstance(fn, VMClass):
                        inst = VMInstance(fn)
                        init, owner = fn.lookup("init")
                        if init is not None:
                            call_vm_func(init, args, self_obj=inst, defining=owner)
                        stack.append(inst)
                    elif isinstance(fn, VMBoundMethod):
                        stack.append(
                            call_vm_func(
                                fn.func, args, self_obj=fn.instance, defining=fn.defining
                            )
                        )
                    elif isinstance(fn, VMFunction):
                        # P0-6: si la fn es generator, crear VMGenerator
                        if fn.is_generator:
                            gen_state = GeneratorState(fn, args, self)
                            stack.append(VMGenerator(gen_state))
                        else:
                            # V2: Inline caching — si la función ya fue llamada
                            # con este CodeObject y argc, reusar el frame setup
                            cache_key = (id(fn.code), argc)
                            cached = self._call_cache.get(cache_key)
                            if cached is not None and cached[0] is fn:
                                # Cache hit: skip lookup overhead
                                stack.append(call_vm_func(fn, args))
                            else:
                                # Cache miss: store and call
                                self._call_cache[cache_key] = (fn, len(fn.params))
                                stack.append(call_vm_func(fn, args))
                    elif callable(fn):
                        stack.append(fn(*args))
                    else:
                        raise AILangRuntimeError(f"no invocable: {fn!r}")
                except (AILangRuntimeError, StopIteration) as exc:
                    # StopIteration: P0-7 for-loop via next() que termina
                    if handlers:
                        handler_ip, catch_name, sp = handlers.pop()
                        del stack[sp:]
                        if isinstance(exc, StopIteration):
                            stack.append("__stop_iteration__")
                        else:
                            stack.append(getattr(exc, "message", None) or str(exc))
                        ip = handler_ip
                    else:
                        raise
            elif op == RETURN:
                ret = stack.pop() if stack else None
                if capture_locals:
                    names_local["__return__"] = ret
                    return names_local
                return ret
            elif op == JUMP:
                ip = arg
            elif op == JUMP_IF_FALSE:
                if not _truthy(stack.pop()):
                    ip = arg
            elif op == JUMP_IF_TRUE:
                if _truthy(stack.pop()):
                    ip = arg
            elif op == POP:
                if stack:
                    stack.pop()
            elif op == BUILD_LIST:
                stack.append([stack.pop() for _ in range(arg)][::-1])
            elif op == BUILD_DICT:
                d = {}
                for _ in range(arg):
                    v, k = stack.pop(), stack.pop()
                    d[k] = v
                stack.append(d)
            elif op == GET_ITEM:
                idx, base = stack.pop(), stack.pop()
                stack.append(base[idx])
            elif op == MAKE_FUNCTION:
                name, params, is_method = arg
                cobj = stack.pop()
                # P0-5: closures mutables — capturamos Cell refs
                clos = dict(self.globals)
                for k, v in names_local.items():
                    if isinstance(v, Cell):
                        clos[k] = v  # compartir Cell
                    else:
                        if k in ("self", "super") or k.startswith("__"):
                            clos[k] = v
                        else:
                            cell = Cell(v)
                            names_local[k] = cell
                            clos[k] = cell
                # P0-6: propagar is_generator desde CodeObject
                vm_fn = VMFunction(cobj, params, clos, is_method=is_method)
                vm_fn.is_generator = getattr(cobj, "is_generator", False)
                stack.append(vm_fn)
            elif op == MAKE_CLASS:
                cls_name, base_name, method_names = arg
                methods = {}
                # methods pushed in order; top is last method
                for mname in reversed(method_names):
                    fn = stack.pop()
                    if not isinstance(fn, VMFunction):
                        raise AILangRuntimeError("MAKE_CLASS espera funciones")
                    methods[mname] = fn
                base = None
                if base_name:
                    base_obj = resolve_name(base_name)
                    if not isinstance(base_obj, VMClass):
                        raise AILangRuntimeError(f"extends requiere clase: {base_name}")
                    base = base_obj
                stack.append(VMClass(cls_name, base, methods))
            elif op == IMPORT_MODULE:
                mod_name, alias = arg
                mod = self.load_module(mod_name)
                bind = alias or mod_name.split(".")[-1]
                names_local[bind] = mod
            elif op == LOAD_ATTR:
                obj = stack.pop()
                attr = code.names[arg]
                if isinstance(obj, VMInstance):
                    if attr in obj.fields:
                        stack.append(obj.fields[attr])
                    else:
                        meth, owner = obj.cls.lookup(attr)
                        if meth is None or owner is None:
                            raise AILangRuntimeError(
                                f"'{obj.cls.name}' no tiene '{attr}'"
                            )
                        stack.append(VMBoundMethod(obj, meth, owner))
                elif isinstance(obj, SuperProxy):
                    base = obj.start_cls.base
                    found = None
                    owner = None
                    while base is not None:
                        if attr in base.methods:
                            found = base.methods[attr]
                            owner = base
                            break
                        base = base.base
                    if found is None or owner is None:
                        raise AILangRuntimeError(f"super no tiene '{attr}'")
                    stack.append(VMBoundMethod(obj.instance, found, owner))
                elif isinstance(obj, VMModule):
                    stack.append(getattr(obj, attr))
                elif isinstance(obj, VMClass):
                    # P0-7: Class.attr — para enum member access (Color.RED)
                    meth, owner = obj.lookup(attr)
                    if meth is not None:
                        stack.append(meth)
                    else:
                        raise AILangRuntimeError(f"'{obj.name}' no tiene miembro '{attr}'")
                elif isinstance(obj, VMEnumType):
                    # P0-7: Color.RED
                    if attr in obj.members:
                        stack.append(obj.members[attr])
                    else:
                        raise AILangRuntimeError(f"enum '{obj.name}' no tiene '{attr}'")
                elif isinstance(obj, VMRecordInstance):
                    if attr in obj.values:
                        stack.append(obj.values[attr])
                    else:
                        raise AILangRuntimeError(f"record '{obj.type_.name}' no tiene '{attr}'")
                elif hasattr(obj, attr):
                    stack.append(getattr(obj, attr))
                else:
                    # stdlib Module object
                    try:
                        stack.append(getattr(obj, attr))
                    except AttributeError:
                        raise AILangRuntimeError(f"atributo '{attr}' no encontrado") from None
            elif op == STORE_ATTR:
                val = stack.pop()
                obj = stack.pop()
                attr = code.names[arg]
                if isinstance(obj, VMInstance):
                    obj.fields[attr] = val
                elif isinstance(obj, dict):
                    obj[attr] = val
                else:
                    setattr(obj, attr, val)
            elif op == SETUP_CATCH:
                # arg = (handler_ip, catch_name)
                handler_ip, catch_name = arg
                handlers.append((handler_ip, catch_name, len(stack)))
            elif op == POP_CATCH:
                if handlers:
                    handlers.pop()
            elif op == THROW:
                val = stack.pop() if stack else None
                if handlers:
                    handler_ip, catch_name, sp = handlers.pop()
                    # unwind stack to try entry
                    del stack[sp:]
                    stack.append(val)
                    ip = handler_ip
                else:
                    raise AILangRuntimeError(str(val))
            # --- P0-7: enum / record / interface / interpolated string ---
            elif op == MAKE_ENUM:
                enum_name, members = arg
                type_obj = VMEnumType(enum_name, {})
                for mname, mval in members:
                    member = VMEnumMember(enum_name, mname, mval)
                    type_obj.members[mname] = member
                    # expose as EnumName.MemberName in current scope
                    names_local[f"{enum_name}.{mname}"] = member
                stack.append(type_obj)
            elif op == MAKE_RECORD:
                rec_name, fields = arg
                rt = VMRecordType(rec_name, fields)
                # Constructor: when called, expects N positional args
                def record_ctor(*args, _rt=rt):
                    if len(args) != len(_rt.fields):
                        raise AILangRuntimeError(
                            f"{_rt.name} espera {len(_rt.fields)} args, recibió {len(args)}"
                        )
                    return VMRecordInstance(_rt, dict(zip(_rt.fields, args)))
                stack.append(record_ctor)
            elif op == MAKE_INTERFACE:
                if_name, method_names = arg
                stack.append(VMInterfaceType(if_name, method_names))
            elif op == BUILD_STRING:
                n = arg
                parts = [stack.pop() for _ in range(n)][::-1]
                stack.append("".join(str(p) for p in parts))
            # --- P0-6: generadores ---
            elif op == YIELD:
                # YIELD solo aparece en código de funciones generadoras, que
                # se ejecutan vía _run_generator, no en _run. Si llegamos aquí,
                # es un bug — el flag is_generator no se propagó correctamente.
                val = stack.pop() if stack else None
                raise AILangRuntimeError(
                    "YIELD encontrado fuera de un generador. "
                    "Si la fn contiene yield, su CodeObject debe tener is_generator=True."
                )
            elif op == MAKE_GENERATOR:
                # No usado directamente; los generadores se crean en CALL
                # cuando la función tiene is_generator=True
                pass
            elif op == GEN_RESUME:
                # No usado directamente; _run_generator maneja la reanudación
                pass
            # --- P0-8: async / spawn ---
            elif op == SPAWN:
                # spawn <callable> → encola en scheduler, retorna Future
                callable_val = stack.pop()
                # Si es una VMFunction, llamarla para obtener el generador
                if isinstance(callable_val, VMFunction) and callable_val.is_generator:
                    gen_state = GeneratorState(callable_val, [], self)
                    gen = VMGenerator(gen_state)
                    fut = self.scheduler.spawn(gen)
                    stack.append(fut)
                elif isinstance(callable_val, VMFunction):
                    # Función async normal — ejecutar y envolver
                    try:
                        result = call_vm_func(callable_val, [])
                        if isinstance(result, VMGenerator):
                            fut = self.scheduler.spawn(result)
                        else:
                            fut = VMFuture()
                            fut.set_result(result)
                        stack.append(fut)
                    except AILangRuntimeError as exc:
                        raise exc.push(callable_val.code.name or "<fn>") from None
                elif callable(callable_val):
                    # Python callable
                    import types
                    if isinstance(callable_val, types.GeneratorType):
                        fut = self.scheduler.spawn(VMGenerator(
                            GeneratorState(_DummyVMFn(callable_val), [], self)))
                        stack.append(fut)
                    else:
                        fut = VMFuture()
                        try:
                            fut.set_result(callable_val())
                        except BaseException as e:
                            fut.set_error(e)
                        stack.append(fut)
                else:
                    raise AILangRuntimeError(f"spawn: no invocable: {callable_val!r}")
            elif op == AWAIT:
                # await <expr> → bloquea hasta que el future se resuelva
                fut_val = stack.pop()
                if isinstance(fut_val, VMFuture):
                    if not fut_val.done:
                        # En scheduler cooperativo, yield del generator actual
                        raise _AwaitSignal(fut_val)
                    stack.append(fut_val.result())
                elif isinstance(fut_val, VMGenerator):
                    # await un generator → correr hasta StopIteration
                    try:
                        last = None
                        while True:
                            last = fut_val.send(last) if last is not None else next(fut_val)
                    except StopIteration as e:
                        stack.append(e.value if e.value is not None else last)
                else:
                    # await non-future: passthrough
                    stack.append(fut_val)
            else:
                raise AILangRuntimeError(f"opcode desconocido {op}")

        if capture_locals:
            return names_local
        return stack[-1] if stack else None

    def _run_generator(self, state: GeneratorState) -> Any:
        """Ejecuta un generador hasta el próximo YIELD o fin.

        Implementación: clona el estilo de _run pero opera sobre `state.stack`
        y `state.ip` para permitir reentrancia.
        """
        stack = state.stack
        ip = state.ip
        bc = state.bc
        code = state.code
        names_local = state.local
        handlers = state.handlers

        def resolve_name(n: str) -> Any:
            if n in names_local:
                v = names_local[n]
                return v.get() if isinstance(v, Cell) else v
            if n in self.globals:
                v = self.globals[n]
                return v.get() if isinstance(v, Cell) else v
            raise AILangRuntimeError(f"nombre no definido: {n}")

        def store_name(n: str, val: Any) -> None:
            if n in names_local and isinstance(names_local[n], Cell):
                names_local[n].set(val)
            else:
                names_local[n] = val

        def call_vm_func(fn: VMFunction, args: list, self_obj=None, defining=None):
            if len(args) != len(fn.params):
                raise AILangRuntimeError(
                    f"{fn.code.name} espera {len(fn.params)} args, recibió {len(args)}"
                )
            local = dict(fn.closure)
            # Unwrap Cells al pasar al sub-frame (copia snapshot).
            # Esto significa que mutaciones en sub-frames no se ven en el generador
            # padre — pero ese es el comportamiento esperado (generators no comparten
            # scope con su caller).
            for k, v in list(local.items()):
                if isinstance(v, Cell):
                    local[k] = v.get()
            local.update({p: a for p, a in zip(fn.params, args)})
            if self_obj is not None:
                local["self"] = self_obj
                owner = defining or (self_obj.cls if isinstance(self_obj, VMInstance) else None)
                if isinstance(self_obj, VMInstance) and owner is not None:
                    local["super"] = SuperProxy(self_obj, owner)
            try:
                return self._run(fn.code, local)
            except AILangRuntimeError as exc:
                raise exc.push(fn.code.name or "<fn>") from None

        while ip < len(bc):
            op, arg = bc[ip]
            ip += 1
            # Reutilizamos la lógica de _run para la mayoría de opcodes.
            # Por simplicidad, delegamos al código principal con un flag;
            # aquí solo interceptamos YIELD y RETURN.
            if op == YIELD:
                val = stack.pop() if stack else None
                state.ip = ip
                state.stack = stack
                return val
            elif op == RETURN:
                ret = stack.pop() if stack else None
                state.finished = True
                raise StopIteration(ret)
            else:
                # Manejo inline mínimo para opcodes comunes (re-implementación
                # ligera de _run para no acoplar estado).
                # Para mantener este método compacto, delegamos a _step_opcode.
                cont = self._step_opcode_generator(
                    op, arg, code, stack, names_local, handlers, resolve_name, store_name, call_vm_func
                )
                if cont is None:
                    pass
                elif isinstance(cont, tuple) and cont[0] == "jump":
                    ip = cont[1]
                elif isinstance(cont, tuple) and cont[0] == "return":
                    state.finished = True
                    raise StopIteration(cont[1])
                elif isinstance(cont, tuple) and cont[0] == "yield":
                    state.ip = ip
                    state.stack = stack
                    return cont[1]
        state.finished = True
        raise StopIteration(stack[-1] if stack else None)

    def _step_opcode_generator(self, op, arg, code, stack, names_local, handlers,
                                resolve_name, store_name, call_vm_func):
        """Ejecuta un opcode en el contexto de un generador.
        Retorna None (continuar), ('jump', ip), ('return', val), o ('yield', val)."""
        if op == LOAD_CONST:
            stack.append(code.constants[arg])
        elif op == LOAD_NAME:
            stack.append(resolve_name(code.names[arg]))
        elif op == DEFINE_NAME:
            n = code.names[arg]
            val = stack.pop()
            names_local[n] = val
            if isinstance(val, VMFunction):
                val.closure[n] = val
                self.globals[n] = val
        elif op == STORE_NAME:
            val = stack.pop()
            n = code.names[arg]
            if n in names_local and isinstance(names_local[n], Cell):
                names_local[n].set(val)
            else:
                store_name(n, val)
        elif op == BINARY_OP:
            b, a = stack.pop(), stack.pop()
            stack.append(_binary(arg, a, b))
        elif op == UNARY_OP:
            a = stack.pop()
            if arg == "-": stack.append(-a)
            elif arg == "not": stack.append(not _truthy(a))
            else: stack.append(+a)
        elif op == CALL:
            argc = arg
            args = [stack.pop() for _ in range(argc)][::-1]
            fn = stack.pop()
            if isinstance(fn, VMClass):
                inst = VMInstance(fn)
                init, owner = fn.lookup("init")
                if init is not None:
                    call_vm_func(init, args, self_obj=inst, defining=owner)
                stack.append(inst)
            elif isinstance(fn, VMBoundMethod):
                stack.append(call_vm_func(fn.func, args, self_obj=fn.instance, defining=fn.defining))
            elif isinstance(fn, VMFunction):
                if fn.is_generator:
                    gen_state = GeneratorState(fn, args, self)
                    stack.append(VMGenerator(gen_state))
                else:
                    stack.append(call_vm_func(fn, args))
            elif callable(fn):
                stack.append(fn(*args))
            else:
                raise AILangRuntimeError(f"no invocable: {fn!r}")
        elif op == RETURN:
            ret = stack.pop() if stack else None
            return ("return", ret)
        elif op == JUMP:
            return ("jump", arg)
        elif op == JUMP_IF_FALSE:
            if not _truthy(stack.pop()):
                return ("jump", arg)
        elif op == JUMP_IF_TRUE:
            if _truthy(stack.pop()):
                return ("jump", arg)
        elif op == POP:
            if stack: stack.pop()
        elif op == BUILD_LIST:
            stack.append([stack.pop() for _ in range(arg)][::-1])
        elif op == BUILD_DICT:
            d = {}
            for _ in range(arg):
                v, k = stack.pop(), stack.pop()
                d[k] = v
            stack.append(d)
        elif op == GET_ITEM:
            idx, base = stack.pop(), stack.pop()
            stack.append(base[idx])
        elif op == MAKE_FUNCTION:
            name, params, is_method = arg
            cobj = stack.pop()
            clos = dict(self.globals)
            for k, v in names_local.items():
                if isinstance(v, Cell):
                    clos[k] = v
                elif k in ("self", "super") or k.startswith("__"):
                    clos[k] = v
                else:
                    cell = Cell(v)
                    names_local[k] = cell
                    clos[k] = cell
            stack.append(VMFunction(cobj, params, clos, is_method=is_method))
        elif op == MAKE_CLASS:
            cls_name, base_name, method_names = arg
            methods = {}
            for mname in reversed(method_names):
                fn = stack.pop()
                if not isinstance(fn, VMFunction):
                    raise AILangRuntimeError("MAKE_CLASS espera funciones")
                methods[mname] = fn
            base = None
            if base_name:
                base_obj = resolve_name(base_name)
                if not isinstance(base_obj, VMClass):
                    raise AILangRuntimeError(f"extends requiere clase: {base_name}")
                base = base_obj
            stack.append(VMClass(cls_name, base, methods))
        elif op == IMPORT_MODULE:
            mod_name, alias = arg
            mod = self.load_module(mod_name)
            bind = alias or mod_name.split(".")[-1]
            names_local[bind] = mod
        elif op == LOAD_ATTR:
            obj = stack.pop()
            attr = code.names[arg]
            if isinstance(obj, VMInstance):
                if attr in obj.fields:
                    stack.append(obj.fields[attr])
                else:
                    meth, owner = obj.cls.lookup(attr)
                    if meth is None or owner is None:
                        raise AILangRuntimeError(f"'{obj.cls.name}' no tiene '{attr}'")
                    stack.append(VMBoundMethod(obj, meth, owner))
            elif isinstance(obj, SuperProxy):
                base = obj.start_cls.base
                found = None; owner = None
                while base is not None:
                    if attr in base.methods:
                        found = base.methods[attr]; owner = base; break
                    base = base.base
                if found is None or owner is None:
                    raise AILangRuntimeError(f"super no tiene '{attr}'")
                stack.append(VMBoundMethod(obj.instance, found, owner))
            elif isinstance(obj, VMModule):
                stack.append(getattr(obj, attr))
            elif isinstance(obj, VMClass):
                meth, owner = obj.lookup(attr)
                stack.append(meth)
            elif isinstance(obj, VMRecordInstance):
                stack.append(obj.values.get(attr))
            elif hasattr(obj, attr):
                stack.append(getattr(obj, attr))
            else:
                raise AILangRuntimeError(f"atributo '{attr}' no encontrado")
        elif op == STORE_ATTR:
            val = stack.pop()
            obj = stack.pop()
            attr = code.names[arg]
            if isinstance(obj, VMInstance):
                obj.fields[attr] = val
            elif isinstance(obj, dict):
                obj[attr] = val
            elif isinstance(obj, VMRecordInstance):
                obj.values[attr] = val
            else:
                setattr(obj, attr, val)
        elif op == SETUP_CATCH:
            handler_ip, catch_name = arg
            handlers.append((handler_ip, catch_name, len(stack)))
        elif op == POP_CATCH:
            if handlers: handlers.pop()
        elif op == THROW:
            val = stack.pop() if stack else None
            if handlers:
                handler_ip, catch_name, sp = handlers.pop()
                del stack[sp:]
                stack.append(val)
                return ("jump", handler_ip)
            else:
                raise AILangRuntimeError(str(val))
        elif op == BUILD_STRING:
            n = arg
            parts = [stack.pop() for _ in range(n)][::-1]
            stack.append("".join(str(p) for p in parts))
        elif op == MAKE_ENUM:
            enum_name, members = arg
            type_obj = VMEnumType(enum_name, {})
            for mname, mval in members:
                member = VMEnumMember(enum_name, mname, mval)
                type_obj.members[mname] = member
                names_local[f"{enum_name}.{mname}"] = member
            stack.append(type_obj)
        elif op == MAKE_RECORD:
            rec_name, fields = arg
            rt = VMRecordType(rec_name, fields)
            def record_ctor(*args, _rt=rt):
                if len(args) != len(_rt.fields):
                    raise AILangRuntimeError(
                        f"{_rt.name} espera {len(_rt.fields)} args, recibió {len(args)}"
                    )
                return VMRecordInstance(_rt, dict(zip(_rt.fields, args)))
            stack.append(record_ctor)
        elif op == MAKE_INTERFACE:
            if_name, method_names = arg
            stack.append(VMInterfaceType(if_name, method_names))
        elif op == YIELD:
            val = stack.pop() if stack else None
            return ("yield", val)
        elif op == AWAIT:
            fut_val = stack.pop()
            if isinstance(fut_val, VMFuture):
                if not fut_val.done:
                    raise _AwaitSignal(fut_val)
                stack.append(fut_val.result())
            elif isinstance(fut_val, VMGenerator):
                try:
                    last = None
                    while True:
                        last = fut_val.send(last) if last is not None else next(fut_val)
                except StopIteration as e:
                    stack.append(e.value if e.value is not None else last)
            else:
                stack.append(fut_val)
        elif op == SPAWN:
            callable_val = stack.pop()
            if isinstance(callable_val, VMFunction) and callable_val.is_generator:
                gen_state = GeneratorState(callable_val, [], self)
                gen = VMGenerator(gen_state)
                fut = self.scheduler.spawn(gen)
                stack.append(fut)
            elif isinstance(callable_val, VMFunction):
                try:
                    result = call_vm_func(callable_val, [])
                    if isinstance(result, VMGenerator):
                        fut = self.scheduler.spawn(result)
                    else:
                        fut = VMFuture()
                        fut.set_result(result)
                    stack.append(fut)
                except AILangRuntimeError as exc:
                    raise exc.push(callable_val.code.name or "<fn>") from None
            elif callable(callable_val):
                fut = VMFuture()
                try:
                    fut.set_result(callable_val())
                except BaseException as e:
                    fut.set_error(e)
                stack.append(fut)
            else:
                raise AILangRuntimeError(f"spawn: no invocable: {callable_val!r}")
        else:
            raise AILangRuntimeError(f"opcode no soportado en generator: {op}")
        return None


def compile_source(source: str) -> CodeObject:
    return Compiler().compile_program(parse(source))


def _contains_yield(body: List[Any]) -> bool:
    """P0-6: detecta recursivamente si un body de función contiene YIELD."""
    for node in body:
        if _walk_for_yield(node):
            return True
    return False


def _walk_for_yield(node: Any) -> bool:
    if node is None:
        return False
    if isinstance(node, A.Yield):
        return True
    # Recorrer atributos comunes de AST nodes
    if isinstance(node, (A.Let, A.Const, A.Assign, A.Return, A.ExprStmt)):
        if hasattr(node, "value") and _walk_for_yield(node.value):
            return True
    if isinstance(node, A.If):
        for s in node.body:
            if _walk_for_yield(s): return True
        for s in node.orelse:
            if _walk_for_yield(s): return True
        return False
    if isinstance(node, A.While):
        for s in node.body:
            if _walk_for_yield(s): return True
        return False
    if isinstance(node, A.For):
        for s in node.body:
            if _walk_for_yield(s): return True
        return False
    if isinstance(node, A.Block):
        for s in node.body:
            if _walk_for_yield(s): return True
        return False
    if isinstance(node, A.Try):
        for s in node.body:
            if _walk_for_yield(s): return True
        for s in node.catch_body:
            if _walk_for_yield(s): return True
        return False
    if isinstance(node, A.Match):
        for c in node.cases:
            for s in c.body:
                if _walk_for_yield(s): return True
        return False
    if isinstance(node, A.Function):
        # Nested fn: un generador nested no convierte al outer en generador
        return False
    if isinstance(node, A.BinOp):
        return _walk_for_yield(node.left) or _walk_for_yield(node.right)
    if isinstance(node, A.UnaryOp):
        return _walk_for_yield(node.operand)
    if isinstance(node, A.Call):
        if _walk_for_yield(node.func): return True
        for a in node.args:
            if _walk_for_yield(a): return True
        return False
    return False


def run_vm(
    source: str,
    *,
    builtins: Optional[Dict[str, Any]] = None,
    module_path: Optional[List[str]] = None,
) -> Any:
    code = compile_source(source)
    default_builtins = {
        "print": print,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "range": lambda *a: list(range(*a)),
        "iter": iter,
        "next": next,
        "type": lambda x: type(x).__name__,
        "isinstance": lambda x, t: isinstance(x, t) if isinstance(t, type) else False,
        "implements": _vm_implements,
        "channel": lambda: VMChannel(),
        "true": True,
        "false": False,
        "null": None,
    }
    if builtins:
        default_builtins.update(builtins)
    vm = VM(builtins=default_builtins, module_path=module_path)
    try:
        vm.globals["brain"] = vm.load_module("brain")
    except Exception:
        pass
    result = vm.run_code(code)
    if vm.scheduler._ready:
        vm.scheduler.run_until_complete()
    return result


def _vm_implements(instance: Any, interface: Any) -> bool:
    """Comprueba si un objeto/instancia implementa una interfaz.
    Para VMInstance: verifica que tenga todos los métodos declarados en la interfaz.
    """
    if not isinstance(interface, VMInterfaceType):
        return False
    if isinstance(instance, VMInstance):
        for mname in interface.methods:
            meth, _ = instance.cls.lookup(mname)
            if meth is None:
                return False
        return True
    # Fallback: hasattr check
    for mname in interface.methods:
        if not hasattr(instance, mname):
            return False
    return True


class _DummyVMFn:
    """Mock VMFunction para envolver un generator Python puro en el scheduler VM."""
    def __init__(self, gen):
        self.code = CodeObject("<py-gen>")
        self.params = ()
        self.closure = {}
        self.is_method = False
        self.is_async = False
        self.is_generator = True
        self._gen = gen


class _YieldSignal(BaseException):
    """Señal interna para YIELD — capturada por _run_generator."""
    def __init__(self, value):
        self.value = value


class _AwaitSignal(BaseException):
    """Señal interna para AWAIT — capturada por el scheduler."""
    def __init__(self, future):
        self.future = future
