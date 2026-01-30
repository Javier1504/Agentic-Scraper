from __future__ import annotations
from typing import Dict, Any, List
import pandas as pd

IMPORT_COLUMNS = [
    "id","university_code","name","slug","short_name","description","logo",
    "type","status","accreditation",
    "website","email","phone","whatsapp",
    "facebook","instagram","twitter","youtube",
    "address","province_id","city_id","postal_code","cover"
]

def load_seed_xlsx(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    # expect minimal: kampus_name, official_website
    # fallback: if different columns, user can rename
    return df

def build_import_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in IMPORT_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[IMPORT_COLUMNS]
    return df

def save_outputs(df: pd.DataFrame, out_xlsx: str, out_csv: str):
    df.to_excel(out_xlsx, index=False)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
