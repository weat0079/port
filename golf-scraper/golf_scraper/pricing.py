"""Brand/model detection and resale-value estimation for golf clubs.

The reference data lives in ``data/reference_prices.json`` so you can tune
the numbers to your own market without touching code. Update the ``resale``
values using eBay "sold" listings for the items you actually plan to flip.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .models import Listing

DEFAULT_REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference_prices.json"
)


class PriceBook:
    def __init__(self, reference_path: Optional[Path] = None):
        path = reference_path or DEFAULT_REFERENCE_PATH
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.currency: str = data.get("currency", "USD")
        self.condition_multipliers: dict[str, float] = data.get(
            "condition_multipliers", {}
        )
        self.references: list[dict] = data.get("references", [])

    def detect_condition_multiplier(self, title: str) -> float:
        """Adjust resale value if the title hints at condition.

        Longer phrases are checked first so "like new" wins over "new".
        """
        text = title.lower()
        for phrase in sorted(
            self.condition_multipliers, key=len, reverse=True
        ):
            if phrase in text:
                return self.condition_multipliers[phrase]
        return self.condition_multipliers.get("good", 0.85)

    def match(self, title: str) -> Optional[dict]:
        """Return the most specific reference entry matching the title.

        "Most specific" = the matching entry with the most keywords, so
        "Stealth 2 Driver" beats a generic "Stealth Driver" entry.
        """
        text = title.lower()
        best: Optional[dict] = None
        best_specificity = -1
        for ref in self.references:
            keywords = [k.lower() for k in ref.get("keywords", [])]
            if keywords and all(_keyword_in(k, text) for k in keywords):
                if len(keywords) > best_specificity:
                    best = ref
                    best_specificity = len(keywords)
        return best

    def estimate(self, listing: Listing) -> None:
        """Populate brand/model/category and estimated resale on a listing."""
        ref = self.match(listing.title)
        if ref is None:
            return
        listing.brand = ref.get("brand", "")
        listing.model = ref.get("model", "")
        listing.category = ref.get("category", "")
        listing.matched_reference = ref.get("model", "")
        base = float(ref.get("resale", 0))
        multiplier = self.detect_condition_multiplier(listing.title)
        listing.estimated_resale = round(base * multiplier, 2)


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _keyword_in(keyword: str, text: str) -> bool:
    """Token-based match, tolerant of simple plurals.

    Matches whole words only (so 'sim' won't match 'simple') but treats
    singular/plural as equal (so 'iron' matches 'irons' and vice versa).
    Multi-word keywords like 'stealth 2' must appear as a contiguous run.
    """
    tokens = _TOKEN_RE.findall(text)
    kw_tokens = _TOKEN_RE.findall(keyword)
    if not kw_tokens:
        return False
    for i in range(len(tokens) - len(kw_tokens) + 1):
        if all(_token_eq(tokens[i + j], kw_tokens[j]) for j in range(len(kw_tokens))):
            return True
    return False


def _token_eq(token: str, keyword: str) -> bool:
    if token == keyword:
        return True
    return token.rstrip("s") == keyword.rstrip("s") and token.rstrip("s") != ""
