from __future__ import annotations


def _search_terms(city: str, region_name: str) -> list[str]:
    terms = [
        f"{city} строительство 2026",
        f"{city} благоустройство проект 2026",
        f"{city} реконструкция 2026",
        f"{city} тендер строительство 2026",
        f"{city} ремонт дорог 2026",
        f"{city} инфраструктурный проект",
        f"{city} строительство школы",
        f"{city} строительство детского сада",
        f"{region_name} строительство объект",
        f"администрация {city} благоустройство",
        f"закупка строительство {city}",
    ]
    return list(dict.fromkeys(terms))


def _region(key: str, display_name: str, city: str, region_name: str) -> dict:
    return {
        "key": key,
        "display_name": display_name,
        "city": city,
        "region_name": region_name,
        "search_terms": _search_terms(city, region_name),
    }


REGIONS = {
    "moscow": _region("moscow", "Москва", "Москва", "Москва"),
    "saint_petersburg": _region(
        "saint_petersburg",
        "Санкт-Петербург",
        "Санкт-Петербург",
        "Санкт-Петербург",
    ),
    "yekaterinburg": _region(
        "yekaterinburg",
        "Екатеринбург / Свердловская область",
        "Екатеринбург",
        "Свердловская область",
    ),
    "novosibirsk": _region("novosibirsk", "Новосибирск", "Новосибирск", "Новосибирская область"),
    "kazan": _region("kazan", "Казань / Республика Татарстан", "Казань", "Республика Татарстан"),
    "nizhny_novgorod": _region(
        "nizhny_novgorod",
        "Нижний Новгород",
        "Нижний Новгород",
        "Нижегородская область",
    ),
    "samara": _region("samara", "Самара", "Самара", "Самарская область"),
    "chelyabinsk": _region("chelyabinsk", "Челябинск", "Челябинск", "Челябинская область"),
    "omsk": _region("omsk", "Омск", "Омск", "Омская область"),
    "rostov_on_don": _region("rostov_on_don", "Ростов-на-Дону", "Ростов-на-Дону", "Ростовская область"),
    "krasnodar": _region("krasnodar", "Краснодар", "Краснодар", "Краснодарский край"),
    "perm": _region("perm", "Пермь", "Пермь", "Пермский край"),
    "ufa": _region("ufa", "Уфа / Республика Башкортостан", "Уфа", "Республика Башкортостан"),
    "krasnoyarsk": _region("krasnoyarsk", "Красноярск", "Красноярск", "Красноярский край"),
    "voronezh": _region("voronezh", "Воронеж", "Воронеж", "Воронежская область"),
    "volgograd": _region("volgograd", "Волгоград", "Волгоград", "Волгоградская область"),
    "saratov": _region("saratov", "Саратов", "Саратов", "Саратовская область"),
    "tyumen": _region("tyumen", "Тюмень", "Тюмень", "Тюменская область"),
    "izhevsk": _region("izhevsk", "Ижевск", "Ижевск", "Удмуртская Республика"),
    "barnaul": _region("barnaul", "Барнаул", "Барнаул", "Алтайский край"),
    "vladivostok": _region("vladivostok", "Владивосток", "Владивосток", "Приморский край"),
    "khabarovsk": _region("khabarovsk", "Хабаровск", "Хабаровск", "Хабаровский край"),
    "irkutsk": _region("irkutsk", "Иркутск", "Иркутск", "Иркутская область"),
    "kaliningrad": _region("kaliningrad", "Калининград", "Калининград", "Калининградская область"),
    "yaroslavl": _region("yaroslavl", "Ярославль", "Ярославль", "Ярославская область"),
    "tula": _region("tula", "Тула", "Тула", "Тульская область"),
    "sochi": _region("sochi", "Сочи", "Сочи", "Краснодарский край"),
    "stavropol": _region("stavropol", "Ставрополь", "Ставрополь", "Ставропольский край"),
    "makhachkala": _region("makhachkala", "Махачкала", "Махачкала", "Республика Дагестан"),
    "tomsk": _region("tomsk", "Томск", "Томск", "Томская область"),
}


TRANSLITERATION_ALIASES = {
    "moscow": ("moscow",),
    "saint_petersburg": ("saint petersburg", "spb"),
    "yekaterinburg": ("yekaterinburg", "ekaterinburg", "sverdlovsk"),
    "novosibirsk": ("novosibirsk", "nsk", "нсо"),
    "kazan": ("kazan",),
    "nizhny_novgorod": ("nizhny novgorod",),
    "samara": ("samara",),
    "chelyabinsk": ("chelyabinsk",),
    "omsk": ("omsk",),
    "rostov_on_don": ("rostov-on-don", "rostov on don"),
    "krasnodar": ("krasnodar",),
    "perm": ("perm",),
    "ufa": ("ufa",),
    "krasnoyarsk": ("krasnoyarsk",),
    "voronezh": ("voronezh",),
    "volgograd": ("volgograd",),
    "saratov": ("saratov",),
    "tyumen": ("tyumen",),
    "izhevsk": ("izhevsk",),
    "barnaul": ("barnaul",),
    "vladivostok": ("vladivostok",),
    "khabarovsk": ("khabarovsk",),
    "irkutsk": ("irkutsk",),
    "kaliningrad": ("kaliningrad",),
    "yaroslavl": ("yaroslavl",),
    "tula": ("tula",),
    "sochi": ("sochi",),
    "stavropol": ("stavropol",),
    "makhachkala": ("makhachkala",),
    "tomsk": ("tomsk",),
}


def _case_variants(value: str) -> tuple[str, ...]:
    variants = {value}
    single_word = " " not in value
    if single_word and value.endswith("ск"):
        variants.add(f"{value}е")
    if single_word and value.endswith("а"):
        variants.add(f"{value[:-1]}е")
    if single_word and value.endswith("ь"):
        variants.add(f"{value[:-1]}и")
    if value.endswith("ая область"):
        variants.add(f"{value[: -len('ая область')]}ой области")
    if value.endswith("ий край"):
        variants.add(f"{value[: -len('ий край')]}ом крае")
    return tuple(variant for variant in variants if variant)


def list_regions() -> list[dict]:
    return list(REGIONS.values())


def get_region(region_key: str) -> dict:
    try:
        return REGIONS[region_key]
    except KeyError as exc:
        raise ValueError(f"Unknown region key: {region_key}") from exc


def target_location_terms(region: dict) -> tuple[str, ...]:
    terms: list[str] = []
    for value in (region["city"], region["region_name"], region["display_name"]):
        if value:
            terms.extend(_case_variants(value))
    terms.extend(TRANSLITERATION_ALIASES.get(region["key"], ()))
    return tuple(dict.fromkeys(terms))
