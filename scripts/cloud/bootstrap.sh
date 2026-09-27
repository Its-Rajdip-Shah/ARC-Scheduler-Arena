#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

EXPECTED_PYTHON="3.14.5"
VENV="$ROOT/.venv-cloud"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "ERROR: cloud bootstrap is intended for Linux."
    exit 1
fi

echo "=== ARC CLOUD BOOTSTRAP ==="
echo "root: $ROOT"
echo "host: $(hostname)"
echo "kernel: $(uname -a)"
echo "logical CPUs: $(nproc)"
echo

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl ca-certificates git build-essential libpq-dev

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

uv python install "$EXPECTED_PYTHON"

if [[ ! -x "$VENV/bin/python" ]]; then
    uv venv --python "$EXPECTED_PYTHON" "$VENV"
fi

ACTUAL_PYTHON="$("$VENV/bin/python" -c 'import platform; print(platform.python_version())')"

if [[ "$ACTUAL_PYTHON" != "$EXPECTED_PYTHON" ]]; then
    echo "ERROR: expected Python $EXPECTED_PYTHON, got $ACTUAL_PYTHON"
    exit 1
fi

uv pip sync \
    --python "$VENV/bin/python" \
    backend/requirements-lock.txt

uv pip freeze --python "$VENV/bin/python" > /tmp/arc-cloud-installed.txt

"$VENV/bin/python" - <<'PYLOCK'
from pathlib import Path
import re
import sys

def norm_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

def load_pins(path: str):
    out = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise SystemExit(f"non-pinned requirement encountered: {line!r}")
        name, version = line.split("==", 1)
        key = norm_name(name.strip())
        version = version.strip()
        if key in out and out[key] != version:
            raise SystemExit(f"conflicting versions for {key}: {out[key]} vs {version}")
        out[key] = version
    return out

expected = load_pins("backend/requirements-lock.txt")
installed = load_pins("/tmp/arc-cloud-installed.txt")

if expected != installed:
    missing = sorted(set(expected) - set(installed))
    extra = sorted(set(installed) - set(expected))
    changed = sorted(
        k for k in set(expected) & set(installed)
        if expected[k] != installed[k]
    )

    if missing:
        print("missing:")
        for k in missing:
            print(f"  {k}=={expected[k]}")
    if extra:
        print("extra:")
        for k in extra:
            print(f"  {k}=={installed[k]}")
    if changed:
        print("version mismatches:")
        for k in changed:
            print(f"  {k}: expected {expected[k]}, installed {installed[k]}")

    sys.exit("ERROR: installed environment differs from requirements-lock.txt")

print(f"dependency lock: exact ({len(expected)} normalized packages)")
PYLOCK

if [[ -e backend/.env ]]; then
    echo "ERROR: backend/.env already exists."
    exit 1
fi

SECRET_KEY="$("$VENV/bin/python" - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)"

FERNET_KEY="$("$VENV/bin/python" - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
)"

DB_PATH="$ROOT/backend/arena-cloud.sqlite3"

cat > backend/.env <<ENV
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=
CORS_ALLOWED_ORIGINS=
DATABASE_URL=sqlite:///$DB_PATH
ARC_FIELD_ENCRYPTION_KEY=$FERNET_KEY
CANVAS_BASE_URL=https://canvas.sydney.edu.au
ENV

chmod 600 backend/.env

(
    cd backend
    "$VENV/bin/python" manage.py migrate --noinput
)

echo "ARC CLOUD BOOTSTRAP COMPLETE"
