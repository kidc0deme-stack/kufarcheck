from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# rgn= — коды регионов kufar.by
CITIES = {
    "minsk": "Минск",
    "brest": "Брестская обл.",
    "vitebsk": "Витебская обл.",
    "gomel": "Гомельская обл.",
    "grodno": "Гродненская обл.",
    "minskaya-oblast": "Минская обл.",
    "mogilev": "Могилёвская обл.",
}

_REGION_CODES = {
    "minsk": 7,
    "brest": 1,
    "vitebsk": 2,
    "gomel": 3,
    "grodno": 4,
    "minskaya-oblast": 5,
    "mogilev": 6,
}

CATEGORIES = {
    "transport": "Транспорт",
    "elektronika": "Электроника",
    "telefony-i-planshety": "Телефоны и планшеты",
    "kompyuternaya-tehnika": "Компьютерная техника",
    "bytovaya-tehnika": "Бытовая техника",
    "mebel": "Мебель",
    "zhenskij-garderob": "Женский гардероб",
    "muzhskoj-garderob": "Мужской гардероб",
    "vse-dlya-detej-i-mam": "Всё для детей и мам",
    "vse-dlya-doma": "Всё для дома",
    "sad-i-ogorod": "Сад и огород",
    "remont-i-strojka": "Ремонт и стройка",
    "hobbi-sport-i-turizm": "Хобби, спорт и туризм",
    "zhivotnye": "Животные",
    "krasota-i-zdorovie": "Красота и здоровье",
    "uslugi": "Услуги",
    "rabota-biznes-uchjoba": "Работа и бизнес",
    "gotovyj-biznes-i-oborudovanie": "Готовый бизнес",
    "svadba-i-prazdniki": "Свадьба и праздники",
    "prochee": "Прочее",
}

# UI slugs -> real kufar.by slugs
_UI_TO_KUFAR_CATEGORY = {
    "transport": "transport",
    "elektro": "elektronika",
    "phones": "telefony-i-planshety",
    "comp": "kompyuternaya-tehnika",
    "home": "vse-dlya-doma",
    "garden": "sad-i-ogorod",
    "clothes": "zhenskij-garderob",
    "hobbies": "hobbi-sport-i-turizm",
    "animals": "zhivotnye",
    "beauty": "krasota-i-zdorovie",
    "services": "uslugi",
    "work": "rabota-biznes-uchjoba",
    "other": "prochee",
}


class KufarParser:
    """Парсит объявления из HTML kufar.by через __NEXT_DATA__ + прямой HTML."""

    BASE = "https://www.kufar.by"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-BY,ru;q=0.9,en;q=0.8",
    }

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=20.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def search_listings(
        self,
        city: str = "minsk",
        category: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
    ) -> list[dict]:
        client = await self._get_client()

        # Формируем URL как /l/<category-slug>?query=...&rgn=<code>&sort=lst.d
        path = f"/l/{category}" if category and category in CATEGORIES else "/l"
        params: dict = {"sort": "lst.d"}

        # Map UI category slug to real kufar.by slug if needed
        kufar_category = _UI_TO_KUFAR_CATEGORY.get(category, category)
        if kufar_category and kufar_category in CATEGORIES:
            path = f"/l/{kufar_category}"

        rgn = _REGION_CODES.get(city)
        if rgn:
            params["rgn"] = rgn
        if query:
            params["query"] = query

        try:
            resp = await client.get(f"{self.BASE}{path}", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Kufar request failed: %s", e)
            return []

        return self._parse_html(resp.text, city)

    def _parse_html(self, html: str, city: str) -> list[dict]:
        listings: list[dict] = []

        # 1. Пробуем JSON из __NEXT_DATA__ (главная /l даёт ads сразу)
        listings = self._try_parse_next_data(html, city)
        if listings:
            return listings

        # 2. Fallback: ищем карточки объявлений прямо в HTML
        listings = self._try_parse_html_cards(html, city)
        return listings

    def _try_parse_next_data(self, html: str, city: str) -> list[dict]:
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        ads = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialState", {})
            .get("listing", {})
            .get("ads", [])
        )

        if not ads:
            return []

        return [self._normalize_ad(ad, city) for ad in ads if self._normalize_ad(ad, city)]

    def _try_parse_html_cards(self, html: str, city: str) -> list[dict]:
        """Fallback: парсим DOM-карточки объявлений."""
        listings: list[dict] = []

        # На главной и в категориях объявления — это <a> с href /item/<id>
        link_pattern = re.compile(
            r'<a[^>]+href="https://www\.kufar\.by/item/(\d+)[^"]*"[^>]*>.*?'
            r'<h3[^>]*>(.*?)</h3>.*?'
            r'<p[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in link_pattern.finditer(html):
            ad_id = m.group(1)
            title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            snippet = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            if not title:
                continue
            listings.append({
                "id": ad_id,
                "title": title,
                "price": snippet.split('\n')[0].strip() if snippet else "",
                "url": f"https://www.kufar.by/item/{ad_id}/",
                "image": "",
                "date": "",
                "city": city,
            })

        return listings

    def _normalize_ad(self, ad: dict, city: str) -> Optional[dict]:
        try:
            ad_id = str(ad.get("ad_id") or ad.get("list_id") or "")
            subject = ad.get("subject") or ""
            if not ad_id or not subject:
                return None

            price_byn = ad.get("price_byn")
            price = f"{price_byn} р." if price_byn else "Договорная"

            ad_link = ad.get("ad_link") or f"{self.BASE}/item/{ad_id}/"

            image = ""
            images = ad.get("images") or []
            if images and isinstance(images[0], dict):
                path = images[0].get("path", "")
                if path:
                    image = f"https://content.kufar.by/rms1/{path}"

            return {
                "id": ad_id,
                "title": subject,
                "price": price,
                "url": ad_link,
                "image": image,
                "date": ad.get("list_time", ""),
                "city": city,
            }
        except Exception as e:
            logger.warning("Failed to normalize ad: %s", e)
            return None

    async def check_new_listings(
        self,
        city: str,
        category: Optional[str] = None,
        query: Optional[str] = None,
        seen_ids: Optional[set] = None,
    ) -> list[dict]:
        all_listings = await self.search_listings(
            city=city, category=category, query=query
        )
        if seen_ids is not None:
            new = [l for l in all_listings if l["id"] not in seen_ids]
            seen_ids.update(l["id"] for l in all_listings)
            return new
        return all_listings
