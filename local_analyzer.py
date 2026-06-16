from __future__ import annotations

import re

from models import ProjectLead
from source_filters import (
    PROJECT_SIGNAL_PATTERNS,
    has_target_location,
    is_recent_publication,
    noise_text_reason,
    parse_publication_date,
)


TYPE_RULES = (
    ("tender", ("тендер", "закуп", "аукцион", "конкурс", "контракт")),
    ("landscaping", ("благоустрой", "парк", "сквер", "набереж", "двор", "озелен")),
    ("renovation", ("реконструк", "капремонт", "ремонт", "модерниз")),
    ("infrastructure", ("дорог", "улиц", "мост", "развяз", "инфраструктур", "сеть", "теплотрас", "водопровод")),
    ("construction", ("строител", "постро", "возвед", "школ", "сад", "больниц", "поликлиник", "жк", "дом")),
)

STAGE_RULES = (
    ("tender", ("тендер", "закуп", "аукцион", "конкурс", "контракт")),
    ("design", ("проектирован", "проектную документац", "псд", "разработк")),
    ("construction", ("строят", "строительств", "начал", "ведутся", "ремонтируют", "реконструируют")),
    ("completed", ("заверш", "откры", "сдали", "готов")),
    ("initiative", ("план", "объяв", "намер", "проект")),
)

HIGH_DEMAND_PATTERNS = (
    "дорог",
    "мост",
    "развяз",
    "школ",
    "детск",
    "сад",
    "больниц",
    "поликлиник",
    "жк",
    "жилой комплекс",
    "дом",
    "инфраструктур",
)

MEDIUM_DEMAND_PATTERNS = (
    "парк",
    "сквер",
    "набереж",
    "благоустрой",
    "двор",
    "площад",
)


def _clean_inline(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_for_match(value: str | None) -> str:
    return _clean_inline(value).casefold().replace("ё", "е")


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _classify_project_type(text: str) -> str:
    for project_type, patterns in TYPE_RULES:
        if _contains_any(text, patterns):
            return project_type
    return "unknown"


def _classify_stage(text: str) -> str:
    for stage, patterns in STAGE_RULES:
        if _contains_any(text, patterns):
            return stage
    return "unknown"


def _classify_materials_demand(text: str, project_type: str) -> str:
    if _contains_any(text, HIGH_DEMAND_PATTERNS):
        return "high"
    if project_type in {"construction", "infrastructure", "tender"}:
        return "high"
    if _contains_any(text, MEDIUM_DEMAND_PATTERNS):
        return "medium"
    if project_type in {"landscaping", "renovation"}:
        return "medium"
    return "low"


def _first_sentence(text: str) -> str:
    text = _clean_inline(text)
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return parts[0][:320].strip()


def _project_name_from_title(title: str, description: str) -> str:
    name = _clean_inline(title)
    for separator in (" | ", " — ", " - "):
        if separator in name:
            left, right = [part.strip() for part in name.split(separator, 1)]
            if len(left) >= 12:
                name = left
            elif len(right) >= 12:
                name = right
            break

    if not name or len(name) < 8:
        name = _first_sentence(description)

    return name[:180].strip()


def _publication_date(value: str | None) -> str | None:
    parsed = parse_publication_date(value)
    if parsed:
        return parsed.isoformat()
    cleaned = _clean_inline(value)
    return cleaned or None


def _not_relevant(article: dict, reason: str, city: str | None, region: str | None) -> ProjectLead:
    return ProjectLead(
        is_relevant=False,
        project_name=None,
        region=region,
        city=city,
        project_type="unknown",
        stage="unknown",
        customer=None,
        short_description=None,
        materials_demand="unknown",
        priority="low",
        source_url=str(article.get("url") or ""),
        publication_date=_publication_date(article.get("publication_date_hint")),
        confidence=0.0,
        reason=reason,
    )


def analyze_article_locally(
    article: dict,
    *,
    city: str | None = None,
    region: str | None = None,
    target_location_terms: tuple[str, ...] | None = None,
    reason_prefix: str = "Local fallback analysis",
) -> ProjectLead:
    title = _clean_inline(article.get("title") or article.get("search_title"))
    snippet = _clean_inline(article.get("search_snippet"))
    text = _clean_inline(article.get("text"))
    haystack = " ".join(part for part in (title, snippet, text[:5000]) if part)
    match_text = _clean_for_match(haystack)

    noise_reason = noise_text_reason(title, snippet)
    if noise_reason:
        return _not_relevant(article, noise_reason, city, region)

    if target_location_terms and not has_target_location(None, None, haystack, target_location_terms):
        return _not_relevant(article, "local fallback: target location not found", city, region)

    if not any(pattern in match_text for pattern in PROJECT_SIGNAL_PATTERNS):
        return _not_relevant(article, "local fallback: no project signal", city, region)

    project_type = _classify_project_type(match_text)
    if project_type == "unknown":
        return _not_relevant(article, "local fallback: unknown project type", city, region)

    publication = _publication_date(article.get("publication_date_hint"))
    if is_recent_publication(publication) is False:
        return _not_relevant(article, f"local fallback: old publication date {publication}", city, region)

    description = snippet or _first_sentence(text) or title
    project_name = _project_name_from_title(title, description)
    stage = _classify_stage(match_text)
    materials_demand = _classify_materials_demand(match_text, project_type)
    confidence = 0.82
    if publication:
        confidence += 0.04
    if target_location_terms and has_target_location(None, None, title + " " + snippet, target_location_terms):
        confidence += 0.04
    confidence = min(confidence, 0.9)
    priority = "high" if materials_demand == "high" and confidence >= 0.84 else "medium"

    return ProjectLead(
        is_relevant=True,
        project_name=project_name,
        region=region,
        city=city,
        project_type=project_type,
        stage=stage,
        customer=None,
        short_description=description[:500],
        materials_demand=materials_demand,
        priority=priority,
        source_url=str(article.get("url") or ""),
        publication_date=publication,
        confidence=confidence,
        reason=f"{reason_prefix}: matched target location and project keywords without remote AI.",
    )
