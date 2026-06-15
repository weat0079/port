"""Unit tests for the offline parts of the pipeline (no browser needed)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from golf_scraper.deals import DealAnalyzer
from golf_scraper.models import Listing
from golf_scraper.pricing import PriceBook
from golf_scraper.scraper import MarketplaceScraper


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.book = PriceBook()

    def test_matches_most_specific(self):
        ref = self.book.match("TaylorMade Stealth 2 Driver mint")
        self.assertIsNotNone(ref)
        self.assertEqual(ref["model"], "Stealth 2 Driver")

    def test_word_boundary_avoids_false_match(self):
        # "sim" should not match inside "simple"
        ref = self.book.match("simple cheap golf driver")
        self.assertIsNone(ref)

    def test_condition_multiplier_prefers_longer_phrase(self):
        # "like new" (1.05) should win over "new" (1.15)
        self.assertEqual(self.book.detect_condition_multiplier("like new club"), 1.05)

    def test_plural_keyword_matches(self):
        # reference keyword is singular "iron"; title says "irons"
        ref = self.book.match("Ping i230 irons 4-PW used")
        self.assertIsNotNone(ref)
        self.assertEqual(ref["model"], "i230 Irons")

    def test_unknown_title_has_no_estimate(self):
        listing = Listing("x", "random mystery item", 10, "u")
        self.book.estimate(listing)
        self.assertIsNone(listing.estimated_resale)


class DealTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = DealAnalyzer(PriceBook(), resale_fee_pct=0.13,
                                     extra_costs=15.0, min_margin_pct=0.40)

    def test_profitable_deal_flagged(self):
        listing = Listing(
            "a", "TaylorMade Stealth 2 Driver excellent", 120,
            "https://www.facebook.com/marketplace/item/1",
        )
        self.analyzer.analyze(listing)
        self.assertGreater(listing.estimated_profit, 0)
        self.assertTrue(self.analyzer.is_deal(listing))

    def test_overpriced_is_not_deal(self):
        listing = Listing("b", "Callaway Paradym Driver good", 400, "u2")
        self.analyzer.analyze(listing)
        self.assertFalse(self.analyzer.is_deal(listing))

    def test_ranking_orders_by_score(self):
        items = [
            Listing("a", "Old set of random golf clubs", 40, "u"),
            Listing("b", "TaylorMade Stealth 2 Driver excellent", 120, "u2"),
        ]
        ranked = self.analyzer.rank(items)
        self.assertEqual(ranked[0].listing_id, "b")


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.s = MarketplaceScraper()

    def test_parse_price_variants(self):
        self.assertEqual(self.s._parse_price("$1,250"), 1250.0)
        self.assertEqual(self.s._parse_price("Free"), 0.0)
        self.assertIsNone(self.s._parse_price("no price here"))

    def test_parse_title_skips_price_line(self):
        text = "$120\nTaylorMade Stealth Driver\nAustin, TX"
        self.assertEqual(self.s._parse_title(text), "TaylorMade Stealth Driver")

    def test_parse_records_filters_non_items(self):
        records = [
            {"href": "https://www.facebook.com/marketplace/item/55",
             "text": "$100\nPing G430 Driver\nAustin, TX", "image_url": ""},
            {"href": "https://www.facebook.com/marketplace/category/golf",
             "text": "$5\nNot an item\nAustin", "image_url": ""},
        ]
        parsed = self.s._parse_records(records)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].title, "Ping G430 Driver")


if __name__ == "__main__":
    unittest.main()
