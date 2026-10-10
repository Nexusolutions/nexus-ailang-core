"""Errores del lenguaje AILang con stack trace propio."""
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


class AILangSyntaxError(Exception):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        self.line, self.col = line, col
        super().__init__(f"line {line}:{col}: {message}" if line else message)


class AILangRuntimeError(Exception):
    def __init__(self, message: str, frames: Optional[List[StackFrame]] = None):
        self.frames: List[StackFrame] = list(frames or [])
        self.message = str(message)
        super().__init__(self.format())

    def push(self, function: str, line: int = 0, detail: str = "") -> "AILangRuntimeError":
        self.frames.append(StackFrame(function, line, detail))
        # refresh message
        Exception.__init__(self, self.format())
        return self

    def format(self) -> str:
        if not self.frames:
            return self.message
        lines = ["Traceback (AILang stack):"]
        for fr in reversed(self.frames):
            lines.append(fr.format())
        lines.append(f"AILangRuntimeError: {self.message}")
        return "\n".join(lines)
