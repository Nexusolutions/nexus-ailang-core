"""Análisis semántico — AST → CognitiveIR + comprobaciones Zero-Footprint."""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from ailang.compiler.parser import ASTModule
from ailang.ir.cognitive import (
    CognitiveIR, CognitiveInstruction, CognitiveOp, OP_CAPABILITIES,
)


class SemanticError(Exception):
    pass


def analyze(ast: ASTModule) -> CognitiveIR:
    if ast.budget_ms is None:
        raise SemanticError("Falta purge_after(<n>ms).")
    if not (0 < ast.budget_ms <= 65535):
        raise SemanticError("purge_after fuera de rango 1..65535.")

    instructions: List[CognitiveInstruction] = []
    caps: Set[str] = set()
    memories: Dict[str, str] = {}

    for stmt in ast.stmts:
        try:
            op = CognitiveOp(stmt.op)
        except ValueError:
            continue  # ignore non-cognitive

        if op == CognitiveOp.MEMORY:
            pers = stmt.args.get("persistence", "durable")
            if pers not in ("volatile", "session", "durable"):
                raise SemanticError(f"Línea {stmt.line}: persistence inválida '{pers}'.")
            name = stmt.args.get("name")
            if name is None or "value" not in stmt.args:
                raise SemanticError(f"Línea {stmt.line}: memory requiere name y value.")
            name = str(name)
            if name in memories:
                raise SemanticError(f"Línea {stmt.line}: memoria duplicada '{name}'.")
            memories[name] = str(pers)
            args = dict(stmt.args)
            args["persistence"] = pers
            req = OP_CAPABILITIES[op]
            instructions.append(CognitiveInstruction(op, args, stmt.line, req))
            caps.update(req)
            continue

        if op == CognitiveOp.PERSIST:
            name = stmt.args.get("memory")
            if name is None or str(name) not in memories:
                raise SemanticError(
                    f"Línea {stmt.line}: persist referencia memoria no declarada '{name}'."
                )
            pers = memories[str(name)]
            if pers == "volatile":
                raise SemanticError(
                    f"Línea {stmt.line}: Zero-Footprint — memoria volatile '{name}' "
                    "no puede persistirse."
                )
            args = dict(stmt.args)
            args["persistence"] = pers
            req = OP_CAPABILITIES[op]
            instructions.append(CognitiveInstruction(op, args, stmt.line, req))
            caps.update(req)
            continue

        # brain.* validation deferred to CognitiveIR.validate
        req = OP_CAPABILITIES[op]
        instructions.append(CognitiveInstruction(op, dict(stmt.args), stmt.line, req))
        caps.update(req)

    ir = CognitiveIR(
        instructions=tuple(instructions),
        required_capabilities=tuple(sorted(caps)),
        metadata={"budget_ms": ast.budget_ms},
    ).with_digest()
    ir.validate()
    return ir
