#!/usr/bin/env python3
"""
isopy – install isolated CPython builds & integrate them with Poetry.
Скачивает архивы python-build-standalone в ~/.isopy/<ver>/bin/python
и даёт команды:
    isopy install 3.13     # скачать новейший патч-релиз 3.13.x
    isopy install 3.13.5   # именно 3.13.5
    isopy list
    isopy use 3.13         # poetry env use ~/.isopy/3.13.z/bin/python
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
from pathlib import Path
from urllib.request import Request, urlopen

# ──────────────────────────────────────────────────────────────────────────────

__version__ = "0.1.1"                       # не забудьте поднять в pyproject.toml
ISOPY_HOME  = Path.home() / ".isopy"
ARCH        = "x86_64-unknown-linux-gnu"
API_ROOT    = ("https://api.github.com/repos/"
               "astral-sh/python-build-standalone")

_RX_ASSET   = re.compile(
    rf"cpython-(\d+\.\d+\.\d+)\+.*{ARCH}.*install_only.*\.(tar\.zst|tar\.gz)$")
_RX_BRANCH  = re.compile(r"^\d+\.\d+$")      # 3.12
_RX_FULLVER = re.compile(r"^\d+\.\d+\.\d+$") # 3.12.10

# ────────────────────────── GitHub helpers ────────────────────────────────────
def _gh_get(endpoint: str,
            params: dict[str, str] | None = None,
            retries: int = 3,
            timeout: float = 15.0) -> list | dict:
    """
    GET /<endpoint>?<params> –> JSON (dict|list)
    • 3 повтора при HTTP 5xx / URLError
    • берёт Bearer $GITHUB_TOKEN, если указан, чтобы снять лимит 60 req/h
    """
    if params is None:
        params = {}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url   = f"{API_ROOT}/{endpoint}"
    if query:
        url += f"?{query}"

    hdrs = {"User-Agent": f"isopy/{__version__}"}
    if tok := os.getenv("GITHUB_TOKEN"):
        hdrs["Authorization"] = f"Bearer {tok}"

    req = Request(url, headers=hdrs)
    for attempt in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if attempt == retries:
                sys.exit(
                    f"❌  GitHub API unreachable ({e}). "
                    "Check internet / proxy / $GITHUB_TOKEN and retry."
                )
            time.sleep(2 * attempt)

def _collect_assets() -> dict[str, str]:
    """
    Собирает {version: download_url} для нашей архитектуры.
    • перебирать pages=1,2,3… с per_page=30 (меньше шансов на 504)
    """
    results: dict[str, str] = {}
    page = 1
    while True:
        releases = _gh_get("releases", {"per_page": "30", "page": str(page)})
        if not releases:
            break                       # страница пуста → дошли до конца
        for rel in releases:
            for asset in rel["assets"]:
                m = _RX_ASSET.match(asset["name"])
                if m and m.group(1) not in results:
                    results[m.group(1)] = asset["browser_download_url"]
        page += 1
    return results

def _latest_patch(branch: str, assets: dict[str, str]) -> str | None:
    """'3.12' → '3.12.10' (самый новый из загруженных assets)"""
    vers = [v for v in assets if v.startswith(branch + ".")]
    return max(vers, key=lambda s: tuple(map(int, s.split(".")))) if vers else None

ASSETS_CACHE: dict[str, str] | None = None  # ленивое кеширование на запуск

def _assets() -> dict[str, str]:
    global ASSETS_CACHE
    if ASSETS_CACHE is None:
        ASSETS_CACHE = _collect_assets()
    return ASSETS_CACHE

# ────────────────────────── download / extract ───────────────────────────────
def _download(version: str, url: str, dest: Path) -> None:
    print(f"⬇  Downloading {url.split('/')[-1]}")
    with urlopen(Request(url, headers={"Accept": "application/octet-stream"})) as r,\
         tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copyfileobj(r, tmp)
    tmp.close()

    print(f"📦  Extracting into {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tmp.name) as tar:
        members = [m for m in tar.getmembers() if m.name.startswith("python/")]
        for m in members:                        # ── strip first dir component
            m.path = "/".join(m.name.split("/")[1:])
        tar.extractall(dest, members)
    os.unlink(tmp.name)

# ────────────────────────── high-level ensure ────────────────────────────────
def _ensure(ver: str) -> Path:
    """
    ver = '3.13'  → найдём новейший 3.13.x, скачаем при необходимости
    ver = '3.13.5' → строго эту версию
    Возврат: Path к bin/python.
    """
    if _RX_BRANCH.match(ver):
        ver = _latest_patch(ver, _assets()) or sys.exit(f"No builds for {ver}.x")
    elif not _RX_FULLVER.match(ver):
        sys.exit("Version must be X.Y or X.Y.Z")

    dest = ISOPY_HOME / ver
    py   = dest / "bin" / "python"

    if not py.exists():
        url = _assets().get(ver) or sys.exit(f"Binary for {ver} not published.")
        _download(ver, url, dest)
    return py

# ────────────────────────── CLI commands ─────────────────────────────────────
def _cmd_install(a):
    py = _ensure(a.version)
    print(f"✔  {py}")
    print(f"   Add to PATH, or let Poetry use it via: isopy use {a.version}")

def _cmd_use(a):
    py = _ensure(a.version)
    subprocess.check_call(["poetry", "env", "use", str(py)])

def _cmd_list(_):
    for p in sorted(ISOPY_HOME.glob("*/bin/python")):
        print(p.parent.name, "→", p)

# ────────────────────────── entry-point ──────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(prog="isopy")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub_i = sub.add_parser("install"); sub_i.add_argument("version")
    sub_u = sub.add_parser("use");     sub_u.add_argument("version")
    sub.add_parser("list")
    ISOPY_HOME.mkdir(exist_ok=True)

    a = p.parse_args()
    {"install": _cmd_install,
     "use":     _cmd_use,
     "list":    _cmd_list}[a.cmd](a)

if __name__ == "__main__":
    main()
