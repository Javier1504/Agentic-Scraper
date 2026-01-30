from __future__ import annotations
import re
from typing import List, Dict, Tuple, Union
from .utils import same_site

KW_INFO = [
    "tentang", "about", "profil", "profile",
    "contact", "kontak", "alamat", "location", "lokasi",
    "akreditasi", "accreditation", "ban-pt", "lam", "pddikti",
    "identitas", "struktur", "organisasi"
]

KW_VISI = [
    "visi", "misi", "vision", "mission", "visi-misi", "visimisi",
    "sejarah", "history", "tentang", "about", "profil", "profile",
    "sambutan", "welcome", "rektor", "rector"
]

BAD_HINT = ["login", "auth", "sso", "logout", "wp-admin", "cart", "checkout"]


def _score(href: str, text: str, keywords: list[str], mode: str) -> float:
    u = (href or "").lower()
    t = (text or "").lower()
    blob = f"{u} {t}"

    if any(b in u for b in BAD_HINT):
        return -5.0

    s = 0.0
    for k in keywords:
        if k in blob:
            s += 2.0

    if mode == "visi":
        if re.search(r"(visi|misi|vision|mission|sejarah|history|profil|profile|about|tentang)", blob):
            s += 10.0
    else:
        if re.search(r"(kontak|contact|alamat|lokasi|location|akredit|pddikti|ban-pt|lam)", blob):
            s += 10.0

    if u.endswith(".pdf"):
        s += 1.0

    return s


def pick_candidates(seed_url: str, links: Union[List[str], List[Dict[str, str]]], mode: str, limit: int) -> List[str]:
    keywords = KW_INFO if mode == "info" else KW_VISI
    scored: List[Tuple[float, str]] = []

    # normalize to list[dict]
    items: List[Dict[str, str]] = []
    if links and isinstance(links[0], dict):  # type: ignore[index]
        for it in links:  # type: ignore[assignment]
            href = (it.get("href") or "").strip()
            if href:
                items.append({"href": href, "text": (it.get("text") or "").strip()})
    else:
        for u in (links or []):  # type: ignore[union-attr]
            u = str(u).strip()
            if u:
                items.append({"href": u, "text": ""})

    for it in items:
        href = (it.get("href") or "").strip()
        text = (it.get("text") or "").strip()
        if not href.startswith("http"):
            continue
        if not same_site(seed_url, href):
            continue
        sc = _score(href, text, keywords, mode=mode)
        scored.append((sc, href))

    scored.sort(key=lambda x: x[0], reverse=True)

    picked: List[str] = []
    for sc, href in scored:
        if sc <= 0:
            continue
        if href not in picked:
            picked.append(href)
        if len(picked) >= limit:
            break
    return picked
