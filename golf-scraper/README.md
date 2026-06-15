# Golf Club Deal Finder (Facebook Marketplace)

Finds underpriced golf clubs on Facebook Marketplace and ranks them by how much
profit you could make reselling them. It drives a **real browser you log into
yourself**, estimates each club's resale value from a tunable price book, and
sorts listings by expected profit and margin. Defaults are set for **Ottawa,
Ontario** with prices in **CAD**, and it ships with a **mobile web dashboard**
you can open on your phone.

![dashboard preview](docs/dashboard.png)

> ⚠️ **Read this first.** Scraping Facebook Marketplace is against Facebook's
> [Terms of Service](https://www.facebook.com/legal/terms). Facebook may rate-limit,
> challenge, or ban accounts that automate access. This tool is built for
> **light, personal, occasional** deal-hunting — it logs in as *you*, scrolls
> gently with human-like pauses, and stores results locally. It does **not**
> bypass logins, solve CAPTCHAs, hide automation, or harvest at scale, and you
> should not modify it to do so. Use it at your own risk, and consider the
> official [Facebook Graph API / Commerce APIs] if you need a sanctioned feed.
> Resale price estimates are rough guesses, not financial advice — always sanity
> check against real eBay "sold" prices before buying.

## How it works

1. **Scrape** — Playwright opens Chromium with a *persistent profile*. You log
   into Facebook by hand once; the session is reused on later runs. It navigates
   to your Marketplace search, scrolls a few times, and reads the listing cards.
2. **Price** — each listing title is matched against `data/reference_prices.json`
   (brand/model → typical used resale value), adjusted by condition hints in the
   title ("like new", "for parts", etc.).
3. **Score** — it subtracts resale fees and your flat per-item costs to estimate
   profit and margin, then ranks everything best-deal-first.
4. **Track** — results go into a local SQLite DB so you can ask for only the
   listings that are *new since last run* with `--new-only`.

## Install

```bash
cd golf-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium      # one-time browser download
```

## Quick start

Try the pipeline with no scraping (uses bundled sample listings):

```bash
python -m golf_scraper.main --demo samples/demo_listings.json
```

Real run — first time, keep the browser visible so you can log in:

```bash
python -m golf_scraper.main \
  --query "golf clubs" \
  --max-price 600 --min-margin 0.4 \
  --new-only --web --serve
```

(Location defaults to Ottawa; `--web --serve` also publishes the mobile
dashboard at `http://localhost:8000/`.)

A Chromium window opens. Log into Facebook within the timeout, then leave it
open — the scraper continues automatically and remembers the login next time
(so you can later add `--headless`).

Or put everything in a config file:

```bash
cp config.example.yaml config.yaml   # edit it
python -m golf_scraper.main -c config.yaml
```

## The mobile dashboard (view it on your phone)

Add `--web` to refresh the dashboard data, then `--serve` to host it:

```bash
python -m golf_scraper.main --demo samples/demo_listings.json --web --serve
# → Dashboard live at http://localhost:8000/
```

`--web` writes `webapp/data.js`; the dashboard (`webapp/index.html`) is a
self-contained mobile-first page — no build step, no external libraries — with
search, "deals only" filter, sort, and tappable cards that open each listing.

**To see it on your phone:** run the scraper on a computer on your home Wi-Fi
with `--serve`, find that computer's local IP (e.g. `192.168.1.42`), and open
`http://192.168.1.42:8000/` in your phone's browser. You can also just open
`webapp/index.html` directly — the data is embedded, so it works offline too.

For a real run that scrapes and refreshes the dashboard in one go:

```bash
python -m golf_scraper.main --query "golf clubs" --web --serve
```

## Location & currency

The default `--location ottawa` and CAD price book target the Ottawa, Ontario
market. To search elsewhere, open Facebook Marketplace, set your location and
radius, and search — the URL looks like
`facebook.com/marketplace/<location>/search?query=...`. Copy the `<location>`
part (e.g. `toronto`, `montreal`, or a numeric id) into `--location`, and tune
`data/reference_prices.json` to that market.

## Useful flags

| Flag | What it does |
|------|--------------|
| `--query` | Search terms (try `"scotty cameron"`, `"taylormade driver"`) |
| `--min-price` / `--max-price` | Price filters passed to Marketplace |
| `--min-margin` | Profit-margin bar for the "deal" flag (`0.4` = 40%) |
| `--fee-pct` | Resale fees you'll pay (default `0.13` for eBay) |
| `--extra-costs` | Flat per-item cost: shipping, cleaning, gas (default `$15`) |
| `--deals-only` | Show only listings that clear the margin bar |
| `--new-only` | Show only listings not seen on a previous run |
| `--csv` / `--json` | Export results |
| `--web` | Refresh the mobile dashboard data (`webapp/data.js`) |
| `--serve [PORT]` | Host the dashboard (default port 8000) to view on your phone |
| `--headless` | Run without a visible window (only after first login) |
| `--max-scrolls` | How far to scroll results — keep modest |

## Tuning the price book — this is the important part

The default `data/reference_prices.json` ships with rough numbers. **Your profit
depends entirely on these being accurate for your market.** For each club you
care about, check recent eBay.ca *sold* listings (and local Facebook "sold"
comparables) and update the `resale` value.
Add new entries for models you flip; the matcher uses the most specific entry
whose keywords all appear in the title (plurals handled, so `iron` matches
`irons`). Point at your own file with `--reference my_prices.json`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover pricing, deal scoring, ranking, and card parsing — all offline,
no browser required.

## Notes & limits

- Marketplace's HTML changes often; if extraction returns 0 listings, the card
  selectors in `scraper.py` may need updating.
- It reads only the data shown on the search results grid (title, price,
  location, thumbnail). It does not open each listing or message sellers.
- Keep runs occasional and the scroll count low to stay under the radar and be
  respectful of Facebook's infrastructure.
```
