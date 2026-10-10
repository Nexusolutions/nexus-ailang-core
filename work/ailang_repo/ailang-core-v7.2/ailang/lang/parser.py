"""Parser recursivo del núcleo AILang."""
from __future__ import annotations

from typing import Any, List, Optional
from ailang.lang.lexer import Tok, tokenize
from ailang.lang.errors import AILangSyntaxError
from ailang.lang import ast_nodes as A


class Parser:
    def __init__(self, tokens: List[Tok]):
        self.tokens = tokens
        self.i = 0

    def cur(self) -> Tok:
        return self.tokens[self.i]

    def adv(self) -> Tok:
        t = self.cur()
        if t.kind != "EOF":
            self.i += 1
        return t

    def match(self, *kinds) -> Optional[Tok]:
        if self.cur().kind in kinds or self.cur().value in kinds:
            return self.adv()
        return None

    def expect(self, kind: str, msg: str = "") -> Tok:
        if self.cur().kind == kind or self.cur().value == kind:
            return self.adv()
        raise AILangSyntaxError(msg or f"se esperaba {kind}, hay {self.cur().kind}",
                                self.cur().line, self.cur().col)

    def skip_nl(self):
        while self.cur().kind == "NEWLINE":
            self.adv()

    def parse(self) -> A.Program:
        body = []
        budget = None
        self.skip_nl()
        while self.cur().kind != "EOF":
            self.skip_nl()
            if self.cur().kind == "EOF":
                break
            if self.cur().kind == "KEYWORD" and self.cur().value == "purge_after":
                self.adv()
                self.expect("LPAREN")
                num = self.expect("NUMBER")
                # optional ms keyword as IDENT
                if self.cur().kind == "IDENT" and self.cur().value == "ms":
                    self.adv()
                self.expect("RPAREN")
                budget = int(float(num.value))
                self.skip_nl()
                continue
            body.append(self.statement())
            self.skip_nl()
        return A.Program(body, budget)

    def statement(self) -> Any:
        t = self.cur()
        if t.kind == "KEYWORD":
            if t.value == "let":
                return self.let_stmt()
            if t.value == "if":
                return self.if_stmt()
            if t.value == "while":
                return self.while_stmt()
            if t.value == "for":
                return self.for_stmt()
            if t.value == "fn":
                return self.fn_stmt()
            if t.value == "return":
                return self.return_stmt()
            if t.value == "import":
                return self.import_stmt()
            if t.value == "try":
                return self.try_stmt()
            if t.value == "throw":
                return self.throw_stmt()
            if t.value == "class":
                return self.class_stmt()
            if t.value == "break":
                self.adv()
                return A.Break(t.line)
            if t.value == "continue":
                self.adv()
                return A.Continue(t.line)
            if t.value == "const":
                return self.const_stmt()
            if t.value == "match":
                return self.match_stmt()
            if t.value == "enum":
                return self.enum_stmt()
            if t.value == "async":
                return self.async_fn_stmt()
            if t.value == "yield":
                return self.yield_stmt()
            if t.value == "interface":
                return self.interface_stmt()
            if t.value == "record":
                return self.record_stmt()
            if t.value == "spawn":
                return self.spawn_stmt()
        if t.kind == "LBRACE":
            return self.block()
        # assign or expr
        expr = self.expression()
        if self.cur().kind == "EQ":
            self.adv()
            val = self.expression()
            if isinstance(expr, A.Name):
                return A.Assign(expr.id, val, t.line)
            if isinstance(expr, A.Attr):
                return A.Assign(expr, val, t.line)  # target is Attr node
            raise AILangSyntaxError("asignación inválida", t.line, t.col)
        return A.ExprStmt(expr, t.line)

    def let_stmt(self) -> A.Let:
        kw = self.adv()
        name = self.expect("IDENT", "se esperaba nombre tras let")
        type_ann = None
        if self.cur().kind == "COLON":
            self.adv()
            type_ann = self.expect("IDENT").value
        self.expect("EQ")
        value = self.expression()
        return A.Let(name.value, value, type_ann, kw.line)

    def if_stmt(self) -> A.If:
        kw = self.adv()
        test = self.expression()
        body = self.block().body
        orelse = []
        self.skip_nl()
        if self.cur().kind == "KEYWORD" and self.cur().value == "else":
            self.adv()
            self.skip_nl()
            orelse = self.block().body
        return A.If(test, body, orelse, kw.line)

    def while_stmt(self) -> A.While:
        kw = self.adv()
        test = self.expression()
        body = self.block().body
        return A.While(test, body, kw.line)

    def for_stmt(self) -> A.For:
        kw = self.adv()
        target = self.expect("IDENT")
        if not (self.cur().kind == "KEYWORD" and self.cur().value == "in"):
            raise AILangSyntaxError("se esperaba 'in'", self.cur().line, self.cur().col)
        self.adv()
        it = self.expression()
        body = self.block().body
        return A.For(target.value, it, body, kw.line)

    def fn_stmt(self) -> A.Function:
        kw = self.adv()
        name = self.expect("IDENT")
        self.expect("LPAREN")
        params = []
        if self.cur().kind != "RPAREN":
            params.append(self.expect("IDENT").value)
            while self.cur().kind == "COMMA":
                self.adv()
                params.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        body = self.block().body
        return A.Function(name.value, params, body, kw.line)

    def return_stmt(self) -> A.Return:
        kw = self.adv()
        if self.cur().kind in ("NEWLINE", "RBRACE", "EOF"):
            return A.Return(None, kw.line)
        return A.Return(self.expression(), kw.line)


    def class_stmt(self) -> A.ClassDef:
        kw = self.adv()
        name = self.expect("IDENT").value
        base = None
        if self.cur().kind == "KEYWORD" and self.cur().value == "extends":
            self.adv()
            base = self.expect("IDENT").value
        self.expect("LBRACE")
        self.skip_nl()
        methods = []
        while self.cur().kind not in ("RBRACE", "EOF"):
            self.skip_nl()
            if self.cur().kind == "KEYWORD" and self.cur().value == "fn":
                methods.append(self.fn_stmt())
            elif self.cur().kind == "RBRACE":
                break
            else:
                raise AILangSyntaxError(
                    "en class solo se permiten métodos fn",
                    self.cur().line, self.cur().col,
                )
            self.skip_nl()
        self.expect("RBRACE")
        return A.ClassDef(name, base, methods, kw.line)




    def yield_stmt(self) -> A.Yield:
        kw = self.adv()
        if self.cur().kind in ("NEWLINE", "RBRACE", "EOF", "SEMICOLON"):
            return A.Yield(None, kw.line)
        return A.Yield(self.expression(), kw.line)

    def interface_stmt(self) -> A.InterfaceDef:
        kw = self.adv()
        name = self.expect("IDENT").value
        self.expect("LBRACE")
        self.skip_nl()
        methods = []
        while self.cur().kind not in ("RBRACE", "EOF"):
            self.skip_nl()
            if self.cur().kind == "KEYWORD" and self.cur().value == "fn":
                self.adv()
                methods.append(self.expect("IDENT").value)
                self.expect("LPAREN")
                while self.cur().kind not in ("RPAREN", "EOF"):
                    self.adv()
                self.expect("RPAREN")
            elif self.cur().kind == "IDENT":
                methods.append(self.adv().value)
            elif self.cur().kind == "RBRACE":
                break
            else:
                self.adv()
            self.skip_nl()
        self.expect("RBRACE")
        return A.InterfaceDef(name, methods, kw.line)

    def record_stmt(self) -> A.RecordDef:
        kw = self.adv()
        name = self.expect("IDENT").value
        self.expect("LBRACE")
        self.skip_nl()
        fields = []
        while self.cur().kind not in ("RBRACE", "EOF"):
            self.skip_nl()
            if self.cur().kind == "IDENT":
                fields.append(self.adv().value)
                if self.cur().kind == "COMMA":
                    self.adv()
            elif self.cur().kind == "RBRACE":
                break
            else:
                raise AILangSyntaxError("campo de record inválido", self.cur().line, self.cur().col)
            self.skip_nl()
        self.expect("RBRACE")
        return A.RecordDef(name, fields, kw.line)

    def spawn_stmt(self) -> A.Spawn:
        kw = self.adv()
        expr = self.expression()
        return A.Spawn(expr, kw.line)

    def enum_stmt(self) -> A.EnumDef:
        kw = self.adv()
        name = self.expect("IDENT").value
        self.expect("LBRACE")
        self.skip_nl()
        variants = []
        while self.cur().kind not in ("RBRACE", "EOF"):
            self.skip_nl()
            if self.cur().kind == "IDENT":
                variants.append(self.adv().value)
                if self.cur().kind == "COMMA":
                    self.adv()
            elif self.cur().kind == "RBRACE":
                break
            else:
                raise AILangSyntaxError("variante de enum inválida", self.cur().line, self.cur().col)
            self.skip_nl()
        self.expect("RBRACE")
        return A.EnumDef(name, variants, kw.line)

    def async_fn_stmt(self) -> A.Function:
        self.adv()  # async
        if not (self.cur().kind == "KEYWORD" and self.cur().value == "fn"):
            raise AILangSyntaxError("se esperaba fn tras async", self.cur().line, self.cur().col)
        fn = self.fn_stmt()
        fn.is_async = True
        return fn

    def const_stmt(self) -> A.Const:
        kw = self.adv()
        name = self.expect("IDENT").value
        type_ann = None
        if self.cur().kind == "COLON":
            self.adv()
            type_ann = self.expect("IDENT").value
        self.expect("EQ")
        value = self.expression()
        return A.Const(name, value, type_ann, kw.line)

    def match_stmt(self) -> A.Match:
        kw = self.adv()
        subject = self.expression()
        self.expect("LBRACE")
        self.skip_nl()
        cases = []
        while self.cur().kind not in ("RBRACE", "EOF"):
            self.skip_nl()
            if not (self.cur().kind == "KEYWORD" and self.cur().value == "case"):
                raise AILangSyntaxError("se esperaba case", self.cur().line, self.cur().col)
            self.adv()
            # pattern: literal, ident (_), or name
            if self.cur().kind == "NUMBER":
                raw = self.adv().value
                pat = A.Literal(float(raw) if ("." in raw or "e" in raw.lower()) else int(raw))
            elif self.cur().kind == "STRING":
                pat = A.Literal(self.adv().value)
            elif self.cur().kind == "KEYWORD" and self.cur().value in ("true", "false", "null"):
                tok = self.adv()
                pat = A.Literal({"true": True, "false": False, "null": None}[tok.value])
            elif self.cur().kind == "IDENT":
                pat = A.Name(self.adv().value)
            else:
                raise AILangSyntaxError("patrón inválido", self.cur().line, self.cur().col)
            body = self.block().body
            cases.append(A.MatchCase(pat, body))
            self.skip_nl()
        self.expect("RBRACE")
        return A.Match(subject, cases, kw.line)

    def import_stmt(self) -> A.Import:
        kw = self.adv()
        if self.cur().kind == "STRING":
            mod = self.adv().value
        elif self.cur().kind == "IDENT":
            parts = [self.adv().value]
            while self.cur().kind == "DOT":
                self.adv()
                parts.append(self.expect("IDENT").value)
            mod = ".".join(parts)
        else:
            raise AILangSyntaxError("se esperaba nombre de módulo", self.cur().line, self.cur().col)
        alias = None
        if self.cur().kind == "KEYWORD" and self.cur().value == "as":
            self.adv()
            alias = self.expect("IDENT").value
        return A.Import(mod, alias, kw.line)

    def try_stmt(self) -> A.Try:
        kw = self.adv()
        body = self.block().body
        self.skip_nl()
        if not (self.cur().kind == "KEYWORD" and self.cur().value == "catch"):
            raise AILangSyntaxError("se esperaba catch tras try", self.cur().line, self.cur().col)
        self.adv()
        name = self.expect("IDENT").value
        catch_body = self.block().body
        return A.Try(body, name, catch_body, kw.line)

    def throw_stmt(self) -> A.Throw:
        kw = self.adv()
        return A.Throw(self.expression(), kw.line)

    def block(self) -> A.Block:
        self.expect("LBRACE")
        self.skip_nl()
        body = []
        while self.cur().kind not in ("RBRACE", "EOF"):
            body.append(self.statement())
            self.skip_nl()
        self.expect("RBRACE")
        return A.Block(body)

    # expressions
    def expression(self) -> Any:
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.cur().kind == "KEYWORD" and self.cur().value == "or":
            self.adv()
            left = A.BinOp("or", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.cur().kind == "KEYWORD" and self.cur().value == "and":
            self.adv()
            left = A.BinOp("and", left, self.not_expr())
        return left

    def not_expr(self):
        if self.cur().kind == "KEYWORD" and self.cur().value == "not":
            self.adv()
            return A.UnaryOp("not", self.not_expr())
        return self.cmp()

    def cmp(self):
        left = self.sum()
        while self.cur().kind in ("EQEQ", "NE", "LT", "GT", "LE", "GE"):
            op = self.adv().value
            left = A.BinOp(op, left, self.sum())
        return left

    def sum(self):
        left = self.term()
        while self.cur().kind in ("PLUS", "MINUS"):
            op = self.adv().value
            left = A.BinOp(op, left, self.term())
        return left

    def term(self):
        left = self.unary()
        while self.cur().kind in ("STAR", "SLASH", "PERCENT"):
            op = self.adv().value
            left = A.BinOp(op, left, self.unary())
        return left

    def unary(self):
        if self.cur().kind in ("PLUS", "MINUS"):
            op = self.adv().value
            return A.UnaryOp(op, self.unary())
        return self.postfix()

    def postfix(self):
        left = self.primary()
        while True:
            if self.cur().kind == "DOT":
                self.adv()
                attr = self.expect("IDENT")
                left = A.Attr(left, attr.value)
            elif self.cur().kind == "LPAREN":
                self.adv()
                args = []
                if self.cur().kind != "RPAREN":
                    args.append(self.expression())
                    while self.cur().kind == "COMMA":
                        self.adv()
                        args.append(self.expression())
                self.expect("RPAREN")
                left = A.Call(left, args)
            elif self.cur().kind == "LBRACK":
                self.adv()
                idx = self.expression()
                self.expect("RBRACK")
                left = A.Index(left, idx)
            else:
                break
        return left


    def _parse_interpolated(self, s: str, line: int) -> A.InterpolatedString:
        """Divide 'hello ${name}' en partes Literal y Name/expr simples (solo IDENT)."""
        parts = []
        i = 0
        buf = []
        while i < len(s):
            if s[i:i+2] == "${":
                if buf:
                    parts.append(A.Literal("".join(buf)))
                    buf = []
                i += 2
                name = []
                while i < len(s) and s[i] != "}":
                    name.append(s[i])
                    i += 1
                if i < len(s) and s[i] == "}":
                    i += 1
                ident = "".join(name).strip()
                parts.append(A.Name(ident))
            else:
                buf.append(s[i])
                i += 1
        if buf:
            parts.append(A.Literal("".join(buf)))
        return A.InterpolatedString(parts, line)

    def primary(self):
        t = self.cur()
        if t.kind == "NUMBER":
            self.adv()
            try:
                v = float(t.value) if "." in t.value else int(t.value)
            except ValueError:
                # Números malformados como "0." o "0..1" — treat as syntax error
                raise AILangSyntaxError(f"número inválido: {t.value!r}", t.line, t.col)
            return A.Literal(v)
        if t.kind == "STRING":
            self.adv()
            s = t.value
            if "${" in s:
                return self._parse_interpolated(s, t.line)
            return A.Literal(s)
        if t.kind == "KEYWORD" and t.value in ("true", "false", "null"):
            self.adv()
            return A.Literal({"true": True, "false": False, "null": None}[t.value])
        if t.kind == "KEYWORD" and t.value in ("self", "super"):
            self.adv()
            return A.Name(t.value)
        if t.kind == "KEYWORD" and t.value == "await":
            self.adv()
            return A.Await(self.unary(), t.line)
        if t.kind == "KEYWORD" and t.value == "fn":
            # lambda: fn(a, b) { body }
            self.adv()
            self.expect("LPAREN")
            params = []
            if self.cur().kind != "RPAREN":
                params.append(self.expect("IDENT").value)
                while self.cur().kind == "COMMA":
                    self.adv()
                    params.append(self.expect("IDENT").value)
            self.expect("RPAREN")
            body = self.block().body
            return A.Lambda(params, body, t.line)
        if t.kind == "IDENT":
            self.adv()
            return A.Name(t.value)
        if t.kind == "LPAREN":
            self.adv()
            e = self.expression()
            self.expect("RPAREN")
            return e
        if t.kind == "LBRACK":
            self.adv()
            elts = []
            if self.cur().kind != "RBRACK":
                elts.append(self.expression())
                while self.cur().kind == "COMMA":
                    self.adv()
                    elts.append(self.expression())
            self.expect("RBRACK")
            return A.ListLit(elts)
        if t.kind == "LBRACE":
            # could be dict literal in expression context only when after = etc.
            # For simplicity, empty dict or key:value pairs
            self.adv()
            keys, vals = [], []
            if self.cur().kind != "RBRACE":
                # if IDENT/STRING then :  → dict, else block not allowed here
                k = self.expression()
                if self.cur().kind == "COLON":
                    self.adv()
                    keys.append(k)
                    vals.append(self.expression())
                    while self.cur().kind == "COMMA":
                        self.adv()
                        keys.append(self.expression())
                        self.expect("COLON")
                        vals.append(self.expression())
                    self.expect("RBRACE")
                    return A.DictLit(keys, vals)
                raise AILangSyntaxError("en expresión, '{' inicia un dict key:value", t.line, t.col)
            self.expect("RBRACE")
            return A.DictLit([], [])
        raise AILangSyntaxError(f"expresión inválida cerca de {t.value!r}", t.line, t.col)


def parse(source: str) -> A.Program:
    return Parser(tokenize(source)).parse()
