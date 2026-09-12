from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

DB_PATH = "kufar.db"


def _new_db(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            category TEXT,
            query TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS seen_listings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            price TEXT NOT NULL,
            url TEXT NOT NULL,
            city TEXT NOT NULL,
            seen_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            filter_id INTEGER NOT NULL,
            sent_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (listing_id) REFERENCES seen_listings(id),
            FOREIGN KEY (filter_id) REFERENCES filters(id)
        );
    """)


@dataclass
class Filter:
    id: int
    city: str
    category: Optional[str] = None
    query: Optional[str] = None
    active: bool = True
    created_at: Optional[str] = None


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def cursor(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self):
        with self.cursor() as conn:
            _new_db(conn)

    # --- Filters ---

    def add_filter(self, city: str, category: Optional[str] = None,
                   query: Optional[str] = None) -> int:
        with self.cursor() as conn:
            cur = conn.execute(
                "INSERT INTO filters (city, category, query) VALUES (?, ?, ?)",
                (city, category, query),
            )
            return cur.lastrowid

    def remove_filter(self, fid: int):
        with self.cursor() as conn:
            conn.execute("DELETE FROM filters WHERE id = ?", (fid,))

    def get_active_filters(self) -> list[Filter]:
        with self.cursor() as conn:
            rows = conn.execute(
                "SELECT * FROM filters WHERE active = 1"
            ).fetchall()
            return [
                Filter(
                    id=r["id"], city=r["city"],
                    category=r["category"], query=r["query"],
                    active=bool(r["active"]), created_at=r["created_at"],
                )
                for r in rows
            ]

    def toggle_filter(self, fid: int, active: bool):
        with self.cursor() as conn:
            conn.execute(
                "UPDATE filters SET active = ? WHERE id = ?",
                (int(active), fid),
            )

    # --- Seen listings ---

    def add_seen(self, id_: str, title: str, price: str, url: str, city: str):
        with self.cursor() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_listings (id, title, price, url, city) "
                "VALUES (?, ?, ?, ?, ?)",
                (id_, title, price, url, city),
            )

    def add_seen_many(self, items: list[dict]):
        for item in items:
            self.add_seen(
                id_=item["id"],
                title=item["title"],
                price=item["price"],
                url=item["url"],
                city=item["city"],
            )

    def seen_id(self, id_: str) -> bool:
        with self.cursor() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_listings WHERE id = ?", (id_,)
            ).fetchone()
            return row is not None

    def get_seen_ids(self) -> set[str]:
        with self.cursor() as conn:
            rows = conn.execute("SELECT id FROM seen_listings").fetchall()
            return {r["id"] for r in rows}

    # --- Notifications log ---

    def log_notification(self, listing_id: str, filter_id: int):
        with self.cursor() as conn:
            conn.execute(
                "INSERT INTO notifications (listing_id, filter_id) VALUES (?, ?)",
                (listing_id, filter_id),
            )
