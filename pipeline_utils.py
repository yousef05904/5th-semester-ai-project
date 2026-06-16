from __future__ import annotations

from models import ProjectLead
from source_filters import (
    blocked_domain_reason,
    has_target_location,
    is_generic_project_name,
    is_recent_publication,
    noise_text_reason,
)


MIN_CONFIDENCE = 0.75


def lead_to_dict(lead: ProjectLead) -> dict:
    if hasattr(lead, "model_dump"):
        return lead.model_dump()
    return lead.dict()


def make_rejection(
    stage: str,
    reason: str,
    *,
    result: dict | None = None,
    article: dict | None = None,
    lead: ProjectLead | None = None,
) -> dict:
    source = result or article or {}
    rejection = {
        "stage": stage,
        "reason": reason,
        "source_url": source.get("source_url") or source.get("url") or getattr(lead, "source_url", None),
        "title": source.get("title"),
        "query": source.get("query"),
        "source_domain": source.get("source_domain"),
    }
    if result:
        rejection["snippet"] = result.get("snippet")
    if article:
        rejection["publication_date_hint"] = article.get("publication_date_hint")
    if lead:
        rejection["lead"] = lead_to_dict(lead)
    return rejection


def lead_rejection_reason(
    lead: ProjectLead,
    article: dict,
    target_location_terms: tuple[str, ...] | None = None,
) -> str | None:
    if not lead.is_relevant:
        return f"ai marked not relevant: {lead.reason}"

    if float(lead.confidence or 0.0) < MIN_CONFIDENCE:
        return f"confidence below {MIN_CONFIDENCE}: {lead.confidence}"

    if not lead.project_name:
        return "missing project_name"

    if is_generic_project_name(lead.project_name):
        return f"generic project_name: {lead.project_name}"

    if not lead.short_description:
        return "missing short_description"

    if lead.project_type == "unknown":
        return "unknown project_type"

    location_hint = " ".join(
        str(value)
        for value in (
            article.get("title"),
            article.get("search_snippet"),
            article.get("text", "")[:1000],
        )
        if value
    )
    if target_location_terms:
        if not has_target_location(None, None, location_hint, target_location_terms=target_location_terms):
            return "location is not target city or region"
    elif not has_target_location(lead.city, lead.region, location_hint, target_location_terms=target_location_terms):
        return "location is not target city or region"

    recent = is_recent_publication(lead.publication_date)
    if recent is False:
        return f"publication_date older than 12 months: {lead.publication_date}"

    domain_reason = blocked_domain_reason(lead.source_url)
    if domain_reason:
        return domain_reason

    text_reason = noise_text_reason(lead.project_name, lead.short_description or "", article.get("title") or "")
    if text_reason:
        return text_reason

    return None
