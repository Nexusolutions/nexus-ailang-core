import sys as _sys
import os as _os

from ailang.versions import RUNTIME_ID

def argv():
    return list(_sys.argv)

def exit(code=0):
    raise SystemExit(int(code))

def getenv(name, default=None):
    return _os.environ.get(str(name), default)

def platform():
    return _sys.platform

def version():
    """Versión del runtime de AILang, leída desde ailang.versions (FASE 1)."""
    return RUNTIME_ID

def stderr_write(msg):
    _sys.stderr.write(str(msg))
    return None
