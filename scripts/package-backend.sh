#!/usr/bin/env bash
###############################################################################
# Package only the backend + integrated security modules into a zip archive.
#
# Produces backend-integrated-modules.zip in the repo root, containing:
#   - executor/            FastAPI backend + integration bridges
#   - modules_unzipped/    integrated security modules (discovery, JWT, mutation,
#                          crawler, TLL-alpha)
#   - backend support files (requirements.txt, run scripts, Dockerfile.api)
#
# Excludes the frontend, node_modules, Python caches, and local .db files.
#
# Usage:  ./scripts/package-backend.sh
###############################################################################
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="backend-integrated-modules.zip"
rm -f "$OUT"

zip -r "$OUT" \
  executor \
  modules_unzipped \
  requirements.txt \
  run.py \
  run_worker.py \
  start-fullstack.sh \
  Dockerfile.api \
  -x "*/__pycache__/*" "*.pyc" "*/.pytest_cache/*" "*/node_modules/*" "*/*.db"

echo ""
echo "Created $ROOT/$OUT"
