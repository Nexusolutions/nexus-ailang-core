#!/usr/bin/env bash
# smoke_test.sh — Replica localmente el flujo del CI de GitHub Actions.
#
# Verifica que el proyecto AILang-Core funcione correctamente en el entorno
# local antes de hacer push. Especialmente útil para detectar problemas de
# portabilidad antes de que el CI los encuentre.
#
# Uso:
#   ./scripts/smoke_test.sh           # Ejecuta todo el smoke test
#   ./scripts/smoke_test.sh --quick   # Solo tests críticos (sin monolito ni benchmarks)
#   ./scripts/smoke_test.sh --help    # Muestra ayuda
#
# Salida:
#   - Exit code 0 si todo pasa
#   - Exit code !=0 si algo falla (con detalles en stderr)
#
# Requisitos:
#   - Python 3.11+
#   - pip install numpy cryptography hypothesis pytest pytest-cov
#   - pip install -e .  (editable)
set -uo pipefail

# ---------------------------------------------------------------------------
# Colores y helpers
# ---------------------------------------------------------------------------
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
NC=$'\033[0m'

info()  { printf "%s[INFO]%s %s\n" "$BLUE" "$NC" "$*"; }
ok()    { printf "%s[OK]%s   %s\n" "$GREEN" "$NC" "$*"; }
warn()  { printf "%s[WARN]%s %s\n" "$YELLOW" "$NC" "$*"; }
fail()  { printf "%s[FAIL]%s %s\n" "$RED" "$NC" "$*" >&2; }

banner() {
    echo
    echo "============================================================"
    echo "  AILang-Core — Smoke Test (CI replica)"
    echo "  Platform: $(uname -s) $(uname -r)"
    echo "  Date:     $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "============================================================"
    echo
}

# ---------------------------------------------------------------------------
# Argumentos
# ---------------------------------------------------------------------------
QUICK=0
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    sed -n '2,20p' "$0"
    exit 0
