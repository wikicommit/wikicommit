#!/usr/bin/env python3
"""Reconcile source management files left at status: pending despite their
content already being in use by a published wiki page.

Background (Issue #474): in a long, multi-source wikicommit-generate batch,
an `action: update` entity's page may end up citing a *different*, already-
registered source management file's `source.hash` in its `sources[]` list
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

**And only files whose own `generated_pages` is empty** (Issue #874). That is
the state described above — the pages were written, the batch moved on, and
this file's `status`/`generated_pages` were never written back. The condition
was not written down originally because nothing put a file back into `pending`
*in order to have its pages rebuilt*. The one other writer of that value —
`add_source.py`, flipping an `outdated` file back when its hash matches the
source again — leaves the earlier run's `generated_pages` in place, so this
clause covers that path too, and rightly so: the source was restored on
purpose, and Pass 1 should pick the file up rather than have it flipped
straight back to `generated`. Something now sets `pending` on purpose as well.
A requeue Skill sets `status: pending` on a source so that the next
`wikicommit-generate` runs Pass 2c against it again, which is the only way a
change to a policy, a type template or a generation rule can reach pages that
already exist. Without this clause those files match all three tests above —
they have to, since a source that made pages has its hash cited by them — and
get written straight back to `generated`. The report
is `RECONCILED:`, a success line, so the queue would empty silently, and the
5-source guard makes that the normal case rather than an edge one: requeue 50,
generate processes 5, and the end-of-run call here returns the other 45.

**The requeue origins are protected by different clauses**, which is worth
saying because none of them is visible from the others' code:

  - from `generated` / `partial` — the source made pages, so `generated_pages`
    is non-empty and the clause above catches it;
  - from `excluded`, never having made a page — its hash appears in no page's
    `sources[]`, so the existing match test catches it. This is the origin
    behind turning a policy switch back *off*, which is the case the requeue
    Skill exists for;
  - from `excluded`, having made pages under an earlier, looser policy — this
    one clears *both* of the above and needs a clause of its own (below). Pass 4
    step 7's `excluded` branch writes no `generated_pages`, while the pages the
    source made earlier stay on disk — nothing in the generate path removes a
    page — still citing its unchanged hash. It is reached by the cycle the
    requeue Skill exists for, run twice: tighten a policy, requeue, generate
    (everything excluded), loosen it again, requeue.

The third clause is `last_generated_at`, and it is a test of *whether this file
ever finished a run* rather than of what it produced. `add_source.py` writes the
key empty at creation and only a completed run fills it, so a date means the
`pending` this file carries now was written after that run, on purpose. Issue
#474's state has no date by construction: its pages were written under another
management file's run and this one was never written back at all.

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
from _wikilink import ENTITY_DIR, collect_entity_pages
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
    for page in collect_entity_pages(ENTITY_DIR):
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


def collect_mgmt_files() -> list[Path]:
    if not SOURCE_DIR.exists():
        return []
    return sorted(SOURCE_DIR.rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile source management files stuck at status: pending "
                     "whose content is already cited by a published wiki page."
    )
    parser.add_argument("--today", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()
    today = args.today or datetime.date.today().isoformat()

    hash_to_pages = build_hash_to_pages()

    reconciled = 0
    for mgmt_file in collect_mgmt_files():
        content = mgmt_file.read_text(encoding="utf-8-sig")
        fm, err = parse_frontmatter(mgmt_file)
        if err:
            print(f"WARNING: {mgmt_file}: {err} — skipping", file=sys.stderr)
            continue
        if (fm or {}).get("status") != "pending":
            continue

        # A file this script is meant to rescue has `generated_pages: []` — that
        # is the state Issue #474 describes: the pages were written, the batch
        # moved on, and this file's own `status`/`generated_pages` were never
        # written back. A `pending` file that *does* list pages was put back in
        # the queue on purpose (Issue #874) and must stay there.
        if (fm or {}).get("generated_pages"):
            continue

        # And a file that has finished a run before. `add_source.py` writes an
        # empty `last_generated_at:` at creation and only a completed run fills
        # it, so a date here means this file reached the end of Pass 4 at least
        # once — and therefore that whatever `pending` it carries now was put
        # there afterwards, on purpose. Issue #474's state has no date: those
        # pages were written under *another* management file's run, and this one
        # was never written back at all.
        #
        # This is the third requeue shape, and the only one the clause above
        # misses. A source that made pages and was later excluded in full sits at
        # `status: excluded` with `generated_pages` cleared (Pass 4 step 7's
        # `excluded` branch writes none) while the pages it made earlier stay on
        # disk — nothing in the generate path removes a page — still citing its
        # unchanged hash. Requeue it and it clears both the clause above and the
        # match test below, and a generate run that does not reach it writes it
        # back to `generated` under a `RECONCILED:` line, which reads as success.
        # That is reached by the switch-off-then-on cycle the requeue Skill
        # exists for, so it is not a corner: tighten a policy, requeue, generate
        # (everything excluded), loosen it again, requeue.
        if (fm or {}).get("last_generated_at"):
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
