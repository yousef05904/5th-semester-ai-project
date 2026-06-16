from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit


BLOCKED_DOMAINS = {
    "wikipedia.org",
    "wiktionary.org",
    "wikidata.org",
    "wikiquote.org",
    "wikimedia.org",
    "academic.ru",
    "dic.academic.ru",
    "kartaslov.ru",
    "gufo.me",
    "znachenie-slova.ru",
    "slovar.cc",
    "diclib.com",
    "encyclopedia.com",
    "britannica.com",
    "yapokupayu.ru",
    "baidu.com",
    "yandex.ru",
    "tripplanet.ru",
}

PRIORITY_DOMAINS = {
    "ekburg.ru",
    "adm-ekburg.ru",
    "midural.ru",
    "gov66.ru",
    "zakupki.gov.ru",
    "rostender.info",
    "bicotender.ru",
    "tender-paritet.ru",
    "myseldon.com",
    "e1.ru",
    "66.ru",
    "urbc.ru",
    "eanews.ru",
    "dk.ru",
    "ngzt.ru",
    "newdaynews.ru",
    "eburg.mk.ru",
    "uralinform.ru",
    "vedomostiural.ru",
    "ural-meridian.ru",
    "kommersant.ru",
}

NEGATIVE_SEARCH_TERMS = (
    "-википедия",
    "-энциклопедия",
    "-\"что такое\"",
    "-топ",
    "-подборка",
    "-ипотека",
)

NOISE_TEXT_PATTERNS = (
    "википедия",
    "энциклопедия",
    "что такое",
    "значение слова",
    "словарь",
    "топ ",
    "топ-",
    "подборка",
    "рейтинг",
    "лучшие новостройки",
    "выгодная ипотека",
    "ипотека",
    "достопримечательности",
    "куда сходить",
    "путеводитель",
    "карта",
    "maps",
    "отзывы",
)

PROJECT_SIGNAL_PATTERNS = (
    "строител",
    "постро",
    "реконструк",
    "ремонт",
    "благоустрой",
    "тендер",
    "закуп",
    "подряд",
    "дорог",
    "улиц",
    "школ",
    "детск",
    "сад",
    "жк",
    "жилой комплекс",
    "инфраструктур",
    "проект",
)

TARGET_LOCATION_PATTERNS = (
    "екатеринбург",
    "свердловск",
    "академический район",
    "ekaterinburg",
    "sverdlovsk",
)

GENERIC_PROJECT_NAMES = {
    "строительство",
    "реконструкция",
    "благоустройство",
    "ремонт дорог",
    "новостройки",
    "квартиры в новостройках",
    "строительство екатеринбург",
    "благоустройство екатеринбург",
}


def get_domain(url: str) -> str:
    domain = urlsplit(url.strip()).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def domain_matches(domain: str, candidates: set[str]) -> str | None:
    for candidate in candidates:
        if domain == candidate or domain.endswith(f".{candidate}"):
            return candidate
    return None


def blocked_domain_reason(url: str) -> str | None:
    domain = get_domain(url)
    blocked = domain_matches(domain, BLOCKED_DOMAINS)
    if blocked:
        return f"blocked domain: {blocked}"
    return None


def is_priority_domain(url: str) -> bool:
    return domain_matches(get_domain(url), PRIORITY_DOMAINS) is not None


def append_negative_terms(query: str) -> str:
    lower_query = query.casefold()
    missing_terms = [term for term in NEGATIVE_SEARCH_TERMS if term.casefold() not in lower_query]
    if not missing_terms:
        return query
    return f"{query} {' '.join(missing_terms)}"


def _clean_for_matching(value: str) -> str:
    text = value.casefold().replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def noise_text_reason(*values: str) -> str | None:
    text = _clean_for_matching(" ".join(value for value in values if value))
    for pattern in NOISE_TEXT_PATTERNS:
        if pattern in text:
            return f"noise text pattern: {pattern}"
    return None


def search_result_rejection_reason(result: dict, target_location_terms: tuple[str, ...] | None = None) -> str | None:
    url = str(result.get("url") or "")
    reason = blocked_domain_reason(url)
    if reason:
        return reason
    reason = noise_text_reason(str(result.get("title") or ""), str(result.get("snippet") or ""))
    if reason:
        return reason
    search_text = f"{result.get('title') or ''} {result.get('snippet') or ''} {url}"
    if not has_target_location(None, None, search_text, target_location_terms=target_location_terms):
        return "search result does not mention target city or region"
    clean_text = _clean_for_matching(search_text)
    if not any(pattern in clean_text for pattern in PROJECT_SIGNAL_PATTERNS):
        return "search result has no concrete project signal"
    return None


def fresh_cutoff(today: date | None = None) -> date:
    today = today or date.today()
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        return today.replace(year=today.year - 1, day=28)


def parse_publication_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw or raw.casefold() in {"unknown", "none", "null", "неизвестно"}:
        return None

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    match = re.search(r"(\d{4})-(\d{2})", raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            return None

    match = re.search(r"\b(20\d{2})\b", raw)
    if match:
        try:
            return date(int(match.group(1)), 1, 1)
        except ValueError:
            return None

    return None


def is_recent_publication(value: str | None, today: date | None = None) -> bool | None:
    published = parse_publication_date(value)
    if not published:
        return None
    return published >= fresh_cutoff(today)


def has_target_location(
    city: str | None,
    region: str | None,
    text_hint: str | None = None,
    target_location_terms: tuple[str, ...] | None = None,
) -> bool:
    text = _clean_for_matching(" ".join(part for part in (city, region, text_hint) if part))
    patterns = target_location_terms or TARGET_LOCATION_PATTERNS
    return any(_clean_for_matching(pattern) in text for pattern in patterns)


def is_generic_project_name(project_name: str | None) -> bool:
    if not project_name:
        return True
    normalized = _clean_for_matching(project_name)
    normalized = re.sub(r"[^\wа-яА-ЯёЁ]+", " ", normalized).strip()
    return normalized in GENERIC_PROJECT_NAMES
