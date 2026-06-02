"""Tests for the Ollama LLM client (Module 5a).

All network calls are mocked — these tests never touch a real Ollama server.
"""

import json
import io
import urllib.error
import contextlib

import pytest

from src.generation.llm_client import LLMClient, LLMResponse


class _FakeResp:
    """Minimal stand-in for the object urlopen() yields as a context manager."""
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_is_available_true(monkeypatch):
    def fake_urlopen(req, timeout=5):
        return _FakeResp(b'{"models": []}', status=200)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert LLMClient().is_available() is True


def test_is_available_false_when_down(monkeypatch):
    def fake_urlopen(req, timeout=5):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert LLMClient().is_available() is False


def test_list_models(monkeypatch):
    payload = json.dumps({"models": [{"name": "mistral:latest"},
                                     {"name": "phi3:latest"}]}).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=5: _FakeResp(payload))
    models = LLMClient().list_models()
    assert "mistral:latest" in models
    assert "phi3:latest" in models


def test_has_model_matches_base_name(monkeypatch):
    payload = json.dumps({"models": [{"name": "mistral:latest"}]}).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=5: _FakeResp(payload))
    client = LLMClient(model="mistral")
    assert client.has_model() is True
    assert client.has_model("nonexistent") is False


def test_generate_success(monkeypatch):
    payload = json.dumps({"response": "A business rule."}).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=120: _FakeResp(payload))
    resp = LLMClient().generate("explain")
    assert isinstance(resp, LLMResponse)
    assert resp.success is True
    assert resp.text == "A business rule."


def test_generate_empty_response_fails(monkeypatch):
    payload = json.dumps({"response": ""}).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=120: _FakeResp(payload))
    # Speed up: no real sleeping between retries.
    monkeypatch.setattr("time.sleep", lambda s: None)
    resp = LLMClient().generate("explain")
    assert resp.success is False
    assert resp.error


def test_generate_handles_connection_error(monkeypatch):
    def boom(req, timeout=120):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    monkeypatch.setattr("time.sleep", lambda s: None)
    resp = LLMClient().generate("explain")
    assert resp.success is False
    assert "error" in resp.error.lower() or "refused" in resp.error.lower()


def test_base_url_trailing_slash_stripped():
    assert LLMClient(base_url="http://x:1234/").base_url == "http://x:1234"
