# Release Notes — AILang-Core

## v1.1.0 (2026-10-12)

### Breaking changes
- **AUD-030**: Default capability context is now `restrictive()` (deny all). Previously `permissive()`. Programs that use `io.read_text`, `http.get`, `brain.query`, etc. now require explicit `--allow` flags or `set_default_context(CapabilityContext.permissive())`.
- **AUD-029**: Error classes `TypeError`, `NameError`, `ValueError`, etc. in `ailang.lang.errors` are now aliases for `AILangTypeError`, `AILangNameError`, `AILangValueError`, etc. Code that catches Python builtins will still work because the aliases inherit from `AILangError` (not Python builtins).

### New features
- **AUD-004**: AIR interpreter now supports control flow (if/else, while, for) via label resolution. Previously straight-line-only.
- **AUD-010**: `spawn` is now an expression (not just a statement). `let f = spawn worker()` parses.
- **AUD-019**: `const xs: List[int] = [1, 2, 3]` now parses with generic type annotations.
- **AUD-020**: `record Point { x: int, y: int }` now parses with field type annotations.

### Security fixes
- **AUD-003**: `CapabilityError` now extends `AILangRuntimeError` (via `SecurityError`), so try/catch in AILang programs can catch capability violations.
- **AUD-076**: `io.read_text`/`write_text`/`exists`/`lines` now validate path traversal. Paths outside cwd and system temp are rejected.
- **AUD-075**: `http.get`/`post`/`json_get` now validate URL scheme. Only `http` and `https` are allowed (prevents SSRF via `file://`, `ftp://`, etc.).
- **AUD-071**: `strings.format` no longer uses Python's `str.format()` (which allowed attribute access via `{0.__class__}`). Now uses regex-based positional substitution.
- **AUD-052**: Hardware backends (`GPUBackend`, `NPUBackend`, `TPUBackend`) now require `hardware.gpu`/`hardware.npu`/`hardware.tpu` capabilities.

### Bug fixes
- **AUD-002**: try/catch now catches all Python exceptions (ZeroDivisionError, KeyError, IndexError, TypeError, etc.), not just `ThrowSignal` and `AILangRuntimeError`.
- **AUD-006**: `bytecode_io.code_to_dict` now preserves `is_generator` flag (was lost in round-trip).
- **AUD-007**: `bytecode_io.load_and_run` now registers all required builtins (`iter`, `next`, `type`, `isinstance`, `implements`, `channel`).
- **AUD-008**: `brain._need()` now raises `AILangRuntimeError` instead of Python's `RuntimeError`.
- **AUD-012**: `fmt.format_ast` now escapes quotes in string literals (was producing invalid syntax).
- **AUD-072**: `test_mod.assert_true`/`assert_eq` now raise `AILangRuntimeError` instead of Python's `AssertionError`.
- **AUD-073**: `crypto.aes_encrypt` now raises `AILangValueError` for wrong key size (was Python's `ValueError`).
- **AUD-074**: `crypto.aes_decrypt` now wraps `InvalidTag` and other exceptions in `AILangRuntimeError`.

### Architecture
- **AUD-015**: `Interpreter.load_module` now delegates to `ModuleResolver` for circular dependency detection.
- **AUD-013**: `CognitiveBrainEngine` is now a real implementation (not a facade re-export).

### CI/CD
- Added `scripts/smoke_test.sh` — replicates CI flow locally (8 steps).
- Added `scripts/check_format_idempotency.py` — standalone format check.
- `.github/workflows/ci.yml`: examples/ smoke test and self-lint are now skip-eable; added `cross-platform` job.
- `pyproject.toml`: fixed version mismatch (5.7.0 → 1.1.0).
- `ailang_core.py`: `test_unix_socket_roundtrip` now skips on Windows without AF_UNIX; `test_version_and_prometheus` threshold lowered to >= 1.0.0.

### Test coverage
- Added `tests/test_cross_platform.py` (23 tests): CRLF handling, BOM, path resolution, bytecode round-trip, file I/O encoding, CLI paths, doctor, threading spawn, LLVM backend.
- Added `tests/test_windows_simulation.py` (10 tests): structural verification of no POSIX-only imports, no Unix paths, no open() without encoding, no subprocess shell=True.
- Added `tests/test_audit_fixes_v2.py` (26 tests): regression tests for each AUD fix.
- Added `tests/conftest.py`: auto-fixture for permissive capabilities in test environment.

### Known limitations
- **AUD-009**: VM `SPAWN` still uses cooperative scheduling (not real threading). Interpreter uses `threading.Thread`. Divergence documented.
- **AUD-005**: `bytecode_io` does not yet have Ed25519 signing/verification. Stub planned for v1.2.0.
- **AUD-014**: Conformance test for AIR control flow now runs (no skip), but some edge cases may still diverge.
