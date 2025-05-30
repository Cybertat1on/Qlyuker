from bot.config.config import settings

try:
    APP_ID = settings.API_ID
    APP_HASH = settings.API_HASH
except (NoOptionError, NoSectionError):
    print("Find your App configs in https://my.telegram.org")

