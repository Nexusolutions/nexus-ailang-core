"""Jerarquía completa de errores de AILang (P3-6).

FASE 7 del prompt maestro:

  AILangError
  ├── LexError
  ├── SyntaxError (alias AILangSyntaxError)
  ├── ParseError
  ├── TypeError
  ├── NameError
  ├── ImportError
  ├── RuntimeError (alias AILangRuntimeError)
  ├── ValueError
  ├── IndexError
  ├── AttributeError
  ├── SecurityError
  ├── CapabilityError
  ├── TimeoutError
  ├── MemoryError
  ├── IOError
  └── ConcurrencyError

Cada error incluye:
- código (e.g., E001, E042)
- archivo (path o <stdin>)
- línea
- columna
- fragmento de código fuente
- indicador visual (caret)
- mensaje
- causa (opcional)
- sugerencia de solución (opcional)

Formato de visualización estilo Rust:

  error[E042]: cannot assign String to variable 'age'
    --> prog.ailang:12:7
     |
  12 | age = "Enrique"
     |       ^^^^^^^^^
     |
  expected: Int
  found:    String
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StackFrame:
    function: str
    line: int = 0
    detail: str = ""

    def format(self) -> str:
        loc = f", line {self.line}" if self.line else ""
        extra = f" ({self.detail})" if self.detail else ""
        return f'  File AILang, in {self.function}{loc}{extra}'


# --- Base class -------------------------------------------------------------

class AILangError(Exception):
    """Base de la jerarquía de errores AILang."""

    CODE: str = "E000"
    DEFAULT_MESSAGE: str = "AILang error"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        file: str = "<stdin>",
        line: int = 0,
        col: int = 0,
        source_snippet: Optional[str] = None,
        cause: Optional[str] = None,
        suggestion: Optional[str] = None,
        frames: Optional[List[StackFrame]] = None,
    ):
        self.message = message or self.DEFAULT_MESSAGE
        self.code = code or self.CODE
        self.file = file
        self.line = line
        self.col = col
        self.source_snippet = source_snippet
        self.cause = cause
        self.suggestion = suggestion
        self.frames: List[StackFrame] = list(frames or [])
        super().__init__(self.format())

    def push(self, function: str, line: int = 0, detail: str = "") -> "AILangError":
        self.frames.append(StackFrame(function, line, detail))
        Exception.__init__(self, self.format())
        return self

    def format(self) -> str:
        # Header estilo Rust
        out = [f"error[{self.code}]: {self.message}"]
        if self.line > 0 or self.file != "<stdin>":
            loc = f"{self.file}:{self.line}:{self.col}" if self.col else f"{self.file}:{self.line}"
            out.append(f"  --> {loc}")
        # Source snippet con caret indicator
        if self.source_snippet and self.line > 0:
            lines = self.source_snippet.splitlines()
            out.append("   |")
            # Línea antes del error
            if 0 < self.line - 1 <= len(lines):
                out.append(f"{self.line - 1:3d} | {lines[self.line - 2]}")
            # Línea del error
            if 0 < self.line <= len(lines):
                out.append(f"{self.line:3d} | {lines[self.line - 1]}")
                # Caret indicator
                caret_col = max(0, self.col - 1)
                caret_len = 1
                caret_line = " " * (len(str(self.line)) + 4 + caret_col) + "^" + "~" * max(0, caret_len - 1)
                out.append(f"   | {caret_line}")
            # Línea después del error
            if 0 < self.line + 1 <= len(lines):
                out.append(f"{self.line + 1:3d} | {lines[self.line]}")
            out.append("   |")
        # Cause
        if self.cause:
            out.append(f"cause: {self.cause}")
        # Suggestion
        if self.suggestion:
            out.append(f"help: {self.suggestion}")
        # Stack trace si hay frames
        if self.frames:
            out.append("")
            out.append("Traceback (AILang stack):")
            for fr in reversed(self.frames):
                out.append(fr.format())
        return "\n".join(out)


# --- Subclases ---------------------------------------------------------------

class LexError(AILangError):
    CODE = "E001"
    DEFAULT_MESSAGE = "lexer error"


class AILangSyntaxError(AILangError):
    """Alias para mantener retrocompatibilidad con código existente."""
    CODE = "E002"
    DEFAULT_MESSAGE = "syntax error"

    def __init__(self, message: str, line: int = 0, col: int = 0, **kwargs):
        super().__init__(message, line=line, col=col, **kwargs)


class ParseError(AILangError):
    CODE = "E003"
    DEFAULT_MESSAGE = "parse error"


# AUD-029: Añadimos nombres con prefijo AILang* para evitar shadowing
# de builtins Python. Los nombres antiguos se mantienen como aliases
# para retrocompatibilidad.

class AILangTypeError(AILangError):
    CODE = "E042"
    DEFAULT_MESSAGE = "type mismatch"


class AILangNameError(AILangError):
    CODE = "E041"
    DEFAULT_MESSAGE = "name not defined"


class AILangImportError(AILangError):
    CODE = "E043"
    DEFAULT_MESSAGE = "module not found or import error"


class AILangRuntimeError(AILangError):
    """Runtime error base. Códigos E0xx."""
    CODE = "E050"
    DEFAULT_MESSAGE = "runtime error"

    def __init__(self, message: str, frames: Optional[List[StackFrame]] = None, **kwargs):
        super().__init__(message, frames=frames, **kwargs)


class AILangValueError(AILangError):
    CODE = "E051"
    DEFAULT_MESSAGE = "invalid value"


class AILangIndexError(AILangError):
    CODE = "E052"
    DEFAULT_MESSAGE = "index out of range"


class AILangAttributeError(AILangError):
    CODE = "E053"
    DEFAULT_MESSAGE = "attribute not found"


class SecurityError(AILangRuntimeError):
    """Base para errores de seguridad.

    AUD-003: hereda de AILangRuntimeError (no de AILangError directo) para que
    try/catch del interpreter los atrape via la rama `except AILangRuntimeError`.
    """
    CODE = "E060"
    DEFAULT_MESSAGE = "security violation"


class CapabilityError(SecurityError):
    """Violation de capability en runtime.

    AUD-003: hereda de SecurityError → AILangRuntimeError, así try/catch
    del lenguaje AILang puede atrapar violaciones de capability.
    """
    CODE = "E061"
    DEFAULT_MESSAGE = "missing required capability"


class AILangTimeoutError(AILangError):
    CODE = "E070"
    DEFAULT_MESSAGE = "operation timed out"


class AILangMemoryError(AILangError):
    CODE = "E080"
    DEFAULT_MESSAGE = "memory limit exceeded"


class AILangIOError(AILangError):
    CODE = "E090"
    DEFAULT_MESSAGE = "I/O error"


class ConcurrencyError(AILangError):
    CODE = "E0A0"
    DEFAULT_MESSAGE = "concurrency error"


# --- Retrocompatibilidad: aliases sin prefijo AILang ---
# AUD-029: estos nombres shadowean builtins Python. Se mantienen por
# retrocompatibilidad pero se recomienda usar los AILang* en código nuevo.

TypeError = AILangTypeError        # noqa: A001
NameError = AILangNameError        # noqa: A001
ImportError = AILangImportError    # noqa: A001
ValueError = AILangValueError      # noqa: A001
IndexError = AILangIndexError      # noqa: A001
AttributeError = AILangAttributeError  # noqa: A001
TimeoutError = AILangTimeoutError  # noqa: A001
MemoryError = AILangMemoryError    # noqa: A001
IOError = AILangIOError            # noqa: A001


# --- Test helpers ------------------------------------------------------------

def render_error(
    message: str,
    *,
    code: str = "E000",
    file: str = "<stdin>",
    line: int = 0,
    col: int = 0,
    source: Optional[str] = None,
    expected: Optional[str] = None,
    found: Optional[str] = None,
    suggestion: Optional[str] = None,
) -> str:
    """Helper para construir mensajes de error visualmente.

    Ejemplo:
      render_error(
          "cannot assign String to variable 'age'",
          code="E042", line=12, col=7,
          source=source_text,
          expected="Int", found="String",
          suggestion="convierte con int(value) o cambia el tipo declarado",
      )
    """
    cause = None
    if expected and found:
        cause = f"expected: {expected}\nfound:    {found}"
    err = AILangError(
        message, code=code, file=file, line=line, col=col,
        source_snippet=source, cause=cause, suggestion=suggestion,
    )
    return err.format()
