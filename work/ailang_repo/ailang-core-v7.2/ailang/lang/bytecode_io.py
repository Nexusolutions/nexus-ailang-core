"""Serialización de bytecode AILang (.ailc).

AUD-006/007: Ahora preserva is_generator y registra builtins faltantes
(iter, next, type, isinstance, implements, channel).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ailang.lang.vm import CodeObject, compile_source, VM, run_vm


def code_to_dict(code: CodeObject) -> dict:
    return {
        "name": code.name,
        "arity": code.arity,
        "names": list(code.names),
        "constants": [_const(c) for c in code.constants],
        "bytecode": [[op, _arg(a)] for op, a in code.bytecode],
        "is_generator": getattr(code, "is_generator", False),  # AUD-006
    }


def _const(c: Any) -> Any:
    if isinstance(c, CodeObject):
        return {"__code__": code_to_dict(c)}
    if isinstance(c, (int, float, str, bool)) or c is None:
        return c
    if isinstance(c, (list, tuple)):
        return list(c)
    return {"__repr__": repr(c)}


def _arg(a: Any) -> Any:
    if isinstance(a, tuple):
        return list(a)
    return a


def dict_to_code(d: dict) -> CodeObject:
    consts = []
    for c in d["constants"]:
        if isinstance(c, dict) and "__code__" in c:
            consts.append(dict_to_code(c["__code__"]))
        else:
            consts.append(c)
    bc = []
    for op, arg in d["bytecode"]:
        if isinstance(arg, list):
            arg = tuple(arg)
        bc.append((op, arg))
    code = CodeObject(d["name"], bc, consts, list(d["names"]), d.get("arity", 0))
    # AUD-006: Restore is_generator flag
    code.is_generator = d.get("is_generator", False)
    return code


def save_bytecode(source: str, path: str) -> Path:
    code = compile_source(source)
    p = Path(path)
    p.write_text(json.dumps(code_to_dict(code), indent=2), encoding="utf-8")
    return p


def load_and_run(path: str) -> Any:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    code = dict_to_code(d)
    # AUD-007: Register ALL builtins that run_vm uses, not just a subset
    vm = VM(builtins={
        "print": print, "len": len, "str": str, "int": int, "float": float,
        "range": lambda *a: list(range(*a)),
        "iter": iter, "next": next,  # AUD-007: for-loops need these
        "type": lambda x: type(x).__name__,
        "isinstance": lambda x, t: isinstance(x, t) if isinstance(t, type) else False,
        "implements": lambda *a: False,  # stub
        "channel": lambda: None,  # stub
        "true": True, "false": False, "null": None,
    })
    try:
        vm.globals["brain"] = vm.load_module("brain")
    except Exception:
        pass
    return vm.run_code(code)
