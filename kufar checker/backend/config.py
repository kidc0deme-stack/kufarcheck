from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    host: str = "0.0.0.0"
    port: int = 8000
    poll_interval: int = 60  # seconds

    class Config:
        env_file = ".env"


settings = Settings()
