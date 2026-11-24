"""Thin adapter around the NLP team's public API.

The NLP module is intentionally not implemented in the backend.  Once added,
``app.nlp_engine`` must expose ``analyze_text(text)`` and
``apply_pronunciation_choices(text, choices)``.
"""

from importlib import import_module
from typing import Any

from app.services.errors import IntegrationContractError, IntegrationUnavailableError


def _engine() -> Any:
    try:
        return import_module("app.nlp_engine")
    except ModuleNotFoundError as exc:
        if exc.name == "app.nlp_engine":
            raise IntegrationUnavailableError("NLP-модуль ещё не подключён.") from exc
        raise


def analyze_text(text: str) -> dict[str, Any]:
    engine = _engine()
    function = getattr(engine, "analyze_text", None)
    if not callable(function):
        raise IntegrationContractError("NLP-модуль не предоставляет analyze_text(text).")
    result = function(text)
    if not isinstance(result, dict):
        raise IntegrationContractError("NLP-анализ должен возвращать JSON-совместимый объект.")
    return result


def apply_pronunciation_choices(text: str, choices: dict[str, str]) -> dict[str, Any]:
    engine = _engine()
    function = getattr(engine, "apply_pronunciation_choices", None)
    if not callable(function):
        raise IntegrationContractError(
            "NLP-модуль не предоставляет apply_pronunciation_choices(text, choices)."
        )
    result = function(text, choices)
    if not isinstance(result, dict) or not isinstance(result.get("text_used"), str):
        raise IntegrationContractError(
            "NLP должен вернуть объект с полем text_used для синтеза."
        )
    return result


def auto_resolve_pronunciations(text: str) -> dict[str, Any]:
    engine = _engine()
    function = getattr(engine, "auto_resolve_pronunciations", None)
    if not callable(function):
        raise IntegrationContractError("NLP-модуль не предоставляет auto_resolve_pronunciations(text).")
    result = function(text)
    if not isinstance(result, dict) or not isinstance(result.get("text_used"), str):
        raise IntegrationContractError("AUTO-NLP должен вернуть объект с полем text_used.")
    return result
