"""python -m ailang — CLI principal.

La versión vive en ailang.versions (FASE 1 del prompt maestro).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ailang.versions import __version__


def main(argv=None):
    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] == "doctor":
        from ailang.doctor import run_doctor
        return run_doctor()
    if raw and raw[0] == "check":
        # P3-1b: análisis sin ejecución. Reporta capabilities y effects requeridos.
        from ailang.runtime.air_runtime import analyze_source
        import json as _json
        from pathlib import Path as P
        if len(raw) < 2:
            print("Uso: ailang check <file.ailang>", file=sys.stderr)
            return 1
        src = P(raw[1]).read_text(encoding="utf-8")
        info = analyze_source(src)
        print(_json.dumps(info, indent=2, default=str))
        return 0
    if raw and raw[0] == "pkg":
        from ailang.pkg import main as pkg_main
        return pkg_main(raw[1:])
    if raw and raw[0] == "fmt":
        from ailang.fmt import format_file
        for f in raw[1:]:
            print(format_file(f), end="")
        return 0
    if raw and raw[0] == "lint":
        from ailang.lint import lint_source
        from pathlib import Path as P
        rc = 0
        for f in raw[1:]:
            for i in lint_source(P(f).read_text(encoding="utf-8")):
                print(f"{f}:{i}")
                if i.level == "error":
                    rc = 1
        return rc
    if raw and raw[0] == "profile":
        from ailang.profiler import profile_source
        import json
        from pathlib import Path as P
        print(json.dumps(profile_source(P(raw[1]).read_text(encoding="utf-8")), indent=2, default=str))
        return 0
    if raw and raw[0] == "compile":
        from ailang.lang.bytecode_io import save_bytecode
        from pathlib import Path as P
        out = raw[2] if len(raw) > 2 else str(P(raw[1]).with_suffix(".ailc"))
        save_bytecode(P(raw[1]).read_text(encoding="utf-8"), out)
        print(out)
        return 0
    if raw and raw[0] == "runbc":
        from ailang.lang.bytecode_io import load_and_run
        r = load_and_run(raw[1])
        if r is not None:
            print(repr(r))
        return 0
    if raw and raw[0] == "coverage":
        from ailang.coverage_tool import coverage_source
        import json
        from pathlib import Path as P
        print(json.dumps(coverage_source(P(raw[1]).read_text(encoding="utf-8")), indent=2, default=str))
        return 0
    if raw and raw[0] == "watch":
        from ailang.watch import watch_file
        watch_file(raw[1], once=("--once" in raw))
        return 0
    if raw and raw[0] == "project":
        from ailang.project import init_project, run_project, load_project
        import json
        if len(raw) > 1 and raw[1] == "init":
            name = raw[2] if len(raw) > 2 else "app"
            print(init_project(".", name))
            return 0
        if len(raw) > 1 and raw[1] == "run":
            r = run_project(".")
            if r is not None:
                print(repr(r))
            return 0
        print(json.dumps(load_project("."), indent=2))
        return 0

    if raw and raw[0] == "bench":
        from ailang.bench import run_bench, print_summary, save_results
        # P2-14: benchmarks reproducibles con output tabular + opcional save
        rounds = 5
        cases = None
        save = False
        for arg in raw[1:]:
            if arg.startswith("--rounds="):
                rounds = int(arg.split("=", 1)[1])
            elif arg == "--save":
                save = True
            else:
                if cases is None:
                    cases = []
                cases.append(arg)
        results = run_bench(rounds=rounds, cases=cases)
        print_summary(results)
        if save:
            path = save_results(results)
            print(f"\nResults saved to: {path}")
        return 0
    if raw and raw[0] == "docgen":
        from ailang.docgen import docgen_file
        out = raw[2] if len(raw) > 2 else None
        print(docgen_file(raw[1], out))
        return 0

    p = argparse.ArgumentParser(prog="python -m ailang",
                                description=f"AILang {__version__}")
    p.add_argument("file", nargs="?", help="Archivo .ailang a ejecutar")
    p.add_argument("-c", "--cmd", help="Ejecutar programa en línea")
    p.add_argument("--repl", action="store_true")
    p.add_argument("--vm", action="store_true")
    p.add_argument("--air", action="store_true",
                   help="Ejecutar via AIR (verifica capabilities + ejecuta via VM)")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--test", nargs="*", metavar="PATH")
    p.add_argument("--version", action="store_true")
    p.add_argument("--lsp", action="store_true", help="Iniciar language server (stdio)")
    p.add_argument("--debug", metavar="FILE", help="Ejecutar con debugger (breakpoints vía --bp)")
    p.add_argument("--bp", action="append", type=int, default=[], help="Breakpoint línea (repetible)")
    p.add_argument("--agent", metavar="GOAL", help="Ejecutar agente demo con goal")
    p.add_argument("--dap", action="store_true", help="Debug Adapter Protocol (stdio)")
    p.add_argument("--allow", action="append", default=[], metavar="CAP",
                   help="Conceder capability (repetible, ej: filesystem.read)")
    p.add_argument("--deny", action="append", default=[], metavar="CAP",
                   help="Denegar capability explícitamente (repetible)")
    args = p.parse_args(argv)

    # P3-9: configurar capability context
    from ailang.runtime.capabilities import parse_cli_capabilities, set_default_context
    set_default_context(parse_cli_capabilities(args.allow, args.deny))

    if args.version:
        print(f"AILang {__version__}")
        return 0

    if args.lsp:
        from ailang.lsp import main as lsp_main
        lsp_main()
        return 0

    if args.dap:
        from ailang.dap import main as dap_main
        dap_main()
        return 0

    if args.agent is not None:
        from ailang.agent_runtime import run_agent
        out = run_agent(
            args.agent,
            [
                {"kind": "observe", "name": "input", "args": {"value": args.agent}},
                {"kind": "think", "name": "reason", "args": {"text": args.agent}},
                {"kind": "decide", "name": "out", "args": {"choice": "done"}},
            ],
        )
        import json
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.debug:
        from ailang.debugger import debug_source
        src = Path(args.debug).read_text(encoding="utf-8")
        import json
        print(json.dumps(debug_source(src, args.bp), indent=2, default=str))
        return 0

    if args.test is not None:
        return _run_tests(args.test, use_vm=args.vm)

    from ailang.lang.interpreter import run_source, create_repl
    kw = {"use_vm": args.vm, "typecheck_strict": True if args.strict else None}

    # P3-1b/S1: --air flag ejecuta via AIR (verificación capabilities + VM)
    if args.air:
        from ailang.runtime.air_interpreter import run_air
        if args.cmd:
            try:
                r = run_air(args.cmd, use_vm=True)
                if r is not None:
                    print(repr(r))
            except Exception as e:
                print(e, file=sys.stderr)
                return 1
            return 0
        if args.file:
            src = Path(args.file).read_text(encoding="utf-8")
            try:
                r = run_air(src, use_vm=True)
                if r is not None:
                    print(repr(r))
            except Exception as e:
                print(e, file=sys.stderr)
                return 1
            return 0

    if args.cmd:
        try:
            r = run_source(args.cmd, **kw)
            if r is not None:
                print(repr(r))
        except Exception as e:
            print(e, file=sys.stderr)
            return 1
        return 0

    if args.file:
        src = Path(args.file).read_text(encoding="utf-8")
        try:
            r = run_source(src, **kw)
            if r is not None:
                print(repr(r))
        except Exception as e:
            print(e, file=sys.stderr)
            return 1
        return 0

    create_repl()
    return 0


def _run_tests(paths, use_vm=False):
    from ailang.lang.interpreter import run_source
    from ailang.lang.stdlib import test_mod
    if not paths:
        import pytest
        root = Path(__file__).resolve().parents[1]
        return pytest.main(["-q", str(root / "tests")])
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("**/*.ailang")))
        elif path.is_file():
            files.append(path)
    total_pass = total_fail = 0
    for f in files:
        test_mod.reset()
        print(f"--- {f}")
        try:
            run_source(f.read_text(encoding="utf-8"), use_vm=use_vm)
            s = test_mod.summary()
            total_pass += s["passed"]
            total_fail += s["failed"]
            print(f"  passed={s['passed']} failed={s['failed']}")
        except Exception as e:
            total_fail += 1
            print(f"  ERROR: {e}")
    print(f"TOTAL passed={total_pass} failed={total_fail}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
