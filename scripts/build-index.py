#!/usr/bin/env python3
"""
build-index.py  —  собирает index.json,
                   парся HTML releases/ страницы (без GitHub API и токенов)
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.request, urllib.error, pathlib, html

ARCH      = "x86_64-unknown-linux-gnu"
BASE_URL  = "https://github.com/astral-sh/python-build-standalone/releases"
MAX_PAGES = 15                         # достаточно на годы вперёд

RX_LINK   = re.compile(
    rf'href="(/astral-sh/python-build-standalone/releases/download/[^"]*?'
    rf'cpython-(\d+\.\d+\.\d+)\+[^"]*?{ARCH}[^"]*?install_only\.tar\.(?:zst|gz))"')

def fetch(page: int) -> str | None:
    url = f"{BASE_URL}?page={page}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "isopy-index-builder/0.5"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        sys.exit(f"HTTP {e.code}: {e.reason}")

def build_index() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in range(1, MAX_PAGES + 1):
        html_page = fetch(p)
        if not html_page:
            break
        for link, ver in RX_LINK.findall(html_page):
            out.setdefault(ver, f"https://github.com{html.unescape(link)}")
        # если нашли все патчи до 3.6 — можно прервать, но это  ≈ микросекунды
        time.sleep(0.1)
    return out

def main() -> None:
    index = build_index()
    if not index:
        sys.exit("❌  ничего не найдено, проверьте структуру страницы.")
    pathlib.Path("index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"✔  index.json written ({len(index)} versions).")

if __name__ == "__main__":
    main()


