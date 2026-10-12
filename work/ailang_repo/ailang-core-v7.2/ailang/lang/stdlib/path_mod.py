"""Stdlib `path` — operaciones de path con capability enforcement (P3-9b).

Operaciones de solo metadata requieren `filesystem.read`.
Operaciones mutadoras requieren `filesystem.write`.
"""
from pathlib import Path as _P
import os

from ailang.runtime.capabilities import require

def join(*parts):
    """Join paths. Sin capability (operación pura sobre strings)."""
    return str(_P(*[str(p) for p in parts]))

def exists(p):
    """Verifica existencia. Requiere `filesystem.read`."""
    require("filesystem.read", op_desc=f"path.exists({p!r})")
    return _P(str(p)).exists()

def is_file(p):
    """Requiere `filesystem.read`."""
    require("filesystem.read", op_desc=f"path.is_file({p!r})")
    return _P(str(p)).is_file()

def is_dir(p):
    """Requiere `filesystem.read`."""
    require("filesystem.read", op_desc=f"path.is_dir({p!r})")
    return _P(str(p)).is_dir()

def name(p):
    """Sin capability (operación pura)."""
    return _P(str(p)).name

def parent(p):
    """Sin capability (operación pura)."""
    return str(_P(str(p)).parent)

def mkdir(p, parents=True):
    """Crea directorio. Requiere `filesystem.write`."""
    require("filesystem.write", op_desc=f"path.mkdir({p!r})")
    _P(str(p)).mkdir(parents=bool(parents), exist_ok=True)
    return None

def listdir(p="."):
    """Lista contenido. Requiere `filesystem.read`."""
    require("filesystem.read", op_desc=f"path.listdir({p!r})")
    return sorted(os.listdir(str(p)))

def cwd():
    """Directorio actual. Sin capability (información pública)."""
    return str(_P.cwd())

def abs(p):
    """Resuelve path absoluto. Sin capability (operación pura)."""
    return str(_P(str(p)).resolve())
