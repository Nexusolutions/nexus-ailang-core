"""Stdlib `time` — operaciones de tiempo con capability enforcement (P3-9b).

  now        → io (clock reading; no requiere capability fuerte)
  sleep      → process.spawn (afecta scheduling; requiere capability)
  format_ts  → pure
  monotonic  → io
"""
import time as _time
from datetime import datetime, timezone

from ailang.runtime.capabilities import require

def now():
    """Timestamp actual. Sin capability (lectura de reloj)."""
    return _time.time()

def sleep(seconds):
    """Duerme el hilo. Requiere `process.spawn` (afecta scheduling)."""
    require("process.spawn", op_desc=f"time.sleep({seconds})")
    _time.sleep(float(seconds))
    return None

def format_ts(ts=None, fmt="%Y-%m-%d %H:%M:%S"):
    """Formatea timestamp. Sin capability (puro)."""
    if ts is None:
        ts = _time.time()
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(str(fmt))

def monotonic():
    """Reloj monotónico. Sin capability."""
    return _time.monotonic()
