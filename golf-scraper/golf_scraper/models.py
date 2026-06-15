"""Core data structures shared across the scraper."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Listing:
    """A single Facebook Marketplace listing."""

    listing_id: str
    title: str
    price: Optional[float]
    url: str
    location: str = ""
    image_url: str = ""
    # Filled in by the deal analyser
    brand: str = ""
    model: str = ""
    category: str = ""
    estimated_resale: Optional[float] = None
    estimated_profit: Optional[float] = None
    margin_pct: Optional[float] = None
    deal_score: float = 0.0
    matched_reference: str = ""
    first_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @staticmethod
    def make_id(url: str, title: str) -> str:
        """Stable id derived from the listing URL (falls back to title)."""
        basis = url.split("?")[0] if url else title
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)
