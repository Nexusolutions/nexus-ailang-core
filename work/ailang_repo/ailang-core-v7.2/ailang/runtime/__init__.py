"""ailang.runtime — runtime components.

P3-9: capability enforcement, scheduler, memory model.
"""
from __future__ import annotations

from ailang.runtime.capabilities import (
    KNOWN_CAPABILITIES,
    EFFECT_TO_CAPABILITY,
    CapabilityContext,
    CapabilityError,
    get_default_context,
    set_default_context,
    reset_default_context,
    require,
    parse_cli_capabilities,
)

__all__ = [
    "KNOWN_CAPABILITIES", "EFFECT_TO_CAPABILITY",
    "CapabilityContext", "CapabilityError",
    "get_default_context", "set_default_context", "reset_default_context",
    "require", "parse_cli_capabilities",
]
