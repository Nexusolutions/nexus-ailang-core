"""Stdlib `io` — operaciones de filesystem con capability enforcement (P3-9b).

Cada operación requiere su capability correspondiente:
  read_text  → filesystem.read
  write_text → filesystem.write
  exists     → filesystem.read  (leer metadata es leer)
  lines      → filesystem.read
"""
from pathlib import Path

from ailang.runtime.capabilities import require


def read_text(path: str) -> str:
    """Lee un archivo de texto. Requiere capability `filesystem.read`."""
    require("filesystem.read", op_desc=f"read_text({path!r})")
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str, content: str) -> None:
    """Escribe a un archivo. Requiere capability `filesystem.write`."""
    require("filesystem.write", op_desc=f"write_text({path!r}, ...)")
    Path(path).write_text(str(content), encoding="utf-8")
    return None


def exists(path: str) -> bool:
    """Verifica si un path existe. Requiere capability `filesystem.read`."""
    require("filesystem.read", op_desc=f"exists({path!r})")
    return Path(path).exists()


def lines(path: str):
    """Lee líneas de un archivo. Requiere capability `filesystem.read`."""
    require("filesystem.read", op_desc=f"lines({path!r})")
    return Path(path).read_text(encoding="utf-8").splitlines()
