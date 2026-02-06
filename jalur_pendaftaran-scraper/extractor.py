from __future__ import annotations
import json
from typing import List, Dict, Any
from utils import slugify
from logger import debug



EXTRACT_PROMPT = """Kamu adalah EXTRACTOR DATA JADWAL DAN JALUR PENDAFTARAN
mahasiswa baru perguruan tinggi di Indonesia.

Tugas kamu:
- Membaca konten halaman jadwal / admission.
- Menghasilkan SEMUA jadwal pendaftaran yang berbeda sebagai
  OBJECT TERPISAH.

====================================
ATURAN PALING PENTING
====================================
- SATU jadwal = SATU object.
- Jika satu halaman memuat banyak jalur, jenjang, atau gelombang,
  keluarkan SEMUA sebagai object TERPISAH.
- JANGAN digabung.
- JANGAN dipilih satu saja.

====================================
OUTPUT
====================================
- Output HARUS array JSON.
- Jika ada 10 jadwal → 10 object.
- Jika tidak ada jadwal → [].

====================================
STRUKTUR OBJECT
====================================
Setiap object WAJIB punya:

- name (string)
  → Nama lengkap jadwal, BOLEH PANJANG
    Contoh:
    "Jadwal Pendaftaran SNBT Sarjana Gelombang 2 Universitas Airlangga Tahun 2026"

Opsional:
- registration_start
- registration_end
- academic_year
- wave
- admission_type
- selection_method
- target_level

====================================
BUKAN JADWAL (JANGAN DIEKSTRAK)
====================================
- biaya
- daya tampung
- kuota
- pengumuman kelulusan
- berita
- biaya kuliah
- profil kampus
- visi misi
- biaya

====================================
KONTEN:
"""

def safe_parse_json_array(raw: str) -> list:
    """
    Defensive JSON parser untuk output LLM.
    Mengambil array JSON paling luar.
    """
    if not raw:
        return []

    raw = raw.strip()

    # cari array JSON terluar
    start = raw.find("[")
    end = raw.rfind("]")

    if start == -1 or end == -1 or end <= start:
        return []

    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return []


def extract_jalur_items_from_text(
        gemini,
        text: str
    ) -> List[Dict[str, Any]]:

        raw = gemini.generate_text(
            EXTRACT_PROMPT + "\n\nKONTEN:\n" + text[:16000]
        )
        
        debug(f"LLM RAW (first 500 chars): {raw[:500]!r}")

        data = safe_parse_json_array(raw)
        out: List[Dict[str, Any]] = []

        if isinstance(data, list):
            for obj in data:
                if not isinstance(obj, dict):
                    continue

                name = (obj.get("name") or "").strip()
                if not name:
                    continue

                obj["slug"] = (obj.get("slug") or "").strip() or slugify(name)
                out.append(obj)

        return out



def extract_jalur_items_from_bytes(
        gemini,
        mime: str,
        data: bytes
    ) -> List[Dict[str, Any]]:
        raw = gemini.generate_with_bytes(
            EXTRACT_PROMPT,
            data=data,
            mime_type=mime
        )

        data = safe_parse_json_array(raw)
        out: List[Dict[str, Any]] = []

        if isinstance(data, list):
            for obj in data:
                if not isinstance(obj, dict):
                    continue

                name = (obj.get("name") or "").strip()
                if not name:
                    continue

                obj["slug"] = (obj.get("slug") or "").strip() or slugify(name)
                out.append(obj)

        return out
