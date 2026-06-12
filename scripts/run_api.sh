#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

export http_proxy="${HTTP_PROXY:-socks5://192.168.1.159:10808}"
export https_proxy="${HTTPS_PROXY:-socks5://192.168.1.159:10808}"
export HTTP_PROXY="${HTTP_PROXY:-socks5://192.168.1.159:10808}"
export HTTPS_PROXY="${HTTPS_PROXY:-socks5://192.168.1.159:10808}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8}"
export no_proxy="$NO_PROXY"

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"

# Debug mode: enable debugpy for VSCode debugging
if [[ "${1:-}" == "--debug" ]]; then
  echo "Starting in DEBUG mode..."
  export DEBUG=1
  python -m debugpy --listen 0.0.0.0:5678 -m uvicorn ai_search_agent.api:app --host 0.0.0.0 --port 18000 --reload
else
  uvicorn ai_search_agent.api:app --host 0.0.0.0 --port 18000 --reload
fi