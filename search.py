from __future__ import annotations

import re
from typing import Iterable, List
from urllib.parse import urldefrag

from duckduckgo_search import DDGS

from source_filters import (
    append_negative_terms,
    get_domain,
    is_priority_domain,
    search_result_rejection_reason,
)


MIN_CANDIDATE_RESULTS_PER_QUERY = 15


def _normalize_url(url: str) -> str:
    clean_url, _fragment = urldefrag(url.strip())
    return clean_url


def _candidate_limit(max_results_per_query: int) -> int:
    return max(max_results_per_query, MIN_CANDIDATE_RESULTS_PER_QUERY)


def _search_query_variants(query: str) -> list[str]:
    variants = [query]
    without_year = re.sub(r"\b20\d{2}\b", "", query)
    without_year = re.sub(r"\s+", " ", without_year).strip()
    if without_year and without_year != query:
        variants.append(without_year)
    return [append_negative_terms(variant) for variant in dict.fromkeys(variants)]


def load_queries(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as handle:
        queries = [line.strip() for line in handle if line.strip() and not line.strip().startswith("#")]
    return queries


def search_web(
    queries: Iterable[str],
    max_results_per_query: int,
    target_location_terms: tuple[str, ...] | None = None,
) -> tuple[List[dict], List[dict], int]:
    results: List[dict] = []
    rejected: List[dict] = []
    seen_urls: set[str] = set()
    queries_list = list(queries)
    total_seen = 0

    print(f"[search] Starting search for {len(queries_list)} queries")
    with DDGS() as ddgs:
        for index, query in enumerate(queries_list, start=1):
            query_variants = _search_query_variants(query)
            for variant_index, search_query in enumerate(query_variants, start=1):
                suffix = f" variant {variant_index}/{len(query_variants)}" if len(query_variants) > 1 else ""
                print(f"[search] Query {index}/{len(queries_list)}{suffix}: {search_query}")
                try:
                    for item in ddgs.text(
                        search_query,
                        region="ru-ru",
                        safesearch="off",
                        timelimit="y",
                        max_results=_candidate_limit(max_results_per_query),
                    ):
                        total_seen += 1
                        url = str(item.get("href") or item.get("url") or "").strip()
                        if not url:
                            continue
                        url = _normalize_url(url)
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        result = {
                            "title": str(item.get("title") or "").strip(),
                            "url": url,
                            "source_url": url,
                            "snippet": str(item.get("body") or item.get("snippet") or "").strip(),
                            "query": query,
                            "search_query": search_query,
                            "source_domain": get_domain(url),
                            "source_priority": is_priority_domain(url),
                        }
                        rejection_reason = search_result_rejection_reason(
                            result,
                            target_location_terms=target_location_terms,
                        )
                        if rejection_reason:
                            rejected.append(
                                {
                                    "stage": "search_filter",
                                    "reason": rejection_reason,
                                    **result,
                                }
                            )
                            continue
                        results.append(result)
                except Exception as exc:
                    print(f"[search] Query failed: {query!r} -> {exc}")

    results.sort(key=lambda result: (not result.get("source_priority", False), result.get("source_domain", "")))
    print(f"[search] Finished. Unique results: {len(results)}")
    print(f"[search] Rejected by search filters: {len(rejected)}")
    return results, rejected, total_seen
