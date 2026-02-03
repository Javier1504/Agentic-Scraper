from __future__ import annotations
from typing import Any, Dict, List, Tuple
import re

# skema
SCHEMA_IMPORT = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},          # key: university/institute/polytechnic/academy
        "status": {"type": "string"},        # key: state/private
        "accreditation": {"type": "string"}, # key: A/B/C/U/BA/BS/-
        "address": {"type": "string"},
        "postal_code": {"type": "string"},

        "email": {"type": "string"},
        "phone": {"type": "string"},
        "whatsapp": {"type": "string"},

        "facebook": {"type": "string"},
        "instagram": {"type": "string"},
        "twitter": {"type": "string"},
        "youtube": {"type": "string"},

        "province_name": {"type": "string"},
        "city_name": {"type": "string"},
    },
    "required": [
        "type","status","accreditation","address","postal_code",
        "email","phone","whatsapp",
        "facebook","instagram","twitter","youtube",
        "province_name","city_name"
    ]
}

RULES_INFO = """
ATURAN SUPER KETAT (ANTI HALU):
- Anda HANYA boleh mengisi email/phone/whatsapp & social link jika NILAI itu muncul di bukti.
- Bukti yang valid hanya dari: TEXT atau LINKS (daftar URL). Jika tidak ada bukti eksplisit, isi "-" .
- Dilarang menebak, dilarang membuat akun sosial/nomor telepon/WA.
- Output HARUS sesuai key berikut:
  type: salah satu ["university","institute","polytechnic","academy","-"]
  status: salah satu ["state","private","-"]
  accreditation: salah satu ["A","B","C","U","BA","BS","-"]
- address: alamat ringkas (jalan/kota/prov). Jika tak ada, "-"
- postal_code: kode pos angka jika ada, else "-"
- social links: harus URL (misal https://instagram.com/xxx), jika tidak ada maka "-"
- phone/whatsapp: harus nomor/URL yang ada di bukti (misal +6231..., wa.me/62...), jika tidak ada maka "-"

TUGAS:
Dari bukti TEXT dan LINKS website resmi kampus, ekstrak informasi berikut.
"""

# VISI MISI schema 
SCHEMA_VISI = {
    "type": "object",
    "properties": {
        "visi": {"type": "string"},
        "misi": {"type": "string"},
        "sejarah_deskripsi": {"type": "string"},
    },
    "required": ["visi","misi","sejarah_deskripsi"]
}

RULES_VISI = """
ATURAN KETAT:
- Jangan mengarang. Jika tidak ditemukan, isi "-" .
- visi: ringkas (boleh 1 paragraf).
- misi: jika list, tulis poin dipisah "; " (bukan bullet).
- sejarah_deskripsi: 1-3 paragraf ringkas, bukan noise.

TUGAS:
Ambil VISI, MISI, dan SEJARAH/DESKRIPSI kampus dari bukti teks.
"""

# ==========
# Normalizer
# ==========
def normalize_info_keys(d: Dict[str, Any]) -> Dict[str, str]:
    keys = ["type","status","accreditation","address","postal_code",
            "email","phone","whatsapp","facebook","instagram","twitter","youtube",
            "province_name","city_name"]
    out = {}
    for k in keys:
        v = d.get(k, "-")
        if v is None or str(v).strip() == "":
            v = "-"
        out[k] = str(v).strip()
    return out

def normalize_visi(d: Dict[str, Any]) -> Dict[str, str]:
    keys = ["visi","misi","sejarah_deskripsi"]
    out = {}
    for k in keys:
        v = d.get(k, "-")
        if v is None or str(v).strip() == "":
            v = "-"
        out[k] = str(v).strip()
    return out


# =========================
# Evidence Gate (ANTI HALU)
# =========================

RE_EMAIL = re.compile(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})")
RE_PHONE = re.compile(r"(\+?\d[\d\-\s\(\)]{7,}\d)")
RE_WA_URL = re.compile(r"(wa\.me\/\d+|whatsapp\.com\/|api\.whatsapp\.com\/send\?phone=\d+)", re.I)

