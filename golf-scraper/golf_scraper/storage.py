"""SQLite persistence so you only get alerted about genuinely new listings."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Listing


class Store:
    def __init__(self, db_path: str = "golf_deals.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                listing_id TEXT PRIMARY KEY,
                title TEXT,
                price REAL,
                url TEXT,
                location TEXT,
                image_url TEXT,
                brand TEXT,
                model TEXT,
                category TEXT,
                estimated_resale REAL,
                estimated_profit REAL,
                margin_pct REAL,
                deal_score REAL,
                matched_reference TEXT,
                first_seen TEXT
            )
            """
        )
        self.conn.commit()

    def is_known(self, listing_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM listings WHERE listing_id = ?", (listing_id,)
        )
        return cur.fetchone() is not None

    def upsert(self, listing: Listing) -> bool:
        """Insert a listing. Returns True if it was new."""
        new = not self.is_known(listing.listing_id)
        self.conn.execute(
            """
            INSERT INTO listings VALUES (
                :listing_id, :title, :price, :url, :location, :image_url,
                :brand, :model, :category, :estimated_resale,
                :estimated_profit, :margin_pct, :deal_score,
                :matched_reference, :first_seen
            )
            ON CONFLICT(listing_id) DO UPDATE SET
                price = excluded.price,
                estimated_resale = excluded.estimated_resale,
                estimated_profit = excluded.estimated_profit,
                margin_pct = excluded.margin_pct,
                deal_score = excluded.deal_score
            """,
            listing.to_dict(),
        )
        self.conn.commit()
        return new

    def save_all(self, listings: Iterable[Listing]) -> list[Listing]:
        """Persist listings, returning only the ones not seen before."""
        fresh = []
        for listing in listings:
            if self.upsert(listing):
                fresh.append(listing)
        return fresh

    def close(self) -> None:
        self.conn.close()
