"""Pipeline lexer → parser → semantic → UnifiedIR."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ailang.compiler.lexer import tokenize
from ailang.compiler.parser import parse_tokens
from ailang.compiler.semantic import analyze, SemanticError
from ailang.ir.cognitive import CognitiveIR
from ailang.ir.security import SecurityIR
from ailang.ir.unified import UnifiedIR


@dataclass
class CompilerPipeline:
    """Compilador separado en fases formales."""
    require_auth: bool = True

    def lex(self, source: str):
        return tokenize(source)

    def parse(self, source: str):
        return parse_tokens(tokenize(source))

    def semantic(self, source: str) -> CognitiveIR:
        return analyze(parse_tokens(tokenize(source)))

    def compile(
        self,
        source: str,
        *,
        capabilities: Optional[Sequence[str]] = None,
    ) -> UnifiedIR:
        cognitive = self.semantic(source)
        granted = tuple(capabilities) if capabilities is not None else cognitive.required_capabilities
        security = SecurityIR.from_capabilities(granted, require_auth=self.require_auth)
        unified = UnifiedIR(cognitive=cognitive, security=security).with_digest()
        unified.validate()
        return unified


def compile_source(
    source: str,
    *,
    capabilities: Optional[Sequence[str]] = None,
    require_auth: bool = True,
) -> UnifiedIR:
    return CompilerPipeline(require_auth=require_auth).compile(
        source, capabilities=capabilities
    )
