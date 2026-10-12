#!/usr/bin/env bash
# reproduce_lint.sh — Reproduce el job de lint del CI.
set -euxo pipefail

cd /home/z/my-project/work/ailang_repo/ailang-core-v7.2

# Fresh venv
python -m venv /tmp/lint_venv
source /tmp/lint_venv/bin/activate

python --version
python -m pip install --upgrade pip

# Install deps (exactly as CI lint job does)
pip install numpy cryptography hypothesis pytest

# Install AILang (editable)
pip install -e .

# Self-lint (with bash conditional for missing examples/)
echo "=== Self-lint ==="
if [ ! -d examples ]; then
    echo "examples/ directory not found — skipping self-lint"
else
    for f in examples/core_demo.ailang examples/modules_demo.ailang; do
        if [ -f "$f" ]; then
            python -m ailang lint "$f"
        fi
    done
fi
echo "Lint exit: $?"

# Self-format check
echo "=== Self-format check ==="
if [ ! -d examples ]; then
    echo "examples/ directory not found — skipping format idempotency check"
else
    python -c "
from ailang.fmt import format_ast
import pathlib
for f in pathlib.Path('examples').glob('*.ailang'):
    src = f.read_text(encoding='utf-8')
    out1 = format_ast(src)
    out2 = format_ast(out1)
    assert out1 == out2, f'format_ast no idempotente: {f}'
print('format_ast idempotency: OK')
"
fi
echo "Format exit: $?"

deactivate
