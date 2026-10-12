#!/usr/bin/env bash
# reproduce_ci.sh — Reproduce los pasos exactos del CI en local.
set -euxo pipefail

cd /home/z/my-project/work/ailang_repo/ailang-core-v7.2

# Create a fresh venv to mimic CI
python -m venv /tmp/ci_venv
source /tmp/ci_venv/bin/activate

python --version
python -m pip install --upgrade pip

# Step: Install dependencies
pip install numpy
pip install cryptography
pip install hypothesis
pip install pytest pytest-cov

# Step: Install AILang (editable)
pip install -e .

echo "=== ailang doctor ==="
python -m ailang doctor
echo "Exit: $?"

echo "=== pytest tests/ ==="
python -m pytest tests/ -v --tb=short
echo "Exit: $?"

echo "=== ailang_core.py test ==="
python ailang_core.py test
echo "Exit: $?"

echo "=== version consistency ==="
python -c "from ailang.versions import __version__; print('version:', __version__)"
python -m ailang --version
echo "Exit: $?"

deactivate
