#!/usr/bin/env python3
"""check_review_coverage.py — read the review records back (Issue #750).

`record_review.py` writes one immutable file per review under
`.wikicommit/review/`. This is the consumer that makes that tree worth having:
without it the records would be a receptacle with nothing reading it, which is
the shape Issue #553 rules out.

It answers four questions a wiki cannot otherwise ask:

- **How much of the wiki has actually been reviewed, and by what?**
  `SUMMARY:` and `COVERAGE:`. The point is the *denominator*. The Completion
  Notice reports failures, so a reader sees "3 findings" with no way to know
  whether that is out of 3 pages or 300; and reporting per model is what makes
  it possible to notice later that one model finds a certain defect and
  another does not.
- **What has nothing standing behind it?** `UNREVIEWED:` — no record judges the
  page as it now stands. Almost always that means no record at all; it also
  covers a page whose every record was `result: discarded`, which judged a draft
  that was thrown away and therefore says nothing about the text on disk
  (Issue #766). Those two are one list rather than two because they call for the
  same thing — someone has to look at this page — and the line says which of the
  two it is, so nothing is hidden by putting them together.
- **What is most worth a human reading?** `RISKY:` — a page whose *standing*
  review took more than one attempt, or raised findings. This is the sampling
  blueprint, and it is exactly what evaporated when the verdict was discarded.
  "Standing" means the newest record that judged the page as it now stands, of
  either kind; the list therefore shrinks when a later review comes back clean,
  rather than accumulating every page that ever had a bad day (Issue #760).
- **Which verdicts no longer apply?** `STALE_REVIEW:`, in both of the two ways
  a verdict can go stale: the page's own text changed after the review, or the
  evidence under it did.

The second staleness case is the one nothing else covers. A `/wikicommit-fix`
edit sends `review_status` back to `pending` (Issue #724) so the *human* side
self-corrects, but the machine's verdict was made against text that no longer
exists and, before this tree, nothing recorded that it had been made at all.

`STALE_REVIEW:` does not become noise, and that follows from the structure
rather than from a threshold: Pass 4 re-runs on every regeneration, so the
only ways a verdict outlives its page are a `/wikicommit-fix` edit and a source
that changed underneath it.

## Which records each line reads

Every per-page line and every count reads the *standing* record: the newest one
that actually judged the page as it now stands. Only the kind it has to be
differs:

- `SUMMARY: ai_reviewed` / `COVERAGE:` — the standing **AI** record, so a model
  is credited with its latest surviving verdict for a page rather than with
  every verdict it ever wrote for it.
- `SUMMARY: human_reviewed` — the standing **human** record.
- `UNREVIEWED:` — printed when there is no standing record of either kind.
- `RISKY:` — the standing record of **any** kind (Issue #760).
- `STALE_REVIEW:` / `RETRACTED_EVIDENCE:` — the standing **AI** record
  (`standing_verdict()`), because staleness is measured against the machine's
  evidence list.

That single definition is the whole of Issue #766. Before it, the counts and
`UNREVIEWED:` used a different rule from the three per-page verdict lines: they
read the newest AI record whether or not it had judged anything, and treated
"has a record" as "has been reviewed". A page whose only records were
`result: discarded` therefore appeared in **no** per-page line at all while
`SUMMARY:` and `COVERAGE:` counted it as reviewed — `COVERAGE:` could report a
page with `attempts>=2` that `RISKY:` stayed silent about, and a model could be
credited with covering a page it never successfully judged. That is not a
contrived state: Pass 4 records a discarded review for an `action: update`
entity that exhausts `max_retries`, and a page generated before this tree
existed has no earlier record to fall back on.

Discarded attempts are still visible, in two places rather than folded into a
number that overstates coverage. Each `COVERAGE:` line carries its own count of
the pages whose **newest AI record** is a discarded one that model wrote — which
is what makes a quiet `RISKY:` legible instead of contradictory — and
`SUMMARY: findings=` still totals their findings.

That column is keyed on the page's newest AI record rather than on each model's
own newest, and deliberately so: it exists to explain a `RISKY:` line that is
missing, and once *any* later review has judged the current text there is no
missing line left to explain. A model whose discarded attempt was superseded by
another model's verdict therefore gets no count here.

`SUMMARY: findings=` is the deliberate exception to the standing rule: it is a
running tally of how much reviewing has caught over the wiki's life, which is a
historical quantity and correctly cumulative, so it counts discarded reviews
too (Issue #760, reaffirmed as out of scope by Issue #766).

## No thresholds, no automation

Nothing here decides anything. There is no pass mark, no percentage a wiki has
to reach, and no action taken. A human reads `RISKY:` and `COVERAGE:` and
decides whether to read a page or run `/wikicommit-generate --regenerate`
(Issue #578); that closes the loop by hand, which is the right place for it
until there is real data to set a threshold from. A number invented before the
measurement exists is a guess wearing a decimal point.

## Orphaned records are deliberately not reported

Records outlive their pages by design, so a deleted page leaves a directory
behind. Whether that is worth reporting is a question to answer once real
repositories have accumulated some — reporting it now would add a line to
every run in exchange for nothing anyone has asked for (Issue #750 検討事項 3).

Usage:
    python .wikicommit/scripts/check_review_coverage.py

Exit code: always 0 (informational, non-blocking).
"""

