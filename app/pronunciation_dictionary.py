"""Small, validated JSON pronunciation dictionary for local MVP use."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "pronunciations.json"

def load_entries() -> list[dict]:
    if not PATH.exists(): return []
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Локальный словарь повреждён.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
        raise ValueError("Некорректная структура локального словаря.")
    return data["entries"]

def save_entries(entries: list[dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=PATH.parent, prefix="pronunciations-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file: json.dump({"entries": entries}, file, ensure_ascii=False, indent=2)
        os.replace(temp, PATH)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def validate_entry(entry: dict) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("Запись словаря должна быть JSON-объектом.")
    word = entry.get("word", "").strip().lower(); options = entry.get("options")
    if not word or not word.isalpha() or not isinstance(options, list) or not options: raise ValueError("Нужно слово и хотя бы один вариант.")
    clean=[]; ids=set()
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("Каждый вариант должен быть JSON-объектом.")
        identifier=option.get("id", "").strip(); display=option.get("display", "").strip(); tts=option.get("tts_text", "").strip(); meaning=option.get("meaning", "").strip()
        if not identifier or identifier in ids or not display or not meaning or tts.count("+") != 1: raise ValueError("Каждый вариант требует уникальный id, описание и один маркер +.")
        ids.add(identifier); clean.append({"id":identifier,"display":display,"tts_text":tts,"meaning":meaning})
    return {"word":word,"options":clean}
