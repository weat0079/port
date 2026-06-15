"""Turn raw listings into ranked resale opportunities."""

from __future__ import annotations

from typing import Iterable

from .models import Listing
from .pricing import PriceBook


class DealAnalyzer:
    """Scores listings by expected resale profit.

    Parameters
    ----------
    resale_fee_pct:
        Marketplace/payment fees you'll pay when you re-sell (e.g. eBay
        ~0.13). Subtracted from the estimated resale value.
    extra_costs:
        Flat per-item cost you expect to eat (shipping supplies, gas to
        pick it up, cleaning, regripping, etc.).
    min_margin_pct:
        Minimum profit margin (profit / buy price) for a listing to be
        flagged as a "deal".
    """

    def __init__(
        self,
        price_book: PriceBook,
        resale_fee_pct: float = 0.13,
        extra_costs: float = 15.0,
        min_margin_pct: float = 0.40,
    ):
        self.price_book = price_book
        self.resale_fee_pct = resale_fee_pct
        self.extra_costs = extra_costs
        self.min_margin_pct = min_margin_pct

    def analyze(self, listing: Listing) -> Listing:
        self.price_book.estimate(listing)
        if listing.estimated_resale is None or listing.price is None:
            return listing

        net_resale = listing.estimated_resale * (1 - self.resale_fee_pct)
        profit = net_resale - listing.price - self.extra_costs
        listing.estimated_profit = round(profit, 2)
        if listing.price > 0:
            listing.margin_pct = round(profit / listing.price, 3)

        # Deal score blends absolute profit and margin so a $200 profit at
        # 30% margin and a $40 profit at 200% margin both surface.
        margin = listing.margin_pct or 0
        listing.deal_score = round(max(profit, 0) * (1 + max(margin, 0)), 2)
        return listing

    def analyze_all(self, listings: Iterable[Listing]) -> list[Listing]:
        return [self.analyze(item) for item in listings]

    def is_deal(self, listing: Listing) -> bool:
        return (
            listing.estimated_profit is not None
            and listing.estimated_profit > 0
            and listing.margin_pct is not None
            and listing.margin_pct >= self.min_margin_pct
        )

    def rank(self, listings: Iterable[Listing]) -> list[Listing]:
        """Return analysed listings sorted best-deal first."""
        analysed = self.analyze_all(listings)
        return sorted(analysed, key=lambda x: x.deal_score, reverse=True)
