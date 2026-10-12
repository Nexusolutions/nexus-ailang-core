#!/usr/bin/env python3
"""Verifica que format_ast es idempotente en todos los archivos .ailang de examples/.

Uso:
    python scripts/check_format_idempotency.py

Sale con código 0 si todo OK, 1 si algún archivo no es idempotente.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    try:
        from ailang.fmt import format_ast
    except ImportError as e:
        print(f"ERROR: no se pudo importar ailang.fmt: {e}", file=sys.stderr)
        return 1

    examples_dir = Path("examples")
    if not examples_dir.is_dir():
        print("examples/ directory not found — nothing to check")
        return 0

    failures = []
    for f in examples_dir.glob("*.ailang"):
        try:
            src = f.read_text(encoding="utf-8")
            out1 = format_ast(src)
            out2 = format_ast(out1)
            if out1 != out2:
                failures.append((str(f), "format_ast no idempotente"))
        except Exception as e:
            failures.append((str(f), f"exception: {e}"))

    if failures:
        print("FAIL: format_ast idempotency check:", file=sys.stderr)
        for name, msg in failures:
            print(f"  - {name}: {msg}", file=sys.stderr)
        return 1

    print("format_ast idempotency: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