def _digits_only(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def _clean_phone(s: str) -> str:
    # keep + and digits
    s = (s or "").strip()
    s = re.sub(r"[^\d+]", "", s)
    return s

def _in_blob(value: str, blob: str) -> bool:
    if not value or value == "-":
        return False
    v = value.strip().lower()
    return v in (blob or "").lower()

def _any_domain_in_links(domains: List[str], links: List[str]) -> str:
    for u in links or []:
        ul = (u or "").lower()
        for d in domains:
            if d in ul:
                return u
    return ""

def _find_first_regex(pattern: re.Pattern, blob: str) -> str:
    m = pattern.search(blob or "")
    return m.group(0) if m else ""

def _sanitize_url(u: str) -> str:
    u = (u or "").strip()
    if not u or u == "-":
        return "-"
    # accept only http(s)
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return "-"

def _sanitize_email(u: str) -> str:
    u = (u or "").strip()
    if not u or u == "-":
        return "-"
    # allow mailto:xxx@yyy
    if u.lower().startswith("mailto:"):
        u = u.split(":", 1)[-1].strip()
    if RE_EMAIL.fullmatch(u):
        return u
    return "-"

def _sanitize_phone(u: str) -> str:
    u = _clean_phone(u)
    digits = _digits_only(u)
    # Indonesia & umum: 9-15 digit
    if 9 <= len(digits) <= 15:
        return u
    return "-"

def _sanitize_whatsapp(u: str) -> str:
    u = (u or "").strip()
    if not u or u == "-":
        return "-"
    # allow wa.me, whatsapp api, or a phone number
    if RE_WA_URL.search(u):
        return u
    # else treat as phone
    ph = _sanitize_phone(u)
    if ph != "-":
        return ph
    return "-"

def enforce_evidence_info(info: Dict[str, str], text: str, links: List[str]) -> Dict[str, str]:
    """
    Kalau model ngisi IG/WA/Phone/Email tapi tidak ada buktinya di text/links => set '-'.
    """
    blob = (text or "") + "\n" + "\n".join(links or [])

    out = dict(info)

    # --- EMAIL: harus muncul di blob (atau bisa kita ambil langsung dari blob)
    email = _sanitize_email(out.get("email", "-"))
    if email != "-" and not _in_blob(email, blob):
        # coba ambil email valid dari blob
        found = _find_first_regex(RE_EMAIL, blob)
        out["email"] = found if found else "-"
    else:
        out["email"] = email

    # --- PHONE: harus muncul di blob
    phone = _sanitize_phone(out.get("phone", "-"))
    if phone != "-" and not _in_blob(_digits_only(phone), _digits_only(blob)):
        # coba ambil phone dari blob
        raws = RE_PHONE.findall(blob or "")
        picked = "-"
        for r in raws:
            cand = _sanitize_phone(r)
            if cand != "-":
                picked = cand
                break
        out["phone"] = picked
    else:
        out["phone"] = phone

    # --- WHATSAPP: harus ada bukti whatsapp URL / kata WA di blob
    wa = _sanitize_whatsapp(out.get("whatsapp", "-"))
    wa_has_evidence = bool(RE_WA_URL.search(blob or "")) or ("whatsapp" in (blob or "").lower()) or ("wa " in (blob or "").lower())
    if wa != "-" and not wa_has_evidence:
        out["whatsapp"] = "-"
    else:
        # kalau model kasih nomor, tapi ada WA URL di links, prefer URL
        wa_url = _find_first_regex(RE_WA_URL, blob)
        out["whatsapp"] = wa_url if wa_url else wa

    # --- SOCIALS: wajib URL domain yang benar & muncul di links/blob
    social_domains = {
        "instagram": ["instagram.com"],
        "facebook": ["facebook.com", "fb.com"],
        "twitter": ["twitter.com", "x.com"],
        "youtube": ["youtube.com", "youtu.be"],
    }

    for k, domains in social_domains.items():
        val = _sanitize_url(out.get(k, "-"))
        # kalau model kasih URL tapi domain salah => drop
        if val != "-":
            vl = val.lower()
            if not any(d in vl for d in domains):
                val = "-"

        # evidence check: harus muncul di links/blob, kalau tidak -> cari dari links
        if val != "-" and not _in_blob(val, blob):
            val = "-"
        if val == "-":
            found = _any_domain_in_links(domains, links or [])
            out[k] = found if found else "-"
        else:
            out[k] = val

    # final trim empty
    for k in list(out.keys()):
        if out[k] is None or str(out[k]).strip() == "":
            out[k] = "-"
        out[k] = str(out[k]).strip()

    return out
