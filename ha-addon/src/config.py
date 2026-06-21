from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class Config:
    ollama_url: str
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket_metrics: str
    telegram_bot_token: str
    telegram_admin_chat_id: int
    alexa_enabled: bool
    alexa_port: int
    alexa_secret: str
    health_check_interval_seconds: int
    log_level: str = "INFO"


def load_config() -> Config:
    path = os.environ.get("SENTINEL_CONFIG_PATH", "/data/options.json")
    with open(path) as f:
        raw = json.load(f)
    return Config(
        ollama_url=raw["ollama_url"],
        influxdb_url=raw["influxdb_url"],
        influxdb_token=raw["influxdb_token"],
        influxdb_org=raw["influxdb_org"],
        influxdb_bucket_metrics=raw["influxdb_bucket_metrics"],
        telegram_bot_token=raw["telegram_bot_token"],
        telegram_admin_chat_id=int(raw.get("telegram_admin_chat_id", 0)),
        alexa_enabled=bool(raw.get("alexa_enabled", False)),
        alexa_port=int(raw.get("alexa_port", 8099)),
        alexa_secret=raw.get("alexa_secret", ""),
        health_check_interval_seconds=int(raw.get("health_check_interval_seconds", 60)),
        log_level=raw.get("log_level", "INFO"),
    )
