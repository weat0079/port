"""Human- and machine-readable output for ranked listings."""

from __future__ import annotations

import csv
import json
from typing import Iterable

from .models import Listing


def _fmt_money(value) -> str:
    return f"${value:,.0f}" if value is not None else "—"


def print_table(listings: list[Listing], limit: int = 25) -> None:
    if not listings:
        print("No listings to show.")
        return

    header = f"{'#':>2}  {'PROFIT':>8}  {'MARGIN':>7}  {'PRICE':>7}  {'RESALE':>7}  TITLE"
    print(header)
    print("-" * len(header))
    for i, item in enumerate(listings[:limit], 1):
        margin = f"{item.margin_pct*100:.0f}%" if item.margin_pct is not None else "—"
        title = (item.title[:48] + "…") if len(item.title) > 49 else item.title
        print(
            f"{i:>2}  {_fmt_money(item.estimated_profit):>8}  {margin:>7}  "
            f"{_fmt_money(item.price):>7}  {_fmt_money(item.estimated_resale):>7}  {title}"
        )
    print()
    for i, item in enumerate(listings[:limit], 1):
        if item.url:
            print(f"  [{i}] {item.url}")


def write_csv(listings: Iterable[Listing], path: str) -> None:
    listings = list(listings)
    if not listings:
        return
    fields = list(listings[0].to_dict().keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for item in listings:
            writer.writerow(item.to_dict())


def write_json(listings: Iterable[Listing], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([item.to_dict() for item in listings], fh, indent=2)
