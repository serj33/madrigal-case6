import pytest

from app.nlp_engine import analyze_text, auto_resolve_pronunciations
from app.services import nlp_adapter


def test_returns_full_contract_without_changes() -> None:
    result = analyze_text("Обычная фраза.")
    assert result == {
        "original_text": "Обычная фраза.",
        "normalized_text": "Обычная фраза.",
        "transformations": [],
        "ambiguities": [],
        "warnings": [],
    }


def test_normalizes_supported_year_time_number_and_abbreviations() -> None:
    result = analyze_text("В 2026 г. встреча в 14:30, кабинет 12, ул. Мира и т. д.")
    assert result["normalized_text"] == "В две тысячи двадцать шестом году встреча в четырнадцать часов тридцать минут, кабинет двенадцать, улица Мира и так далее"
    assert [item["type"] for item in result["transformations"]] == ["year", "time", "сокращение", "сокращение", "number"]


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        ("01:01", "один час одна минута"),
        ("02:02", "два часа две минуты"),
        ("00:01", "ноль часов одна минута"),
        ("14:30", "четырнадцать часов тридцать минут"),
        ("21:01", "двадцать один час одна минута"),
        ("23:59", "двадцать три часа пятьдесят девять минут"),
    ],
)
def test_time_uses_correct_gender_and_count_forms(time: str, expected: str) -> None:
    assert analyze_text(time)["normalized_text"] == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("В 2000 г.", "В двухтысячном году"),
        ("В 2001 г.", "В две тысячи первом году"),
        ("Счёт: 0, 9999.", "Счёт: ноль, девять тысяч девятьсот девяносто девять."),
    ],
)
def test_supported_numeric_rules(text: str, expected: str) -> None:
    assert analyze_text(text)["normalized_text"] == expected


def test_unsupported_year_and_ambiguous_abbreviations_warn_without_replacement() -> None:
    result = analyze_text("В 1999 г. г. N, 5 руб. и 2 кг.")
    assert "1999 г." in result["normalized_text"]
    assert "г. N" in result["normalized_text"]
    assert any("1999" in warning for warning in result["warnings"])
    assert any("«г.»" in warning for warning in result["warnings"])
    assert any("«руб.»" in warning for warning in result["warnings"])


def test_protects_contacts_urls_versions_and_codes() -> None:
    text = "URL https://a.example/2026, e-mail a12@example.org, +7 999 123-45-67, v1.2 и AB-123."
    result = analyze_text(text)
    assert result["normalized_text"] == text
    assert result["transformations"] == []


def test_each_homograph_occurrence_gets_its_own_id_and_original_offsets() -> None:
    text = "Замок и мука; замок."
    ambiguities = analyze_text(text)["ambiguities"]
    assert [item["id"] for item in ambiguities] == ["amb_0", "amb_1", "amb_2"]
    assert [(item["word"], item["start"], item["end"]) for item in ambiguities] == [("Замок", 0, 5), ("мука", 8, 12), ("замок", 14, 19)]
    assert ambiguities[0]["options"][0]["display"] == "за́мок"
    assert ambiguities[1]["options"][1]["display"] == "му́ка"


def test_homographs_inside_protected_text_are_ignored() -> None:
    assert analyze_text("https://example.org/замок")["ambiguities"] == []


def test_choices_validate_and_keep_plain_text_for_unverified_tts() -> None:
    result = apply_pronunciation_choices("замок и замок", {"amb_1": "lock"})
    assert result["text_used"] == "замок и зам+ок"
    assert result["applied_choices"][0]["option"]["tts_text"] == "зам+ок"
    assert result["remaining_ambiguity_ids"] == ["amb_0"]
    assert any("не указан" in warning for warning in result["warnings"])


def test_opposite_choices_produce_distinct_silero_text() -> None:
    building = apply_pronunciation_choices("замок", {"amb_0": "building"})
    lock = apply_pronunciation_choices("замок", {"amb_0": "lock"})
    assert building["text_used"] == "з+амок"
    assert lock["text_used"] == "зам+ок"




@pytest.mark.parametrize("text", ["", "   "])
def test_blank_text_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        analyze_text(text)


def test_nlp_adapter_imports_and_uses_engine() -> None:
    result = nlp_adapter.analyze_text("замок")
    assert result["ambiguities"][0]["id"] == "amb_0"
    assert nlp_adapter.apply_pronunciation_choices("мука", {"amb_0": "flour"})["text_used"] == "мук+а"


@pytest.mark.parametrize("text, words", [
    ("замок и замок", ["замок", "замок"]),
    ("Мука из пшеницы не доставила никакой муки.", ["Мука", "муки"]),
    ("атлас и атлас", ["атлас", "атлас"]),
    ("орган и орган", ["орган", "орган"]),
])
def test_repeated_and_inflected_homographs_have_independent_positions(text, words) -> None:
    ambiguities = analyze_text(text)["ambiguities"]
    assert [item["word"] for item in ambiguities] == words
    assert len({item["id"] for item in ambiguities}) == len(words)
    assert [text[item["start"]:item["end"]] for item in ambiguities] == words


def test_auto_resolves_context_and_passes_stress_markers() -> None:
    building = auto_resolve_pronunciations("В старом замке жил король.")
    lock = auto_resolve_pronunciations("На двери висел замок с ключом.")
    food = auto_resolve_pronunciations("Мука из пшеницы подходит для пирога.")
    pain = auto_resolve_pronunciations("Никакой муки и страданий не было.")
    assert "з+амке" in building["text_used"]
    assert "зам+ок" in lock["text_used"]
    assert "мук+а" in food["text_used"]
    assert "м+уки" in pain["text_used"]
    assert all(item["confidence"] in {"высокая", "средняя", "низкая"} for item in building["auto_decisions"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("В 2026 году", "В две тысячи двадцать шестом году"),
        ("В 2021 году", "В две тысячи двадцать первом году"),
        ("В 2000 году", "В двухтысячном году"),
        ("В 1999 году", "В 1999 году"),
    ],
)
def test_year_before_godu_uses_ordinal_prepositional_form(text: str, expected: str) -> None:
    assert analyze_text(text)["normalized_text"] == expected


def test_auto_resolves_repeated_homograph_per_occurrence() -> None:
    text = "На горе стоял старый замок, а на двери висел новый замок."
    result = auto_resolve_pronunciations(text)
    assert result["text_used"] == "На горе стоял старый з+амок, а на двери висел новый зам+ок."
    assert [item["option_id"] for item in result["auto_decisions"]] == ["building", "lock"]


def test_auto_distinguishes_flour_and_torment_forms_in_one_sentence() -> None:
    text = "Мама мыла раму, пока брат ел муку, а сестра страдала от муки."
    result = auto_resolve_pronunciations(text)
    assert result["text_used"] == "Мама мыла раму, пока брат ел мук+у, а сестра страдала от м+уки."
    assert [item["option_id"] for item in result["auto_decisions"]] == ["flour", "torment"]


def test_auto_marks_accusative_muku_as_flour_after_eating_verb() -> None:
    result = auto_resolve_pronunciations("Брат ел муку.")
    assert result["text_used"] == "Брат ел мук+у."
    assert result["auto_decisions"][0]["option_id"] == "flour"
