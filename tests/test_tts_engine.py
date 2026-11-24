import wave
import struct
from pathlib import Path

import pytest

from app import tts_engine
from app.services import tts_adapter


class FakeTensor:
    def __init__(self, samples: list[float]) -> None:
        self.samples = samples

    def detach(self):
        return self

    def cpu(self):
        return self

    def flatten(self):
        return self

    def tolist(self):
        return self.samples


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def apply_tts(self, **kwargs):
        self.calls.append(kwargs)
        return FakeTensor([0.0, 0.5, -0.5, 0.0])

    def to(self, device: str) -> None:
        self.device = device


@pytest.fixture(autouse=True)
def reset_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts_engine, "_MODEL", None)


def test_load_model_is_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model_path = tmp_path / "silero.pt"
    model_path.write_bytes(b"model")
    model = FakeModel()

    class Importer:
        def __init__(self, path: str) -> None:
            assert path == str(model_path)

        def load_pickle(self, package: str, name: str) -> FakeModel:
            assert (package, name) == ("tts_models", "model")
            return model

    class Torch:
        class package:
            PackageImporter = Importer

        @staticmethod
        def device(name: str) -> str:
            return name

    monkeypatch.setenv("MADRIGAL_SILERO_MODEL_PATH", str(model_path))
    monkeypatch.setattr(tts_engine, "_load_torch", lambda: Torch)
    tts_engine.load_model()
    tts_engine.load_model()
    assert tts_engine._MODEL is model


def test_synthesize_creates_valid_wav_and_real_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = FakeModel()
    monkeypatch.setattr(tts_engine, "_MODEL", model)
    output = tmp_path / "speech.wav"
    result = tts_engine.synthesize("Тест", str(output))
    with wave.open(str(output), "rb") as generated:
        assert generated.getframerate() == 48_000
        assert generated.getnframes() == 14_404
        assert generated.getnchannels() == 1
        samples = struct.unpack("<" + "h" * generated.getnframes(), generated.readframes(generated.getnframes()))
    assert samples[:14_400] == (0,) * 14_400
    assert samples[14_400:] == (0, 16_384, -16_384, 0)
    assert result["duration_seconds"] == pytest.approx(14_404 / 48_000)
    assert result["generation_seconds"] >= 0
    assert result["voice"] == "xenia"
    assert model.calls == [{"text": "Тест", "speaker": "xenia", "sample_rate": 48_000}]


def test_stress_marker_is_passed_to_silero_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = FakeModel()
    monkeypatch.setattr(tts_engine, "_MODEL", model)
    tts_engine.synthesize("к+ошка", str(tmp_path / "stress.wav"))
    assert model.calls[0]["text"] == "к+ошка"


def test_base_and_improved_inputs_use_same_model_voice_and_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = FakeModel()
    monkeypatch.setattr(tts_engine, "_MODEL", model)
    tts_engine.synthesize("Замок", str(tmp_path / "base.wav"))
    tts_engine.synthesize("Замок", str(tmp_path / "improved.wav"))
    assert [call["speaker"] for call in model.calls] == ["xenia", "xenia"]
    assert [call["sample_rate"] for call in model.calls] == [48_000, 48_000]


def test_adapter_accepts_engine_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tts_engine, "_MODEL", FakeModel())
    output = tmp_path / "adapter.wav"
    result = tts_adapter.synthesize("Тест", output)
    assert output.is_file() and output.stat().st_size > 0
    assert result["sample_rate"] == 48_000


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_is_rejected(text: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        tts_engine.synthesize(text, str(tmp_path / "speech.wav"))


def test_invalid_voice_and_existing_output_are_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tts_engine, "_MODEL", FakeModel())
    output = tmp_path / "speech.wav"
    output.write_bytes(b"existing")
    with pytest.raises(ValueError):
        tts_engine.synthesize("Тест", str(tmp_path / "other.wav"), voice="unknown")
    with pytest.raises(FileExistsError):
        tts_engine.synthesize("Тест", str(output))
