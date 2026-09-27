#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$HOME/Desktop/ARC_CLOUD_BUNDLE_$STAMP"
ARCHIVE="$HOME/Desktop/ARC_CLOUD_BUNDLE_$STAMP.tar.gz"

mkdir -p "$OUT_DIR/ARC-Scheduler-Arena"

rsync -a ./ "$OUT_DIR/ARC-Scheduler-Arena/" \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='.venv-cloud/' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='.pytest_cache/' \
    --exclude='.mypy_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.DS_Store' \
    --exclude='*.pyc' \
    --exclude='*.zip' \
    --exclude='*.tar.gz' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='*.pem' \
    --exclude='*.key' \
    --exclude='id_rsa*' \
    --exclude='id_ed25519*' \
    --exclude='*.sqlite3' \
    --exclude='*.db'

cat > "$OUT_DIR/DEPLOYMENT_PROVENANCE.txt" <<PROV
created_at=$(date -Iseconds)
git_branch=$(git branch --show-current 2>/dev/null || true)
git_head=$(git rev-parse HEAD 2>/dev/null || true)
requirements_sha256=$(shasum -a 256 backend/requirements-lock.txt | awk '{print $1}')
PROV

tar -C "$OUT_DIR" \
    -czf "$ARCHIVE" \
    ARC-Scheduler-Arena \
    DEPLOYMENT_PROVENANCE.txt

shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256"

rm -rf "$OUT_DIR"

echo "ARC CLOUD BUNDLE READY"
echo "$ARCHIVE"
cat "$ARCHIVE.sha256"

open -R "$ARCHIVE" 2>/dev/null || true
