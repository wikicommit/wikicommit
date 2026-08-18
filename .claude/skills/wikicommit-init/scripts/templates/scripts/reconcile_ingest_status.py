#!/usr/bin/env python3
"""Reconcile ingest management files left at status: pending despite their
content already being in use by a published wiki page.

Background (Issue #474): in a long, multi-source wikicommit-generate batch,
an `action: update` entity's page may end up citing a *different*, already-
registered ingest management file's `source.hash` in its `sources[]` list
(e.g. several related sources about the same entity, processed in the same
run) without that other management file's own `status`/`generated_pages`
ever being written back — it is left at `status: pending`, indefinitely,
even though its content is demonstrably already published. An earlier
version of this fix tried to solve this via SKILL.md prose (an inline
"batch-wide scope" rule plus an end-of-run grep-based sweep); code review
found that design non-deterministic and unsafe in ways a script is not:
prose applied the wrong per-file entity outcome across files, and a naive
grep could not distinguish a genuinely-reconciled `pending` file from a
`status: outdated` file whose hash is *deliberately* left stale by
check_ingest_freshness.py (matching there does not mean "already handled" —
it means "was generated before the source changed and still needs
reprocessing"). This script is deliberately narrow to stay fully
deterministic: it only ever touches `status: pending` files, and only ever
sets them to `status: generated` — never `partial`/`excluded`/`failed`,
since distinguishing those requires per-entity Pass 2/4 results that do not
exist on disk.

Usage:
    python .wikicommit/scripts/reconcile_ingest_status.py [--today=YYYY-MM-DD]

--today: test-only override for the date written to `last_generated_at`
(same convention as check_expires.py). Defaults to the system date.

Exit code: always 0 (workflow step, not a wikicommit-merge quality gate).

Side effect: writes `status`, `generated_pages`, and `last_generated_at`
back to reconciled management files, and removes a `## Failure Reason`
section if present (same as the Pass 4 step 7 `generated` branch).
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _wikilink import ENTITY_DIR
SOURCE_DIR = Path(".wikicommit/source")

FRONTMATTER_RE = re.compile(r"^(---\r?\n)(.*?)(\r?\n---\r?\n?)", re.DOTALL)
FAILURE_REASON_RE = re.compile(r"\n?## Failure Reason\n.*?(?=\n## |\Z)", re.DOTALL)


def _strip_hash_prefix(raw: str | None) -> str:
    if not raw:
        return ""
    return str(raw).removeprefix("sha256:").strip()


def build_hash_to_pages() -> dict[str, list[str]]:
    """Map each hex hash used by any on-disk wiki page's sources[] to the
    page path(s) that cite it."""
    mapping: dict[str, list[str]] = {}
    if not ENTITY_DIR.exists():
        return mapping
    for page in sorted(ENTITY_DIR.rglob("*.md")):
        if page.name == "index.md":
            continue
        fm, err = parse_frontmatter(page)
        if err or not fm:
            continue
        sources = fm.get("sources")
        if not isinstance(sources, list):
            continue
        page_path = str(page)
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            hex_hash = _strip_hash_prefix(entry.get("hash"))
            if not hex_hash:
                continue
            mapping.setdefault(hex_hash, []).append(page_path)
    return mapping


def _upsert_line(yaml_block: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    line = f"{key}: {value}"
    if pattern.search(yaml_block):
        return pattern.sub(lambda _m: line, yaml_block, count=1)
    return yaml_block.rstrip("\r\n") + f"\n{line}"


def _yaml_flow_list(paths: list[str]) -> str:
    return "[" + ", ".join(f'"{p}"' for p in paths) + "]"


def _reconcile_file(mgmt_file: Path, content: str, matched_pages: list[str], today: str) -> None:
    m = FRONTMATTER_RE.match(content)
    if not m:
        return
    yaml_block = m.group(2)
    yaml_block = _upsert_line(yaml_block, "status", "generated")
    yaml_block = _upsert_line(yaml_block, "generated_pages", _yaml_flow_list(matched_pages))
    yaml_block = _upsert_line(yaml_block, "last_generated_at", f'"{today}"')
    body = content[m.end():]
    body = FAILURE_REASON_RE.sub("", body)
    mgmt_file.write_text(content[: m.start(2)] + yaml_block + m.group(3) + body, encoding="utf-8")


def collect_ingest_files() -> list[Path]:
    if not SOURCE_DIR.exists():
        return []
    return sorted(SOURCE_DIR.rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile ingest management files stuck at status: pending "
                     "whose content is already cited by a published wiki page."
    )
    parser.add_argument("--today", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()
    today = args.today or datetime.date.today().isoformat()

    hash_to_pages = build_hash_to_pages()

    reconciled = 0
    for mgmt_file in collect_ingest_files():
        content = mgmt_file.read_text(encoding="utf-8-sig")
        fm, err = parse_frontmatter(mgmt_file)
        if err:
            print(f"WARNING: {mgmt_file}: {err} — skipping", file=sys.stderr)
            continue
        if (fm or {}).get("status") != "pending":
            continue

        source = (fm or {}).get("source") or {}
        hex_hash = _strip_hash_prefix(source.get("hash"))
        if not hex_hash:
            continue

        matched_pages = sorted(set(hash_to_pages.get(hex_hash, [])))
        if not matched_pages:
            continue

        _reconcile_file(mgmt_file, content, matched_pages, today)
        pages_desc = ", ".join(matched_pages)
        print(f"RECONCILED: {mgmt_file} (status: pending -> generated, generated_pages: {pages_desc})")
        print(f"page: {mgmt_file}")
        reconciled += 1

    print(f"SUMMARY: reconciled={reconciled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
