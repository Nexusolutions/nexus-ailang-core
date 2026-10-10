"""Serialización de bytecode AILang (.ailc)."""
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
    return CodeObject(d["name"], bc, consts, list(d["names"]), d.get("arity", 0))


def save_bytecode(source: str, path: str) -> Path:
    code = compile_source(source)
    p = Path(path)
    p.write_text(json.dumps(code_to_dict(code), indent=2), encoding="utf-8")
    return p


def load_and_run(path: str) -> Any:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    code = dict_to_code(d)
    vm = VM(builtins={
        "print": print, "len": len, "str": str, "int": int, "float": float,
        "range": lambda *a: list(range(*a)), "true": True, "false": False, "null": None,
    })
    try:
        vm.globals["brain"] = vm.load_module("brain")
    except Exception:
        pass
    return vm.run_code(code)
