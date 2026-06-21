"""Regression / smoke tests for the orchestrator's pure logic.

These exercise the code paths that do NOT need a live network: config parsing
and defaulting, the structured-logging setup, and the Alexa endpoint's request
validation + auth gate (which is decided before any Ollama call). External
services (Ollama, InfluxDB, the HA Supervisor, Telegram) are never contacted.

Run: `pytest tests/ -q`
"""
from __future__ import annotations

import json
import logging

import pytest

# ── config.load_config ───────────────────────────────────────────────────────

def _write_options(tmp_path, **overrides):
    base = {
        "ollama_url": "http://ollama:11434",
        "influxdb_url": "http://influx:8086",
        "influxdb_token": "tok",
        "influxdb_org": "org",
        "influxdb_bucket_metrics": "bucket",
        "telegram_bot_token": "bot",
    }
    base.update(overrides)
    p = tmp_path / "options.json"
    p.write_text(json.dumps(base))
    return p


def test_load_config_required_fields(tmp_path, monkeypatch):
    import config

    p = _write_options(tmp_path)
    monkeypatch.setenv("SENTINEL_CONFIG_PATH", str(p))
    cfg = config.load_config()
    assert cfg.ollama_url == "http://ollama:11434"
    assert cfg.influxdb_bucket_metrics == "bucket"


def test_load_config_applies_defaults(tmp_path, monkeypatch):
    import config

    p = _write_options(tmp_path)
    monkeypatch.setenv("SENTINEL_CONFIG_PATH", str(p))
    cfg = config.load_config()
    # Defaults documented in config.yaml / load_config().
    assert cfg.alexa_enabled is False
    assert cfg.alexa_port == 8099
    assert cfg.alexa_secret == ""
    assert cfg.health_check_interval_seconds == 60
    assert cfg.log_level == "INFO"
    assert cfg.telegram_admin_chat_id == 0


def test_load_config_coerces_types(tmp_path, monkeypatch):
    import config

    # HA may hand strings/ints through options.json; load_config must coerce.
    p = _write_options(
        tmp_path,
        telegram_admin_chat_id="12345",
        alexa_enabled=True,
        alexa_port="9000",
        health_check_interval_seconds="30",
    )
    monkeypatch.setenv("SENTINEL_CONFIG_PATH", str(p))
    cfg = config.load_config()
    assert cfg.telegram_admin_chat_id == 12345
    assert isinstance(cfg.telegram_admin_chat_id, int)
    assert cfg.alexa_enabled is True
    assert cfg.alexa_port == 9000
    assert cfg.health_check_interval_seconds == 30


def test_load_config_missing_required_raises(tmp_path, monkeypatch):
    import config

    p = tmp_path / "options.json"
    p.write_text(json.dumps({"ollama_url": "http://x"}))  # missing the rest
    monkeypatch.setenv("SENTINEL_CONFIG_PATH", str(p))
    with pytest.raises(KeyError):
        config.load_config()


# ── utils.setup_logging ──────────────────────────────────────────────────────

def test_setup_logging_levels_and_handler():
    from utils import setup_logging

    setup_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1

    setup_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING
    # Re-running does not pile up handlers (handlers.clear() in setup_logging).
    assert len(logging.getLogger().handlers) == 1


def test_setup_logging_unknown_level_defaults_to_info():
    from utils import setup_logging

    setup_logging("NOPE")
    assert logging.getLogger().level == logging.INFO


# ── Alexa endpoint: request validation + auth gate (no network) ──────────────

class _Cfg:
    """Minimal config stub for the AlexaEndpoint constructor."""

    def __init__(self, secret="", port=8099, ollama_url="http://ollama:11434"):
        self.alexa_secret = secret
        self.alexa_port = port
        self.ollama_url = ollama_url


class _FakeRequest:
    def __init__(self, headers=None, body=None, raise_json=False):
        self.headers = headers or {}
        self._body = body
        self._raise_json = raise_json

    async def json(self):
        if self._raise_json:
            raise ValueError("bad json")
        return self._body


@pytest.fixture
def alexa_module():
    from interfaces import alexa
    return alexa


async def _handle(alexa_module, cfg, request):
    ep = alexa_module.AlexaEndpoint(cfg)
    return await ep._handle(request)


@pytest.mark.asyncio
async def test_alexa_rejects_bad_token(alexa_module):
    cfg = _Cfg(secret="s3cret")
    req = _FakeRequest(headers={"Authorization": "Bearer wrong"}, body={"text": "hi"})
    resp = await _handle(alexa_module, cfg, req)
    assert resp.status == 401


@pytest.mark.asyncio
async def test_alexa_invalid_json_is_400(alexa_module):
    cfg = _Cfg()  # no secret -> auth skipped
    req = _FakeRequest(raise_json=True)
    resp = await _handle(alexa_module, cfg, req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_alexa_missing_text_is_400(alexa_module):
    cfg = _Cfg()
    req = _FakeRequest(body={"not_text": "x"})
    resp = await _handle(alexa_module, cfg, req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_alexa_blank_text_is_400(alexa_module):
    cfg = _Cfg()
    req = _FakeRequest(body={"text": "   "})
    resp = await _handle(alexa_module, cfg, req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_alexa_valid_request_calls_ollama(alexa_module, monkeypatch):
    cfg = _Cfg()
    ep = alexa_module.AlexaEndpoint(cfg)

    captured = {}

    async def fake_ask(text):
        captured["text"] = text
        return "respuesta"

    monkeypatch.setattr(ep, "_ask_ollama", fake_ask)
    req = _FakeRequest(body={"text": "  enciende la luz  "})
    resp = await ep._handle(req)
    assert resp.status == 200
    assert captured["text"] == "enciende la luz"
    payload = json.loads(resp.text)
    assert payload == {"response": "respuesta", "success": True}


# ── HealthChecker: construction is pure (no I/O until run/_tick) ──────────────

def test_health_checker_construct_is_side_effect_free(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "abc")
    from observability import HealthChecker

    cfg = _Cfg()
    cfg.health_check_interval_seconds = 42
    hc = HealthChecker(cfg)
    assert hc._interval == 42
    assert hc._supervisor_token == "abc"
