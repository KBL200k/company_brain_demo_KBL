"""Download the Qdrant server binary + web dashboard for this OS into qdrant_server/ and write start scripts.

  python scripts/setup_qdrant.py               # Qdrant v1.19.2 (the version this project was built with)
  python scripts/setup_qdrant.py --version v1.19.2

Then start it with qdrant_server/start_qdrant.bat (Windows) or qdrant_server/start_qdrant.sh (Linux/macOS).
Alternative without a binary: docker run -p 127.0.0.1:6333:6333 -v ./qdrant_server/storage:/qdrant/storage qdrant/qdrant:v1.19.2
"""
import argparse
import platform
import shutil
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "qdrant_server"
WEB_UI = "https://github.com/qdrant/qdrant-web-ui/releases/download/v0.2.19/dist-qdrant.zip"

ASSETS = {
    ("Windows", "AMD64"): "qdrant-x86_64-pc-windows-msvc.zip",
    ("Linux", "x86_64"): "qdrant-x86_64-unknown-linux-gnu.tar.gz",
    ("Linux", "aarch64"): "qdrant-aarch64-unknown-linux-musl.tar.gz",
    ("Darwin", "arm64"): "qdrant-aarch64-apple-darwin.tar.gz",
    ("Darwin", "x86_64"): "qdrant-x86_64-apple-darwin.tar.gz",
}

BAT = """@echo off
REM Start Qdrant: API on http://localhost:6333, dashboard at http://localhost:6333/dashboard
cd /d %~dp0
set QDRANT__STORAGE__STORAGE_PATH=./storage
set QDRANT__SERVICE__STATIC_CONTENT_DIR=./static
set QDRANT__TELEMETRY_DISABLED=true
REM Only accept connections from this machine
set QDRANT__SERVICE__HOST=127.0.0.1
qdrant.exe
"""

SH = """#!/usr/bin/env sh
# Start Qdrant: API on http://localhost:6333, dashboard at http://localhost:6333/dashboard
cd "$(dirname "$0")"
export QDRANT__STORAGE__STORAGE_PATH=./storage
export QDRANT__SERVICE__STATIC_CONTENT_DIR=./static
export QDRANT__TELEMETRY_DISABLED=true
# Only accept connections from this machine
export QDRANT__SERVICE__HOST=127.0.0.1
exec ./qdrant
"""


def download(url, dest):
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1.19.2")
    ap.add_argument("--dest", type=Path, default=DEST, help="install folder (default: qdrant_server/)")
    args = ap.parse_args()
    dest = args.dest
    key = (platform.system(), platform.machine())
    asset = ASSETS.get(key)
    if not asset:
        raise SystemExit(f"No prebuilt Qdrant for {key}; use Docker instead (see the docstring).")
    dest.mkdir(exist_ok=True)
    tmp = dest / asset
    download(f"https://github.com/qdrant/qdrant/releases/download/{args.version}/{asset}", tmp)
    if asset.endswith(".zip"):
        with zipfile.ZipFile(tmp) as z:
            z.extractall(dest)
    else:
        with tarfile.open(tmp) as t:
            t.extractall(dest)
        binary = dest / "qdrant"
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    tmp.unlink()

    ui_zip = dest / "webui.zip"
    download(WEB_UI, ui_zip)
    shutil.rmtree(dest / "static", ignore_errors=True)
    with zipfile.ZipFile(ui_zip) as z:
        z.extractall(dest / "_ui")
    (dest / "_ui" / "dist").rename(dest / "static")
    shutil.rmtree(dest / "_ui")
    ui_zip.unlink()

    (dest / "start_qdrant.bat").write_text(BAT, encoding="utf-8")
    sh = dest / "start_qdrant.sh"
    sh.write_text(SH, encoding="utf-8", newline="\n")
    sh.chmod(sh.stat().st_mode | stat.S_IEXEC)
    print(f"Qdrant {args.version} installed in {dest}. Start it with "
          + ("qdrant_server\\start_qdrant.bat" if key[0] == "Windows" else "./qdrant_server/start_qdrant.sh"))


if __name__ == "__main__":
    main()
