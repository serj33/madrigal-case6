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


def test_root_serves_only_two_modes(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "BASE" in response.text and "AUTO" in response.text
    assert "IMPROVED" not in response.text
    assert "словар" not in response.text.lower()


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
        assert text == "Текст"
        output_path.write_bytes(b"RIFF test audio")
        return {"duration_seconds": 1.25, "generation_seconds": 0.5}
    monkeypatch.setattr("app.main.tts_adapter.synthesize", fake_synthesize)
    response = client.post("/api/synthesize", json={"text": "Текст", "mode": "base"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "base" and body["text_used"] == "Текст"
    assert client.get(body["audio_url"]).status_code == 200


def test_auto_synthesis_uses_auto_prepared_text_without_manual_choices(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.nlp_adapter.auto_resolve_pronunciations", lambda text: {"text_used": "з+амок", "auto_decisions": [{"confidence": "средняя"}]})
    received = {}
    def fake_synthesize(text: str, output_path: Path, voice: str | None) -> dict:
        received["text"] = text
        output_path.write_bytes(b"RIFF audio")
        return {"duration_seconds": 1, "generation_seconds": 0.1}
    monkeypatch.setattr("app.main.tts_adapter.synthesize", fake_synthesize)
    response = client.post("/api/synthesize", json={"text": "замок", "mode": "auto"})
    assert response.status_code == 200
    assert received["text"] == "з+амок"
    assert response.json()["auto_decisions"][0]["confidence"] == "средняя"


def test_choices_contract_is_rejected(client: TestClient) -> None:
    response = client.post("/api/synthesize", json={"text": "замок", "mode": "auto", "choices": {"amb_0": "lock"}})
    assert response.status_code == 422


def test_improved_mode_is_removed(client: TestClient) -> None:
    response = client.post("/api/synthesize", json={"text": "замок", "mode": "improved"})
    assert response.status_code == 422


def test_unknown_and_unsafe_audio_paths_are_not_served(client: TestClient) -> None:
    assert client.get("/outputs/missing.wav").status_code == 404
    assert client.get("/outputs/%2E%2E%2Fsecret.wav").status_code in {404, 422}
