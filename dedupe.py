from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, List
from urllib.parse import urlsplit, urlunsplit

from source_filters import parse_publication_date


PROJECT_NAME_STOPWORDS = {
    "в",
    "во",
    "на",
    "по",
    "для",
    "и",
    "или",
    "с",
    "со",
    "к",
    "от",
    "до",
    "г",
    "город",
    "города",
    "екатеринбург",
    "екатеринбурга",
    "екатеринбурге",
    "свердловская",
    "свердловской",
    "область",
    "области",
    "строительство",
    "строительства",
    "строительный",
    "реконструкция",
    "реконструкции",
    "ремонт",
    "капитальный",
    "капремонт",
    "благоустройство",
    "благоустройства",
    "проект",
    "проекта",
    "объект",
    "объекта",
    "работы",
    "работ",
    "ул",
    "улица",
    "улицы",
    "проспект",
    "пр",
}


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.IGNORECASE)
    tokens = [token for token in text.split() if token not in PROJECT_NAME_STOPWORDS]
    return " ".join(tokens)


def _normalize_city(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.IGNORECASE).strip()


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    if path == "":
        path = "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _to_dict(item) -> dict:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return item.dict()


def _name_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))

    sequence_score = SequenceMatcher(None, left, right).ratio()
    return max(token_score, sequence_score)


def _completeness_score(lead) -> int:
    data = _to_dict(lead)
    score = 0
    for key, value in data.items():
        if key == "is_relevant":
            continue
        if isinstance(value, str):
            if value.strip() and value.strip().casefold() not in {"unknown", "none", "null", "неизвестно"}:
                score += 1
        elif value is not None:
            score += 1
    return score


def _date_score(lead) -> int:
    published = parse_publication_date(getattr(lead, "publication_date", None))
    return published.toordinal() if published else 0


def _lead_rank(lead) -> tuple[int, int, float]:
    return (
        _completeness_score(lead),
        _date_score(lead),
        float(getattr(lead, "confidence", 0.0) or 0.0),
    )


def _same_city(left, right) -> bool:
    left_city = _normalize_city(getattr(left, "city", None) or getattr(left, "region", None) or "")
    right_city = _normalize_city(getattr(right, "city", None) or getattr(right, "region", None) or "")
    return bool(left_city and right_city and left_city == right_city)


def _duplicate_reason(left, right) -> str | None:
    left_url = normalize_url(getattr(left, "source_url", "") or "")
    right_url = normalize_url(getattr(right, "source_url", "") or "")
    if left_url and right_url and left_url == right_url:
        return "duplicate source_url"

    if not _same_city(left, right):
        return None

    left_name = normalize_text(getattr(left, "project_name", "") or "")
    right_name = normalize_text(getattr(right, "project_name", "") or "")
    if left_name and right_name and left_name == right_name:
        return "duplicate normalized project_name + city"

    similarity = _name_similarity(left_name, right_name)
    if similarity > 0.85:
        return f"duplicate similar project_name + city: similarity={similarity:.2f}"

    return None


def _rejected_duplicate(lead, kept, reason: str) -> dict:
    return {
        "stage": "dedupe",
        "reason": reason,
        "source_url": getattr(lead, "source_url", None),
        "project_name": getattr(lead, "project_name", None),
        "kept_source_url": getattr(kept, "source_url", None),
        "kept_project_name": getattr(kept, "project_name", None),
        "lead": _to_dict(lead),
    }


def dedupe_leads(leads: Iterable) -> tuple[List, List[dict]]:
    unique: List = []
    rejected: List[dict] = []

    for lead in leads:
        duplicate_index = None
        duplicate_reason = None

        for index, existing in enumerate(unique):
            reason = _duplicate_reason(lead, existing)
            if reason:
                duplicate_index = index
                duplicate_reason = reason
                break

        if duplicate_index is None:
            unique.append(lead)
            continue

        existing = unique[duplicate_index]
        if _lead_rank(lead) > _lead_rank(existing):
            unique[duplicate_index] = lead
            rejected.append(_rejected_duplicate(existing, lead, f"{duplicate_reason}; replaced by better lead"))
        else:
            rejected.append(_rejected_duplicate(lead, existing, f"{duplicate_reason}; kept better lead"))

    return unique, rejected
