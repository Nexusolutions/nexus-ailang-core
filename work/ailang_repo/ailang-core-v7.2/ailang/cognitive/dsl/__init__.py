"""ailang.cognitive.dsl — compilador del DSL cognitivo.

P1-3/P1-4: migrado desde `ailang/compiler/` para eliminar la duplicidad de
frontend. El frontend normativo del lenguaje AILang vive en `ailang/lang/`;
este módulo es específicamente el compilador del DSL cognitivo (brain.ingest,
brain.query, memory, persist, purge_after) que produce un `UnifiedIR`.

El símbolo público pasa a ser `compile_cognitive` para evitar la colisión
con `ailang.lang.vm.compile_source` (P1-4). `compile_source` se mantiene
como alias deprecated temporalmente para retrocompatibilidad con tests.
"""
from __future__ import annotations

from ailang.cognitive.dsl.pipeline import (
    compile_cognitive,
    compile_source,  # alias deprecated (P1-4)
    CompilerPipeline,
)
from ailang.cognitive.dsl.lexer import tokenize, Token
from ailang.cognitive.dsl.parser import parse_tokens, ASTModule, ASTStmt
from ailang.cognitive.dsl.semantic import analyze, SemanticError

__all__ = [
    "compile_cognitive",  # canónico
    "compile_source",     # deprecated alias (P1-4)
    "CompilerPipeline",
    "tokenize", "Token",
    "parse_tokens", "ASTModule", "ASTStmt",
    "analyze", "SemanticError",
]
