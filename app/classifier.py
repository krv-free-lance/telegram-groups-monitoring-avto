"""Rule-based classifier of lead messages.

Words are matched by stems via regex, so different word forms
("самосвал", "самосвалы", "самосвалом") are covered without morphology libs.
"""
import re
from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    NEED_TRUCK = "need_truck"
    REMOVAL = "removal"
    SELL = "sell"
    BUY = "buy"


CATEGORY_TITLES = {
    Category.NEED_TRUCK: "🚛 Нужен самосвал / машины",
    Category.REMOVAL: "🚛 Вывоз грунта / боя",
    Category.SELL: "🟢 Продам вторичный щебень / бой",
    Category.BUY: "🔵 Куплю вторичный щебень / бой",
}

# Stems. \b is not reliable for Cyrillic in some cases, so we use lookarounds.
_W = r"(?<![а-яa-z])"

NEED = _W + r"(нуж[нед]|требу[ею]т|ищ[уеа]м?|ищем|необходим|срочно)"
TRUCK = _W + r"(самосвал|тонар|камаз|шакман|шахман|howo|хово|машин[уыа]?|техник[аиу]|грузовик|полуприцеп|20\s*-?\s*кубов|25\s*-?\s*кубов|30\s*-?\s*кубов)"
REMOVAL = _W + r"(вывез|вывоз|увез|утилизац|убрать|забрать|забер)"
WASTE = _W + r"(грунт|бо[йяю]\b|бой|кирпичн\w*\s+бо|бетонн\w*\s+бо|бо[йя]\s+(кирпич|бетон)|строительн\w*\s+мусор|мусор|глин[ау]|земл[юяи]|асфальт\w*\s+(скол|крош)|снег)"
SELL = _W + r"(прода[мюёе]|продаж|реализ|отгруж|в\s+наличии)"
BUY = _W + r"(купл|купим|покупа|приобрет|закуп|прим[уе]м)"
MATERIAL = (
    _W + r"(вторичн\w*\s+щеб|щеб[её]нк?|щеб[её]н|втор\w*\s+щ|бо[йя]\s+(кирпич|бетон)|"
    r"(кирпичн|бетонн)\w*\s+бо|асфальт\w*\s+крош|вторичк|бой|отсев)"
)

# Messages that offer services rather than request them, vacancies, etc.
NEGATIVE = _W + r"(предлага[юе]|оказыва|услуги\s+самосвал|сда[мю]\s+в\s+аренд|сда[её]тся|ищу\s+работ|ищем\s+водител|требу\w+\s+водител|вакансия|водител[ьи]\s+на\s+самосвал|есть\s+(свободн\w+\s+)?(самосвал|машин|техник)|свободн\w+\s+(самосвал|машин|техник))"


@dataclass(frozen=True)
class Match:
    category: Category
    reason: str


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


def _has(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(0) if m else None


def classify(text: str) -> Match | None:
    """Return the most specific category for a message or None if it's not a lead."""
    if not text:
        return None
    t = normalize(text)
    if _has(NEGATIVE, t):
        return None

    material = _has(MATERIAL, t)
    if material:
        if w := _has(SELL, t):
            return Match(Category.SELL, f"{w} + {material}")
        if w := _has(BUY, t):
            return Match(Category.BUY, f"{w} + {material}")

    removal, waste = _has(REMOVAL, t), _has(WASTE, t)
    if removal and waste:
        return Match(Category.REMOVAL, f"{removal} + {waste}")

    need, truck = _has(NEED, t), _has(TRUCK, t)
    if need and truck:
        return Match(Category.NEED_TRUCK, f"{need} + {truck}")
    return None
