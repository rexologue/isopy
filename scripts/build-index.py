#!/usr/bin/env python3
"""
build-index.py — формирует index.json для isopy
                (без GitHub API, только статический manifest.json)
"""

from __future__ import annotations
import json, os, re, sys, pathlib, urllib.request, urllib.error, gzip, io

ARCH = "x86_64-unknown-linux-gnu"
RAW_BASE = "https://raw.githubusercontent.com/astral-sh/python-build-standalone/main/"
CANDIDATES = ["manifest.json", "manifest.json.gz"]        # пробуем по порядку
RX = re.compile(rf"cpython-(\d+\.\d+\.\d+)\+.*{ARCH}.*install_only")

def fetch_manifest() -> dict:
    headers = {"User-Agent": "isopy-index-builder/0.4"}
    for fname in CANDIDATES:
        url = RAW_BASE + fname
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=30
            ) as resp:
                data = resp.read()
                if fname.endswith(".gz"):
                    data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
                print(f"✔  downloaded {fname}  ({len(data)//1024} KB)")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue          # пробуем следующий кандидат
            print(f"❌  HTTP {e.code} on {fname}: {e.reason}")
            sys.exit(0)
        except urllib.error.URLError as e:
            print(f"❌  Network error: {e.reason}")
            sys.exit(0)
    print("❌  manifest.json not found in repo — aborting.")
    sys.exit(0)

def build_index(manifest: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in manifest["files"]:
        n = f["filename"]
        if (m := RX.match(n)) and m.group(1) not in out:
            out[m.group(1)] = f["download_url"]
    return out

def main() -> None:
    manifest = fetch_manifest()
    index = build_index(manifest)
    pathlib.Path("index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"✔  index.json written ({len(index)} versions)")

if __name__ == "__main__":
    main()

