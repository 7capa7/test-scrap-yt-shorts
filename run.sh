#!/usr/bin/env bash
# Uruchamia scraper w lokalnym venv (folder .venv w tym projekcie).
# Nic nie instaluje globalnie – żeby wszystko usunąć, skasuj folder .venv.
#
#   ./run.sh https://www.youtube.com/@SERHITO_SH0TY/shorts
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "→ Tworzę venv (.venv)..."
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python scraper.py "$@"
