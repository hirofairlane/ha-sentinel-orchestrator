"""
HealthChecker — polls Ollama, HA Supervisor, InfluxDB and Telegram every N seconds.
Writes results to InfluxDB and sends a Telegram alert to the admin on any failure.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

import aiohttp
from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

log = logging.getLogger(__name__)


class HealthChecker:
    def __init__(self, cfg) -> None:
        self._cfg = cfg
        self._interval = cfg.health_check_interval_seconds
        self._supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")

    async def run(self) -> None:
        log.info('{"event":"health_checker_started","interval":%d}', self._interval)
        while True:
            await self._tick()
            await asyncio.sleep(self._interval)

    async def _tick(self) -> None:
        results = await asyncio.gather(
            self._check_ollama(),
            self._check_supervisor(),
            self._check_influxdb(),
            self._check_telegram(),
            return_exceptions=True,
        )
        labels = ["ollama", "supervisor", "influxdb", "telegram"]
        failures = []

        async with InfluxDBClientAsync(
            url=self._cfg.influxdb_url,
            token=self._cfg.influxdb_token,
            org=self._cfg.influxdb_org,
        ) as client:
            write_api = client.write_api()
            for label, result in zip(labels, results):
                if isinstance(result, Exception):
                    status, latency = "error", -1.0
                    log.error(
                        '{"event":"health_check_exception","service":"%s","error":"%s"}',
                        label, str(result),
                    )
                    failures.append(f"{label}: {result}")
                else:
                    status = result.get("status", "error")
                    latency = result.get("latency_ms", -1.0)
                    if status != "ok":
                        failures.append(f"{label}: {result.get('detail', status)}")

                point = (
                    Point("health_check")
                    .tag("service", label)
                    .field("status", status)
                    .field("latency_ms", float(latency))
                )
                await write_api.write(
                    bucket=self._cfg.influxdb_bucket_metrics, record=point
                )

        if failures:
            await self._alert(failures)

    async def _check_ollama(self) -> dict:
        t0 = time.monotonic()
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5)
        ) as s:
            async with s.get(f"{self._cfg.ollama_url}/api/tags") as r:
                r.raise_for_status()
                data = await r.json()
                latency = (time.monotonic() - t0) * 1000
                models = [m["name"] for m in data.get("models", [])]
                return {"status": "ok", "latency_ms": latency, "models": models}

    async def _check_supervisor(self) -> dict:
        t0 = time.monotonic()
        headers = {"Authorization": f"Bearer {self._supervisor_token}"}
        async with aiohttp.ClientSession(
            headers=headers, timeout=aiohttp.ClientTimeout(total=5)
        ) as s:
            async with s.get("http://supervisor/core/info") as r:
                r.raise_for_status()
                latency = (time.monotonic() - t0) * 1000
                return {"status": "ok", "latency_ms": latency}

    async def _check_influxdb(self) -> dict:
        t0 = time.monotonic()
        async with InfluxDBClientAsync(
            url=self._cfg.influxdb_url,
            token=self._cfg.influxdb_token,
            org=self._cfg.influxdb_org,
        ) as client:
            ok = await client.ping()
            latency = (time.monotonic() - t0) * 1000
            return {"status": "ok" if ok else "error", "latency_ms": latency}

    async def _check_telegram(self) -> dict:
        t0 = time.monotonic()
        url = f"https://api.telegram.org/bot{self._cfg.telegram_bot_token}/getMe"
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5)
        ) as s:
            async with s.get(url) as r:
                data = await r.json()
                latency = (time.monotonic() - t0) * 1000
                ok = data.get("ok", False)
                return {"status": "ok" if ok else "error", "latency_ms": latency}

    async def _alert(self, failures: list[str]) -> None:
        if not self._cfg.telegram_admin_chat_id:
            return
        msg = "⚠️ HA-Sentinel health check failed:\n" + "\n".join(f"• {f}" for f in failures)
        url = f"https://api.telegram.org/bot{self._cfg.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self._cfg.telegram_admin_chat_id, "text": msg}
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as s:
                await s.post(url, json=payload)
        except Exception as exc:
            log.error('{"event":"telegram_alert_failed","error":"%s"}', str(exc))
