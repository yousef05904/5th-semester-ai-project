from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from ai_analyzer import analyze_article
from config import (
    MAX_ARTICLE_CHARS,
    MAX_RESULTS_PER_QUERY,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OUTPUT_DIR,
)
from dedupe import dedupe_leads
from exporter import export_leads, export_rejections
from fetcher import fetch_article
from models import ProjectLead
from pipeline_utils import lead_rejection_reason, make_rejection
from search import load_queries, search_web
from source_filters import (
    blocked_domain_reason,
    is_recent_publication,
)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    queries = load_queries(str(base_dir / "queries.txt"))
    if not queries:
        raise RuntimeError("queries.txt is empty.")

    client = OpenAI(api_key=OPENAI_API_KEY)

    search_results, rejected_items, total_search_results = search_web(queries, MAX_RESULTS_PER_QUERY)
    fetched_articles = []
    relevant_leads: list[ProjectLead] = []
    ai_analyzed = 0

    print(f"[main] Fetching {len(search_results)} filtered search results")
    for result in search_results:
        domain_reason = blocked_domain_reason(result["url"])
        if domain_reason:
            rejected_items.append(make_rejection("pre_fetch_filter", domain_reason, result=result))
            continue

        try:
            article = fetch_article(
                result["url"],
                title_hint=result.get("title") or None,
                max_article_chars=MAX_ARTICLE_CHARS,
            )
            if not article:
                rejected_items.append(make_rejection("fetch", "fetch failed or page text was too short", result=result))
                continue

            article.update(
                {
                    "query": result.get("query"),
                    "search_query": result.get("search_query"),
                    "search_title": result.get("title"),
                    "search_snippet": result.get("snippet"),
                    "source_domain": result.get("source_domain"),
                    "source_priority": result.get("source_priority"),
                }
            )

            recent = is_recent_publication(article.get("publication_date_hint"))
            if recent is False:
                rejected_items.append(
                    make_rejection(
                        "date_filter",
                        f"publication_date_hint older than 12 months: {article.get('publication_date_hint')}",
                        article=article,
                    )
                )
                continue

            fetched_articles.append(article)
        except Exception as exc:
            rejected_items.append(make_rejection("fetch", f"fetch exception: {exc}", result=result))
            print(f"[main] Fetch failed for {result['url']}: {exc}")

    print(f"[main] Analyzing {len(fetched_articles)} fetched articles")
    for article in fetched_articles:
        ai_analyzed += 1
        try:
            lead = analyze_article(client=client, model=OPENAI_MODEL, article=article)
            if not lead:
                rejected_items.append(make_rejection("ai", "analysis returned no lead", article=article))
                continue

            rejection_reason = lead_rejection_reason(lead, article)
            if rejection_reason:
                rejected_items.append(make_rejection("post_ai_filter", rejection_reason, article=article, lead=lead))
                continue

            relevant_leads.append(lead)
        except Exception as exc:
            rejected_items.append(make_rejection("ai", f"analysis exception: {exc}", article=article))
            print(f"[main] Analysis failed for {article['url']}: {exc}")

    deduplicated_leads, duplicate_rejections = dedupe_leads(relevant_leads)
    rejected_items.extend(duplicate_rejections)
    json_path, csv_path = export_leads(deduplicated_leads, OUTPUT_DIR)
    rejected_path = export_rejections(rejected_items, OUTPUT_DIR)

    summary = {
        "total_search_results": total_search_results,
        "fetched_articles": len(fetched_articles),
        "ai_analyzed": ai_analyzed,
        "relevant_before_dedup": len(relevant_leads),
        "rejected_count": len(rejected_items),
        "final_leads_count": len(deduplicated_leads),
        "duplicates_removed": len(duplicate_rejections),
    }

    print("[main] Summary")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"  JSON output: {json_path}")
    print(f"  CSV output: {csv_path}")
    print(f"  Rejected output: {rejected_path}")


if __name__ == "__main__":
    main()
