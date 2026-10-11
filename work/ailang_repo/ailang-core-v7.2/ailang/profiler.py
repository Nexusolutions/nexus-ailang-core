"""Profiler simple de statements AILang."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict

from ailang.lang.parser import parse
from ailang.lang.interpreter import Interpreter


def profile_source(source: str) -> Dict[str, Any]:
    program = parse(source)
    interp = Interpreter()
    counts: Dict[str, int] = defaultdict(int)
    times: Dict[str, float] = defaultdict(float)
    t0 = time.perf_counter()
    result = None
    for stmt in program.body:
        name = type(stmt).__name__
        s = time.perf_counter()
        result = interp.exec_stmt(stmt, interp.global_env)
        times[name] += time.perf_counter() - s
        counts[name] += 1
    total = time.perf_counter() - t0
    return {
        "result": result,
        "total_s": total,
        "counts": dict(counts),
        "times_s": dict(times),
    }