import sys
from pathlib import Path

from _frontmatter import parse_frontmatter, parse_frontmatter_or_warn
from _wikilink import ENTITY_DIR, VIEW_DIR, collect_entity_pages, collect_view_pages
from record_review import (
    REVIEW_DIR,
    RecordError,
    compute_page_content_hash,
    record_dir_for,
    record_sort_key,
)

SOURCE_DIR = Path(".wikicommit/source")


def load_records(page_rel: str) -> list[dict]:
    """Return every review record for a page, oldest first.

    Ordered with `record_sort_key()` rather than by raw filename: the collision
    suffix a same-second record gets (`...-ai-2.md`) sorts *before* the unsuffixed
    name, so plain lexical order would hand back the oldest record of that second
    as the newest.
    """
    directory = record_dir_for(page_rel)
    if not directory.is_dir():
        return []
    records = []
    for record_file in sorted(directory.glob("*.md"), key=record_sort_key):
        fm = parse_frontmatter_or_warn(record_file)
        if fm:
            fm["_file"] = str(record_file)
            records.append(fm)
    return records


def latest_by_kind(records: list[dict], kind: str) -> dict | None:
    """The most recent record of one kind, or None — judged page or not.

    Coverage and the per-page lines all read `standing_review()` instead
    (Issue #766). The one thing left that has to see a discarded record is the
    `discarded` column of `COVERAGE:`, whose whole subject is the attempt that
    was thrown away.
    """
    matching = [r for r in records if r.get("kind") == kind]
    return matching[-1] if matching else None


def standing_review(records: list[dict], kind: str | None = None) -> dict | None:
    """The most recent record that actually judged the page as it now stands.

    A record with an empty `page_content_hash` is `result: discarded` — no page was
    written for it to hash — so it says nothing about the page on disk and is
    skipped here whatever its kind.

    `kind=None` accepts a human record as readily as a machine one. That matters
    for `RISKY:` (Issue #760): `/wikicommit-review` can write `--result fail` with
    findings, so restricting the search to `kind: ai` would drop a human's findings
    on the floor instead of surfacing them.
    """
    for record in reversed(records):
        if kind is not None and record.get("kind") != kind:
            continue
        if str(record.get("page_content_hash") or ""):
            return record
    return None


def standing_verdict(records: list[dict]) -> dict | None:
    """The most recent AI record that actually judged a page that got written.

    A `result: discarded` record carries an empty `page_content_hash`, because no
    page was written for it to hash (`record_review.py`). It therefore says nothing
    about the page now on disk, and must not be the record staleness is measured
    against.

    That distinction is not theoretical. Pass 4 step 5 records a discarded review
    for an `action: update` entity too, and there the pre-existing page *stays* on
    disk untouched while `reviewed_sources` is built from `--sources-from` — the
    source that was being ingested, which is precisely the source the page does not
    carry. Measured against the page, that record reports `source no longer on the
    page` on every run forever, and, by being the newest AI record, it also hides
    the earlier verdict that does still stand behind the page's text.
    """
    return standing_review(records, kind="ai")


