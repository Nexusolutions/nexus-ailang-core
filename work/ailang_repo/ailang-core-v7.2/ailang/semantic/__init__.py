"""ailang.semantic — pass semánticos del lenguaje.

P3-6 (diagnostics), P3-8 (effects), P3-9 (capabilities).
"""
from __future__ import annotations

from ailang.semantic.effects import (
    EFFECTS,
    BUILTIN_EFFECTS,
    STD_MODULE_EFFECTS,
    EffectIssue,
    infer_effects,
    check_effects,
    check_source as check_effects_source,
)

__all__ = [
    "EFFECTS", "BUILTIN_EFFECTS", "STD_MODULE_EFFECTS",
    "EffectIssue",
    "infer_effects", "check_effects", "check_effects_source",
]
