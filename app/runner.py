from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openai import OpenAI
from sqlmodel import Session

from ai_analyzer import analyze_article
from app.database import create_db_and_tables, engine
from app.db_models import MonitoringRun, ProjectLeadDB, RejectedItemDB
from app.region_config import get_region, target_location_terms
from dedupe import dedupe_leads
from exporter import export_leads_excel, export_leads_json
from fetcher import fetch_article
from models import ProjectLead
from pipeline_utils import lead_rejection_reason, lead_to_dict, make_rejection
from search import search_web
from source_filters import blocked_domain_reason, is_recent_publication


def _load_runtime_config():
    try:
        from config import MAX_ARTICLE_CHARS, MAX_RESULTS_PER_QUERY, OPENAI_API_KEY, OPENAI_MODEL, OUTPUT_DIR
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc

    return {
        "max_article_chars": MAX_ARTICLE_CHARS,
        "max_results_per_query": MAX_RESULTS_PER_QUERY,
        "openai_api_key": OPENAI_API_KEY,
        "openai_model": OPENAI_MODEL,
        "output_dir": OUTPUT_DIR,
    }


def _save_leads(session: Session, run_id: int, leads: list[ProjectLead]) -> None:
    for lead in leads:
        data = lead_to_dict(lead)
        session.add(
            ProjectLeadDB(
                run_id=run_id,
                project_name=data.get("project_name"),
                region=data.get("region"),
                city=data.get("city"),
                project_type=data.get("project_type"),
                stage=data.get("stage"),
                customer=data.get("customer"),
                short_description=data.get("short_description"),
                materials_demand=data.get("materials_demand"),
                priority=data.get("priority"),
                source_url=data.get("source_url") or "",
                publication_date=data.get("publication_date"),
                confidence=float(data.get("confidence") or 0.0),
                reason=data.get("reason") or "",
            )
        )


def _save_rejections(session: Session, run_id: int, rejections: list[dict]) -> None:
    for item in rejections:
        session.add(
            RejectedItemDB(
                run_id=run_id,
                title=item.get("title") or item.get("project_name"),
                source_url=item.get("source_url") or item.get("url"),
                reason=str(item.get("reason") or "rejected"),
            )
        )


def run_monitoring_for_region(region_key: str) -> dict:
    create_db_and_tables()
    runtime = _load_runtime_config()
    region = get_region(region_key)
    target_terms = target_location_terms(region)
    started_at = datetime.utcnow()

    print(f"[runner] Starting monitoring for {region['display_name']}")
    with Session(engine) as session:
        run = MonitoringRun(
            region_key=region["key"],
            region_name=region["region_name"],
            city=region["city"],
            started_at=started_at,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = int(run.id)

        client = OpenAI(api_key=runtime["openai_api_key"])
        search_results, rejected_items, total_search_results = search_web(
            region["search_terms"],
            runtime["max_results_per_query"],
            target_location_terms=target_terms,
        )

        fetched_articles: list[dict] = []
        relevant_leads: list[ProjectLead] = []
        ai_analyzed = 0

        print(f"[runner] Fetching {len(search_results)} filtered search results")
        for result in search_results:
            domain_reason = blocked_domain_reason(result["url"])
            if domain_reason:
                rejected_items.append(make_rejection("pre_fetch_filter", domain_reason, result=result))
                continue

            try:
                article = fetch_article(
                    result["url"],
                    title_hint=result.get("title") or None,
                    max_article_chars=runtime["max_article_chars"],
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
                print(f"[runner] Fetch failed for {result['url']}: {exc}")

        print(f"[runner] Analyzing {len(fetched_articles)} fetched articles")
        for article in fetched_articles:
            ai_analyzed += 1
            try:
                lead = analyze_article(
                    client=client,
                    model=runtime["openai_model"],
                    article=article,
                    target_city=region["city"],
                    target_region=region["region_name"],
                    target_location_terms=target_terms,
                )
                if not lead:
                    rejected_items.append(make_rejection("ai", "analysis returned no lead", article=article))
                    continue

                rejection_reason = lead_rejection_reason(lead, article, target_location_terms=target_terms)
                if rejection_reason:
                    rejected_items.append(make_rejection("post_ai_filter", rejection_reason, article=article, lead=lead))
                    continue

                relevant_leads.append(lead)
            except Exception as exc:
                rejected_items.append(make_rejection("ai", f"analysis exception: {exc}", article=article))
                print(f"[runner] Analysis failed for {article['url']}: {exc}")

        deduplicated_leads, duplicate_rejections = dedupe_leads(relevant_leads)
        rejected_items.extend(duplicate_rejections)

        output_dir: Path = runtime["output_dir"]
        excel_path = output_dir / f"{region_key}_run_{run_id}_leads.xlsx"
        json_path = output_dir / f"{region_key}_run_{run_id}_leads.json"
        export_leads_excel(deduplicated_leads, excel_path)
        export_leads_json(deduplicated_leads, json_path)

        run.finished_at = datetime.utcnow()
        run.total_search_results = total_search_results
        run.fetched_articles = len(fetched_articles)
        run.ai_analyzed = ai_analyzed
        run.relevant_before_dedup = len(relevant_leads)
        run.rejected_count = len(rejected_items)
        run.duplicates_removed = len(duplicate_rejections)
        run.final_leads_count = len(deduplicated_leads)
        run.excel_path = str(excel_path)
        run.json_path = str(json_path)

        _save_leads(session, run_id, deduplicated_leads)
        _save_rejections(session, run_id, rejected_items)
        session.add(run)
        session.commit()
        session.refresh(run)

    summary = {
        "run_id": run_id,
        "region_key": region_key,
        "region_name": region["region_name"],
        "city": region["city"],
        "total_search_results": total_search_results,
        "fetched_articles": len(fetched_articles),
        "ai_analyzed": ai_analyzed,
        "relevant_before_dedup": len(relevant_leads),
        "rejected_count": len(rejected_items),
        "duplicates_removed": len(duplicate_rejections),
        "final_leads_count": len(deduplicated_leads),
        "excel_path": str(excel_path),
        "json_path": str(json_path),
    }
    print(f"[runner] Finished run {run_id}: {summary}")
    return summary
