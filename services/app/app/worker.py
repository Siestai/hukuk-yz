import asyncio
import logging
import signal

from app.logging import configure_logging
from app.settings import get_settings

logger = logging.getLogger("app.worker")

HEARTBEAT_SECONDS = 30


async def run(stop: asyncio.Event) -> None:
    """Placeholder loop: log a heartbeat until `stop` is set."""
    while not stop.is_set():
        logger.info("worker heartbeat")
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_SECONDS)
        except TimeoutError:
            pass
    logger.info("worker stopped")


async def main() -> None:
    configure_logging(get_settings().log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run(stop)


if __name__ == "__main__":
    asyncio.run(main())
