"""Local Silero TTS engine for Madrigal.

The engine has no import-time dependency on PyTorch, so the API can start and
return a useful integration error when the optional runtime is unavailable.
"""

from __future__ import annotations

import os
import threading
import time
import wave
from pathlib import Path
from typing import Any


MODEL_ID = "v5_ru"
DEFAULT_VOICE = "xenia"
SUPPORTED_VOICES = frozenset({"aidar", "baya", "kseniya", "xenia", "eugene"})
DEFAULT_SAMPLE_RATE = 48_000
SUPPORTED_SAMPLE_RATES = frozenset({8_000, 24_000, 48_000})
LEADING_SILENCE_SECONDS = 0.3
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "V5_ru.pt"

_MODEL: Any | None = None
_MODEL_LOCK = threading.Lock()


class TTSConfigurationError(RuntimeError):
    """Raised when the local Silero runtime is not ready for synthesis."""


def _load_torch() -> Any:
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise TTSConfigurationError(
            "PyTorch не установлен. Для Silero на Windows используйте поддерживаемый Python 3.9–3.12."
        ) from exc
    return torch


def _model_path() -> Path:
    configured = os.getenv("MADRIGAL_SILERO_MODEL_PATH")
    return Path(configured) if configured else DEFAULT_MODEL_PATH


def load_model() -> None:
    """Load the configured Silero package once and retain it in process memory."""
    global _MODEL
    if _MODEL is not None:
        return
    with _MODEL_LOCK:
        if _MODEL is not None:
            return
        path = _model_path()
        if not path.is_file():
            raise TTSConfigurationError(
                f"Файл модели Silero не найден: {path}. "
                "Скачайте v5_ru.pt локально и задайте MADRIGAL_SILERO_MODEL_PATH."
            )
        torch = _load_torch()
        try:
            model = torch.package.PackageImporter(str(path)).load_pickle("tts_models", "model")
            model.to(torch.device("cpu"))
        except Exception as exc:
            raise TTSConfigurationError(f"Не удалось загрузить Silero {MODEL_ID}: {exc}") from exc
        _MODEL = model


def _audio_samples(audio: Any) -> list[float]:
    """Extract mono float samples from the Tensor-like value returned by Silero."""
    try:
        samples = audio.detach().cpu().flatten().tolist()
    except AttributeError as exc:
        raise TTSConfigurationError("Silero вернул аудио в неподдерживаемом формате.") from exc
    if not samples:
        raise TTSConfigurationError("Silero вернул пустое аудио.")
    return [float(sample) for sample in samples]


def _prepend_leading_silence(samples: list[float], sample_rate: int) -> list[float]:
    """Add digital silence after synthesis, preserving every speech sample."""
    silence_samples = round(sample_rate * LEADING_SILENCE_SECONDS)
    return [0.0] * silence_samples + samples


def _write_wav(path: Path, samples: list[float], sample_rate: int) -> None:
    if path.exists():
        raise FileExistsError(f"Выходной аудиофайл уже существует: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = bytearray()
    for sample in samples:
        clipped = max(-1.0, min(1.0, sample))
        value = int(round(clipped * 32767))
        pcm.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(pcm))


def _settings(settings: dict[str, Any] | None) -> int:
    if settings is None:
        return DEFAULT_SAMPLE_RATE
    if not isinstance(settings, dict):
        raise ValueError("settings должен быть словарём или null.")
    unsupported = set(settings) - {"sample_rate"}
    if unsupported:
        raise ValueError(f"Неподдерживаемые настройки TTS: {sorted(unsupported)}")
    sample_rate = settings.get("sample_rate", DEFAULT_SAMPLE_RATE)
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise ValueError(f"sample_rate должен быть одним из {sorted(SUPPORTED_SAMPLE_RATES)}.")
    return sample_rate


def synthesize(
    text: str,
    output_path: str,
    voice: str | None = None,
    settings: dict | None = None,
) -> dict[str, Any]:
    """Generate a real PCM WAV with one cached Silero model instance."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Текст для синтеза не должен быть пустым.")
    if not isinstance(output_path, str) or not output_path:
        raise ValueError("output_path должен быть непустым путём.")
    selected_voice = voice or DEFAULT_VOICE
    if selected_voice not in SUPPORTED_VOICES:
        raise ValueError(f"Неподдерживаемый голос: {selected_voice}.")
    sample_rate = _settings(settings)

    load_model()
    started = time.perf_counter()
    try:
        audio = _MODEL.apply_tts(text=text, speaker=selected_voice, sample_rate=sample_rate)
        speech_samples = _audio_samples(audio)
        samples = _prepend_leading_silence(speech_samples, sample_rate)
        target = Path(output_path)
        _write_wav(target, samples, sample_rate)
    except (ValueError, FileExistsError, TTSConfigurationError):
        raise
    except Exception as exc:
        raise TTSConfigurationError(f"Ошибка синтеза Silero: {exc}") from exc

    generation_seconds = time.perf_counter() - started
    return {
        "audio_path": str(target),
        "sample_rate": sample_rate,
        "duration_seconds": len(samples) / sample_rate,
        "generation_seconds": generation_seconds,
        "voice": selected_voice,
    }
