from __future__ import annotations

import re
from typing import Optional

import requests
import trafilatura
from bs4 import BeautifulSoup


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
}


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_with_bs4(html: str) -> tuple[Optional[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    text = soup.get_text("\n", strip=True)
    return title, _clean_text(text)


def fetch_article(url: str, title_hint: Optional[str], max_article_chars: int) -> Optional[dict]:
    print(f"[fetch] Downloading: {url}")
    html = None
    title = title_hint
    publication_date_hint = None
    text = ""

    try:
        html = trafilatura.fetch_url(url)
    except Exception as exc:
        print(f"[fetch] trafilatura.fetch_url failed for {url}: {exc}")

    if html:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_links=False,
                favor_precision=True,
            )
            if extracted:
                text = _clean_text(extracted)

            metadata = trafilatura.extract_metadata(html)
            if metadata and getattr(metadata, "title", None):
                title = metadata.title
            if metadata and getattr(metadata, "date", None):
                publication_date_hint = str(metadata.date)
        except Exception as exc:
            print(f"[fetch] trafilatura extraction failed for {url}: {exc}")

    if not text:
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
            response.raise_for_status()
            title_from_bs4, text = _extract_with_bs4(response.text)
            if not title:
                title = title_from_bs4
        except Exception as exc:
            print(f"[fetch] requests/bs4 fallback failed for {url}: {exc}")
            return None

    text = _clean_text(text)
    if len(text) < 500:
        print(f"[fetch] Skipping short page ({len(text)} chars): {url}")
        return None

    if len(text) > max_article_chars:
        text = text[:max_article_chars]

    return {
        "url": url,
        "title": title or "",
        "publication_date_hint": publication_date_hint,
        "text": text,
    }
