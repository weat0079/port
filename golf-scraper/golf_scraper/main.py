"""Command-line entry point for the golf-club deal finder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .deals import DealAnalyzer
from .models import Listing
from .pricing import PriceBook
from .report import print_table, write_csv, write_json, write_webapp_data
from .storage import Store


def load_config(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        print(f"Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = p.read_text(encoding="utf-8")
    if p.suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError:
            print("PyYAML not installed. `pip install pyyaml` or use JSON config.",
                  file=sys.stderr)
            sys.exit(1)
        return yaml.safe_load(text) or {}
    return json.loads(text)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="golf-scraper",
        description="Find resale deals on golf clubs on Facebook Marketplace.",
    )
    parser.add_argument("-c", "--config", help="Path to YAML/JSON config file.")
    parser.add_argument("-q", "--query", default="golf clubs",
                        help="Search query (default: 'golf clubs').")
    parser.add_argument("--location", default="ottawa",
                        help="Marketplace location slug/id (default: ottawa).")
    parser.add_argument("--min-price", type=int, default=None)
    parser.add_argument("--max-price", type=int, default=None)
    parser.add_argument("--radius-km", type=int, default=None)
    parser.add_argument("--sort", choices=["best_match", "newest"],
                        default="newest")
    parser.add_argument("--max-scrolls", type=int, default=8,
                        help="How many times to scroll the results (be gentle).")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser headless (only works once logged in).")
    parser.add_argument("--profile-dir", default=".fb_profile",
                        help="Persistent browser profile dir (stores login).")
    parser.add_argument("--db", default="golf_deals.db",
                        help="SQLite database path for dedup/history.")
    parser.add_argument("--fee-pct", type=float, default=0.13,
                        help="Resale marketplace/payment fee fraction.")
    parser.add_argument("--extra-costs", type=float, default=15.0,
                        help="Flat per-item cost (shipping, cleaning, gas).")
    parser.add_argument("--min-margin", type=float, default=0.40,
                        help="Min profit margin to flag as a deal (0.40 = 40%%).")
    parser.add_argument("--reference", default=None,
                        help="Path to a custom reference_prices.json.")
    parser.add_argument("--csv", default=None, help="Write results to CSV.")
    parser.add_argument("--json", default=None, help="Write results to JSON.")
    parser.add_argument("--web", action="store_true",
                        help="Update the mobile dashboard (webapp/data.js).")
    parser.add_argument("--serve", type=int, nargs="?", const=8000, default=None,
                        metavar="PORT",
                        help="After running, serve the dashboard on this port "
                             "(default 8000) so you can open it on your phone.")
    parser.add_argument("--limit", type=int, default=25,
                        help="How many rows to print.")
    parser.add_argument("--deals-only", action="store_true",
                        help="Only show listings that clear the margin bar.")
    parser.add_argument("--new-only", action="store_true",
                        help="Only show listings not seen on a previous run.")
    parser.add_argument("--demo", metavar="FILE",
                        help="Skip scraping; analyse listings from a JSON file. "
                             "Use samples/demo_listings.json to try the pipeline.")
    return parser


def _merge(args: argparse.Namespace, config: dict) -> argparse.Namespace:
    """CLI flags win over config-file values when explicitly provided."""
    defaults = build_arg_parser().parse_args([])
    for key, value in config.items():
        attr = key.replace("-", "_")
        if not hasattr(args, attr):
            continue
        if getattr(args, attr) == getattr(defaults, attr, None):
            setattr(args, attr, value)
    return args


def _load_demo_listings(path: str) -> list[Listing]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    listings = []
    for rec in data:
        url = rec.get("url", "")
        title = rec.get("title", "")
        listings.append(
            Listing(
                listing_id=Listing.make_id(url, title),
                title=title,
                price=rec.get("price"),
                url=url,
                location=rec.get("location", ""),
                image_url=rec.get("image_url", ""),
            )
        )
    return listings


def run(args: argparse.Namespace) -> int:
    price_book = PriceBook(Path(args.reference) if args.reference else None)
    analyzer = DealAnalyzer(
        price_book,
        resale_fee_pct=args.fee_pct,
        extra_costs=args.extra_costs,
        min_margin_pct=args.min_margin,
    )

    if args.demo:
        listings = _load_demo_listings(args.demo)
    else:
        from .scraper import MarketplaceScraper
        scraper = MarketplaceScraper(
            user_data_dir=args.profile_dir, headless=args.headless
        )
        print(f"Searching Marketplace for '{args.query}'...")
        listings = scraper.scrape_search(
            query=args.query,
            location=args.location,
            min_price=args.min_price,
            max_price=args.max_price,
            radius_km=args.radius_km,
            sort_by=args.sort,
            max_scrolls=args.max_scrolls,
        )
        print(f"Found {len(listings)} listings.")

    ranked = analyzer.rank(listings)

    store = Store(args.db)
    try:
        fresh_ids = {l.listing_id for l in store.save_all(ranked)}
    finally:
        store.close()

    shown = ranked
    if args.deals_only:
        shown = [l for l in shown if analyzer.is_deal(l)]
    if args.new_only:
        shown = [l for l in shown if l.listing_id in fresh_ids]

    print()
    print_table(shown, limit=args.limit)

    deals = [l for l in ranked if analyzer.is_deal(l)]
    print(f"\n{len(deals)} of {len(ranked)} listings clear your "
          f"{args.min_margin*100:.0f}% margin bar "
          f"({len(fresh_ids)} new since last run).")

    if args.csv:
        write_csv(shown, args.csv)
        print(f"Wrote CSV: {args.csv}")
    if args.json:
        write_json(shown, args.json)
        print(f"Wrote JSON: {args.json}")

    webapp_dir = Path(__file__).resolve().parent.parent / "webapp"
    if args.web or args.serve is not None:
        from datetime import datetime
        meta = {
            "location": args.location,
            "query": args.query,
            "currency": price_book.currency,
            "min_margin": args.min_margin,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        data_path = webapp_dir / "data.js"
        write_webapp_data(ranked, str(data_path), meta)
        print(f"Updated dashboard data: {data_path}")

    if args.serve is not None:
        _serve(webapp_dir, args.serve)
    return 0


def _serve(directory: Path, port: int) -> None:
    import functools
    import http.server
    import socketserver

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(directory)
    )
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"\nDashboard live at http://localhost:{port}/  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    args = _merge(args, config)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
