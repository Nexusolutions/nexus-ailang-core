"""Bytecode VM apilada para AILang (v8.3) — núcleo + class/import + try/catch."""
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
) = range(23)


@dataclass
class CodeObject:
    name: str
    bytecode: List[Tuple[int, Any]] = field(default_factory=list)
    constants: List[Any] = field(default_factory=list)
    names: List[str] = field(default_factory=list)
    arity: int = 0


@dataclass
class VMFunction:
    code: CodeObject
    params: Tuple[str, ...]
    closure: Dict[str, Any]
    is_method: bool = False


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
            self.compile_expr(node.iter)
            self.emit(DEFINE_NAME, self.name("__it"))
            self.emit(LOAD_CONST, self.const(0))
            self.emit(DEFINE_NAME, self.name("__i"))
            breaks, continues = [], []
            self._loop_stack.append((breaks, continues))
            start = len(self.code.bytecode)
            # condición: __i < len(__it)
            self.emit(LOAD_NAME, self.name("__i"))
            self.emit(LOAD_NAME, self.name("len"))
            self.emit(LOAD_NAME, self.name("__it"))
            self.emit(CALL, 1)
            self.emit(BINARY_OP, "<")
            j_exit = self.emit(JUMP_IF_FALSE, 0)
            self.emit(LOAD_NAME, self.name("__it"))
            self.emit(LOAD_NAME, self.name("__i"))
            self.emit(GET_ITEM)
            self.emit(DEFINE_NAME, self.name(node.target))
            for s in node.body:
                self.compile_stmt(s)
            cont_target = len(self.code.bytecode)
            self.emit(LOAD_NAME, self.name("__i"))
            self.emit(LOAD_CONST, self.const(1))
            self.emit(BINARY_OP, "+")
            self.emit(STORE_NAME, self.name("__i"))
            self.emit(JUMP, start)
            exit_ip = len(self.code.bytecode)
            self.code.bytecode[j_exit] = (JUMP_IF_FALSE, exit_ip)
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

        def resolve_name(n: str) -> Any:
            if n in names_local:
                return names_local[n]
            if n in self.globals:
                return self.globals[n]
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
                store_name(code.names[arg], stack.pop())
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
                        stack.append(call_vm_func(fn, args))
                    elif callable(fn):
                        stack.append(fn(*args))
                    else:
                        raise AILangRuntimeError(f"no invocable: {fn!r}")
                except AILangRuntimeError as exc:
                    if handlers:
                        handler_ip, catch_name, sp = handlers.pop()
                        del stack[sp:]
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
                clos = dict(self.globals)
                clos.update(names_local)
                stack.append(VMFunction(cobj, params, clos, is_method=is_method))
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
                    meth, owner = obj.lookup(attr)
                    stack.append(meth)
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
            else:
                raise AILangRuntimeError(f"opcode desconocido {op}")

        if capture_locals:
            return names_local
        return stack[-1] if stack else None


def compile_source(source: str) -> CodeObject:
    return Compiler().compile_program(parse(source))


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
        "true": True,
        "false": False,
        "null": None,
    }
    if builtins:
        default_builtins.update(builtins)
    vm = VM(builtins=default_builtins, module_path=module_path)
    # Gramática unificada: brain siempre disponible si el módulo existe
    try:
        vm.globals["brain"] = vm.load_module("brain")
    except Exception:
        pass
    return vm.run_code(code)
