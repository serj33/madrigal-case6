from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.errors import IntegrationUnavailableError


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.main.OUTPUTS_DIR", tmp_path)
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "service": "madrigal-tts"}


def test_analyze_returns_nlp_result(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {"original_text": "Текст", "normalized_text": "Текст", "transformations": [], "ambiguities": [], "warnings": []}
    monkeypatch.setattr("app.main.nlp_adapter.analyze_text", lambda text: expected)
    response = client.post("/api/analyze", json={"text": "Текст"})
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("text", ["", "   "])
def test_analyze_rejects_blank_text(client: TestClient, text: str) -> None:
    assert client.post("/api/analyze", json={"text": text}).status_code == 422


def test_analyze_returns_503_when_nlp_is_unavailable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.nlp_adapter.analyze_text", lambda text: (_ for _ in ()).throw(IntegrationUnavailableError("NLP unavailable")))
    assert client.post("/api/analyze", json={"text": "Текст"}).status_code == 503


def test_base_synthesis(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_synthesize(text: str, output_path: Path, voice: str | None) -> dict:
        output_path.write_bytes(b"RIFF test audio")
        return {"duration_seconds": 1.25, "generation_seconds": 0.5}

    monkeypatch.setattr("app.main.tts_adapter.synthesize", fake_synthesize)
    response = client.post("/api/synthesize", json={"text": "Текст", "mode": "base"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "base"
    assert body["text_used"] == "Текст"
    assert client.get(body["audio_url"]).status_code == 200


def test_improved_requires_choice(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.nlp_adapter.analyze_text", lambda text: {"ambiguities": [{"id": "amb_0", "status": "needs_choice"}]})
    response = client.post("/api/synthesize", json={"text": "замок", "mode": "improved"})
    assert response.status_code == 409


def test_improved_synthesis_applies_choices(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.nlp_adapter.analyze_text", lambda text: {"ambiguities": [{"id": "amb_0", "status": "needs_choice"}]})
    monkeypatch.setattr("app.main.nlp_adapter.apply_pronunciation_choices", lambda text, choices: {"text_used": "за́мок"})

    def fake_synthesize(text: str, output_path: Path, voice: str | None) -> dict:
        assert text == "за́мок"
        output_path.write_bytes(b"RIFF test audio")
        return {"duration_seconds": 1, "generation_seconds": 0.1}

    monkeypatch.setattr("app.main.tts_adapter.synthesize", fake_synthesize)
    response = client.post("/api/synthesize", json={"text": "замок", "mode": "improved", "choices": {"amb_0": "building"}})
    assert response.status_code == 200
    assert response.json()["text_used"] == "за́мок"


def test_invalid_mode_is_rejected(client: TestClient) -> None:
    assert client.post("/api/synthesize", json={"text": "Текст", "mode": "unknown"}).status_code == 422


def test_unknown_and_unsafe_audio_paths_are_not_served(client: TestClient) -> None:
    assert client.get("/outputs/missing.wav").status_code == 404
    assert client.get("/outputs/%2E%2E%2Fsecret.wav").status_code in {404, 422}
