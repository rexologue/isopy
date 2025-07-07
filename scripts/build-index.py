#!/usr/bin/env python3
"""
build-index.py – генерирует index.json для isopy, обходя HTML-страницы GitHub,
НЕ пользуясь REST-API и не требуя токенов.

Алгоритм
────────
1. Проходит список релизов https://github.com/<repo>/releases?page=N.
2. Для каждого тега /releases/tag/<TAG> скачивает страницу.
   • Если список ассетов «схлопнут» ссылкой *Show all … assets*,
     вытягивает фрагмент из include-fragment и парсит его.
3. Забирает ссылки на архивы
      cpython-X.Y.Z+…-<ARCH>-…install_only.tar.{zst|gz}
   и строит словарь  { "X.Y.Z": "https://github.com/…download/…" }.
4. Предпочитает полный архив (без «stripped») при совпадении версий.
5. Сохраняет результат в index.json (UTF-8, с отступами).

Настройка
─────────
• ARCH            – нужная архитектура; по умолчанию x86_64-unknown-linux-gnu  
• ASSET_KIND      – строка-маркер в имени файла (install_only, stripped …)  
• PAGE_MAX        – глубина пагинации /releases (10 страниц ≈ 1,5 года истории)

Зависимости:  requests, beautifulsoup4
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import pathlib
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ───────────────────────────────────────────── Настройки ────────────────────────────────────────────
REPO = "astral-sh/python-build-standalone"
BASE = f"https://github.com/{REPO}"
ARCH = os.getenv("ISOPY_ARCH", "x86_64-unknown-linux-gnu")
ASSET_KIND = "install_only"
PAGE_MAX = 10                       # глубина /releases?page=N (хватает на годы)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# ───────────────────────────────────────────── Session + retry ──────────────────────────────────────
session = requests.Session()
session.headers.update(
    {
        "User-Agent": UA,
        "Accept-Encoding": "gzip, deflate, br",
    }
)
retry_cfg = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[502, 503, 504],
    raise_on_status=False,
)
session.mount("https://", HTTPAdapter(max_retries=retry_cfg))

# ───────────────────────────────────────────── Регулярки ────────────────────────────────────────────
rx_tag_link = re.compile(r"/releases/tag/(?P<tag>[^\"/]+)$")
rx_rel_ver = re.compile(r"cpython-(\d+\.\d+\.\d+)")
rx_asset = re.compile(
    rf"/{REPO}/releases/download/(?P<tag>[^\"/]+)/"
    rf"[^\"/]*{ARCH}[^\"/]*{ASSET_KIND}[^\"/]*\.(?:tar\.gz|tar\.zst)"
)

# ───────────────────────────────────────────── Вспомогательные ─────────────────────────────────────
def fetch(url: str) -> BeautifulSoup:
    """GET url → BeautifulSoup (выход  sys.exit при non-200)."""
    try:
        r = session.get(url, timeout=40)
        r.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"❌ HTTP error for {url}: {e}")
    return BeautifulSoup(r.text, "html.parser")


def expanded_assets(html_page: BeautifulSoup) -> str | None:
    """Если есть include-fragment со всеми ассетами — вернём его src."""
    frag = html_page.select_one("include-fragment[src*='expanded_assets']")
    return frag["src"] if frag else None


def collect_assets(tag_url: str) -> list[str]:
    """Возвращает download-URL-ы ассетов, удовлетворяющих фильтрам."""
    page = fetch(tag_url)

    # если список ассетов схлопнут
    if frag := expanded_assets(page):
        page = fetch(urljoin(BASE, frag))

    links: list[str] = []
    for a in page.select("a[href]"):
        href = a["href"]
        if rx_asset.search(href):
            links.append(urljoin("https://github.com", html.unescape(href)))
    return links


# ───────────────────────────────────────────── Построение словаря ───────────────────────────────────
def build_mapping() -> dict[str, str]:
    mapping: dict[str, str] = {}

    for page_n in range(1, PAGE_MAX + 1):
        list_url = f"{BASE}/releases?page={page_n}"
        rel_page = fetch(list_url)

        # собираем ссылки на теги
        tag_urls = {
            urljoin(BASE, a["href"])
            for a in rel_page.select("a[href*='/releases/tag/']")
            if rx_tag_link.search(a["href"])
        }
        if not tag_urls:
            break  # страницы кончились

        for tag_url in tag_urls:
            for asset_url in collect_assets(tag_url):
                ver_match = rx_rel_ver.search(asset_url)
                if not ver_match:
                    continue
                ver = ver_match.group(1)

                # предпочитаем полный архив (без 'stripped')
                if ver in mapping:
                    if "stripped" in mapping[ver] and "stripped" not in asset_url:
                        mapping[ver] = asset_url
                else:
                    mapping[ver] = asset_url

        time.sleep(0.1)  # мелкая задержка, чтобы не ловить rate-limit

    return mapping


# ───────────────────────────────────────────── Точка входа ──────────────────────────────────────────
def main() -> None:
    mp = build_mapping()
    if not mp:
        sys.exit("❌ Не удалось найти ни одной подходящей сборки.")

    out_file = pathlib.Path("index.json")
    out_file.write_text(json.dumps(mp, indent=2) + "\n", encoding="utf-8")

    print(f"✔ index.json создан ({len(mp)} версий). Путь: {out_file.resolve()}")


if __name__ == "__main__":
    main()


