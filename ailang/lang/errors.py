"""Jerarquía completa de errores de AILang (P3-6 + Y3).

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

Y3: Mejoras de UX:
- Colores ANSI cuando stdout es terminal
- "Did you mean...?" suggestions via Levenshtein distance
- Error codes con URL a documentación
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional
from difflib import get_close_matches


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
        """Formatea el error con colores ANSI si stdout es terminal."""
        use_color = _is_terminal()
        return self._format(use_color)

    def _format(self, use_color: bool = False) -> str:
        # Colors
        if use_color:
            RED = "\033[91m"
            BOLD = "\033[1m"
            DIM = "\033[2m"
            CYAN = "\033[96m"
            YELLOW = "\033[93m"
            GREEN = "\033[92m"
            RESET = "\033[0m"
        else:
            RED = BOLD = DIM = CYAN = YELLOW = GREEN = RESET = ""

        # Header
        out = [f"{RED}{BOLD}error[{self.code}]{RESET}: {self.message}"]

        # Location
        if self.line > 0 or self.file != "<stdin>":
            loc = f"{self.file}:{self.line}:{self.col}" if self.col else f"{self.file}:{self.line}"
            out.append(f"  {DIM}--> {loc}{RESET}")

        # Source snippet con caret
        if self.source_snippet and self.line > 0:
            lines = self.source_snippet.splitlines()
            out.append(f"   {DIM}|{RESET}")
            if 0 < self.line - 1 <= len(lines):
                out.append(f"{self.line - 1:3d} {DIM}|{RESET} {lines[self.line - 2]}")
            if 0 < self.line <= len(lines):
                out.append(f"{YELLOW}{self.line:3d}{RESET} {DIM}|{RESET} {lines[self.line - 1]}")
                caret_col = max(0, self.col - 1)
                caret_len = 1
                caret = " " * (len(str(self.line)) + 4 + caret_col) + f"{RED}{'^' + '~' * max(0, caret_len - 1)}{RESET}"
                out.append(f"   {DIM}|{RESET} {caret}")
            if 0 < self.line + 1 <= len(lines):
                out.append(f"{self.line + 1:3d} {DIM}|{RESET} {lines[self.line]}")
            out.append(f"   {DIM}|{RESET}")

        # Cause
        if self.cause:
            out.append(f"{CYAN}note:{RESET} {self.cause}")

        # Suggestion (Y3: did-you-mean)
        if self.suggestion:
            out.append(f"{GREEN}help:{RESET} {self.suggestion}")

        # Stack trace
        if self.frames:
            out.append("")
            out.append(f"{DIM}Traceback (AILang stack):{RESET}")
            for fr in reversed(self.frames):
                out.append(fr.format())

        # Y3: Error code URL
        if use_color:
            out.append(f"\n{DIM}For more information: https://docs.ailang.org/errors/{self.code}{RESET}")

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


class TypeError(AILangError):  # noqa: A001 (intentional shadow of builtin)
    CODE = "E042"
    DEFAULT_MESSAGE = "type mismatch"


class NameError(AILangError):  # noqa: A001
    CODE = "E041"
    DEFAULT_MESSAGE = "name not defined"


class ImportError(AILangError):  # noqa: A001
    CODE = "E043"
    DEFAULT_MESSAGE = "module not found or import error"


class AILangRuntimeError(AILangError):
    """Alias para mantener retrocompatibilidad. Códigos E0xx."""
    CODE = "E050"
    DEFAULT_MESSAGE = "runtime error"

    def __init__(self, message: str, frames: Optional[List[StackFrame]] = None, **kwargs):
        super().__init__(message, frames=frames, **kwargs)


class ValueError(AILangError):  # noqa: A001
    CODE = "E051"
    DEFAULT_MESSAGE = "invalid value"


class IndexError(AILangError):  # noqa: A001
    CODE = "E052"
    DEFAULT_MESSAGE = "index out of range"


class AttributeError(AILangError):  # noqa: A001
    CODE = "E053"
    DEFAULT_MESSAGE = "attribute not found"


class SecurityError(AILangError):
    CODE = "E060"
    DEFAULT_MESSAGE = "security violation"


class CapabilityError(SecurityError):
    CODE = "E061"
    DEFAULT_MESSAGE = "missing required capability"


class TimeoutError(AILangError):  # noqa: A001
    CODE = "E070"
    DEFAULT_MESSAGE = "operation timed out"


class MemoryError(AILangError):  # noqa: A001
    CODE = "E080"
    DEFAULT_MESSAGE = "memory limit exceeded"


class IOError(AILangError):  # noqa: A001
    CODE = "E090"
    DEFAULT_MESSAGE = "I/O error"


class ConcurrencyError(AILangError):
    CODE = "E0A0"
    DEFAULT_MESSAGE = "concurrency error"


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


# --- Y3: Helpers de "did you mean" ---

def did_you_mean(name: str, candidates: List[str], n: int = 3) -> Optional[str]:
    """Retorna una sugerencia 'did you mean X?' si hay un match cercano.

    Usa difflib.get_close_matches para encontrar el nombre más parecido.

    Args:
        name: el nombre que el usuario escribió (posiblemente incorrecto)
        candidates: lista de nombres válidos (variables, funciones, keywords, etc.)
        n: número máximo de sugerencias

    Returns:
        String con sugerencia formateada, o None si no hay match.
    """
    matches = get_close_matches(name, candidates, n=n, cutoff=0.6)
    if not matches:
        return None
    if len(matches) == 1:
        return f"did you mean '{matches[0]}'?"
    return f"did you mean one of: {', '.join(f'{m!r}' for m in matches)}?"


def suggest_keyword(name: str) -> Optional[str]:
    """Sugiere un keyword de AILang si el usuario escribió algo parecido."""
    keywords = [
        "let", "const", "fn", "if", "else", "while", "for", "in", "return",
        "class", "extends", "import", "try", "catch", "throw", "as",
        "self", "super", "break", "continue", "match", "case",
        "enum", "async", "await", "yield", "interface", "record", "spawn",
        "implements", "purge_after", "and", "or", "not",
    ]
    return did_you_mean(name, keywords)


def suggest_name(name: str, known_names: List[str]) -> Optional[str]:
    """Sugiere un nombre de variable/función si el usuario escribió algo parecido."""
    return did_you_mean(name, known_names)


def _is_terminal() -> bool:
    """Detecta si stdout es un terminal (para activar colores ANSI)."""
    return hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
