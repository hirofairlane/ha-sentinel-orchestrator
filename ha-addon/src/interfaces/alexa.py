"""
AlexaEndpoint — minimal HTTP server that receives text from an Alexa Skill
or local bridge, forwards it to Ollama, and returns a plain-text response.
"""

from __future__ import annotations

import logging

import aiohttp
from aiohttp import web

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Eres el asistente de hogar inteligente HA-Sentinel. "
    "Responde siempre en español (España), de forma concisa y útil. "
    "Si te piden controlar un dispositivo, indica claramente la acción que se tomaría."
)


class AlexaEndpoint:
    def __init__(self, cfg) -> None:
        self._cfg = cfg
        self._app = web.Application()
        self._app.router.add_post("/alexa", self._handle)

    async def start(self) -> None:
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._cfg.alexa_port)
        await site.start()
        log.info('{"event":"alexa_endpoint_started","port":%d}', self._cfg.alexa_port)

    async def _handle(self, request: web.Request) -> web.Response:
        # Optional bearer token auth
        if self._cfg.alexa_secret:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {self._cfg.alexa_secret}":
                return web.Response(status=401, text="Unauthorized")

        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")

        text = body.get("text", "").strip()
        if not text:
            return web.Response(status=400, text="Missing 'text' field")

        log.info('{"event":"alexa_request","text":"%s"}', text[:100])

        response_text = await self._ask_ollama(text)

        return web.json_response({"response": response_text, "success": True})

    async def _ask_ollama(self, user_text: str) -> str:
        payload = {
            "model": "qwen2.5:14b",
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        }
        timeout = aiohttp.ClientTimeout(total=self._cfg.__dict__.get("ollama_timeout", 15))
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._cfg.ollama_url}/api/chat", json=payload
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("message", {}).get("content", "Sin respuesta.")
        except Exception as exc:
            log.error('{"event":"alexa_ollama_error","error":"%s"}', str(exc))
            return "Lo siento, el servicio de IA no está disponible en este momento."
