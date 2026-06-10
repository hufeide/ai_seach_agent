#!/usr/bin/env bash
set -euo pipefail

curl -X POST "http://127.0.0.1:18000/search-agent" \
  -H "Content-Type: application/json" \
  -d '{"question":"最近 LangGraph 的 StateGraph 主要怎么用？","mode":"deep"}'
