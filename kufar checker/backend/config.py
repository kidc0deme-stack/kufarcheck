from __future__ import annotations

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    host: str = "0.0.0.0"
    port: int = int(os.environ.get("PORT", "8000"))
    poll_interval: int = 60  # seconds

    class Config:
        env_file = ".env"


settings = Settings()