fi
if [[ "${1:-}" == "--quick" ]]; then
    QUICK=1
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight() {
    info "Pre-flight checks..."

    if ! command -v python &>/dev/null; then
        fail "Python no encontrado en PATH"
        exit 1
    fi
    PY_VERSION=$(python --version 2>&1)
    info "Python: $PY_VERSION"

    if [[ ! -f "pyproject.toml" || ! -d "ailang" ]]; then
        fail "No se está en la raíz del proyecto (falta pyproject.toml o ailang/)"
        fail "Cwd actual: $(pwd)"
        exit 1
    fi
    ok "Directorio del proyecto correcto"

    local missing=()
    python -c "import numpy" 2>/dev/null || missing+=("numpy")
    python -c "import cryptography" 2>/dev/null || missing+=("cryptography")
    python -c "import hypothesis" 2>/dev/null || missing+=("hypothesis")
    python -c "import pytest" 2>/dev/null || missing+=("pytest")

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Dependencias faltantes: ${missing[*]}"
        info "Instalando dependencias faltantes..."
        pip install --quiet "${missing[@]}" 2>&1 | tail -3 || {
            fail "No se pudieron instalar las dependencias"
            exit 1
        }
        ok "Dependencias instaladas"
    else
        ok "Dependencias críticas presentes"
    fi

    if ! python -c "import ailang" 2>/dev/null; then
        warn "Paquete ailang no instalado; instalando en modo editable..."
        pip install --quiet -e . 2>&1 | tail -3 || {
            fail "No se pudo instalar el paquete"
            exit 1
        }
        ok "Paquete instalado"
    else
        ok "Paquete ailang importable"
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 1: ailang doctor
# ---------------------------------------------------------------------------
step_doctor() {
    info "Step 1: ailang doctor..."
    if python -m ailang doctor > /tmp/ailang_doctor.out 2>&1; then
        tail -5 /tmp/ailang_doctor.out
        ok "ailang doctor OK"
        return 0
    else
        tail -20 /tmp/ailang_doctor.out >&2
        fail "ailang doctor falló"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 2: Unit tests
# ---------------------------------------------------------------------------
step_unit_tests() {
    info "Step 2: Unit tests (pytest tests/ -v --tb=short)..."
    if python -m pytest tests/ --tb=short -q > /tmp/ailang_pytest.out 2>&1; then
        tail -5 /tmp/ailang_pytest.out
        ok "Unit tests OK"
        return 0
    else
        tail -30 /tmp/ailang_pytest.out >&2
        fail "Unit tests fallaron"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 3: Monolith embedded tests
# ---------------------------------------------------------------------------
step_monolith() {
    if [[ "$QUICK" -eq 1 ]]; then
        info "Step 3: SKIPPED (--quick)"
        return 0
    fi
    info "Step 3: Monolith embedded tests (python ailang_core.py test)..."
    if python ailang_core.py test > /tmp/ailang_monolith.out 2>&1; then
        tail -3 /tmp/ailang_monolith.out
        ok "Monolith tests OK"
        return 0
    else
        tail -20 /tmp/ailang_monolith.out >&2
        fail "Monolith tests fallaron"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 4: Cross-platform portability tests
# ---------------------------------------------------------------------------
step_cross_platform() {
    info "Step 4: Cross-platform portability tests..."
    if python -m pytest tests/test_cross_platform.py tests/test_windows_simulation.py --tb=short -q > /tmp/ailang_xplat.out 2>&1; then
        tail -5 /tmp/ailang_xplat.out
        ok "Cross-platform tests OK"
        return 0
    else
        tail -30 /tmp/ailang_xplat.out >&2
        fail "Cross-platform tests fallaron"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 5: Version consistency
# ---------------------------------------------------------------------------
step_version() {
    info "Step 5: Version consistency..."
    local v1 v2
    v1=$(python -c "from ailang.versions import __version__; print(__version__)")
    v2=$(python -m ailang --version 2>&1 | awk '{print $2}')
    if [[ "$v1" == "$v2" ]]; then
        ok "Versiones consistentes: $v1"
        return 0
    else
        fail "Versión inconsistente: versions.py=$v1, CLI=$v2"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 6: Examples smoke test (si existe examples/)
# ---------------------------------------------------------------------------
step_examples() {
    if [[ "$QUICK" -eq 1 ]]; then
        info "Step 6: SKIPPED (--quick)"
        return 0
    fi
    info "Step 6: Examples smoke test..."
    if [[ ! -d "examples" ]]; then
        warn "examples/ no existe — saltando este paso"
        return 0
    fi
    local failed=0
    for f in examples/core_demo.ailang examples/modules_demo.ailang examples/oop_demo.ailang examples/selftest.ailang; do
        if [[ -f "$f" ]]; then
            info "  → $f"
            if ! python -m ailang "$f" >/dev/null 2>&1; then
                fail "  $f falló"
                failed=1
            fi
        fi
    done
    if [[ "$failed" -eq 0 ]]; then
        ok "Examples OK"
        return 0
    else
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 7: Format idempotency check
# ---------------------------------------------------------------------------
step_format_idempotency() {
    if [[ "$QUICK" -eq 1 ]]; then
        info "Step 7: SKIPPED (--quick)"
        return 0
    fi
    info "Step 7: Format idempotency check..."
    if [[ ! -d "examples" ]]; then
        warn "examples/ no existe — saltando idempotency check"
        return 0
    fi
    local tmp_py
    tmp_py=$(mktemp /tmp/ailang_fmt_idem.XXXXXX.py)
    cat > "$tmp_py" <<'PYEOF'
from ailang.fmt import format_ast
import pathlib
failed = []
for f in pathlib.Path('examples').glob('*.ailang'):
    src = f.read_text(encoding='utf-8')
    out1 = format_ast(src)
    out2 = format_ast(out1)
    if out1 != out2:
        failed.append(str(f))
if failed:
    print("FAIL: format_ast no idempotente en:", failed)
    raise SystemExit(1)
print("format_ast idempotency: OK")
PYEOF
    if python "$tmp_py"; then
        ok "Format idempotency OK"
        rm -f "$tmp_py"
        return 0
    else
        fail "Format idempotency check falló"
        rm -f "$tmp_py"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Step 8: Structural portability scan
# ---------------------------------------------------------------------------
step_structural_scan() {
    info "Step 8: Structural portability scan..."
    local tmp_py
    tmp_py=$(mktemp /tmp/ailang_struct_scan.XXXXXX.py)
    cat > "$tmp_py" <<'PYEOF'
import ast
import pathlib
issues = []

posix_only = {"fcntl", "termios", "tty", "resource", "grp", "pwd"}
for py in pathlib.Path("ailang").rglob("*.py"):
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in posix_only:
                    issues.append(f"{py}: import {alias.name} (POSIX-only)")
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[0]
            if mod in posix_only:
                issues.append(f"{py}: from {node.module} import ... (POSIX-only)")

for py in pathlib.Path("ailang").rglob("*.py"):
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "open":
                has_encoding = any(kw.arg == "encoding" for kw in node.keywords)
                has_binary = False
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                    if isinstance(mode, str) and "b" in mode:
                        has_binary = True
                if not has_encoding and not has_binary:
                    issues.append(f"{py}:{node.lineno} open() sin encoding= (rompe en Windows cp1252)")

for py in pathlib.Path("ailang").rglob("*.py"):
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                if node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}:
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            issues.append(f"{py}:{node.lineno} subprocess.{node.func.attr}(shell=True) - no cross-platform")

if issues:
    print("FAIL: Encontrados problemas de portabilidad:")
    for i in issues:
        print("  - " + i)
    raise SystemExit(1)
print("Estructural: sin imports POSIX-only, sin open() sin encoding, sin subprocess shell=True")
PYEOF
    if python "$tmp_py"; then
        ok "Structural scan OK"
        rm -f "$tmp_py"
        return 0
    else
        fail "Structural scan encontro problemas"
        rm -f "$tmp_py"
        return 1
    fi
    echo
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
summary() {
    echo
    echo "============================================================"
    echo "  SMOKE TEST SUMMARY"
    echo "============================================================"
    if [[ ${#FAILURES[@]} -eq 0 ]]; then
        ok "Todos los pasos completados exitosamente"
        echo
        info "Listo para push. El CI de GitHub deberia pasar en los tres OS."
        exit 0
    else
        fail "Fallaron ${#FAILURES[@]} pasos:"
        for f in "${FAILURES[@]}"; do
            echo "  - $f"
        done
        echo
        warn "Corrige los problemas antes de hacer push."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
declare -a FAILURES=()

banner
preflight

step_doctor             || FAILURES+=("ailang doctor")
step_unit_tests         || FAILURES+=("unit tests")
step_monolith           || FAILURES+=("monolith tests")
step_cross_platform     || FAILURES+=("cross-platform tests")
step_version            || FAILURES+=("version consistency")
step_examples           || FAILURES+=("examples smoke")
step_format_idempotency || FAILURES+=("format idempotency")
step_structural_scan    || FAILURES+=("structural scan")

summary
