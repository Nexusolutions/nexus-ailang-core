from pathlib import Path as _P
import os

def join(*parts):
    return str(_P(*[str(p) for p in parts]))

def exists(p):
    return _P(str(p)).exists()

def is_file(p):
    return _P(str(p)).is_file()

def is_dir(p):
    return _P(str(p)).is_dir()

def name(p):
    return _P(str(p)).name

def parent(p):
    return str(_P(str(p)).parent)

def mkdir(p, parents=True):
    _P(str(p)).mkdir(parents=bool(parents), exist_ok=True)
    return None

def listdir(p="."):
    return sorted(os.listdir(str(p)))

def cwd():
    return str(_P.cwd())

def abs(p):
    return str(_P(str(p)).resolve())
