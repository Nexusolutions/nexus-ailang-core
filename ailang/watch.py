"""Watch mode: re-ejecuta un archivo al cambiar."""
from __future__ import annotations
import time
from pathlib import Path


def watch_file(path: str, *, use_vm: bool = False, interval: float = 0.5, once: bool = False) -> None:
    from ailang.lang.interpreter import run_source
    p = Path(path)
    last = None
    while True:
        try:
            mtime = p.stat().st_mtime
            if mtime != last:
                last = mtime
                print(f"[watch] running {p}...")
                try:
                    r = run_source(p.read_text(encoding="utf-8"), use_vm=use_vm)
                    if r is not None:
                        print(repr(r))
                except Exception as e:
                    print(f"[watch] error: {e}")
                if once:
                    return
            time.sleep(interval)
        except KeyboardInterrupt:
            print("[watch] stop")
            return
