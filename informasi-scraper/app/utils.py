from __future__ import annotations
import re
import unicodedata
from urllib.parse import urlparse, urljoin, urldefrag

# basic text helpers
RE_SPACES = re.compile(r"\s+")
RE_NONSLUG = re.compile(r"[^a-z0-9\-]+")

def compact_text(s: str, max_len: int) -> str:
    """Normalize whitespace and cut to max_len."""
    if not s:
        return ""
    s = s.replace("\u00a0", " ")
    s = RE_SPACES.sub(" ", s).strip()
    return s[:max_len]


def slugify(name: str) -> str:
    """Stable slug for Indonesian/English campus names."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^\w\s-]", " ", s)
    s = RE_SPACES.sub(" ", s).strip().replace(" ", "-")
    s = RE_NONSLUG.sub("", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s

# URL helpers
def normalize_url(u: str) -> str:
    """
    Normalize URL:
    - strip spaces
    - remove fragment (#...)
    - keep query (important for some portals)
    """
    if not u:
        return ""
    u = u.strip()
    u, _frag = urldefrag(u)
    return u


def same_site(seed: str, u: str) -> bool:
    """
    Loose same-site check:
    - Accept subdomains
    - Works well for *.ac.id where site often uses pmb.*, admisi.*, etc
    """
    try:
        a = urlparse(seed)
        b = urlparse(u)
        if not a.netloc or not b.netloc:
            return False

        an = a.netloc.split(":")[0].lower()
        bn = b.netloc.split(":")[0].lower()

        # Exact match or subdomain match
        if bn.endswith(an) or an.endswith(bn):
            return True
        an2 = an.replace("www.", "")
        bn2 = bn.replace("www.", "")
        return bn2.endswith(an2) or an2.endswith(bn2)

    except Exception:
        return False


def absolutize_url(base: str, href: str) -> str:
    """Join relative URL with base and normalize."""
    if not href:
        return ""
    return normalize_url(urljoin(base, href))

# Contact extraction
RE_EMAIL = re.compile(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})")
RE_PHONE = re.compile(r"(\+?\d[\d\-\s\(\)]{7,}\d)")
RE_WA = re.compile(r"(wa\.me\/\d+|whatsapp\.com\/|api\.whatsapp\.com\/send\?phone=\d+)", re.IGNORECASE)

def extract_emails(text: str) -> list[str]:
    if not text:
        return []
    emails = list(dict.fromkeys(RE_EMAIL.findall(text)))
    return emails[:5]

def extract_phones(text: str) -> list[str]:
    if not text:
        return []
    raw = RE_PHONE.findall(text)
    cleaned: list[str] = []
    for p in raw:
        # keep digits and leading +
        p2 = re.sub(r"[^\d+]", "", p)
        digits = re.sub(r"\D", "", p2)
        if len(digits) >= 9:
            cleaned.append(p2)
    cleaned = list(dict.fromkeys(cleaned))
    return cleaned[:5]

def contains_whatsapp(text: str) -> bool:
    return bool(RE_WA.search(text or ""))

# Short name / Acronym
RE_PAREN_ACR = re.compile(r"\(([A-Z0-9]{2,12})\)")
RE_WORDS = re.compile(r"[A-Za-z0-9]+")

STOPWORDS = {"of", "the", "and", "&", "dan"}

def acronym_from_parentheses(name: str) -> str:
    """Extract (UI) if present in name."""
    if not name:
        return ""
    m = RE_PAREN_ACR.search(name)
    if m:
        v = m.group(1).strip().upper()
        if 2 <= len(v) <= 12:
            return v
    return ""

def acronym_from_domain(url: str) -> str:
    """
    Extract brand-ish shortname from domain:
    - ubaya.ac.id -> UBAYA
    - unmul.ac.id -> UNMUL
    - ui.ac.id -> UI
    - pmb.ui.ac.id -> UI
    - usu.ac.id -> USU
    """
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        parts = host.split(".")
        if len(parts) < 2:
            return ""

        # Prefer label just before ac/edu/sch
        cand = ""
        if len(parts) >= 3 and parts[-2] in {"ac", "edu", "sch"}:
            cand = parts[-3]
        else:
            cand = parts[-2]

        cand = re.sub(r"[^a-z0-9]", "", cand)

        # If got generic subdomain by accident, try one step left
        if cand in {"www", "pmb", "spmb", "admisi", "admission"}:
            if len(parts) >= 4 and parts[-2] in {"ac", "edu", "sch"}:
                cand = re.sub(r"[^a-z0-9]", "", parts[-4])

        if 2 <= len(cand) <= 12:
            return cand.upper()
    except Exception:
        return ""
    return ""

def acronym_from_initials(name: str) -> str:
    """
    Fallback initials:
    - Universitas Indonesia -> UI
    - University of North Sumatra -> UONS (fallback if domain not available)
    """
    if not name:
        return ""
    words = RE_WORDS.findall(name)
    words = [w for w in words if w and w.lower() not in STOPWORDS]
    if not words:
        words = RE_WORDS.findall(name)

    ac = "".join(w[0].upper() for w in words if w)
    # prevent 1-letter acronym for 2+ word names
    if len(ac) == 1 and len(words) >= 2:
        ac = (words[0][0] + words[1][0]).upper()
    return ac[:12]

def best_short_name(name: str, website: str = "") -> str:
    """
    Best effort short_name WITHOUT manual per-campus keyword:
    Priority:
    1) (UI) in name
    2) domain shortname (ubaya/unmul/ui/ugm/itb/usu...)
    3) initials fallback
    """
    p = acronym_from_parentheses(name)
    if p:
        return p

    d = acronym_from_domain(website)
    if d:
        return d

    return acronym_from_initials(name) or "-"

def acronym(name: str) -> str:
    """
    Backward-compatible alias:
    - Previously this function produced wrong result for UI because it removed 'universitas/university'.
    - Now it simply uses initials fallback.
    NOTE: Prefer best_short_name(name, website) if you have website.
    """
    return acronym_from_initials(name)

def pick_best_url(urls: list[str]) -> str:
    """Pick first valid http URL from list."""
    for u in urls or []:
        if u and u.startswith("http"):
            return u
    return urls[0] if urls else ""
