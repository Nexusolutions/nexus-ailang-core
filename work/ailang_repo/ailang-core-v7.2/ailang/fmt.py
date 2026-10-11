"""Formateador de AILang (P2-4).

Dos modos:
- `format_source(source)`: formatea desde tokens (rápido, no idempotente en comments).
- `format_ast(source)`: formatea desde AST (idempotente, preserva estructura semántica,
  pero pierde comentarios). Recomendado para uso programático y CI.

Reglas: indent 2 espacios, llaves en misma línea del header, espacios alrededor de `=`,
`==`, etc. Una sola expresión por línea. Sin líneas en blanco consecutivas.
"""
from __future__ import annotations

from typing import Any

from ailang.lang.lexer import tokenize
from ailang.lang.parser import parse
from ailang.lang.errors import AILangSyntaxError
from ailang.lang import ast_nodes as A


def format_source(source: str) -> str:
    """Formato desde tokens (modo legacy, mantiene comentarios)."""
    tokens = tokenize(source)
    out = []
    indent = 0
    i = 0
    newline = True
    while i < len(tokens):
        t = tokens[i]
        if t.kind == "EOF":
            break
        if t.kind == "NEWLINE":
            out.append("\n")
            newline = True
            i += 1
            continue
        if t.kind == "RBRACE":
            indent = max(0, indent - 1)
        if newline:
            out.append("  " * indent)
            newline = False
        if t.kind == "STRING":
            out.append(repr(t.value) if False else f'"{t.value}"')
        elif t.kind == "NUMBER":
            out.append(t.value)
        elif t.kind in ("IDENT", "KEYWORD"):
            out.append(t.value)
        elif t.kind == "LBRACE":
            out.append(" {")
            indent += 1
            out.append("\n")
            newline = True
            i += 1
            continue
        elif t.kind == "RBRACE":
            out.append("}")
            out.append("\n")
            newline = True
            i += 1
            continue
        elif t.kind in ("EQ", "EQEQ", "NE", "LE", "GE", "LT", "GT"):
            op = {"EQ": "=", "EQEQ": "==", "NE": "!=", "LE": "<=", "GE": ">=", "LT": "<", "GT": ">"}.get(t.kind, t.value)
            out.append(f" {op} ")
        elif t.kind == "COMMA":
            out.append(", ")
        else:
            out.append(t.value)
        if t.kind == "KEYWORD" and i + 1 < len(tokens) and tokens[i + 1].kind in ("IDENT", "NUMBER", "STRING"):
            out.append(" ")
        i += 1
    text = "".join(out)
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)
    return "\n".join(cleaned).rstrip() + "\n"


# --- P2-4: Formateador AST-based (idempotente) ---

def format_ast(source: str) -> str:
    """Formatea desde AST. Idempotente: format_ast(format_ast(x)) == format_ast(x).

    NOTA: NO preserva comentarios (los comentarios no están en el AST).
    Para preservar comentarios, usa `format_source` (token-based).
    """
    try:
        program = parse(source)
    except AILangSyntaxError:
        return format_source(source)
    lines: list[str] = []
    for stmt in program.body:
        _emit_stmt(stmt, lines, indent=0)
    # Cada _emit_stmt appends complete lines; filtrar vacías y dedupe consecutivas
    result: list[str] = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                result.append("")
        else:
            blank = 0
            result.append(ln)
    return "\n".join(result).rstrip() + "\n"


def _emit_indent(lines: list[str], indent: int) -> None:
    lines.append("  " * indent)


