"""Framework mínimo de tests en AILang / host."""
from ailang.lang.errors import AILangRuntimeError

_passed = 0
_failed = 0
_errors = []

def _reset():
    global _passed, _failed, _errors
    _passed = 0
    _failed = 0
    _errors = []

def assert_true(cond, msg="assert_true failed"):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        _errors.append(str(msg))
        # AUD-072: raise AILangRuntimeError (not Python's AssertionError)
        # so try/catch del lenguaje AILang puede atraparlo
        raise AILangRuntimeError(str(msg), code="E042")

def assert_eq(a, b, msg=None):
    global _passed, _failed
    if a == b:
        _passed += 1
    else:
        _failed += 1
        m = msg or f"assert_eq: {a!r} != {b!r}"
        _errors.append(m)
        # AUD-072: raise AILangRuntimeError (not Python's AssertionError)
        raise AILangRuntimeError(m, code="E042")

def assert_raises(fn, *args):
    global _passed, _failed
    try:
        fn(*args)
        _failed += 1
        raise AILangRuntimeError("assert_raises: no exception", code="E042")
    except AILangRuntimeError:
        raise
    except Exception:
        _passed += 1

def summary():
    return {"passed": _passed, "failed": _failed, "errors": list(_errors)}

def reset():
    _reset()
    return None
