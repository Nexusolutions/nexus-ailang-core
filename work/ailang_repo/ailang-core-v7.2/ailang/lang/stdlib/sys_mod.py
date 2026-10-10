"""Stdlib `sys` — info del sistema con capability enforcement (P3-9b).

  argv         → process.spawn  (leer argumentos del proceso)
  exit         → process.spawn  (terminar proceso)
  getenv       → system.env
  platform     → pure (sin capability)
  version      → pure
  stderr_write → io (no requiere capability)
"""
import sys as _sys
import os as _os

from ailang.versions import RUNTIME_ID
from ailang.runtime.capabilities import require

def argv():
    """Retorna argv del proceso. Requiere capability `process.spawn`."""
    require("process.spawn", op_desc="sys.argv()")
    return list(_sys.argv)

def exit(code=0):
    """Termina el proceso. Requiere capability `process.spawn`."""
    require("process.spawn", op_desc=f"sys.exit({code})")
    raise SystemExit(int(code))

def getenv(name, default=None):
    """Lee variable de entorno. Requiere capability `system.env`."""
    require("system.env", op_desc=f"sys.getenv({name!r})")
    return _os.environ.get(str(name), default)

def platform():
    """Retorna plataforma. Sin capability (información pública)."""
    return _sys.platform

def version():
    """Versión del runtime de AILang, leída desde ailang.versions (FASE 1)."""
    return RUNTIME_ID

def stderr_write(msg):
    """Escribe a stderr. Sin capability (output, no side-effect en fs)."""
    _sys.stderr.write(str(msg))
    return None
