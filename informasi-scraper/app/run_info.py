from __future__ import annotations
import os, json, time
from typing import Dict, Any

from app.config import DEFAULT_INPUT_XLSX, OUT_DIR, STATE_DIR, MAX_PAGES_VISIT, MAX_INTERNAL_CANDIDATES, MAX_COMBINED_TEXT
from app.fetcher import PlaywrightFetcher
from app.selector import pick_candidates
from app.gemini_client import GeminiJSON
from app.extractors import SCHEMA_IMPORT, RULES_INFO, normalize_info_keys
from app.mapper_region import load_region_table, match_region
from app.utils import slugify, acronym, compact_text
from app.io_excel import load_seed_xlsx, build_import_frame, save_outputs

IMPORT_SCHEMA_XLSX = os.path.join(os.path.dirname(__file__), "(3) Import Informasi Kampus.xlsx")  # taruh file ini di root

def bundle_text(fetcher: PlaywrightFetcher, seed_url: str, mode: str) -> str:
    visited = set()
    to_visit = [seed_url]
    all_links = []
    combined = ""

    while to_visit and len(visited) < MAX_PAGES_VISIT and len(combined) < MAX_COMBINED_TEXT:
        u = to_visit.pop(0)
        if u in visited:
            continue
        visited.add(u)

        r = fetcher.fetch(u)
        if r.text:
            combined += "\n\n" + r.text

        all_links.extend(r.links)

        # setelah seed terkumpul link, pilih kandidat internal untuk mode
        if len(visited) == 1:
            cands = pick_candidates(r.final_url or seed_url, all_links, mode=mode, limit=MAX_INTERNAL_CANDIDATES)
            to_visit.extend([x for x in cands if x not in visited])

    return compact_text(combined, MAX_COMBINED_TEXT)

def main():
    inp = load_seed_xlsx(DEFAULT_INPUT_XLSX)
    region_df = load_region_table(IMPORT_SCHEMA_XLSX)

    state_path = os.path.join(STATE_DIR, "state_info.json")
    state = {"done": {}} if not os.path.exists(state_path) else json.load(open(state_path, "r", encoding="utf-8"))

    gem = GeminiJSON()
    rows = []
    total_usage = {"prompt_tokens":0,"candidates_tokens":0,"total_tokens":0}

    with PlaywrightFetcher() as fetcher:
        for i, row in inp.iterrows():
            name = str(row.get("kampus_name", "")).strip()
            website = str(row.get("official_website", "")).strip()
            key = f"{i}:{website}"

            if state["done"].get(key) == "ok":
                print(f"[SKIP] {name}")
                continue

            print(f"[INFO] start {i+1}/{len(inp)} | {name} | {website}")

            text = bundle_text(fetcher, website, mode="info")
            data, usage = gem.extract_json(text=text, schema=SCHEMA_IMPORT, system_rules=RULES_INFO)
            info = normalize_info_keys(data)

            # mapping province_id city_id
            prov_id, city_id = match_region(region_df, info.get("province_name","-"), info.get("city_name","-"))

            # build import row
            out: Dict[str, Any] = {
                "id": i+1,
                "university_code": None,
                "name": name,
                "slug": slugify(name),
                "short_name": acronym(name),
                "description": None,  # akan diisi di run_visimisi / run_all
                "logo": None,
                "type": info["type"],
                "status": info["status"],
                "accreditation": info["accreditation"],
                "website": website,
                "email": info["email"],
                "phone": info["phone"],
                "whatsapp": info["whatsapp"],
                "facebook": info["facebook"],
                "instagram": info["instagram"],
                "twitter": info["twitter"],
                "youtube": info["youtube"],
                "address": info["address"],
                "province_id": prov_id,
                "city_id": city_id,
                "postal_code": info["postal_code"],
                "cover": None,
            }
            rows.append(out)

            # token usage sum
            for k in total_usage:
                total_usage[k] += int(usage.get(k,0) or 0)

            state["done"][key] = "ok"
            json.dump(state, open(state_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

            print(f"[INFO] done | usage={usage} | total={total_usage}")

    df_out = build_import_frame(rows)
    out_xlsx = os.path.join(OUT_DIR, "import_info.xlsx")
    out_csv  = os.path.join(OUT_DIR, "import_info.csv")
    save_outputs(df_out, out_xlsx, out_csv)
    print(f"[DONE] saved: {out_xlsx} + {out_csv}")
    print(f"[TOKENS] total: {total_usage}")

if __name__ == "__main__":
    main()
