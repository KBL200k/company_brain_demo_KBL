@echo off
REM Start Qdrant: API on http://localhost:6333, dashboard at http://localhost:6333/dashboard
cd /d %~dp0
set QDRANT__STORAGE__STORAGE_PATH=./storage
set QDRANT__SERVICE__STATIC_CONTENT_DIR=./static
set QDRANT__TELEMETRY_DISABLED=true
REM Only accept connections from this machine
set QDRANT__SERVICE__HOST=127.0.0.1
qdrant.exe
