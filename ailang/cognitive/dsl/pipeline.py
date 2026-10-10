"""Pipeline del DSL cognitivo: lexer → parser → semantic → UnifiedIR.

P1-3/P1-4: migrado desde `ailang/compiler/pipeline.py`. Renombrado
`compile_source` → `compile_cognitive` para evitar colisión con
`ailang.lang.vm.compile_source`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ailang.cognitive.dsl.lexer import tokenize
from ailang.cognitive.dsl.parser import parse_tokens
from ailang.cognitive.dsl.semantic import analyze, SemanticError
from ailang.ir.cognitive import CognitiveIR
from ailang.ir.security import SecurityIR
from ailang.ir.unified import UnifiedIR


@dataclass
class CompilerPipeline:
    """Compilador separado en fases formales del DSL cognitivo."""
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


def compile_cognitive(
    source: str,
    *,
    capabilities: Optional[Sequence[str]] = None,
    require_auth: bool = True,
) -> UnifiedIR:
    """Compila fuente del DSL cognitivo a UnifiedIR (canónico, P1-4)."""
    return CompilerPipeline(require_auth=require_auth).compile(
        source, capabilities=capabilities
    )


def compile_source(
    source: str,
    *,
    capabilities: Optional[Sequence[str]] = None,
    require_auth: bool = True,
) -> UnifiedIR:
    """Alias deprecated para retrocompatibilidad. Usar `compile_cognitive`."""
    import warnings
    warnings.warn(
        "ailang.cognitive.dsl.compile_source está deprecado; "
        "usa ailang.cognitive.dsl.compile_cognitive en su lugar (P1-4).",
        DeprecationWarning,
        stacklevel=2,
    )
    return compile_cognitive(source, capabilities=capabilities, require_auth=require_auth)
