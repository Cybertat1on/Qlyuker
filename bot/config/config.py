from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    USE_PROXY_FROM_FILE: bool = False
    REF_ID: str = "bro-1197825376"

    MIN_TAPS: int = 10
    MAX_TAPS: int = 100
    MIN_SLEEP_BETWEEN_TAPS: int = 1
    MAX_SLEEP_BETWEEN_TAPS: int = 3
    ENERGY_THRESHOLD: float = 0.05
    SLEEP_ON_LOW_ENERGY: int = 60 * 15
    SLEEP_AFTER_UPGRADE: int = 1
    SLEEP_AFTER_TAPS: int = 0
    MIN_DELAY_BETWEEN_TASKS: int = 3
    MAX_DELAY_BETWEEN_TASKS: int = 15

    UPGRADE_CHECK_DELAY: int = 5
    RETRY_DELAY: int = 3
    MAX_RETRIES: int = 5
settings = Settings()
