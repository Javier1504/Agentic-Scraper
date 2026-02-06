# crawler.py — ADMISSION CRAWLER v2 FINAL (FIXED)

from collections import deque
from typing import List, Set, Tuple

from config import JALUR_WORD_RE
from utils import CandidateLink, normalize_url, same_site
from extract_assets import extract_links_and_assets
from logger import info


# =========================
# CONFIG
# =========================

ADMISSION_ENTRY_KEYWORDS = [
    "pmb",
    "ppmb",
    "admission",
    "penerimaan",
    "pendaftaran mahasiswa baru",
]

HARD_REJECT_KEYWORDS = [
    "daya-tampung",
    "kuota",
    "kapasitas",
    "program-studi",
    "prodi",
    "fakultas",
    "mbkm",
    "rpl",
    "alumni",
    "berita",
    "news",
    "artikel",
    "biaya",
    "fee",
    "ukt",
    "beasiswa",
    "scholarship",
    "kontak",
    "contact",
    "lokasi",
    "location",
    "peta-situs",
    "bayar",
]

MAX_ADMISSION_DEPTH = 3


# =========================
# HELPERS
# =========================

def is_admission_entry(url: str) -> bool:
    u = url.lower()
    return any(k in u for k in ADMISSION_ENTRY_KEYWORDS)


def hard_reject(url: str) -> bool:
    u = url.lower()
    return any(k in u for k in HARD_REJECT_KEYWORDS)


def _priority(url: str) -> int:
    u = url.lower()
    if "jadwal" in u or "timeline" in u:
        return 100
    if any(k in u for k in ["snbp", "snbt", "mandiri"]):
        return 80
    if is_admission_entry(u):
        return 60
    return 10


# =========================
# MAIN CRAWLER
# =========================

async def crawl_site(
    campus_name: str,
    official_website: str,
    fetcher,
    max_pages: int = 80,
) -> List[CandidateLink]:

    start = normalize_url(official_website)
    visited: Set[str] = set()
    candidates: List[CandidateLink] = []

    info(f"admission_discovery | {campus_name}")

    # --- STEP 1: ENTRY POINT FROM MENU ---
    fr, menu_links = await fetcher.fetch_with_menu(start)
    roots = [
        normalize_url(u)
        for u in menu_links
        if same_site(u, start) and is_admission_entry(u)
    ]

    if not roots:
        info(f"admission_abort | {campus_name}")
        return []

    q = deque([(u, 0) for u in roots[:3]])

    # --- STEP 2: BFS CRAWLING ---
    while q and len(visited) < max_pages:
        url, depth = q.popleft()

        if url in visited:
            continue
        if depth > MAX_ADMISSION_DEPTH:
            continue
        if not same_site(url, start):
            continue
        if hard_reject(url):
            continue

        visited.add(url)
        info(f"crawl | {campus_name} depth={depth} url={url}")

        fr = (await fetcher.fetch_with_menu(url))[0]
        if not fr.ok:
            continue

        html = fr.content.decode("utf-8", errors="ignore")
        found = extract_links_and_assets(fr.final_url, html)

        # --- STEP 3: LINK ANALYSIS ---
        for u, kind, hint, score in found:
            u = normalize_url(u)

            if not same_site(u, start):
                continue
            if hard_reject(u):
                continue

            text_blob = (u + " " + hint).lower()

            # 🔥 PATCH UTAMA:
            # Semua halaman jadwal ATAU halaman yang mengandung kata jalur
            # dianggap kandidat. Pemecahan detail dilakukan di extractor.
            is_candidate = (
                "jadwal" in text_blob
                or JALUR_WORD_RE.search(text_blob)
            )

            if is_candidate:
                candidates.append(
                    CandidateLink(
                        campus_name=campus_name,
                        official_website=official_website,
                        url=u,
                        kind=kind,
                        source_page=fr.final_url,
                        context_hint=hint[:300],
                        score=score,
                    )
                )

            if kind == "html" and u not in visited:
                q.append((u, depth + 1))

    # --- STEP 4: DEDUP (NON-DESTRUCTIVE) ---
    best: List[CandidateLink] = []
    seen: Set[Tuple[str, str, str]] = set()

    for c in candidates:
        key = (
            c.url,
            c.kind,
            c.context_hint[:80],  # pembeda jalur / gelombang / tabel
        )

        if key in seen:
            continue

        seen.add(key)
        best.append(c)

    info(f"crawl_done | {campus_name} candidates={len(best)}")
    return best
