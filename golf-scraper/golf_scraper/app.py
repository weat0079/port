"""Golf Flip Finder — a real local web application (Ottawa only).

Run it:

    python -m golf_scraper.app

It starts a small web server, opens the dashboard in your browser, and prints a
LAN address you can open on your phone. Click **Find deals** and a Chromium
window opens for you to log into Facebook once; it then scrapes live Ottawa
Marketplace golf-club listings, scores them, and shows the best flips.

Locked to Ottawa, Ontario on purpose — the location cannot be changed from the
UI or the API.

Only the standard library is required to *run the app*; Playwright is needed
for the live scrape (`pip install -r requirements.txt && playwright install
chromium`).
"""

from __future__ import annotations

import json
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .deals import DealAnalyzer
from .pricing import PriceBook
from .storage import Store

# Ottawa is hard-locked. Do not make this configurable.
LOCATION = "ottawa"
LOCATION_LABEL = "Ottawa, ON"

WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"
DB_PATH = str(Path(__file__).resolve().parent.parent / "golf_deals.db")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".json": "application/json; charset=utf-8",
}


class ScrapeJob:
    """Tracks the single in-flight scrape (only one runs at a time)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = "idle"          # idle | running | done | error
        self.message = "Ready."
        self.new_count = 0
        self.total = 0
        self.finished_at = ""

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "state": self.state,
                "message": self.message,
                "new_count": self.new_count,
                "total": self.total,
                "finished_at": self.finished_at,
            }

    def set(self, **kw) -> None:
        with self.lock:
            self.__dict__.update(kw)


class App:
    def __init__(self, query: str = "golf clubs", min_margin: float = 0.40,
                 fee_pct: float = 0.13, extra_costs: float = 15.0,
                 min_price: int = 20, max_price: int = 600,
                 max_scrolls: int = 8):
        self.query = query
        self.min_margin = min_margin
        self.price_book = PriceBook()
        self.analyzer = DealAnalyzer(
            self.price_book, resale_fee_pct=fee_pct,
            extra_costs=extra_costs, min_margin_pct=min_margin,
        )
        self.min_price = min_price
        self.max_price = max_price
        self.max_scrolls = max_scrolls
        self.job = ScrapeJob()

    # -- data ------------------------------------------------------------

    def deals_payload(self) -> dict:
        store = Store(DB_PATH)
        try:
            listings = store.all_listings()
        finally:
            store.close()
        # Re-score in case pricing rules changed since they were stored.
        listings = self.analyzer.rank(listings)
        return {
            "meta": {
                "location": LOCATION,
                "location_label": LOCATION_LABEL,
                "query": self.query,
                "currency": self.price_book.currency,
                "min_margin": self.min_margin,
                "generated": self.job.finished_at,
            },
            "listings": [l.to_dict() for l in listings],
        }

    # -- scraping --------------------------------------------------------

    def start_scrape(self) -> dict:
        with self.job.lock:
            if self.job.state == "running":
                return {"state": "running", "message": self.job.message}
            self.job.state = "running"
            self.job.message = "Opening browser — log into Facebook if asked…"
        threading.Thread(target=self._scrape_worker, daemon=True).start()
        return {"state": "running", "message": self.job.message}

    def _scrape_worker(self) -> None:
        try:
            from .scraper import MarketplaceScraper
        except Exception as exc:  # pragma: no cover - import guard
            self.job.set(state="error",
                         message=f"Playwright not installed: {exc}")
            return
        try:
            scraper = MarketplaceScraper(headless=False)
            listings = scraper.scrape_search(
                query=self.query,
                location=LOCATION,          # hard-locked to Ottawa
                min_price=self.min_price,
                max_price=self.max_price,
                sort_by="newest",
                max_scrolls=self.max_scrolls,
            )
            ranked = self.analyzer.rank(listings)
            store = Store(DB_PATH)
            try:
                fresh = store.save_all(ranked)
            finally:
                store.close()
            self.job.set(
                state="done",
                message=f"Found {len(ranked)} listings ({len(fresh)} new).",
                new_count=len(fresh),
                total=len(ranked),
                finished_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
        except Exception as exc:
            self.job.set(state="error", message=f"Scrape failed: {exc}")


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quieter console
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode("utf-8"),
                       _CONTENT_TYPES[".json"])

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/deals":
                return self._json(app.deals_payload())
            if path == "/api/status":
                return self._json(app.job.snapshot())
            return self._serve_static(path)

        def do_POST(self):
            path = self.path.split("?")[0]
            if path == "/api/scrape":
                return self._json(app.start_scrape())
            self._json({"error": "not found"}, 404)

        def _serve_static(self, path: str):
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            target = (WEBAPP_DIR / rel).resolve()
            # Prevent path traversal outside the webapp dir.
            if not str(target).startswith(str(WEBAPP_DIR.resolve())) or not target.is_file():
                return self._json({"error": "not found"}, 404)
            ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            self._send(200, target.read_bytes(), ctype)

    return Handler


def _lan_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def serve(port: int = 8000, open_browser: bool = True) -> None:
    app = App()
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler(app))
    local = f"http://localhost:{port}/"
    lan = f"http://{_lan_ip()}:{port}/"
    print("\n  ⛳  Golf Flip Finder — Ottawa\n")
    print(f"     On this computer:  {local}")
    print(f"     On your phone:     {lan}   (same Wi-Fi)\n")
    print("     Click “Find deals” in the page to scrape live Ottawa listings.")
    print("     Press Ctrl+C to stop.\n")
    if open_browser:
        try:
            webbrowser.open(local)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        httpd.shutdown()


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Golf Flip Finder (Ottawa) web app.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-open", action="store_true",
                   help="Don't auto-open the browser.")
    args = p.parse_args()
    serve(port=args.port, open_browser=not args.no_open)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
