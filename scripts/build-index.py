#!/usr/bin/env python3
"""
build-index.py – builds index.json for isopy
"""

import json, re, requests, sys, pathlib

ARCH = "x86_64-unknown-linux-gnu"            
RX   = re.compile(rf"cpython-(\d+\.\d+\.\d+)\+.*{ARCH}.*install_only")

out  = {}
page = 1
while True:
    url = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"
    rels = requests.get(url, params={"per_page": 30, "page": page}, timeout=30).json()
    if not rels:                     # пустая страница – всё, вышли
        break
    for rel in rels:
        for a in rel["assets"]:
            if (m := RX.match(a["name"])) and m.group(1) not in out:
                out[m.group(1)] = a["browser_download_url"]
    page += 1

pathlib.Path("index.json").write_text(json.dumps(out, indent=2) + "\n")
print(f"✔  index.json written with {len(out)} versions")
