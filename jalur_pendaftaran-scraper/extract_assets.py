from __future__ import annotations

from typing import List, Tuple
from bs4 import BeautifulSoup

from config import (
    JALUR_WORD_RE,
    JALUR_KEYWORDS,
    NOISE_KEYWORDS,
    PDF_EXT,
    IMG_EXT,
)
from utils import safe_join, normalize_url


def _is_noise(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in NOISE_KEYWORDS)


def score_hint(text: str) -> float:
    """
    Scoring konteks link berdasarkan indikasi jalur pendaftaran
    """
    t = (text or "").lower()
    score = 0.0

    for kw in JALUR_KEYWORDS:
        if kw in t:
            score += 2.0

    for nk in NOISE_KEYWORDS:
        if nk in t:
            score -= 1.5

    return score


def extract_links_and_assets(page_url: str, html: str) -> List[Tuple[str, str, str, float]]:
    """
    Return (url, kind, hint, score)
    kind: html | pdf | image
    """
    soup = BeautifulSoup(html, "lxml")
    out: List[Tuple[str, str, str, float]] = []

    # =====================================================
    # a[href]
    # =====================================================
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue

        text = (a.get_text(" ", strip=True) or "")[:200]
        u = safe_join(page_url, href)
        hint = f"{text} {href}".strip()

        # anti-noise: skip jika jelas noise dan tidak ada indikasi jalur
        if _is_noise(hint) and not JALUR_WORD_RE.search(hint):
            continue

        ul = u.lower()
        kind = "html"
        if ul.endswith(PDF_EXT):
            kind = "pdf"
        elif ul.endswith(IMG_EXT):
            kind = "image"

        sc = score_hint(hint)
        out.append((u, kind, hint, sc))

    # =====================================================
    # iframe / embed / object (brosur PMB, PDF)
    # =====================================================
    for tag, attr in [("iframe", "src"), ("embed", "src"), ("object", "data")]:
        for el in soup.find_all(tag):
            src = (el.get(attr) or "").strip()
            if not src:
                continue

            u = safe_join(page_url, src)
            hint = f"{tag}:{attr} {src}"
            kind = "pdf" if u.lower().endswith(PDF_EXT) else "html"
            sc = score_hint(hint)
            out.append((u, kind, hint, sc))

    # =====================================================
    # Images: hanya jika halaman terindikasi jalur pendaftaran
    # =====================================================
    page_text = soup.get_text(" ", strip=True).lower()
    page_has_jalur = bool(JALUR_WORD_RE.search(page_text))

    if page_has_jalur:
        for img in soup.select("img"):
            src = (img.get("src") or "").strip()
            srcset = (img.get("srcset") or "").strip()

            cand = []
            if src:
                cand.append(src)
            if srcset:
                first = srcset.split(",")[0].strip().split(" ")[0].strip()
                if first:
                    cand.append(first)

            alt = (img.get("alt") or "").strip()
            title = (img.get("title") or "").strip()
            hint = f"img {alt} {title}".strip()

            # tetap filter noise
            if _is_noise(hint) and not JALUR_WORD_RE.search(hint) and not page_has_jalur:
                continue

            for c in cand:
                u = safe_join(page_url, c)
                if not u.lower().endswith(IMG_EXT):
                    continue

                sc = score_hint(hint) + 1.0
                out.append((u, "image", hint, sc))

    # =====================================================
    # normalize + dedup
    # =====================================================
    seen = set()
    uniq = []

    for u, kind, hint, sc in out:
        u2 = normalize_url(u)
        key = (u2, kind)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((u2, kind, hint, sc))

    return uniq
