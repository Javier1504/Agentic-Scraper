from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .config import HEADLESS, NAV_TIMEOUT_MS, WAIT_AFTER_LOAD_MS, MAX_TEXT_PER_PAGE
from .utils import normalize_url


@dataclass
class FetchResult:
    ok: bool
    final_url: str
    html: str
    text: str
    links: List[Dict[str, str]]  # [{"href": "...", "text": "..."}]
    error: str = ""
    status: int = 0


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = soup.get_text(" ", strip=True)
    return (text or "")[:MAX_TEXT_PER_PAGE]


def _dedup_links(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for it in items:
        href = (it.get("href") or "").strip()
        if not href:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({"href": href, "text": (it.get("text") or "").strip()})
    return out


class PlaywrightFetcher:
    """
    Stronger fetcher:
    - Human-like context (UA/locale/timezone/headers)
    - Scroll + innerText extraction (better for JS-heavy pages)
    - Link extraction from DOM (anchor text captured)
    - Also extracts embedded assets (iframe/embed/object/img/link)
    """

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=HEADLESS)
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="id-ID",
            timezone_id="Asia/Jakarta",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
            },
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def _extract_dom_links(self, page, base_url: str) -> List[Dict[str, str]]:
        try:
            items = page.evaluate(
                """() => {
                    const out = [];
                    const els = Array.from(document.querySelectorAll("a[href]"));
                    for (const a of els) {
                      const href = (a.getAttribute("href") || "").trim();
                      const text = (a.innerText || a.textContent || "").trim();
                      if (href) out.push({href, text});
                    }
                    return out;
                }"""
            ) or []
        except Exception:
            items = []

        out = []
        for it in items:
            href = (it.get("href") or "").strip()
            text = (it.get("text") or "").strip()
            if not href or href.startswith("#"):
                continue

            if href.startswith("/"):
                href = urljoin(base_url, href)
            else:
                href = urljoin(base_url, href)

            href = normalize_url(href)
            if href.startswith("http"):
                out.append({"href": href, "text": text})
        return _dedup_links(out)

    def _extract_embeds(self, html: str, base_url: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html or "", "html.parser")
        urls: List[Dict[str, str]] = []

        selectors = [
            ("img", "src"),
            ("source", "src"),
            ("iframe", "src"),
            ("embed", "src"),
            ("object", "data"),
            ("link", "href"),
        ]
        for tag, attr in selectors:
            for el in soup.select(f"{tag}[{attr}]"):
                v = (el.get(attr) or "").strip()
                if not v:
                    continue
                u = normalize_url(urljoin(base_url, v))
                if u.startswith("http"):
                    urls.append({"href": u, "text": ""})
        return _dedup_links(urls)

    def _extract_text_multi(self, page) -> str:
        try:
            # scroll to trigger lazy content
            for _ in range(4):
                page.mouse.wheel(0, 1600)
                page.wait_for_timeout(350)

            txt = page.evaluate(
                """() => {
                    const t = (document.body && document.body.innerText) ? document.body.innerText : "";
                    const t2 = (document.documentElement && document.documentElement.innerText) ? document.documentElement.innerText : "";
                    return (t.length >= t2.length ? t : t2);
                }"""
            )
            txt = (txt or "").strip()
            if txt:
                txt = " ".join(txt.split())
                return txt[:MAX_TEXT_PER_PAGE]
        except Exception:
            pass

        try:
            html = page.content()
            return _html_to_text(html)
        except Exception:
            return ""

    def fetch(self, url: str) -> FetchResult:
        url = normalize_url(url)
        page = self._context.new_page()
        status = 0
        try:
            page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
            resp = page.goto(url, wait_until="domcontentloaded")
            if resp:
                status = resp.status

            page.wait_for_timeout(WAIT_AFTER_LOAD_MS)

            final_url = page.url
            html = page.content()

            title = ""
            try:
                title = (page.title() or "").lower()
            except Exception:
                title = ""

            text = self._extract_text_multi(page)
            dom_links = self._extract_dom_links(page, final_url)
            embed_links = self._extract_embeds(html, final_url)

            links = _dedup_links(dom_links + embed_links)

            ok = bool(resp) and status < 400 and ("just a moment" not in title)
            err = ""
            if "just a moment" in title or "checking your browser" in (text or "").lower():
                err = "blocked_cloudflare_like"

            return FetchResult(ok=ok, final_url=final_url, html=html, text=text, links=links, error=err, status=status)

        except PWTimeout as e:
            return FetchResult(False, url, "", "", [], error=f"playwright_timeout:{e}", status=status)
        except Exception as e:
            return FetchResult(False, url, "", "", [], error=f"playwright_err:{e}", status=status)
        finally:
            page.close()