def source_identity(entry: dict) -> str | None:
    """The identity a source entry is matched on: its `url` or its `path`.

    Same key `add_source.py` matches registration on (Issue #572 / #573) and
    `check_retracted_sources.py` matches retraction on, so a management file
    written under an older naming rule still lines up.
    """
    for key in ("url", "path"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def source_versions(entries: list) -> dict[str, str]:
    """Map each source entry's identity to the version string that pins it.

    `hash` for a source document, `source_commit` for a `derived_from` entry on
    a view page. One function covers both because the question is the same:
    which version of this evidence was in front of the reviewer.
    """
    versions: dict[str, str] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        identity = source_identity(entry)
        if identity is None:
            continue
        version = entry.get("hash") or entry.get("source_commit") or ""
        versions[identity] = str(version)
    return versions


def page_source_entries(fm: dict) -> list:
    for key in ("sources", "derived_from"):
        value = fm.get(key)
        if isinstance(value, list):
            return value
    return []


def collect_retracted_identities(source_dir: Path = SOURCE_DIR) -> set[str]:
    """Identities of sources a human has retracted (Issue #737)."""
    retracted: set[str] = set()
    if not source_dir.exists():
        return retracted
    for mgmt_file in sorted(source_dir.rglob("*.md")):
        fm = parse_frontmatter_or_warn(mgmt_file)
        if not fm or fm.get("status") != "retracted":
            continue
        source = fm.get("source")
        if isinstance(source, dict):
            identity = source_identity(source)
            if identity:
                retracted.add(identity)
    return retracted


def stale_reasons(page: Path, fm: dict, record: dict) -> list[str]:
    """Why a record's verdict no longer applies to the page as it stands.

    Two independent causes, both reported, because they call for different
    responses: changed text means the review should be re-run, while a changed
    source means the evidence moved and the page itself may need regenerating.
    """
    reasons: list[str] = []

    recorded_hash = str(record.get("page_content_hash") or "")
    if recorded_hash:
        # An empty hash is `result: discarded` — no page was ever written, so
        # there is nothing for it to have diverged from.
        try:
            current_hash = compute_page_content_hash(page)
        except (RecordError, OSError):
            current_hash = ""
        if current_hash and current_hash != recorded_hash:
            reasons.append(f"page content changed since {record.get('reviewed_at', 'the review')}")

    reviewed = source_versions(record.get("reviewed_sources") or [])
    current = source_versions(page_source_entries(fm))
    for identity, version in reviewed.items():
        if identity not in current:
            reasons.append(f"source no longer on the page: {identity}")
        elif version and current[identity] and version != current[identity]:
            reasons.append(f"source changed: {identity}")
    return reasons


def main() -> int:
    if not REVIEW_DIR.exists():
        # Distinguish "no wiki has been reviewed yet" from "everything came back
        # zero": only the first means there was nothing to look at.
        print("SUMMARY: pages=0, ai_reviewed=0, human_reviewed=0, findings=0, models=0")
        print(f"NOTE: {REVIEW_DIR.as_posix()}/ does not exist yet; no reviews have been recorded.")
        return 0

    pages = collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)
    retracted = collect_retracted_identities()

    total = 0
    ai_reviewed = 0
    human_reviewed = 0
    total_findings = 0
    # model -> [pages, findings, pages needing more than one attempt,
    #           pages whose newest AI record is a discarded one this model wrote]
    by_model: dict[str, list[int]] = {}
    unreviewed: list[str] = []
    risky: list[str] = []
    stale: list[str] = []
    retracted_evidence: list[str] = []

    for page in sorted(pages):
        fm, err = parse_frontmatter(page)
        if err or not fm or fm.get("status") == "removed":
            continue
        total += 1
        page_rel = page.as_posix()
        records = load_records(page_rel)

        # The one deliberate exception to the standing rule (Issue #760, kept out
        # of scope by Issue #766): a running tally over the whole history, so a
        # finding a discarded review caught still counts toward what reviewing has
        # caught over this wiki's life.
        total_findings += sum(len(r.get("findings") or []) for r in records)

        # Credited before the `continue` below, because the page this matters most
        # for is the one with nothing but discarded records — the case that used to
        # fall through every line silently.
        newest_ai = latest_by_kind(records, "ai")
        if newest_ai is not None and newest_ai.get("result") == "discarded":
            model = str(newest_ai.get("model") or "(unrecorded)")
            by_model.setdefault(model, [0, 0, 0, 0])[3] += 1

        # Everything below reads the standing record — the newest one that judged
        # the page as it now stands (Issue #766). A page can hold records and still
        # have none standing: every one of them may have been discarded, and a
        # discarded review judged a draft that was thrown away.
        standing_ai = standing_verdict(records)
        standing_any = standing_review(records)
        if standing_any is None:
            # Say which of the two states this is. "No record at all" and "records,
            # but every one discarded" want the same response, but a reader who is
            # told the second exists can go and look at why the reviews kept being
            # thrown away.
            #
            # The reason is read off `result`, not off the empty hash that made the
            # record non-standing: those two coincide for everything
            # `record_review.py` writes, but a record a human wrote by hand — which
            # this tree is explicitly meant to allow (Issue #750) — can simply lack
            # `page_content_hash`, and telling its author it "was discarded" would
            # send them looking for a discarded review that never existed.
            note = ""
            if records:
                if all(r.get("result") == "discarded" for r in records):
                    note = (
                        f" ({len(records)} record(s) exist, but every one was discarded;"
                        " none judged the page as it now stands)"
                    )
                else:
                    note = (
                        f" ({len(records)} record(s) exist, but none carries a"
                        " page_content_hash, so none judged the page as it now stands)"
                    )
            unreviewed.append(f"UNREVIEWED: {page_rel}{note}")
            continue

        if standing_ai is not None:
            ai_reviewed += 1
            model = str(standing_ai.get("model") or "(unrecorded)")
            stats = by_model.setdefault(model, [0, 0, 0, 0])
            stats[0] += 1
            stats[1] += len(standing_ai.get("findings") or [])
            if int(standing_ai.get("attempts") or 1) >= 2:
                stats[2] += 1
        if standing_review(records, kind="human") is not None:
            human_reviewed += 1

        # `RISKY:` reads exactly one record: the newest review that judged the page
        # as it now stands (Issue #760). Summing over the whole history instead —
        # what this did originally — meant a page that was ever retried or ever drew
        # a finding stayed on the list forever, because records are immutable and
        # never deleted (Issue #750). In a wiki that keeps ingesting, the sampling
        # list therefore converged on the whole wiki, and at that point it selects
        # nothing; Issue #562 already recorded what happens to a finding that is
        # always lit.
        #
        # The "it took two rounds to pass" signal Issue #750 called the one most
        # worth having is *not* lost by this: that review is the standing one, and
        # it carries its own `attempts: 2`. It only stops being reported once a
        # later review has judged the current text, which is exactly when it stops
        # describing the page.
        attempts = int(standing_any.get("attempts") or 1)
        standing_findings = len(standing_any.get("findings") or [])
        if attempts >= 2 or standing_findings:
            risky.append(
                f"RISKY: {page_rel} (attempts={attempts}, findings={standing_findings})"
            )

        # Both questions below are about the verdict that stands behind the page's
        # current text, so both read `standing_ai` (`standing_verdict()`) rather
        # than the newest AI record: a discarded review judged a draft that was
        # thrown away.
        if standing_ai is not None:
            for reason in stale_reasons(page, fm, standing_ai):
                stale.append(f"STALE_REVIEW: {page_rel} ({reason})")

            # Issue #750 検討事項 7. `check_retracted_sources.py` already reports
            # pages that still name a retracted source, so repeating that here
            # would be a second copy of the same finding. What only a review
            # record can say is whether the retracted source was *evidence for a
            # verdict* — that the review rested on material since withdrawn,
            # rather than the source merely having been added afterwards.
            for identity in source_versions(standing_ai.get("reviewed_sources") or []):
                if identity in retracted:
                    retracted_evidence.append(
                        f"RETRACTED_EVIDENCE: {page_rel} (the review of"
                        f" {standing_ai.get('reviewed_at', 'this page')} rested on"
                        f" {identity}, since retracted)"
                    )

    print(
        f"SUMMARY: pages={total}, ai_reviewed={ai_reviewed},"
        f" human_reviewed={human_reviewed}, findings={total_findings},"
        f" models={len(by_model)}"
    )
    for model in sorted(by_model):
        page_count, finding_count, retried, discarded = by_model[model]
        # `discarded` is what keeps a quiet `RISKY:` legible rather than
        # contradictory (Issue #766): the first three numbers describe verdicts
        # that stand, this one counts the pages whose newest AI record is a
        # discarded one this model wrote, and so describes nothing on disk. It is
        # keyed on the page's newest AI record, not on this model's own newest —
        # once a later review has judged the current text there is no silent
        # `RISKY:` left to explain, so a superseded discard is not reported.
        print(
            f"COVERAGE: {model} {page_count} pages, {finding_count} findings,"
            f" {retried} pages with attempts>=2, {discarded} discarded"
        )
    for line in unreviewed + risky + stale + retracted_evidence:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
