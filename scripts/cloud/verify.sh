#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY="$ROOT/.venv-cloud/bin/python"

[[ -x "$PY" ]] || {
    echo "ERROR: .venv-cloud missing"
    exit 1
}

echo "=== ARC CLOUD VERIFICATION ==="
echo "host: $(hostname)"
echo "logical CPUs: $(nproc)"
echo "python: $("$PY" --version)"

"$PY" -m pytest \
    arena/tuning/tests/test_parallel_execution.py \
    arena/experiments/tests \
    -q

"$PY" -m pytest arena -q

echo "ARC CLOUD HOST VERIFIED"
