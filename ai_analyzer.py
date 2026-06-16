from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from openai import OpenAI

from local_analyzer import analyze_article_locally
from models import ProjectLead
from source_filters import fresh_cutoff


PROJECT_LEAD_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_relevant",
        "project_name",
        "region",
        "city",
        "project_type",
        "stage",
        "customer",
        "short_description",
        "materials_demand",
        "priority",
        "source_url",
        "publication_date",
        "confidence",
        "reason",
    ],
    "properties": {
        "is_relevant": {"type": "boolean"},
        "project_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "region": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "city": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "project_type": {
            "type": "string",
            "enum": [
                "construction",
                "landscaping",
                "renovation",
                "infrastructure",
                "tender",
                "other",
                "unknown",
            ],
        },
        "stage": {
            "type": "string",
            "enum": [
                "initiative",
                "design",
                "tender",
                "construction",
                "completed",
                "unknown",
            ],
        },
        "customer": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "short_description": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "materials_demand": {
            "type": "string",
            "enum": ["low", "medium", "high", "unknown"],
        },
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "source_url": {"type": "string"},
        "publication_date": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
}


SYSTEM_PROMPT = """
You are an analyst for Russian-language news and web pages.

Your task:
- Decide whether the page describes one concrete project lead for construction,
  renovation, landscaping, urban improvement, infrastructure, tender, or real
  estate development in Yekaterinburg or the Sverdlovsk region.
- Extract structured fields from the page.
- Return only JSON that matches the given schema.

Rules:
- Set is_relevant=false if there is no concrete project, object, tender, address,
  named public space, named road, named building, named residential complex, or
  clearly described single scope of work.
- Set is_relevant=false for general construction articles, encyclopedia/reference
  pages, dictionaries, generic SEO pages, rankings, "top" lists, mortgage/real
  estate marketing articles, and pages that only discuss construction in general.
- Set is_relevant=false if the location is not clearly Yekaterinburg or the
  Sverdlovsk region.
- Set is_relevant=false if project_name is unknown or cannot be generated clearly.
- If the article clearly describes one concrete project but no formal name is
  written, generate a concise Russian project_name from the object and scope,
  for example "Ремонт улицы Малышева" or "Благоустройство набережной Исети".
- Do not use generic project names like "Строительство", "Реконструкция",
  "Благоустройство", "Квартиры в новостройках", or "Ремонт дорог".
- Prefer pages from the last 12 months. If a page is clearly old or describes
  historical/non-current work, mark it not relevant unless the project is still
  active or has a current tender.
- Confidence must be lower than 0.7 for weak, unclear, marketing-like, or only
  partially location-matched cases.
- For not relevant pages, still fill the required fields using:
  project_type = "unknown"
  stage = "unknown"
  materials_demand = "unknown"
  priority = "low"
- project_name, region, city, customer, short_description, publication_date may
  be null for not relevant pages.
- Use Russian context correctly even if the source page is Russian.
- Confidence must be a float from 0 to 1.
- reason should briefly explain the decision in English or Russian.

Stage mapping:
- initiative: announcement, plan, discussion, proposal
- design: design, проектирование, разработка ПСД
- tender: конкурс, закупка, тендер, аукцион
- construction: construction started, works ongoing, строят, начались работы
- completed: completed, opened, finished
- unknown: unclear

Materials demand:
- high for large buildings, residential complexes, roads, schools, hospitals,
  major reconstruction
- medium for parks, landscaping, small public spaces
- low for minor repairs or unclear demand
""".strip()


def _location_label(target_city: str | None, target_region: str | None) -> str:
    parts = [part for part in (target_city, target_region) if part]
    if parts:
        return " / ".join(parts)
    return "the target city or region from the search query"


def _build_system_prompt(target_city: str | None, target_region: str | None) -> str:
    location = _location_label(target_city, target_region)
    prompt = SYSTEM_PROMPT.replace(
        "in Yekaterinburg or the Sverdlovsk region",
        f"in {location}",
    )
    prompt = prompt.replace(
        "not clearly Yekaterinburg or the\n  Sverdlovsk region",
        f"not clearly {location}",
    )
    return (
        f"{prompt}\n\n"
        f"Current target location: {location}.\n"
        "Treat that target location as authoritative for this run."
    )


def _is_unavailable_ai_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    return (
        "unsupported_country_region_territory" in message
        or "request_forbidden" in message
        or "country, region, or territory not supported" in message
    )


def _to_project_lead(payload: dict, source_url: str) -> ProjectLead:
    payload = dict(payload)
    payload.setdefault("source_url", source_url)
    for field in ("project_name", "region", "city", "customer", "short_description", "publication_date"):
        value = payload.get(field)
        if isinstance(value, str):
            value = value.strip()
            if not value or value.casefold() in {"unknown", "none", "null", "неизвестно"}:
                value = None
            payload[field] = value
    if hasattr(ProjectLead, "model_validate"):
        return ProjectLead.model_validate(payload)
    return ProjectLead.parse_obj(payload)


def _extract_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)


def _create_completion(client: OpenAI, model: str, system_prompt: str, user_prompt: str, use_schema: bool):
    kwargs = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if use_schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "project_lead",
                "schema": PROJECT_LEAD_SCHEMA,
                "strict": True,
            },
        }
    else:
        kwargs["response_format"] = {"type": "json_object"}
    return client.chat.completions.create(**kwargs)


def analyze_article(
    client: OpenAI,
    model: str,
    article: dict,
    max_retries: int = 3,
    target_city: str | None = None,
    target_region: str | None = None,
    target_location_terms: tuple[str, ...] | None = None,
    enable_local_fallback: bool = True,
) -> Optional[ProjectLead]:
    source_url = article["url"]
    title = article.get("title") or ""
    publication_date_hint = article.get("publication_date_hint") or ""
    search_snippet = article.get("search_snippet") or ""
    text = article.get("text") or ""
    today = date.today()
    cutoff = fresh_cutoff(today)
    system_prompt = _build_system_prompt(target_city, target_region)

    user_prompt = f"""
Analyze this page and return a structured lead.

Current date: {today.isoformat()}
Freshness cutoff: {cutoff.isoformat()} (prefer pages on or after this date)
Target city: {target_city or ""}
Target region: {target_region or ""}
URL: {source_url}
Title: {title}
Publication date hint: {publication_date_hint}
Search snippet: {search_snippet}

Text:
{text}
""".strip()

    last_error: Optional[Exception] = None
    use_schema = True

    for attempt in range(1, max_retries + 1):
        print(f"[ai] Analyzing {source_url} (attempt {attempt}/{max_retries})")
        try:
            response = _create_completion(client, model, system_prompt, user_prompt, use_schema)
            content = response.choices[0].message.content or ""
            data = _extract_json(content)
            return _to_project_lead(data, source_url)
        except Exception as exc:
            last_error = exc
            print(f"[ai] Failed for {source_url}: {exc}")
            if _is_unavailable_ai_error(exc):
                print("[ai] Remote AI is unavailable in this environment. Using local fallback.")
                break
            if use_schema:
                print("[ai] Retrying with plain JSON object mode.")
                use_schema = False

    print(f"[ai] Giving up on {source_url}: {last_error}")
    if enable_local_fallback:
        return analyze_article_locally(
            article,
            city=target_city,
            region=target_region,
            target_location_terms=target_location_terms,
            reason_prefix=f"Local fallback after AI failure ({last_error})",
        )
    return None
