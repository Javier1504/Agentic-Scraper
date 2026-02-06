# menu_crawler.py
from __future__ import annotations
from typing import List
from playwright.async_api import Page

MENU_SELECTORS = [
    "nav a",
    "header a",
    "[role='navigation'] a",
    ".menu a",
    ".navbar a",
]

MENU_KEYWORDS = [
    "pmb", "pendaftaran", "admission", "registrasi",
    "mahasiswa baru", "snbp", "snbt", "mandiri", "jalur"
]

async def extract_menu_links(page: Page) -> List[str]:
    links = set()

    for sel in MENU_SELECTORS:
        els = await page.query_selector_all(sel)
        for el in els:
            try:
                href = await el.get_attribute("href")
                text = (await el.inner_text() or "").lower()

                if not href:
                    continue

                h = href.lower()
                if any(k in h or k in text for k in MENU_KEYWORDS):
                    links.add(href)

            except Exception:
                pass

    return list(links)
