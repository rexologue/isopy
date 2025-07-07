#!/usr/bin/env python3
"""
build-index.py  —  обновляет index.json для isopy
"""

import json, os, re, sys, time, pathlib, requests, backoff

ARCH = "x86_64-unknown-linux-gnu"
RX   = re.compile(rf"cpython-(\d+\.\d+\.\d+)\+.*{ARCH}.*install_only")
API  = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"

HEADERS = {
    "User-Agent": "isopy-index-builder/0.2",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if tok := os.getenv("GITHUB_TOKEN"):          # получаем от GitHub Actions
    HEADERS["Authorization"] = f"Bearer {tok}"

@backoff.on_exception(backoff.expo,  # повторы 1 с, 2 с, 4 с, … (до 5 раз)
                      (requests.HTTPError, requests.ConnectionError),
                      max_tries=5, jitter=None)
def gh_get(page: int) -> list[dict]:
    r = requests.get(API,
                     params={"per_page": 30, "page": page},
                     headers=HEADERS,
                     timeout=30)
    if r.status_code != 200:
        raise requests.HTTPError(f"status {r.status_code}: {r.text[:120]}")
    return r.json()

def build_index() -> dict[str, str]:
    out, page = {}, 1
    while True:
        rels = gh_get(page)
        if not rels:
            break
        for rel in rels:
            for a in rel["assets"]:
                if (m := RX.match(a["name"])) and m.group(1) not in out:
                    out[m.group(1)] = a["browser_download_url"]
        page += 1
        time.sleep(0.1)          # мини-пауза против secondary rate limit
    return out

def main():
    try:
        index = build_index()
    except Exception as e:
        print(f"⚠️  Failed to refresh index: {e}\n"
              "    Keeping previous version (if any).")
        sys.exit(0)              # не валим workflow

    pathlib.Path("index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"✔ index.json generated: {len(index)} versions")

if __name__ == "__main__":
    main()

