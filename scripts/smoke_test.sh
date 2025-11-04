#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-http://127.0.0.1:8000}

echo "Smoke test: base=$BASE"

echo -n "GET /productos -> "
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/productos?page=1&size=1")
if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then echo "OK ($code)"; else echo "FAIL ($code)"; exit 2; fi

echo -n "GET /categorias -> "
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/categorias")
if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then echo "OK ($code)"; else echo "FAIL ($code)"; exit 3; fi

echo -n "GET /_latency -> "
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/_latency")
if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then echo "OK ($code)"; else echo "WARN ($code)"; fi

echo "All smoke checks completed."
