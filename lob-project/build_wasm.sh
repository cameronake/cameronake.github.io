#!/usr/bin/env bash
# OFFLINE build: compiles the single-threaded engine + browser bindings into
# lob.js / lob.wasm at the repo root, which GitHub Pages then serves as-is.
#
# Needs the Emscripten SDK on PATH:
#   git clone https://github.com/emscripten-core/emsdk
#   cd emsdk && ./emsdk install latest && ./emsdk activate latest
#   source ./emsdk_env.sh        # Windows: emsdk_env.bat
#   emcc --version                 # sanity check
#
# Run from anywhere: bash build_wasm.sh  (or bash /path/to/lob-project/build_wasm.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
INC="$ROOT/include"

emcc -O3 -std=c++20 \
  -I "$INC" \
  "$ROOT/src/order_book.cpp" \
  "$ROOT/wasm/bindings.cpp" \
  -s MODULARIZE=1 \
  -s EXPORT_NAME=LOBModule \
  -s ENVIRONMENT=web,worker \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s "EXPORTED_RUNTIME_METHODS=['ccall','cwrap','UTF8ToString']" \
  -s "EXPORTED_FUNCTIONS=['_lob_reset','_lob_submit_limit','_lob_market','_lob_cancel','_lob_step_feed','_lob_snapshot','_malloc','_free']" \
  -o "$ROOT/lob.js"

echo "built $ROOT/lob.js + $ROOT/lob.wasm"
