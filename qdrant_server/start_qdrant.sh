#!/usr/bin/env sh
# Start Qdrant: API on http://localhost:6333, dashboard at http://localhost:6333/dashboard
cd "$(dirname "$0")"
export QDRANT__STORAGE__STORAGE_PATH=./storage
export QDRANT__SERVICE__STATIC_CONTENT_DIR=./static
export QDRANT__TELEMETRY_DISABLED=true
# Only accept connections from this machine
export QDRANT__SERVICE__HOST=127.0.0.1
exec ./qdrant