def _emit_stmt(node: Any, lines: list[str], indent: int) -> None:
    if isinstance(node, A.Let) or isinstance(node, A.Const):
        kw = "const" if isinstance(node, A.Const) else "let"
        _emit_indent(lines, indent)
        line = f"{kw} {node.name}"
        if getattr(node, "type_ann", None):
            line += f": {node.type_ann}"
        line += f" = {_emit_expr(node.value)}"
        lines[-1] = line
    elif isinstance(node, A.Assign):
        _emit_indent(lines, indent)
        if isinstance(node.name, str):
            lines[-1] = f"{node.name} = {_emit_expr(node.value)}"
        elif isinstance(node.name, A.Attr):
            lines[-1] = f"{_emit_expr(node.name.value)}.{node.name.attr} = {_emit_expr(node.value)}"
        else:
            lines[-1] = f"= {_emit_expr(node.value)}"
    elif isinstance(node, A.Function):
        _emit_indent(lines, indent)
        async_kw = "async " if getattr(node, "is_async", False) else ""
        lines[-1] = f"{async_kw}fn {node.name}({', '.join(node.params)}) {{"
        for s in node.body:
            _emit_stmt(s, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.ClassDef):
        _emit_indent(lines, indent)
        base = f" extends {node.base}" if node.base else ""
        lines[-1] = f"class {node.name}{base} {{"
        for m in node.methods:
            _emit_stmt(m, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.If):
        _emit_indent(lines, indent)
        lines[-1] = f"if {_emit_expr(node.test)} {{"
        for s in node.body:
            _emit_stmt(s, lines, indent + 1)
        if node.orelse:
            _emit_indent(lines, indent)
            lines[-1] = "} else {"
            for s in node.orelse:
                _emit_stmt(s, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.While):
        _emit_indent(lines, indent)
        lines[-1] = f"while {_emit_expr(node.test)} {{"
        for s in node.body:
            _emit_stmt(s, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.For):
        _emit_indent(lines, indent)
        lines[-1] = f"for {node.target} in {_emit_expr(node.iter)} {{"
        for s in node.body:
            _emit_stmt(s, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.Return):
        _emit_indent(lines, indent)
        if node.value is not None:
            lines[-1] = f"return {_emit_expr(node.value)}"
        else:
            lines[-1] = "return"
    elif isinstance(node, A.Break):
        _emit_indent(lines, indent)
        lines[-1] = "break"
    elif isinstance(node, A.Continue):
        _emit_indent(lines, indent)
        lines[-1] = "continue"
    elif isinstance(node, A.ExprStmt):
        _emit_indent(lines, indent)
        lines[-1] = _emit_expr(node.value)
    elif isinstance(node, A.Import):
        _emit_indent(lines, indent)
        if node.alias:
            lines[-1] = f"import {node.module} as {node.alias}"
        else:
            lines[-1] = f"import {node.module}"
    elif isinstance(node, A.Throw):
        _emit_indent(lines, indent)
        lines[-1] = f"throw {_emit_expr(node.value)}"
    elif isinstance(node, A.Try):
        _emit_indent(lines, indent)
        lines[-1] = "try {"
        for s in node.body:
            _emit_stmt(s, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = f"}} catch ({node.catch_name}) {{"
        for s in node.catch_body:
            _emit_stmt(s, lines, indent + 1)
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.EnumDef):
        _emit_indent(lines, indent)
        lines[-1] = f"enum {node.name} {{"
        for v in node.variants:
            _emit_indent(lines, indent + 1)
            lines[-1] = v
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.RecordDef):
        _emit_indent(lines, indent)
        lines[-1] = f"record {node.name} {{ {', '.join(node.fields)} }}"
    elif isinstance(node, A.InterfaceDef):
        _emit_indent(lines, indent)
        lines[-1] = f"interface {node.name} {{"
        if isinstance(node.methods, list) and node.methods and isinstance(node.methods[0], str):
            for m in node.methods:
                _emit_indent(lines, indent + 1)
                lines[-1] = f"fn {m}"
        _emit_indent(lines, indent)
        lines[-1] = "}"
    elif isinstance(node, A.Yield):
        _emit_indent(lines, indent)
        if node.value is not None:
            lines[-1] = f"yield {_emit_expr(node.value)}"
        else:
            lines[-1] = "yield"
    elif isinstance(node, A.Match):
        _emit_indent(lines, indent)
        lines[-1] = f"match {_emit_expr(node.subject)} {{"
        for c in node.cases:
            _emit_indent(lines, indent + 1)
            pattern_str = _emit_pattern(c.pattern)
            lines[-1] = f"{pattern_str} => {{"
            for s in c.body:
                _emit_stmt(s, lines, indent + 2)
            _emit_indent(lines, indent + 1)
            lines[-1] = "}"
        _emit_indent(lines, indent)
        lines[-1] = "}"
    else:
        _emit_indent(lines, indent)
        lines[-1] = f"// {type(node).__name__}"


def _emit_expr(node: Any) -> str:
    if isinstance(node, A.Literal):
        if isinstance(node.value, str):
            # AUD-012: Escape quotes and backslashes in string literals
            escaped = node.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
            return f'"{escaped}"'
        if node.value is True:
            return "true"
        if node.value is False:
            return "false"
        if node.value is None:
            return "null"
        return str(node.value)
    if isinstance(node, A.Name):
        return node.id
    if isinstance(node, A.BinOp):
        return f"{_emit_expr(node.left)} {node.op} {_emit_expr(node.right)}"
    if isinstance(node, A.UnaryOp):
        return f"{node.op}{_emit_expr(node.operand)}"
    if isinstance(node, A.Call):
        args = ", ".join(_emit_expr(a) for a in node.args)
        return f"{_emit_expr(node.func)}({args})"
    if isinstance(node, A.Attr):
        return f"{_emit_expr(node.value)}.{node.attr}"
    if isinstance(node, A.Lambda):
        return f"fn({', '.join(node.params)}) {{ ... }}"
    if isinstance(node, A.ListLit):
        return f"[{', '.join(_emit_expr(e) for e in node.elts)}]"
    if isinstance(node, A.DictLit):
        items = ", ".join(f"{_emit_expr(k)}: {_emit_expr(v)}" for k, v in zip(node.keys, node.values))
        return f"{{{items}}}"
    if isinstance(node, A.Index):
        return f"{_emit_expr(node.value)}[{_emit_expr(node.index)}]"
    if isinstance(node, A.Await):
        return f"await {_emit_expr(node.value)}"
    if isinstance(node, A.InterpolatedString):
        parts = []
        for p in node.parts:
            if isinstance(p, str):
                parts.append(p)
            else:
                parts.append("${" + _emit_expr(p) + "}")
        joined = "".join(parts)
        return '"' + joined + '"'
    return f"<{type(node).__name__}>"


def _emit_pattern(node: Any) -> str:
    if isinstance(node, A.Literal):
        if isinstance(node.value, str):
            return f'"{node.value}"'
        return str(node.value)
    if isinstance(node, A.Name):
        return node.id
    return "_"


def format_file(path: str, *, ast_mode: bool = False) -> str:
    from pathlib import Path
    p = Path(path)
    formatter = format_ast if ast_mode else format_source
    formatted = formatter(p.read_text(encoding="utf-8"))
    p.write_text(formatted, encoding="utf-8")
    return formatted
