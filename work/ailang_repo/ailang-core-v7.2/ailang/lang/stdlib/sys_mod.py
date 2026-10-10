import sys as _sys
import os as _os

def argv():
    return list(_sys.argv)

def exit(code=0):
    raise SystemExit(int(code))

def getenv(name, default=None):
    return _os.environ.get(str(name), default)

def platform():
    return _sys.platform

def version():
    return "ailang-8.1"

def stderr_write(msg):
    _sys.stderr.write(str(msg))
    return None
