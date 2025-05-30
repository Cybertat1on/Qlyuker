import asyncio
import fasteners
from random import uniform
from os import path

from bot.utils import logger


class AsyncInterProcessLock:
    def __init__(self, lock_file: str):
        self._lock = fasteners.InterProcessLock(lock_file)
        self._file_name, _ = path.splitext(path.basename(lock_file))

    async def __aenter__(self) -> 'AsyncInterProcessLock':
        while True:
            lock_acquired = await asyncio.to_thread(self._lock.acquire, timeout=uniform(5, 10))
            if lock_acquired:
                return self
            sleep_time = uniform(30, 150)
            logger_message = (
                f"<LY><k>{self._file_name}</k></LY> | Failed to acquire lock for "
                f"{'accounts_config' if 'accounts_config' in self._file_name else 'session'}. "
                f"Retrying in {int(sleep_time)} seconds"
            )
            logger.info(logger_message)
            await asyncio.sleep(sleep_time)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await asyncio.to_thread(self._lock.release)
