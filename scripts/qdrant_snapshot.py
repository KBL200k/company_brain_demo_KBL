"""Move the built vector index between machines without re-embedding (re-indexing the reviews takes ~1 hour on CPU).

  python scripts/qdrant_snapshot.py export     # source machine -> data/snapshots/<collection>.snapshot.gz
  python scripts/qdrant_snapshot.py import     # target machine (Qdrant running) <- data/snapshots/

Uses the Qdrant REST API at QDRANT_URL (default http://127.0.0.1:6333). Import replaces existing collections
with the same name.
"""
import argparse
import gzip
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
SNAP_DIR = ROOT / "data" / "snapshots"
COLLECTIONS = ["kb", "reviews"]
URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
HEADERS = {"api-key": os.environ["QDRANT_API_KEY"]} if os.getenv("QDRANT_API_KEY") else {}


def export(client):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    for name in COLLECTIONS:
        print(f"{name}: creating snapshot ...", flush=True)
        r = client.post(f"{URL}/collections/{name}/snapshots", params={"wait": "true"})
        r.raise_for_status()
        snap = r.json()["result"]["name"]
        # snapshots are mostly preallocated empty space: gzip shrinks them ~50-100x for transfer
        dest = SNAP_DIR / f"{name}.snapshot.gz"
        with client.stream("GET", f"{URL}/collections/{name}/snapshots/{snap}") as resp:
            resp.raise_for_status()
            with gzip.open(dest, "wb", compresslevel=1) as f:
                for chunk in resp.iter_bytes(1 << 20):
                    f.write(chunk)
        client.delete(f"{URL}/collections/{name}/snapshots/{snap}")  # don't keep a copy inside Qdrant
        print(f"{name}: {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")


def import_(client, target_suffix=""):
    for name in COLLECTIONS:
        src = SNAP_DIR / f"{name}.snapshot.gz"
        if not src.exists():
            sys.exit(f"missing {src}; run 'export' on the source machine and copy data/snapshots/ here")
        target = name + target_suffix
        print(f"{target}: restoring from {src.name} ({src.stat().st_size / 1e6:.1f} MB) ...", flush=True)
        t = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / f"{name}.snapshot"
            with gzip.open(src, "rb") as zin, open(raw, "wb") as out:
                shutil.copyfileobj(zin, out, 1 << 20)
            with open(raw, "rb") as f:
                r = client.post(f"{URL}/collections/{target}/snapshots/upload",
                                params={"priority": "snapshot", "wait": "true"},
                                files={"snapshot": (raw.name, f, "application/octet-stream")})
        r.raise_for_status()
        count = client.post(f"{URL}/collections/{target}/points/count", json={"exact": True}).json()["result"]["count"]
        print(f"{target}: restored, {count} points ({time.time() - t:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["export", "import"])
    ap.add_argument("--suffix", default="", help=argparse.SUPPRESS)  # testing: import under another name
    args = ap.parse_args()
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(1800.0)) as client:
        try:
            client.get(URL).raise_for_status()
        except httpx.HTTPError as e:
            sys.exit(f"Qdrant is not reachable at {URL} ({e}). Start it first.")
        export(client) if args.action == "export" else import_(client, args.suffix)


if __name__ == "__main__":
    main()
