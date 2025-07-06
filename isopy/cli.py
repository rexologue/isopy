#!/usr/bin/env python3
"""
isopy – install isolated CPython builds & integrate them with Poetry
"""

import argparse, json, os, re, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path
from urllib.request import urlopen, Request

ISOPY_HOME = Path.home() / ".isopy"                  # ~/.isopy/<ver>/bin/python
ARCH       = "x86_64-unknown-linux-gnu"
REPO_API   = ("https://api.github.com/repos/"
              "astral-sh/python-build-standalone/releases?per_page=100")

_version_rx   = re.compile(rf"cpython-(\d+\.\d+\.\d+)\+.*{ARCH}.*install_only")
_branch_rx    = re.compile(r"^\d+\.\d+$")            # e.g. 3.12
_semver_rx    = re.compile(r"^\d+\.\d+\.\d+$")       # e.g. 3.12.10

# --------------------------------------------------------------------------- helpers
def _github_json():
    return json.load(urlopen(REPO_API))

def _all_versions():
    """Return {version: url} for all assets matching our arch."""
    out = {}
    for rel in _github_json():
        for a in rel["assets"]:
            m = _version_rx.match(a["name"])
            if m:
                out[m.group(1)] = a["browser_download_url"]
    return out

def _latest_patch(branch: str) -> str | None:
    """branch = '3.12'  →  newest '3.12.x' or None"""
    candidates = [v for v in _all_versions() if v.startswith(branch + ".")]
    return max(candidates, key=lambda v: tuple(map(int, v.split(".")))) if candidates else None

def _download(version: str, url: str, target: Path):
    print(f"⬇  Downloading {url.split('/')[-1]}")
    with urlopen(Request(url, headers={"Accept": "application/octet-stream"})) as r,\
         tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copyfileobj(r, tmp)
    tmp.close()
    print(f"📦  Extracting into {target}")
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tmp.name) as tar:
        members = [m for m in tar.getmembers() if m.name.startswith("python/")]
        for m in members:
            m.path = "/".join(m.name.split("/")[1:])   # strip top dir
        tar.extractall(target, members)
    os.unlink(tmp.name)

def ensure(version_or_branch: str) -> Path:
    """Return Path to python, downloading if needed."""
    if _branch_rx.match(version_or_branch):
        version = _latest_patch(version_or_branch) or sys.exit(
            f"No builds for {version_or_branch}.x found.")
    elif _semver_rx.match(version_or_branch):
        version = version_or_branch
    else:
        sys.exit("Version must be 'X.Y' or 'X.Y.Z'.")

    dest = ISOPY_HOME / version
    py   = dest / "bin" / "python"

    if not py.exists():
        url = _all_versions().get(version)
        if not url:
            sys.exit(f"Binary for {version} not published yet.")
        _download(version, url, dest)

    return py

# --------------------------------------------------------------------------- CLI commands
def cmd_install(args):
    py = ensure(args.version)
    print(f"✔  {py}")
    print(f"   Add to PATH or let Poetry use it via: isopy use {args.version}")

def cmd_list(_):
    for p in sorted((ISOPY_HOME).glob("*/bin/python")):
        print(p.parent.name, "→", p)

def cmd_use(args):
    py = ensure(args.version)
    subprocess.check_call(["poetry", "env", "use", str(py)])

def main():
    p = argparse.ArgumentParser(prog="isopy")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("install"); a.add_argument("version")
    a = sub.add_parser("use");     a.add_argument("version")
    sub.add_parser("list")

    os.makedirs(ISOPY_HOME, exist_ok=True)
    args = p.parse_args()
    {"install": cmd_install, "use": cmd_use, "list": cmd_list}[args.cmd](args)

if __name__ == "__main__":
    main()
