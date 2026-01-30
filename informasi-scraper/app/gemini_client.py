from __future__ import annotations
from typing import Any, Dict, Tuple, Optional
import json
import random
import time

from google import genai
from google.genai import errors as genai_errors

from .config import GEMINI_API_KEY, GEMINI_MODEL


def _usage_from_resp(resp) -> Dict[str, int]:
    usage = {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0}
    try:
        um = getattr(resp, "usage_metadata", None)
        if um:
            usage["prompt_tokens"] = int(getattr(um, "prompt_token_count", 0) or 0)
            usage["candidates_tokens"] = int(getattr(um, "candidates_token_count", 0) or 0)
            usage["total_tokens"] = int(getattr(um, "total_token_count", 0) or 0)
    except Exception:
        pass
    return usage


def _safe_json_loads(s: str) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


class GeminiJSON:
    """
    Robust JSON extractor (schema-based):
    - Retry on 503/429/transient errors with backoff + jitter
    - Fallback model chain if primary overloaded
    - Never crash pipeline: returns {} if all attempts fail
    - Browse fallback: pass URL and instruct model to open/browse it (like your visimisi.py)
    """

    def __init__(self, model: Optional[str] = None):
        assert GEMINI_API_KEY, "GEMINI_API_KEY kosong. Pastikan ada di .env"
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        primary = (model or GEMINI_MODEL).strip()

        # fallback order (hapus yang tidak tersedia di akun Anda)
        self.models = [
            primary,
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

    def _sleep(self, attempt: int, max_sleep: float = 60.0):
        sleep_s = min(max_sleep, (2 ** (attempt - 1))) + random.uniform(0.0, 1.5)
        time.sleep(sleep_s)
        return sleep_s

    def extract_json(
        self,
        text: str,
        schema: Dict[str, Any],
        system_rules: str,
        max_retries: int = 7,
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        payload = system_rules + "\n\n=== BUKTI TEKS ===\n" + (text or "")

        total_usage = {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0}
        last_err: Optional[Exception] = None

        for mi, model_name in enumerate(self.models):
            for attempt in range(1, max_retries + 1):
                try:
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=[{"role": "user", "parts": [{"text": payload}]}],
                        config={
                            "temperature": 0.0,
                            "response_mime_type": "application/json",
                            "response_schema": schema,
                        },
                    )
                    usage = _usage_from_resp(resp)
                    for k in total_usage:
                        total_usage[k] += int(usage.get(k, 0) or 0)

                    data = _safe_json_loads(getattr(resp, "text", "") or "")
                    return data, total_usage

                except genai_errors.ServerError as e:
                    last_err = e
                    msg = str(e).lower()
                    if "503" in msg or "unavailable" in msg or "overloaded" in msg:
                        s = self._sleep(attempt)
                        print(f"[GEMINI] 503 overloaded | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s")
                        continue
                    s = self._sleep(attempt, max_sleep=30.0)
                    print(f"[GEMINI] server err | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s | err={e}")
                    continue

                except genai_errors.ClientError as e:
                    last_err = e
                    msg = str(e).lower()
                    if "429" in msg or "resource_exhausted" in msg:
                        s = self._sleep(attempt)
                        print(f"[GEMINI] 429 limited | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s")
                        continue
                    print(f"[GEMINI] client error (no-retry): {e}")
                    return {}, total_usage

                except Exception as e:
                    last_err = e
                    s = self._sleep(attempt, max_sleep=30.0)
                    print(f"[GEMINI] transient err | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s | err={e}")
                    continue

            if mi < len(self.models) - 1:
                print(f"[GEMINI] switch model -> {self.models[mi + 1]}")

        print(f"[GEMINI] FAILED all models. last_err={last_err}")
        return {}, total_usage

    def extract_json_browse(
        self,
        url: str,
        campus_name: str,
        schema: Dict[str, Any],
        system_rules: str,
        max_retries: int = 7,
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Browse fallback ala visimisi.py:
        - Provide official URL and ask model to open/browse it and fill the schema.
        - Use ONLY when Playwright text bundle is too short / blocked.
        """
        prompt = f"""
Kamu akan diberi URL website universitas.
TUGAS: Buka URL tersebut dan ekstrak informasi sesuai schema di bawah secara akurat.

OUTPUT HARUS JSON sesuai schema (tanpa teks lain).

SCHEMA:
{json.dumps(schema, ensure_ascii=False)}

ATURAN / SYSTEM RULES:
{system_rules}

Konteks:
- nama kampus (dari database): {campus_name}
- official_url: {url}

URL:
{url}
""".strip()

        total_usage = {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0}
        last_err: Optional[Exception] = None

        for mi, model_name in enumerate(self.models):
            for attempt in range(1, max_retries + 1):
                try:
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=[{"role": "user", "parts": [{"text": prompt}]}],
                        config={
                            "temperature": 0.0,
                            "response_mime_type": "application/json",
                            "response_schema": schema,
                        },
                    )
                    usage = _usage_from_resp(resp)
                    for k in total_usage:
                        total_usage[k] += int(usage.get(k, 0) or 0)

                    data = _safe_json_loads(getattr(resp, "text", "") or "")
                    return data, total_usage

                except genai_errors.ServerError as e:
                    last_err = e
                    msg = str(e).lower()
                    if "503" in msg or "unavailable" in msg or "overloaded" in msg:
                        s = self._sleep(attempt)
                        print(f"[GEMINI:BROWSE] 503 overloaded | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s")
                        continue
                    s = self._sleep(attempt, max_sleep=30.0)
                    print(f"[GEMINI:BROWSE] server err | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s | err={e}")
                    continue

                except genai_errors.ClientError as e:
                    last_err = e
                    msg = str(e).lower()
                    if "429" in msg or "resource_exhausted" in msg:
                        s = self._sleep(attempt)
                        print(f"[GEMINI:BROWSE] 429 limited | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s")
                        continue
                    print(f"[GEMINI:BROWSE] client error (no-retry): {e}")
                    return {}, total_usage

                except Exception as e:
                    last_err = e
                    s = self._sleep(attempt, max_sleep=30.0)
                    print(f"[GEMINI:BROWSE] transient err | model={model_name} | retry={attempt}/{max_retries} | sleep={s:.1f}s | err={e}")
                    continue

            if mi < len(self.models) - 1:
                print(f"[GEMINI:BROWSE] switch model -> {self.models[mi + 1]}")

        print(f"[GEMINI:BROWSE] FAILED all models. last_err={last_err}")
        return {}, total_usage
