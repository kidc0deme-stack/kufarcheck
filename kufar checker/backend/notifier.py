from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._client: Optional[httpx.AsyncClient] = None

    def configure(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def send(self, message: str):
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured (missing token or chat_id)")
            return

        client = await self._get_client()
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        try:
            await client.post(url, json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
            logger.info("Telegram notification sent")
        except httpx.HTTPError as e:
            logger.error("Failed to send Telegram notification: %s", e)

    @staticmethod
    def format_listing(item: dict) -> str:
        lines = [
            f"🆕 <b>Новое объявление!</b>",
            f"💰 <b>{item.get('price', 'N/A')}</b>",
            f"📝 {item.get('title', 'Без названия')}",
            f"📍 {item.get('city', 'N/A')}",
        ]
        url = item.get("url", "")
        if url:
            lines.append(f"🔗 {url}")
        return "\n".join(lines)

    async def send_listings(self, items: list[dict]):
        if not items:
            return

        # Group by city
        by_city: dict[str, list[dict]] = {}
        for item in items:
            city = item.get("city", "N/A")
            by_city.setdefault(city, []).append(item)

        for city, city_items in by_city.items():
            header = f"🔔 <b>{city}</b> — {len(city_items)} новых\n{'─' * 25}"
            messages = [header]
            for item in city_items:
                messages.append(self.format_listing(item))

            full_message = "\n\n".join(messages)

            # Telegram has a 4096 char limit per message
            if len(full_message) > 4000:
                # Split into chunks
                for i in range(0, len(full_message), 3500):
                    chunk = full_message[i:i + 3500]
                    await self.send(chunk)
            else:
                await self.send(full_message)
