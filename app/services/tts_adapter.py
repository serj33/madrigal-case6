"""Thin adapter around the TTS team's public API."""

from importlib import import_module
from pathlib import Path
from typing import Any

from app.services.errors import IntegrationContractError, IntegrationUnavailableError


def synthesize(text: str, output_path: Path, voice: str | None = None) -> dict[str, Any]:
    try:
        engine = import_module("app.tts_engine")
    except ModuleNotFoundError as exc:
        if exc.name == "app.tts_engine":
            raise IntegrationUnavailableError("TTS-модуль ещё не подключён.") from exc
        raise

    function = getattr(engine, "synthesize", None)
    if not callable(function):
        raise IntegrationContractError("TTS-модуль не предоставляет synthesize(...).")

    result = function(text, str(output_path), voice=voice, settings=None)
    if not isinstance(result, dict):
        raise IntegrationContractError("TTS должен вернуть JSON-совместимый объект.")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise IntegrationContractError("TTS не создал непустой аудиофайл по запрошенному пути.")

    for key in ("duration_seconds", "generation_seconds"):
        if not isinstance(result.get(key), (int, float)):
            raise IntegrationContractError(f"TTS не вернул фактическое поле {key}.")
    return result
