"""
HA-Sentinel Add-on — asyncio entrypoint.
Starts the health check daemon and (optionally) the Alexa HTTP endpoint.
"""

import asyncio
import logging

from config import load_config
from interfaces import AlexaEndpoint
from observability import HealthChecker
from utils import setup_logging


async def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)

    log = logging.getLogger(__name__)
    log.info('{"event":"addon_start","version":"0.2.0"}')

    tasks = [asyncio.create_task(HealthChecker(cfg).run())]

    if cfg.alexa_enabled:
        alexa = AlexaEndpoint(cfg)
        await alexa.start()
        log.info('{"event":"alexa_enabled","port":%d}', cfg.alexa_port)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
