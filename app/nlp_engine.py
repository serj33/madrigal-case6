"""Conservative Russian text preparation for the Madrigal MVP.

The module intentionally supports a small, documented set of rules.  It does
not guess a word's stress and it preserves identifiers, contacts, URLs and
other machine-readable fragments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


ACCENT = "\u0301"


@dataclass(frozen=True)
class Homograph:
    options: tuple[dict[str, str], ...]


HOMOGRAPHS = {
    "замок": Homograph(
        options=(
            {"id": "building", "display": f"за{ACCENT}мок", "tts_text": "з+амок", "meaning": "Здание"},
            {"id": "lock", "display": f"замо{ACCENT}к", "tts_text": "зам+ок", "meaning": "Устройство для запирания"},
        )
    ),
    "мука": Homograph(
        options=(
            {"id": "flour", "display": f"мука{ACCENT}", "tts_text": "мук+а", "meaning": "Пищевой продукт"},
            {"id": "torment", "display": f"му{ACCENT}ка", "tts_text": "м+ука", "meaning": "Страдание"},
        )
    ),
}

# Each inflected spelling is an independent candidate.  This preserves source
# positions and lets the UI offer separate choices for "мука" and "муки".
HOMOGRAPH_FORMS: dict[str, Homograph] = {
    **HOMOGRAPHS,
    "замка": Homograph((
        {"id": "building", "display": f"за{ACCENT}мка", "tts_text": "з+амка", "meaning": "Здание"},
        {"id": "lock", "display": f"замка{ACCENT}", "tts_text": "замк+а", "meaning": "Устройство для запирания"},
    )),
    "замке": Homograph((
        {"id": "building", "display": f"за{ACCENT}мке", "tts_text": "з+амке", "meaning": "Здание"},
        {"id": "lock", "display": f"замке{ACCENT}", "tts_text": "замк+е", "meaning": "Устройство для запирания"},
    )),
    "муки": Homograph((
        {"id": "flour", "display": f"муки{ACCENT}", "tts_text": "мук+и", "meaning": "Пищевой продукт"},
        {"id": "torment", "display": f"му{ACCENT}ки", "tts_text": "м+уки", "meaning": "Страдания, мучения"},
    )),
    "муку": Homograph((
        {"id": "flour", "display": f"мук{ACCENT}у", "tts_text": "мук+у", "meaning": "Пищевой продукт"},
        {"id": "torment", "display": f"му{ACCENT}ку", "tts_text": "м+уку", "meaning": "Страдание"},
    )),
    "атлас": Homograph((
        {"id": "maps", "display": f"а{ACCENT}тлас", "tts_text": "+атлас", "meaning": "Сборник карт"},
        {"id": "fabric", "display": f"атла{ACCENT}с", "tts_text": "атл+ас", "meaning": "Ткань"},
    )),
    "орган": Homograph((
        {"id": "institution", "display": f"о{ACCENT}рган", "tts_text": "+орган", "meaning": "Учреждение"},
        {"id": "instrument", "display": f"орга{ACCENT}н", "tts_text": "орг+ан", "meaning": "Музыкальный инструмент"},
    )),
}

AUTO_CUES = {
    "building": ("дворец", "корол", "стар", "крепост", "жил", "возвыш", "башн", "на горе", "на холме"),
    "lock": ("двер", "ключ", "висел", "откр", "закр", "запир"),
    "flour": ("пшен", "пирог", "тест", "изготов", "готов", "ел", "есть", "просе"),
    "torment": ("никак", "достав", "страдан", "мучен", "боль", "от муки", "от мук"),
    "maps": ("карт", "географ", "страниц", "книг"),
    "fabric": ("ткан", "шелк", "плать", "материал"),
    "institution": ("власт", "государ", "исполнител", "комитет"),
    "instrument": ("музык", "играл", "концерт", "собор"),
}

PROTECTED_PATTERNS = (
    re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE),
    re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)"),
    re.compile(r"(?<!\w)v?\d+(?:\.\d+){1,}(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)[A-Za-zА-Яа-яЁё]+[-_]?\d+(?:[-_][A-Za-zА-Яа-яЁё\d]+)*(?!\w)"),
)

TIME_RE = re.compile(r"(?<!\w)([01]?\d|2[0-3]):([0-5]\d)(?!\w)")
YEAR_RE = re.compile(r"(?<!\w)(\d{4})\s+г\.(?!\w)", re.IGNORECASE)
YEAR_IN_GODU_RE = re.compile(r"(?<!\w)(\d{4})(?=\s+году\b)", re.IGNORECASE)
# A terminal full stop is punctuation, not part of a number.  Dots followed by
# a digit are protected as decimal/version-like notation; a year plus ``г.``
# is handled only by the dedicated year rule.
NUMBER_RE = re.compile(r"(?<![\w.])([0-9]{1,4})(?!\w|\.\d|\s+г\.|\s+году\b)", re.IGNORECASE)
ABBREVIATION_RULES = (
    (re.compile(r"(?<!\w)т\.\s*д\.(?!\w)", re.IGNORECASE), "так далее", "сокращение"),
    (re.compile(r"(?<!\w)т\.\s*п\.(?!\w)", re.IGNORECASE), "тому подобное", "сокращение"),
    (re.compile(r"(?<!\w)ул\.(?!\w)", re.IGNORECASE), "улица", "сокращение"),
)

ONES = ("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять")
TEENS = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
TENS = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто")
HUNDREDS = ("", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот")
ORDINAL_1_TO_19 = (
    "первом", "втором", "третьем", "четвёртом", "пятом", "шестом", "седьмом", "восьмом", "девятом",
    "десятом", "одиннадцатом", "двенадцатом", "тринадцатом", "четырнадцатом", "пятнадцатом",
    "шестнадцатом", "семнадцатом", "восемнадцатом", "девятнадцатом",
)
ORDINAL_TENS = {20: "двадцатом", 30: "тридцатом", 40: "сороковом", 50: "пятидесятом", 60: "шестидесятом", 70: "семидесятом", 80: "восьмидесятом", 90: "девяностом"}


def _number_to_words(value: int) -> str:
    """Return a cardinal Russian phrase for the supported range 0..9999."""
    if not 0 <= value <= 9999:
        raise ValueError("Поддерживаются только числа от 0 до 9999.")
    if value == 0:
        return ONES[0]
    parts: list[str] = []
    if value >= 1000:
        thousands, value = divmod(value, 1000)
        # The exact feminine form is needed for the two singular thousands.
        thousand_forms = ("тысяч", "тысяча", "тысячи", "тысячи", "тысячи", "тысяч", "тысяч", "тысяч", "тысяч", "тысяч")
        prefix = {1: "одна", 2: "две"}.get(thousands, _number_to_words(thousands))
        parts.extend((prefix, thousand_forms[thousands]))
    if value >= 100:
        hundreds, value = divmod(value, 100)
        parts.append(HUNDREDS[hundreds])
    if value >= 20:
        tens, value = divmod(value, 10)
        parts.append(TENS[tens])
    if value >= 10:
        parts.append(TEENS[value - 10])
    elif value:
        parts.append(ONES[value])
    return " ".join(parts)


def _number_to_words_feminine(value: int) -> str:
    """Return a cardinal phrase whose final 1/2 agrees with ``минута``."""
    words = _number_to_words(value)
    if 11 <= value % 100 <= 14:
        return words
    if value % 10 == 1:
        return f"{words.rsplit(' ', 1)[0]} одна" if " " in words else "одна"
    if value % 10 == 2:
        return f"{words.rsplit(' ', 1)[0]} две" if " " in words else "две"
    return words


def _decline_count(value: int, singular: str, paucal: str, plural: str) -> str:
    """Choose the Russian count form for a non-negative integer."""
    if 11 <= value % 100 <= 14:
        return plural
    if value % 10 == 1:
        return singular
    if value % 10 in {2, 3, 4}:
        return paucal
    return plural


def _time_to_words(hour: int, minute: int) -> str:
    return (
        f"{_number_to_words(hour)} {_decline_count(hour, 'час', 'часа', 'часов')} "
        f"{_number_to_words_feminine(minute)} {_decline_count(minute, 'минута', 'минуты', 'минут')}"
    )


def _year_to_words(year: int) -> str:
    """Return a prepositional ordinal year form for 1000..2099."""
    if not 1000 <= year <= 2099:
        raise ValueError("Поддерживаются годы от 1000 до 2099.")
    if year == 2000:
        return "двухтысячном году"
    if year > 2000:
        remainder = year - 2000
        prefix = "две тысячи"
    else:
        remainder = year - 1000
        prefix = "тысяча"
        if remainder == 0:
            return "тысячном году"

    hundreds, tail = divmod(remainder, 100)
    parts = [prefix]
    if hundreds:
        parts.append(HUNDREDS[hundreds])
    if tail == 0:
        ordinal_hundreds = {
            1: "сотом", 2: "двухсотом", 3: "трёхсотом", 4: "четырёхсотом",
            5: "пятисотом", 6: "шестисотом", 7: "семисотом",
            8: "восьмисотом", 9: "девятисотом",
        }
        if hundreds:
            parts[-1] = ordinal_hundreds[hundreds]
        return " ".join(parts) + " году"
    if 1 <= tail <= 19:
        parts.append(ORDINAL_1_TO_19[tail - 1])
    elif tail in ORDINAL_TENS:
        parts.append(ORDINAL_TENS[tail])
    else:
        tens, unit = divmod(tail, 10)
        parts.extend((TENS[tens], ORDINAL_1_TO_19[unit - 1]))
    return " ".join(parts) + " году"


def _protect_spans(text: str) -> list[tuple[int, int]]:
    spans = sorted((match.start(), match.end()) for pattern in PROTECTED_PATTERNS for match in pattern.finditer(text))
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _is_protected(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def _find_ambiguities(text: str, protected: list[tuple[int, int]]) -> list[dict]:
    lexicon = HOMOGRAPH_FORMS
    pattern = re.compile(r"(?<![А-Яа-яЁё])(" + "|".join(map(re.escape, lexicon)) + r")(?![А-Яа-яЁё])", re.IGNORECASE)
    ambiguities: list[dict] = []
    for match in pattern.finditer(text):
        if _is_protected(match.start(), protected):
            continue
        key = match.group(1).lower()
        ambiguities.append(
            {
                "id": f"amb_{len(ambiguities)}",
                "word": match.group(1),
                "start": match.start(),
                "end": match.end(),
                "options": [dict(option) for option in lexicon[key].options],
                "status": "needs_choice",
            }
        )
    return ambiguities


def _auto_choice(text: str, ambiguity: dict) -> tuple[str, str]:
    """Choose a documented heuristic option using local, occurrence-specific context."""
    # Restrict context to the current clause. A distant cue for a repeated
    # homograph must not influence another occurrence in the same sentence.
    left_bounds = [text.rfind(mark, 0, ambiguity["start"]) for mark in ",;:.!?"]
    left = max(left_bounds, default=-1) + 1
    right_candidates = [text.find(mark, ambiguity["end"]) for mark in ",;:.!?"]
    right_candidates = [position for position in right_candidates if position >= 0]
    right = min(right_candidates, default=len(text))
    context = text[left:right].lower()
    word = ambiguity["word"].lower()

    # Explicit case-sensitive collocations help distinguish the genitive
    # "муки" (of torment) from accusative "муку" (flour) and from "муки" (flour).
    if word == "муки":
        if re.search(r"\b(?:от|без|из-за|полон|полна|полны|испытал|испытала|испытали)\s+муки\b", context):
            return "torment", "высокая"
        if re.search(r"\b(?:ел|ела|ели|купил|купила|купили|добавил|добавила|просеял|просеяла)\s+муку\b", context):
            return "flour", "высокая"
    if word == "муку":
        if re.search(r"\b(?:от|без|из-за|полон|полна|полны|испытал|испытала|испытали)\s+муку\b", context):
            return "torment", "высокая"
        if re.search(r"\b(?:ел|ела|ели|купил|купила|купили|добавил|добавила|просеял|просеяла)\s+муку\b", context):
            return "flour", "высокая"

    scored = []
    for option in ambiguity["options"]:
        cues = AUTO_CUES.get(option["id"], ())
        score = sum(cue in context for cue in cues)
        scored.append((score, option["id"]))
    # max() is stable: ties retain the lexicon order instead of silently
    # preferring whichever option id sorts last alphabetically.
    top_score, option_id = max(scored, key=lambda item: item[0])
    confidence = "высокая" if top_score >= 2 else "средняя" if top_score == 1 else "низкая"
    return option_id, confidence

def auto_resolve_pronunciations(text: str) -> dict:
    """Prepare all detected ambiguities without pretending the heuristic is certain."""
    analysis = analyze_text(text)
    choices: dict[str, str] = {}
    decisions: list[dict] = []
    for ambiguity in analysis["ambiguities"]:
        option_id, confidence = _auto_choice(text, ambiguity)
        choices[ambiguity["id"]] = option_id
        decisions.append({"ambiguity_id": ambiguity["id"], "word": ambiguity["word"], "option_id": option_id, "confidence": confidence})
    prepared = _apply_resolved_choices(text, choices)
    # Keep the UI-facing normalized text conservative, but spell out older
    # years in the TTS-only string so Silero never receives a bare year numeral.
    def expand_tts_year(match: re.Match[str]) -> str:
        year = int(match.group(1))
        if 1000 <= year <= 2099:
            return _year_to_words(year)
        return match.group(0)

    prepared["text_used"] = YEAR_IN_GODU_RE.sub(expand_tts_year, prepared["text_used"])
    prepared["auto_decisions"] = decisions
    prepared["normalized_text"] = analysis["normalized_text"]
    return prepared

def _replace_with_diagnostics(
    text: str,
    pattern: re.Pattern[str],
    replacement: Callable[[re.Match[str]], tuple[str, str]],
    transformation_type: str,
    transformations: list[dict],
) -> str:
    def replace(match: re.Match[str]) -> str:
        value, reason = replacement(match)
        transformations.append({"type": transformation_type, "original": match.group(0), "replacement": value, "reason": reason})
        return value

    return pattern.sub(replace, text)


def _normalize_unprotected(segment: str, transformations: list[dict], warnings: list[str]) -> str:
    def year_replacement(match: re.Match[str]) -> tuple[str, str]:
        year = int(match.group(1))
        if not 2000 <= year <= 2099:
            warnings.append(f"Год «{match.group(0)}» не поддерживается MVP-правилом и оставлен без изменений.")
            return match.group(0), "Неподдерживаемый год"
        return _year_to_words(year), "Нормализация года"

    # Unsupported years remain visible in the original string and are not reported as transformations.
    def replace_year(match: re.Match[str]) -> str:
        year = int(match.group(1))
        if not 2000 <= year <= 2099:
            warnings.append(f"Год «{match.group(0)}» не поддерживается MVP-правилом и оставлен без изменений.")
            return match.group(0)
        value = _year_to_words(year)
        transformations.append({"type": "year", "original": match.group(0), "replacement": value, "reason": "Нормализация года"})
        return value

    segment = YEAR_RE.sub(replace_year, segment)

    # A year written before "году" is an ordinal in the prepositional case,
    # not a cardinal number ("двадцать шестом", not "двадцать шесть").
    def replace_year_in_godu(match: re.Match[str]) -> str:
        year = int(match.group(1))
        if not 2000 <= year <= 2099:
            warnings.append(f"Год «{match.group(0)} году» не поддерживается MVP-правилом и оставлен без изменений.")
            return match.group(0)
        value = _year_to_words(year).removesuffix(" году")
        transformations.append({"type": "year", "original": match.group(0), "replacement": value, "reason": "Склонение года перед словом «году»"})
        return value

    segment = YEAR_IN_GODU_RE.sub(replace_year_in_godu, segment)
    segment = _replace_with_diagnostics(
        segment,
        TIME_RE,
        lambda match: (
            _time_to_words(int(match.group(1)), int(match.group(2))),
            "Нормализация времени",
        ),
        "time",
        transformations,
    )
    for pattern, value, transformation_type in ABBREVIATION_RULES:
        segment = _replace_with_diagnostics(segment, pattern, lambda _: (value, "Раскрытие сокращения"), transformation_type, transformations)

    if re.search(r"(?<!\w)г\.(?!\w)", segment, re.IGNORECASE):
        warnings.append("Сокращение «г.» оставлено без изменений: без года оно может означать «город» или «год».")
    for abbreviation in ("руб.", "кг", "см"):
        if re.search(rf"(?<!\w){re.escape(abbreviation)}(?!\w)", segment, re.IGNORECASE):
            warnings.append(f"Сокращение «{abbreviation}» оставлено без изменений: MVP не определяет его форму без контекста.")

    def number_replacement(match: re.Match[str]) -> tuple[str, str]:
        # A four-digit number immediately followed by «году» is a year.
        # Unsupported years (for example, 1999) must remain numeric.
        if len(match.group(1)) == 4 and re.match(r"\s+году\b", match.string[match.end():], re.IGNORECASE):
            return match.group(1), "Год вне поддерживаемого диапазона оставлен без изменений"
        return _number_to_words(int(match.group(1))), "Нормализация целого числа"

    segment = _replace_with_diagnostics(
        segment,
        NUMBER_RE,
        number_replacement,
        "number",
        transformations,
    )
    return segment


def analyze_text(text: str) -> dict:
    """Analyze and conservatively normalize a Russian text string.

    The original text is never mutated. Positions in ``ambiguities`` always
    refer to it, rather than to the normalized text.
    """
    if not isinstance(text, str):
        raise TypeError("text должен быть строкой.")
    if not text.strip():
        raise ValueError("Текст не должен быть пустым.")

    protected = _protect_spans(text)
    transformations: list[dict] = []
    warnings: list[str] = []
    chunks: list[str] = []
    cursor = 0
    for start, end in protected:
        chunks.append(_normalize_unprotected(text[cursor:start], transformations, warnings))
        chunks.append(text[start:end])
        cursor = end
    chunks.append(_normalize_unprotected(text[cursor:], transformations, warnings))
    return {
        "original_text": text,
        "normalized_text": "".join(chunks),
        "transformations": transformations,
        "ambiguities": _find_ambiguities(text, protected),
        "warnings": list(dict.fromkeys(warnings)),
    }

def _apply_resolved_choices(text: str, choices: dict[str, str]) -> dict:
    """Validate choices and prepare text for the TTS adapter.

    Chosen forms use Silero's ``+`` stress marker. Replacements are derived
    from ambiguity spans in reverse order, so repeated words stay independent.
    """
    if not isinstance(choices, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in choices.items()):
        raise ValueError("choices должен быть объектом вида {ambiguity_id: option_id}.")
    analysis = analyze_text(text)
    ambiguities = {item["id"]: item for item in analysis["ambiguities"]}
    replacements: list[tuple[int, int, str]] = []
    applied_choices: list[dict] = []
    for ambiguity_id, option_id in choices.items():
        ambiguity = ambiguities.get(ambiguity_id)
        if ambiguity is None:
            raise ValueError(f"Неизвестный ambiguity id: {ambiguity_id}.")
        option = next((item for item in ambiguity["options"] if item["id"] == option_id), None)
        if option is None:
            raise ValueError(f"Вариант «{option_id}» не принадлежит {ambiguity_id}.")
        replacements.append((ambiguity["start"], ambiguity["end"], option["tts_text"]))
        applied_choices.append({"ambiguity_id": ambiguity_id, "word": ambiguity["word"], "option": dict(option)})

    prepared = text
    for start, end, replacement in sorted(replacements, reverse=True):
        prepared = prepared[:start] + replacement + prepared[end:]
    prepared_analysis = analyze_text(prepared)

    remaining = [item["id"] for item in analysis["ambiguities"] if item["id"] not in choices]
    warnings = list(prepared_analysis["warnings"])
    if remaining:
        warnings.append("Для части омографов выбор не указан; их текстовая форма не изменена.")
    return {
        "text_used": prepared_analysis["normalized_text"],
        "applied_choices": applied_choices,
        "remaining_ambiguity_ids": remaining,
        "warnings": warnings,
    }
# End of module.
