#!/usr/bin/env python3
"""Detect wiki pages whose expires_at date has passed.

Usage:
    python .wikicommit/scripts/check_expires.py [--today=YYYY-MM-DD]

Exit code: always 0 (warning-only, non-blocking).
"""

import argparse
import datetime
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_or_warn as _parse_frontmatter
from _wikilink import ENTITY_DIR, VIEW_DIR, collect_entity_pages, collect_view_pages


def collect_pages() -> list[Path]:
    # View pages carry expires_at on the same terms as any other page
    # (Issue #675), so freshness is checked across both trees.
    return collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect expired wiki pages.")
    parser.add_argument("--today", metavar="YYYY-MM-DD", help="Override today's date (for testing).")
    args = parser.parse_args()

    if args.today:
        try:
            today = datetime.date.fromisoformat(args.today)
        except ValueError:
            print(f"ERROR: --today value is not a valid YYYY-MM-DD date: {args.today}")
            print("SUMMARY: expired=0")
            return 0
    else:
        today = datetime.date.today()

    expired_count = 0

    for page in collect_pages():
        fm = _parse_frontmatter(page)

        if fm.get("status") == "removed":
            continue

        expires_at_raw = fm.get("expires_at")
        if expires_at_raw is None:
            continue

        if isinstance(expires_at_raw, datetime.datetime):
            expires_at = expires_at_raw.date()
        elif isinstance(expires_at_raw, datetime.date):
            expires_at = expires_at_raw
        else:
            try:
                expires_at = datetime.date.fromisoformat(str(expires_at_raw))
            except ValueError:
                print(
                    f"WARNING: {page}: expires_at has invalid format (expected YYYY-MM-DD): {expires_at_raw!r}",
                )
                continue

        if expires_at <= today:
            print(f"EXPIRED: {page} (expires_at: {expires_at}, today: {today})")
            print(f"page: {page}")
            expired_count += 1

    print(f"SUMMARY: expired={expired_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
