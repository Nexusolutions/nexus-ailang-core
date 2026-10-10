"""Genera documentación markdown desde comentarios // y firmas fn/class."""
from __future__ import annotations
from pathlib import Path
from typing import List

from ailang.lang.lexer import tokenize
from ailang.lang.parser import parse
from ailang.lang import ast_nodes as A


def docgen_source(source: str, title: str = "AILang module") -> str:
    lines = source.splitlines()
    comments = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("//"):
            comments.append(s[2:].strip())
    program = parse(source)
    sections = [f"# {title}", ""]
    if comments:
        sections.append("## Notes")
        sections.extend(f"- {c}" for c in comments[:20])
        sections.append("")
    sections.append("## API")
    for stmt in program.body:
        if isinstance(stmt, A.Function):
            async_p = "async " if getattr(stmt, "is_async", False) else ""
            sections.append(f"- `{async_p}fn {stmt.name}({', '.join(stmt.params)})`")
        elif isinstance(stmt, A.ClassDef):
            base = f" extends {stmt.base}" if stmt.base else ""
            sections.append(f"- `class {stmt.name}{base}`")
            for m in stmt.methods:
                sections.append(f"  - `fn {m.name}({', '.join(m.params)})`")
        elif isinstance(stmt, A.EnumDef):
            sections.append(f"- `enum {stmt.name} {{ {', '.join(stmt.variants)} }}`")
        elif isinstance(stmt, A.RecordDef):
            sections.append(f"- `record {stmt.name} {{ {', '.join(stmt.fields)} }}`")
        elif isinstance(stmt, A.InterfaceDef):
            sections.append(f"- `interface {stmt.name}` methods={stmt.methods}")
    sections.append("")
    return "\n".join(sections)


def docgen_file(path: str, out: str = None) -> str:
    p = Path(path)
    md = docgen_source(p.read_text(encoding="utf-8"), title=p.name)
    if out:
        Path(out).write_text(md, encoding="utf-8")
    return md
