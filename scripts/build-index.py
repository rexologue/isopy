#!/usr/bin/env python3
"""
build-index.py  —  builds index.json from manifest.json in astral-sh/python-build-standalone
"""

import json, os, re, sys, pathlib, urllib.request, urllib.error, gzip, io

ARCH = "x86_64-unknown-linux-gnu"                         
RAW_URL = (
    "https://raw.githubusercontent.com/"
    "astral-sh/python-build-standalone/main/manifest.json.gz"
)                                                         

RX = re.compile(rf"cpython-(\d+\.\d+\.\d+)\+.*{ARCH}.*install_only")

def fetch_manifest() -> dict:
    req = urllib.request.Request(
        RAW_URL,
        headers={
            "User-Agent": "isopy-index-builder/0.3",
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip" or RAW_URL.endswith(".gz"):
                data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
            return json.loads(data)
    except urllib.error.URLError as e:
        sys.exit(f"❌  Cannot download manifest.json: {e}")

def build_index(manifest: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in manifest["files"]:
        name = entry["filename"]
        if (m := RX.match(name)) and m.group(1) not in out:
            out[m.group(1)] = entry["download_url"]
    return out

def main() -> None:
    manifest = fetch_manifest()
    index = build_index(manifest)
    pathlib.Path("index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"✔ index.json generated: {len(index)} versions (from manifest)")

if __name__ == "__main__":
    main()
