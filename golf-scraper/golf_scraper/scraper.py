"""Facebook Marketplace scraping via a real, logged-in browser session.

Why a real browser? Marketplace requires authentication and aggressively
blocks headless bots and raw HTTP scraping. The approach here uses Playwright
with a *persistent profile*: the first run opens a visible browser, you log in
to Facebook by hand once, and the session cookie is reused on later runs.

Be a good citizen: keep ``max_scrolls`` modest, leave the delays in place, and
don't run this on a tight loop. Scraping Marketplace is against Facebook's
Terms of Service; use this for your own occasional deal-hunting, at your own
risk, not for high-volume harvesting.
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from .models import Listing

ITEM_HREF_RE = re.compile(r"/marketplace/item/(\d+)")
PRICE_RE = re.compile(r"(?:[$£€])\s?([\d,]+(?:\.\d{2})?)")

# Runs inside the page; returns one record per Marketplace item card.
_EXTRACT_JS = r"""
() => {
    const seen = new Set();
    const out = [];
    const anchors = document.querySelectorAll('a[href*="/marketplace/item/"]');
    for (const a of anchors) {
        const href = a.href.split('?')[0];
        if (seen.has(href)) continue;
        seen.add(href);
        const img = a.querySelector('img');
        out.push({
            href,
            text: (a.innerText || '').trim(),
            image_url: img ? img.src : '',
        });
    }
    return out;
}
"""


class MarketplaceScraper:
    def __init__(
        self,
        user_data_dir: str = ".fb_profile",
        headless: bool = False,
        locale: str = "en-US",
    ):
        self.user_data_dir = str(Path(user_data_dir).resolve())
        self.headless = headless
        self.locale = locale

    def build_search_url(
        self,
        query: str,
        location: str = "",
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        radius_km: Optional[int] = None,
        sort_by: str = "best_match",
    ) -> str:
        base = "https://www.facebook.com/marketplace"
        path = f"{base}/{location}/search" if location else f"{base}/search"
        params = {"query": query}
        if min_price is not None:
            params["minPrice"] = str(min_price)
        if max_price is not None:
            params["maxPrice"] = str(max_price)
        if radius_km is not None:
            params["radius"] = str(radius_km)
        if sort_by == "newest":
            params["sortBy"] = "creation_time_descend"
        return f"{path}?{urllib.parse.urlencode(params)}"

    def scrape_search(
        self,
        query: str,
        location: str = "",
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        radius_km: Optional[int] = None,
        sort_by: str = "best_match",
        max_scrolls: int = 8,
        login_timeout: int = 180,
    ) -> list[Listing]:
        # Imported lazily so the rest of the package works without Playwright
        # installed (e.g. for running the unit tests).
        from playwright.sync_api import sync_playwright

        url = self.build_search_url(
            query, location, min_price, max_price, radius_km, sort_by
        )
        raw_records: list[dict] = []

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                locale=self.locale,
                viewport={"width": 1280, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()

            page.goto(url, wait_until="domcontentloaded")
            self._dismiss_dialogs(page)

            if self._needs_login(page):
                print(
                    "Not logged in. A browser window is open — log in to "
                    f"Facebook within {login_timeout}s, then leave it open."
                )
                self._wait_for_login(page, login_timeout)
                page.goto(url, wait_until="domcontentloaded")
                self._dismiss_dialogs(page)

            self._scroll_and_collect(page, max_scrolls)
            raw_records = page.evaluate(_EXTRACT_JS)
            context.close()

        return self._parse_records(raw_records)

    # -- internals ---------------------------------------------------------

    def _needs_login(self, page) -> bool:
        if "login" in page.url:
            return True
        # The email field only exists on the logged-out gate.
        return page.query_selector('input[name="email"]') is not None

    def _wait_for_login(self, page, timeout: int) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._needs_login(page):
                return
            time.sleep(2)
        raise TimeoutError("Timed out waiting for manual Facebook login.")

    def _dismiss_dialogs(self, page) -> None:
        """Best-effort close of cookie banners / login pop-ups."""
        for label in ["Decline optional cookies", "Allow all cookies", "Close"]:
            try:
                el = page.get_by_label(label).first
                if el and el.is_visible():
                    el.click(timeout=1500)
            except Exception:
                pass

    def _scroll_and_collect(self, page, max_scrolls: int) -> None:
        for _ in range(max_scrolls):
            page.mouse.wheel(0, random.randint(1500, 2500))
            time.sleep(random.uniform(1.5, 3.0))

    def _parse_records(self, records: list[dict]) -> list[Listing]:
        listings: list[Listing] = []
        for rec in records:
            href = rec.get("href", "")
            if not ITEM_HREF_RE.search(href):
                continue
            text = rec.get("text", "")
            price = self._parse_price(text)
            title = self._parse_title(text)
            if not title:
                continue
            listings.append(
                Listing(
                    listing_id=Listing.make_id(href, title),
                    title=title,
                    price=price,
                    url=href,
                    location=self._parse_location(text),
                    image_url=rec.get("image_url", ""),
                )
            )
        return listings

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        if re.search(r"\bfree\b", text, re.IGNORECASE):
            return 0.0
        m = PRICE_RE.search(text)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _parse_title(text: str) -> str:
        """Pick the most title-like line from a card's text block.

        Card text is typically: price line, then title, then location. We
        skip pure price/metadata lines and take the first substantive line.
        """
        for line in (l.strip() for l in text.splitlines()):
            if not line:
                continue
            if PRICE_RE.fullmatch(line) or line.lower() in {"free", "just listed"}:
                continue
            if len(line) < 3:
                continue
            return line[:200]
        return ""

    @staticmethod
    def _parse_location(text: str) -> str:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return lines[-1] if lines else ""
