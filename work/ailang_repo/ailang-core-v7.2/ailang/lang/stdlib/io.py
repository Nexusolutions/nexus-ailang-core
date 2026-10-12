"""Stdlib `io` — operaciones de filesystem con capability enforcement (P3-9b).

Cada operación requiere su capability correspondiente:
  read_text  → filesystem.read
  write_text → filesystem.write
  exists     → filesystem.read  (leer metadata es leer)
  lines      → filesystem.read

AUD-076: path traversal protection. Se rechazan paths que escapen del
directorio de trabajo vía `..` o symlinks maliciosos.
"""
import os
from pathlib import Path

from ailang.runtime.capabilities import require
from ailang.lang.errors import AILangRuntimeError


# Bases permitidas para acceso a filesystem. Por defecto, el cwd.
# El usuario puede ampliar vía `add_allowed_base(path)`.
_ALLOWED_BASES: list[Path] = []


def add_allowed_base(path: str | Path) -> None:
    """Añade un directorio base permitido para acceso a filesystem."""
    p = Path(path).resolve()
    if p not in _ALLOWED_BASES:
        _ALLOWED_BASES.append(p)


def _validate_path(path: str) -> Path:
    """Valida que el path no escape del directorio de trabajo.

    AUD-076: rechaza path traversal (`../etc/passwd`) y symlinks maliciosos.
    Permite paths bajo el cwd, el system temp dir, y cualquier base
    explícitamente añadida vía `add_allowed_base()`.
    """
    if not path or not isinstance(path, str):
        raise AILangRuntimeError(
            f"path inválido: {path!r}", code="E091"
        )

    # Resolver el path absoluto
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError) as e:
        raise AILangRuntimeError(
            f"path inválido: {path!r} ({e})", code="E091"
        )

    # Bases permitidas: cwd, system temp, y bases explícitas
    import tempfile
    bases = list(_ALLOWED_BASES)
    bases.append(Path.cwd().resolve())
    bases.append(Path(tempfile.gettempdir()).resolve())

    # Verificar que el path está dentro de alguna base permitida
    for base in bases:
        try:
            # relative_to lanza ValueError si no es subpath
            resolved.relative_to(base)
            return resolved  # OK
        except ValueError:
            continue

    # Path está fuera de todas las bases permitidas
    raise AILangRuntimeError(
        f"acceso denegado: path {path!r} fuera de los directorios permitidos",
        code="E091",
    )


def read_text(path: str) -> str:
    """Lee un archivo de texto. Requiere capability `filesystem.read`.

    AUD-076: valida path traversal.
    """
    require("filesystem.read", op_desc=f"read_text({path!r})")
    safe_path = _validate_path(path)
    return safe_path.read_text(encoding="utf-8")


def write_text(path: str, content: str) -> None:
    """Escribe a un archivo. Requiere capability `filesystem.write`.

    AUD-076: valida path traversal.
    """
    require("filesystem.write", op_desc=f"write_text({path!r}, ...)")
    safe_path = _validate_path(path)
    safe_path.write_text(str(content), encoding="utf-8")
    return None


def exists(path: str) -> bool:
    """Verifica si un path existe. Requiere capability `filesystem.read`.

    AUD-076: valida path traversal.
    """
    require("filesystem.read", op_desc=f"exists({path!r})")
    safe_path = _validate_path(path)
    return safe_path.exists()


def lines(path: str):
    """Lee líneas de un archivo. Requiere capability `filesystem.read`.

    AUD-076: valida path traversal.
    """
    require("filesystem.read", op_desc=f"lines({path!r})")
    safe_path = _validate_path(path)
    return safe_path.read_text(encoding="utf-8").splitlines()
