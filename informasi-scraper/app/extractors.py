from __future__ import annotations
from typing import Any, Dict

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

        # untuk mapping province/city, minta nama juga
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
ATURAN KETAT:
- Jangan mengarang. Jika tidak ada bukti di teks, isi "-" .
- Output HARUS sesuai key berikut:
  type: salah satu ["university","institute","polytechnic","academy","-"]
  status: salah satu ["state","private","-"]
  accreditation: salah satu ["A","B","C","U","BA","BS","-"]
- address: alamat ringkas (jalan/kota/prov). Jika tak ada, "-"
- postal_code: kode pos angka jika ada, else "-"
- email/phone/whatsapp & social links: isi URL/handle bila ada, else "-"
- province_name & city_name: gunakan nama PROVINSI dan KOTA/KAB yang paling mungkin dari alamat; jika tidak ada, "-"
- Jangan masukkan kalimat panjang. Ringkas.

TUGAS:
Dari bukti teks website resmi kampus, ekstrak informasi berikut.
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

def normalize_info_keys(d: Dict[str, Any]) -> Dict[str, str]:
    # memastikan kunci dan value aman
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
