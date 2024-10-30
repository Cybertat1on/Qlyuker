from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    USE_PROXY_FROM_FILE: bool = False
    REF_ID: str = "bro-1197825376"

    TAPS: list = [10, 100]
    SLEEP_BETWEEN_TAPS: list = [1, 3]
    ENERGY_THRESHOLD: float = 0.05
    SLEEP_ON_LOW_ENERGY: int = 60 * 15
    SLEEP_AFTER_UPGRADE: int = 1
    DELAY_BETWEEN_TASKS: list = [3, 15]

    MAX_INCOME: float = 0

    UPGRADE_CHECK_DELAY: int = 60
    RETRY_DELAY: int = 3
    MAX_RETRIES: int = 5

    ENABLE_TAPS: bool = True
    ENABLE_CLAIM_REWARDS: bool = True
    ENABLE_UPGRADES: bool = True
    ENABLE_TASKS: bool = True

    @property
    def MIN_TAPS(self):
        return self.TAPS[0]

    @property
    def MAX_TAPS(self):
        return self.TAPS[1]

    @property
    def MIN_SLEEP_BETWEEN_TAPS(self):
        return self.SLEEP_BETWEEN_TAPS[0]

    @property
    def MAX_SLEEP_BETWEEN_TAPS(self):
        return self.SLEEP_BETWEEN_TAPS[1]

    @property
    def MIN_DELAY_BETWEEN_TASKS(self):
        return self.DELAY_BETWEEN_TASKS[0]

    @property
    def MAX_DELAY_BETWEEN_TASKS(self):
        return self.DELAY_BETWEEN_TASKS[1]


settings = Settings()

