"""Micro-benchmarks de AILang (P2-14).

Suite reproducible de benchmarks que cubre las categorías del prompt maestro
(FASE 30): arithmetic, loops, function calls, closures, classes, strings,
lists, dicts, exceptions, modules, JSON, concurrency, startup, compile time.

Compara Interpreter vs VM. Genera output JSON listo para commit en
`benchmarks/results/<date>.json`.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ailang.lang.interpreter import run_source
from ailang.lang.vm import run_vm, compile_source


# --- Categorías de benchmarks (FASE 30) ------------------------------------

CASES: Dict[str, str] = {
    "arith_sum_1k": "let s = 0\nlet i = 0\nwhile i < 1000 { i = i + 1\n s = s + i }\ns",
    "arith_multiply_100": "let p = 1\nlet i = 0\nwhile i < 100 { i = i + 1\n p = p * 2 }\np",

    "loop_nested_100x100": "let s = 0\nlet i = 0\nwhile i < 100 {\nlet j = 0\nwhile j < 100 {\nj = j + 1\ns = s + 1\n}\ni = i + 1\n}\ns",

    "fn_recursive_fib_10": "fn fib(n) {\nif n < 2 { return n }\nreturn fib(n - 1) + fib(n - 2)\n}\nfib(10)",
    "fn_call_500": "fn add(a,b){ return a+b }\nlet s=0\nlet i=0\nwhile i<500 { i=i+1\n s=add(s,i) }\ns",

    "closures_counter": "fn make_counter() {\nlet count = 0\nfn inc() {\ncount = count + 1\nreturn count\n}\nreturn inc\n}\nlet c = make_counter()\nlet i = 0\nwhile i < 100 {\nc()\ni = i + 1\n}\nc()",

    "classes_dispatch_100": "class Animal {\nfn init(name) { self.name = name }\nfn speak() { return \"generic\" }\n}\nclass Dog extends Animal {\nfn speak() { return \"woof\" }\n}\nlet d = Dog(\"Rex\")\nlet s = \"\"\nlet i = 0\nwhile i < 100 {\ns = d.speak()\ni = i + 1\n}\ns",

    "string_concat_100": "let s = \"\"\nlet i = 0\nwhile i < 100 {\ns = s + \"x\"\ni = i + 1\n}\ns",

    "list_build_100": "let xs = []\nlet i = 0\nwhile i < 100 {\nxs = [i]\ni = i + 1\n}\nxs",

    "dict_build_10": "let d = {}\nlet i = 0\nwhile i < 10 {\nd = {i: i * 2}\ni = i + 1\n}\nd",

    "exceptions_throw_catch_50": "let i = 0\nlet caught = 0\nwhile i < 50 {\ntry {\nthrow \"test\"\n} catch e {\ncaught = caught + 1\n}\ni = i + 1\n}\ncaught",

    "modules_import_math": "import math\nmath.sqrt(16)",
    "modules_import_json": "import json\njson.loads(\"[1,2,3]\")",

    "json_roundtrip": "import json\njson.loads(json.dumps([1, 2, 3]))",

    "generators_yield_sum": "fn gen() {\nyield 1\nyield 2\nyield 3\nyield 4\nyield 5\n}\nlet s = 0\nfor v in gen() { s = s + v }\ns",

    "interpolation_50": "let s = \"\"\nlet i = 0\nwhile i < 50 {\ns = \"val=${i}\"\ni = i + 1\n}\ns",

    "channel_send_recv_50": "let c = channel()\nlet i = 0\nwhile i < 50 {\nc.send(i)\nc.recv()\ni = i + 1\n}\ni",
}


# --- Measurement -----------------------------------------------------------

def bench_once(source: str, use_vm: bool = False) -> float:
    """Ejecuta una vez y retorna el tiempo en segundos."""
    t0 = time.perf_counter()
    if use_vm:
        run_vm(source)
    else:
        run_source(source)
    return time.perf_counter() - t0


def bench_case(source: str, rounds: int = 5) -> Dict[str, Any]:
    """Ejecuta un caso `rounds` veces y retorna estadísticas."""
    times_interp = [bench_once(source, use_vm=False) for _ in range(rounds)]
    try:
        times_vm = [bench_once(source, use_vm=True) for _ in range(rounds)]
        vm_ok = True
    except Exception as e:
        times_vm = []
        vm_ok = False
        vm_error = str(e)

    result: Dict[str, Any] = {
        "interp_mean_s": statistics.mean(times_interp),
        "interp_median_s": statistics.median(times_interp),
        "interp_min_s": min(times_interp),
        "interp_max_s": max(times_interp),
        "interp_stdev_s": statistics.stdev(times_interp) if len(times_interp) > 1 else 0,
    }
    if vm_ok:
        result.update({
            "vm_mean_s": statistics.mean(times_vm),
            "vm_median_s": statistics.median(times_vm),
            "vm_min_s": min(times_vm),
            "vm_max_s": max(times_vm),
            "vm_stdev_s": statistics.stdev(times_vm) if len(times_vm) > 1 else 0,
            "vm_supported": True,
        })
        mean_i = result["interp_mean_s"]
        mean_v = result["vm_mean_s"]
        if mean_v > 0:
            result["speedup_vm_vs_interp"] = mean_i / mean_v
    else:
        result.update({
            "vm_supported": False,
            "vm_error": vm_error,
        })
    return result


def run_bench(rounds: int = 5, cases: List[str] = None) -> Dict[str, Any]:
    """Ejecuta todos los benchmarks (o solo los listados en `cases`).

    Retorna un dict listo para serializar a JSON.
    """
    selected = cases or list(CASES.keys())
    results: Dict[str, Any] = {}
    for name in selected:
        if name not in CASES:
            results[name] = {"error": f"caso desconocido: {name}"}
            continue
        results[name] = bench_case(CASES[name], rounds=rounds)

    # Metadatos del run
    from ailang.versions import (
        __version__, LANGUAGE_VERSION, RUNTIME_VERSION, BYTECODE_VERSION, IR_VERSION
    )
    output = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "language_version": LANGUAGE_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "bytecode_version": BYTECODE_VERSION,
            "ir_version": IR_VERSION,
            "package_version": __version__,
            "python_version": sys.version,
            "platform": sys.platform,
            "rounds": rounds,
        },
        "results": results,
    }

    # Resumen ejecutivo
    summary = {"vm_faster_cases": 0, "interp_faster_cases": 0, "vm_unsupported": 0}
    for name, r in results.items():
        if not r.get("vm_supported", False):
            summary["vm_unsupported"] += 1
        elif r.get("speedup_vm_vs_interp", 1.0) > 1.0:
            summary["vm_faster_cases"] += 1
        else:
            summary["interp_faster_cases"] += 1
    output["summary"] = summary
    return output


def bench_compile_time(source: str, rounds: int = 10) -> Dict[str, float]:
    """Mide solo el tiempo de compilación (parse + AST → bytecode)."""
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        compile_source(source)
        times.append(time.perf_counter() - t0)
    return {
        "compile_mean_s": statistics.mean(times),
        "compile_median_s": statistics.median(times),
        "compile_min_s": min(times),
        "compile_max_s": max(times),
    }


def save_results(results: Dict[str, Any], out_dir: str = "benchmarks/results") -> str:
    """Guarda resultados en JSON. Crea el dir si no existe. Retorna el path."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = out_path / f"bench-{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    return str(filename)


def print_summary(results: Dict[str, Any]) -> None:
    """Imprime un resumen tabular de los resultados."""
    print("=" * 78)
    print(f"Benchmark suite — AILang {results['metadata']['package_version']}")
    print(f"Python: {results['metadata']['python_version'].split()[0]}")
    print(f"Platform: {results['metadata']['platform']}")
    print(f"Rounds: {results['metadata']['rounds']}")
    print("=" * 78)
    print(f"{'Case':<28} {'Interp (ms)':>12} {'VM (ms)':>12} {'Speedup':>10}")
    print("-" * 78)
    for name, r in results["results"].items():
        interp_ms = r.get("interp_mean_s", 0) * 1000
        if r.get("vm_supported", False):
            vm_ms = r.get("vm_mean_s", 0) * 1000
            speedup = r.get("speedup_vm_vs_interp", 0)
            speedup_str = f"{speedup:.2f}x" if speedup > 0 else "N/A"
        else:
            vm_ms = float("nan")
            speedup_str = f"unsupported"
        print(f"{name:<28} {interp_ms:>12.3f} {vm_ms:>12.3f} {speedup_str:>10}")
    print("-" * 78)
    s = results["summary"]
    print(f"Summary: VM faster in {s['vm_faster_cases']} cases, "
          f"interp faster in {s['interp_faster_cases']} cases, "
          f"VM unsupported in {s['vm_unsupported']} cases.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="AILang benchmark suite")
    p.add_argument("--rounds", type=int, default=5, help="Rounds per case (default: 5)")
    p.add_argument("--save", action="store_true", help="Save results to benchmarks/results/")
    p.add_argument("--cases", nargs="*", help="Specific cases to run (default: all)")
    args = p.parse_args()

    results = run_bench(rounds=args.rounds, cases=args.cases)
    print_summary(results)

    if args.save:
        path = save_results(results)
        print(f"\nResults saved to: {path}")
