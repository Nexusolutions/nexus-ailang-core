from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass
class Program:
    body: List[Any]
    budget_ms: Optional[int] = None


@dataclass
class Let:
    name: str
    value: Any
    type_ann: Optional[str] = None
    line: int = 0


@dataclass
class Assign:
    name: Any  # str | Attr
    value: Any
    line: int = 0


@dataclass
class If:
    test: Any
    body: List[Any]
    orelse: List[Any]
    line: int = 0


@dataclass
class While:
    test: Any
    body: List[Any]
    line: int = 0


@dataclass
class For:
    target: str
    iter: Any
    body: List[Any]
    line: int = 0


@dataclass
class Function:
    name: str
    params: List[str]
    body: List[Any]
    line: int = 0
    is_async: bool = False


@dataclass
class Return:
    value: Any = None
    line: int = 0


@dataclass
class ExprStmt:
    value: Any
    line: int = 0


@dataclass
class Block:
    body: List[Any]


@dataclass
class BinOp:
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp:
    op: str
    operand: Any


@dataclass
class Call:
    func: Any
    args: List[Any]


@dataclass
class Name:
    id: str


@dataclass
class Literal:
    value: Any


@dataclass
class ListLit:
    elts: List[Any]


@dataclass
class DictLit:
    keys: List[Any]
    values: List[Any]


@dataclass
class Index:
    value: Any
    index: Any


@dataclass
class Import:
    module: str
    alias: Optional[str] = None
    line: int = 0


@dataclass
class Try:
    body: List[Any]
    catch_name: str
    catch_body: List[Any]
    line: int = 0


@dataclass
class Throw:
    value: Any
    line: int = 0


@dataclass
class Attr:
    value: Any
    attr: str


@dataclass
class ClassDef:
    name: str
    base: Optional[str]
    methods: List[Any]  # Function nodes
    line: int = 0


@dataclass
class Lambda:
    """fn anónima: fn(a, b) { ... }"""
    params: List[str]
    body: List[Any]
    line: int = 0


@dataclass
class Break:
    line: int = 0


@dataclass
class Continue:
    line: int = 0


@dataclass
class Const:
    name: str
    value: Any
    type_ann: Optional[str] = None
    line: int = 0


@dataclass
class MatchCase:
    pattern: Any  # Literal | Name("_") | list pattern simplified as Literal
    body: List[Any]


@dataclass
class Match:
    subject: Any
    cases: List[MatchCase]
    line: int = 0


@dataclass
class EnumDef:
    name: str
    variants: List[str]
    line: int = 0


@dataclass
class Await:
    value: Any
    line: int = 0


@dataclass
class Yield:
    value: Any = None
    line: int = 0


@dataclass
class InterfaceDef:
    name: str
    methods: List[str]  # method names required
    line: int = 0


@dataclass
class RecordDef:
    name: str
    fields: List[str]
    line: int = 0


@dataclass
class Spawn:
    call: Any  # Call expr
    line: int = 0


@dataclass
class InterpolatedString:
    parts: List[Any]  # alternating Literal str and expr nodes
    line: int = 0
