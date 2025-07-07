#!/usr/bin/env python3
"""
isopy – install isolated CPython builds & integrate them with Poetry
         ♦ НЕ требует GitHub API ♦
"""

from __future__ import annotations

import argparse, json, os, re, shutil, subprocess, sys, tarfile, tempfile, time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

__version__   = "0.2.0"

# ───────────── настраиваемые «константы» ─────────────────────────────────────
ISOPY_HOME    = Path.home() / ".isopy"
ARCH          = os.getenv("ISOPY_ARCH", "x86_64-unknown-linux-gnu")
INDEX_URL     = os.getenv("ISOPY_INDEX_URL",
                "https://raw.githubusercontent.com/"
                "rexologue/isopy/main/index.json")      # поменяйте на свой
CACHE_FILE    = Path.home() / ".cache" / "isopy" / "index.json"
CACHE_TTL     = 12 * 60 * 60        # 12 ч

_RX_BRANCH    = re.compile(r"^\d+\.\d+$")      # 3.12
_RX_FULL      = re.compile(r"^\d+\.\d+\.\d+$") # 3.12.10

# ───────────── index handling ────────────────────────────────────────────────
def _download_index() -> dict[str, str]:
    print("⇣  Fetching version index…")
    hdrs = {"User-Agent": f"isopy/{__version__}"}
    try:
        with urlopen(Request(INDEX_URL, headers=hdrs), timeout=10) as r:
            data = r.read()
    except (URLError, HTTPError) as e:
        sys.exit(f"❌  Cannot download index.json ({e}). "
                 "Set ISOPY_INDEX_URL or use offline cache.")
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_bytes(data)
    return json.loads(data)

def _load_index() -> dict[str, str]:
    if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < CACHE_TTL:
        return json.loads(CACHE_FILE.read_text())
    return _download_index()

INDEX: dict[str, str] = _load_index()

# ───────────── helpers ───────────────────────────────────────────────────────
def _latest(branch: str) -> str | None:
    """'3.12' → самая свежая '3.12.x' из INDEX"""
    vers = [v for v in INDEX if v.startswith(branch + ".")]
    return max(vers, key=lambda s: tuple(map(int, s.split(".")))) if vers else None

def _download(url: str, dest: Path) -> None:
    print(f"⬇  {url.split('/')[-1]}")
    with urlopen(Request(url, headers={"Accept": "application/octet-stream"})) as r,\
         tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copyfileobj(r, tmp)
    print(f"📦  Extracting → {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tmp.name) as tar:
        members=[m for m in tar.getmembers() if m.name.startswith("python/")]
        for m in members: m.path="/".join(m.name.split("/")[1:])
        tar.extractall(dest, members)
    os.unlink(tmp.name)

def _ensure(ver: str) -> Path:
    """Resolve + download if needed, return …/bin/python"""
    if _RX_BRANCH.match(ver):
        ver = _latest(ver) or sys.exit(f"No builds for {ver}.x in index.")
    elif not _RX_FULL.match(ver):
        sys.exit("Version must be X.Y or X.Y.Z")

    dest = ISOPY_HOME / ver
    py   = dest / "bin" / "python"
    if not py.exists():
        url = INDEX.get(ver) or sys.exit(f"{ver} absent from index.")
        _download(url, dest)
    return py

# ───────────── CLI commands ──────────────────────────────────────────────────
def _cmd_install(a):
    py = _ensure(a.version)
    print(f"✔  {py}")

def _cmd_use(a):
    py = _ensure(a.version)
    subprocess.check_call(["poetry", "env", "use", str(py)])

def _cmd_list(_):
    for p in sorted(ISOPY_HOME.glob("*/bin/python")):
        print(p.parent.name, "→", p)

def _cmd_update(_):
    CACHE_FILE.unlink(missing_ok=True)
    _download_index()
    print("✔  Index updated.")

# ───────────── entry point ───────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(prog="isopy")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install").add_argument("version")
    sub.add_parser("use").add_argument("version")
    sub.add_parser("list")
    sub.add_parser("update-index")
    ISOPY_HOME.mkdir(exist_ok=True)

    a = p.parse_args()
    {"install": _cmd_install,
     "use":     _cmd_use,
     "list":    _cmd_list,
     "update-index": _cmd_update}[a.cmd](a)

if __name__ == "__main__":
    main()

