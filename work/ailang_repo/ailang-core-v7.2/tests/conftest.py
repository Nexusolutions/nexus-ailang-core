"""conftest.py — fixtures globales para tests de AILang.

AUD-030: el default context ahora es restrictive (deny all). Los tests
que ejercitan stdlib functions (io, http, etc.) necesitan capabilities
concedidas. Este conftest instala un contexto permissive por defecto
para todos los tests, EXCEPTO los que explícitamente testean capabilities.
"""
import pytest


@pytest.fixture(autouse=True)
def permissive_capabilities():
    """Auto-fixture: instala contexto permissive para cada test.

    Tests que quieran verificar capabilities restrictivas pueden usar:
        from ailang.runtime.capabilities import set_default_context, CapabilityContext
        set_default_context(CapabilityContext.restrictive())
    """
    from ailang.runtime.capabilities import (
        set_default_context,
        reset_default_context,
        CapabilityContext,
    )
    set_default_context(CapabilityContext.permissive())
    yield
    reset_default_context()
