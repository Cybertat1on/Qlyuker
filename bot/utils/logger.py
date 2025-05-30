import sys
from loguru import logger
from bot.config import settings
from datetime import date

logger.remove()

logger.add(
    sink=sys.stdout,
    format="<light-white>{time:YYYY-MM-DD HH:mm:ss}</light-white>"
           " | <level>{level: <8}</level>"
           " | <light-white><b>{message}</b></light-white>",
    filter=lambda record: record["level"].name != "TRACE",
    colorize=True
)

if settings.DEBUG_LOGGING:
    logger.add(
        f"logs/err_tracebacks_{date.today()}.txt",
        format="{time:DD.MM.YYYY HH:mm:ss} - {level} - {message}",
        level="TRACE",
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].name == "TRACE"
    )

logger = logger.opt(colors=True)

def log_error(text: str) -> None:
    if settings.DEBUG_LOGGING:
        logger.opt(exception=True).trace(text)
    logger.error(text)
