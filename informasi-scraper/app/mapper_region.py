from __future__ import annotations
from typing import Tuple, Optional
import pandas as pd
from rapidfuzz import fuzz

def load_region_table(path_import_schema_xlsx: str) -> pd.DataFrame:
    df = pd.read_excel(path_import_schema_xlsx, sheet_name="Option provinsi_id & city_id")
    df.columns = ["province_id", "province_name", "city_id", "city_name"]
    # normalisasi
    df["province_name_norm"] = df["province_name"].astype(str).str.lower()
    df["city_name_norm"] = df["city_name"].astype(str).str.lower()
    return df

def match_region(df_region: pd.DataFrame, province_name: str, city_name: str) -> Tuple[Optional[str], Optional[str]]:
    p = (province_name or "").strip().lower()
    c = (city_name or "").strip().lower()
    if not p and not c:
        return None, None

    best_score = -1
    best_row = None

    for _, row in df_region.iterrows():
        sp = fuzz.partial_ratio(p, row["province_name_norm"]) if p else 0
        sc = fuzz.partial_ratio(c, row["city_name_norm"]) if c else 0
        score = (sp * 0.6) + (sc * 0.9)
        if score > best_score:
            best_score = score
            best_row = row

    # threshold 
    if best_row is None or best_score < 130:
        return None, None
    return str(best_row["province_id"]), str(best_row["city_id"])
