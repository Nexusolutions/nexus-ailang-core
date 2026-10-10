"""Stdlib mínima AILang: módulos builtin cargables con `import`."""
from __future__ import annotations

from typing import Any, Dict

from ailang.lang.stdlib import io as _io
from ailang.lang.stdlib import json as _json
from ailang.lang.stdlib import listops as _listops
from ailang.lang.stdlib import math as _math
from ailang.lang.stdlib import brain as _brain
from ailang.lang.stdlib import strings as _strings
from ailang.lang.stdlib import time_mod as _time
from ailang.lang.stdlib import sys_mod as _sys
from ailang.lang.stdlib import test_mod as _test
from ailang.lang.stdlib import path_mod as _path
from ailang.lang.stdlib import random_mod as _random
from ailang.lang.stdlib import re_mod as _re
from ailang.lang.stdlib import http_mod as _http


class Module:
    """Namespace de módulo (atributos = funciones/valores)."""

    def __init__(self, name: str, exports: Dict[str, Any]):
        self.__name__ = name
        self._exports = dict(exports)

    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"):
            return object.__getattribute__(self, item)
        try:
            return self._exports[item]
        except KeyError as e:
            raise AttributeError(f"módulo '{self.__name__}' no tiene '{item}'") from e

    def __getitem__(self, item: str) -> Any:
        return self._exports[item]

    def keys(self):
        return self._exports.keys()

    def __repr__(self) -> str:
        return f"<module {self.__name__}>"


def builtin_modules() -> Dict[str, Module]:
    return {
        "io": Module("io", {
            "read_text": _io.read_text,
            "write_text": _io.write_text,
            "exists": _io.exists,
            "lines": _io.lines,
        }),
        "json": Module("json", {
            "loads": _json.loads,
            "dumps": _json.dumps,
        }),
        "listops": Module("listops", {
            "map": _listops.map_,
            "filter": _listops.filter_,
            "reduce": _listops.reduce_,
            "sum": _listops.sum_,
            "sorted": _listops.sorted_,
        }),
        "http": Module("http", {
            "get": _http.get, "post": _http.post, "json_get": _http.json_get,
        }),
        "path": Module("path", {
            "join": _path.join, "exists": _path.exists, "is_file": _path.is_file,
            "is_dir": _path.is_dir, "name": _path.name, "parent": _path.parent,
            "mkdir": _path.mkdir, "listdir": _path.listdir, "cwd": _path.cwd, "abs": _path.abs,
        }),
        "random": Module("random", {
            "seed": _random.seed, "random": _random.random, "randint": _random.randint,
            "choice": _random.choice, "shuffle": _random.shuffle, "sample": _random.sample,
        }),
        "re": Module("re", {
            "search": _re.search, "match": _re.match, "findall": _re.findall,
            "sub": _re.sub, "split": _re.split,
        }),
        "strings": Module("strings", {
            "length": _strings.length,
            "upper": _strings.upper,
            "lower": _strings.lower,
            "strip": _strings.strip,
            "split": _strings.split,
            "join": _strings.join,
            "replace": _strings.replace,
            "startswith": _strings.startswith,
            "endswith": _strings.endswith,
            "contains": _strings.contains,
            "format": _strings.format,
        }),
        "time": Module("time", {
            "now": _time.now,
            "sleep": _time.sleep,
            "format_ts": _time.format_ts,
            "monotonic": _time.monotonic,
        }),
        "sys": Module("sys", {
            "argv": _sys.argv,
            "exit": _sys.exit,
            "getenv": _sys.getenv,
            "platform": _sys.platform,
            "version": _sys.version,
            "stderr_write": _sys.stderr_write,
        }),
        "test": Module("test", {
            "assert_true": _test.assert_true,
            "assert_eq": _test.assert_eq,
            "assert_raises": _test.assert_raises,
            "summary": _test.summary,
            "reset": _test.reset,
        }),
        "brain": Module("brain", {
            "ingest": _brain.ingest,
            "query": _brain.query,
            "think": _brain.think,
            "graph": _brain.graph,
            "bind_engine": _brain.bind_engine,
        }),
        "math": Module("math", {
            "abs": _math.abs_,
            "min": _math.min_,
            "max": _math.max_,
            "sqrt": _math.sqrt_,
            "pow": _math.pow_,
            "floor": _math.floor_,
            "ceil": _math.ceil_,
            "pi": _math.pi,
            "e": _math.e,
        }),
    }
