"""Micro-benchmarks de AILang."""
from __future__ import annotations
import time
from typing import Any, Dict, List

from ailang.lang.interpreter import run_source
from ailang.lang.vm import run_vm


CASES = {
    "arith": "let s = 0\nlet i = 0\nwhile i < 1000 { i = i + 1\n s = s + i }\ns",
    "fn": "fn add(a,b){ return a+b }\nlet s=0\nlet i=0\nwhile i<500 { i=i+1\n s=add(s,i) }\ns",
    "list": "let xs = [1,2,3,4,5]\nlet s=0\nfor x in xs { s = s + x }\ns",
}


def bench_once(source: str, use_vm: bool = False) -> float:
    t0 = time.perf_counter()
    if use_vm:
        run_vm(source)
    else:
        run_source(source)
    return time.perf_counter() - t0


def run_bench(rounds: int = 5) -> Dict[str, Any]:
    results = {}
    for name, src in CASES.items():
        times_ast = [bench_once(src, False) for _ in range(rounds)]
        try:
            times_vm = [bench_once(src, True) for _ in range(rounds)]
        except Exception as e:
            times_vm = [float("nan")]
        results[name] = {
            "ast_mean_s": sum(times_ast) / len(times_ast),
            "vm_mean_s": sum(x for x in times_vm if x == x) / max(1, len([x for x in times_vm if x == x])),
        }
    return results
