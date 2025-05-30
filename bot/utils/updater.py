import os
import sys
import asyncio
from bot.utils import logger
from bot.config import settings

class UpdateManager:
    def __init__(self):
        self.check_interval = settings.CHECK_UPDATE_INTERVAL
        self.is_update_restart = "--update-restart" in sys.argv

    async def run(self) -> None:
        if not self.is_update_restart:
            await asyncio.sleep(10)
        
        while True:
            try:
                logger.info("🔍 Update check skipped (Git checks disabled)")
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error during update loop: {e}")
                await asyncio.sleep(60)
