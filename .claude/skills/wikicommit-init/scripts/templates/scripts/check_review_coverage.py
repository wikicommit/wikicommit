#!/usr/bin/env python3
"""check_review_coverage.py — read the review records back.

Reads what `record_review.py` wrote under `.wikicommit/review/` and reports how
much of the wiki has been reviewed and which pages need a look. Every per-page
line and count reads the *standing* record — the newest one that judged the
page as it now stands (non-empty `page_content_hash`); `SUMMARY: findings=` is
the one cumulative exception.

Usage:
    python .wikicommit/scripts/check_review_coverage.py
    python .wikicommit/scripts/check_review_coverage.py --discarded-reason <page>...

Output (default mode):
    SUMMARY: pages=<N>, ai_reviewed=<N>, human_reviewed=<N>, human_notes=<N>, findings=<N>, models=<N>
    COVERAGE: <model> <N> pages, <N> findings, <N> pages with attempts>=2, <N> discarded
    UNREVIEWED: <page> [(<why no record stands>)]
    RISKY: <page> (attempts=<N>, findings=<N>)
    STALE_REVIEW: <page> (<reason>)
    RETRACTED_EVIDENCE: <page> (the review of <date> rested on <source>, since retracted)
    WARNING: <record file>: <why it could not be read>
    NOTE: .wikicommit/review/ does not exist yet; no reviews have been recorded.

Output (`--discarded-reason`): `REASON:` with indented findings, `NO_RECORD:`,
`ERROR:` for a path outside the page trees, and `SUMMARY: pages=, with_reason=`.

Exit code: always 0 (informational, non-blocking).

The full specification is the `check_review_coverage.py` section of the
WikiCommit script specification (ScriptSpec).
"""

import argparse
import sys
from functools import lru_cache
from pathlib import Path

import yaml

from _frontmatter import (
    parse_frontmatter,
    parse_frontmatter_and_body_text,
    parse_frontmatter_or_warn,
)
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    collect_view_pages,
    retarget_wikilink,
)
from record_review import (
    ACCEPTED_PREFIXES,
    REVIEW_DIR,
    RecordError,
    compute_content_hash,
    compute_page_content_hash,
    page_evidence_entries,
    record_dir_for,
    record_sort_key,
)

SOURCE_DIR = Path(".wikicommit/source")
RELATIONS_FILE = Path(".wikicommit/relations.yml")


def load_records(page_rel: str) -> list[dict]:
    """Return every review record for a page, oldest first.

    Ordered with `record_sort_key()` rather than by raw filename: the collision
    suffix a same-second record gets (`...-ai-2.md`) sorts *before* the unsuffixed
    name, so plain lexical order would hand back the oldest record of that second
    as the newest.

    Each record is read **once**, frontmatter and body together, because
    `human_notes` needs the body: a second read could fail where the first
    succeeded and silently undercount. The warning text matches
    `parse_frontmatter_or_warn()`'s.
    """
    directory = record_dir_for(page_rel)
    if not directory.is_dir():
        return []
    records = []
    for record_file in sorted(directory.glob("*.md"), key=record_sort_key):
        try:
            text = record_file.read_text(encoding="utf-8-sig")
        except OSError as e:
            print(f"WARNING: {record_file}: could not be read: {e}")
            continue
        fm, err, body = parse_frontmatter_and_body_text(text)
        if err:
            print(f"WARNING: {record_file}: {err}")
            continue
        if fm:
            fm["_file"] = str(record_file)
            if fm.get("kind") == "human":
                # Only `kind: human`: an AI body holds Pass 4's observations,
                # not a trace of a person having read the page.
                fm["_body"] = body.strip()
            records.append(fm)
    return records


def latest_by_kind(records: list[dict], kind: str) -> dict | None:
    """The most recent record of one kind, or None — judged page or not.

    Coverage and the per-page lines all read `standing_review()` instead. Only
    the `discarded` column of `COVERAGE:` has to see a discarded record.
    """
    matching = [r for r in records if r.get("kind") == kind]
    return matching[-1] if matching else None


def standing_review(records: list[dict], kind: str | None = None) -> dict | None:
    """The most recent record that actually judged the page as it now stands.

    A record with an empty `page_content_hash` is `result: discarded` — no page was
    written for it to hash — so it says nothing about the page on disk and is
    skipped here whatever its kind.

    `kind=None` accepts a human record as readily as a machine one, so `RISKY:`
    surfaces a human's `--result fail` findings too.
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

    For an `action: update` entity the old page stays on disk while the
    discarded record's `reviewed_sources` names the source being ingested, so
    measuring against it would report `source no longer on the page` forever and
    hide the verdict that still stands.
    """
    return standing_review(records, kind="ai")


def source_identity(entry: dict) -> str | None:
    """The identity a source entry is matched on: its `url` or its `path`.

    Same key `add_source.py` matches registration on and
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
    # The same function record_review.py snapshots with, so a translation's
    # `translated_from` / `source_commit` is compared like any other evidence
    # entry instead of reading as "no longer on the page".
    return page_evidence_entries(fm)


def collect_retracted_identities(source_dir: Path = SOURCE_DIR) -> set[str]:
    """Identities of sources a human has retracted."""
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


@lru_cache(maxsize=4)
def _relation_items(path: str, mtime_ns: int) -> tuple[dict, ...]:
    """The mapping items of `relations.yml`, read once per file version.

    Shared by `merge_pairs()` and `rename_predecessors()`, which both read the
    same file on every page. An unreadable or malformed file gives no items.
    """
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(item for item in data if isinstance(item, dict))


@lru_cache(maxsize=4)
def _merge_pairs_cached(path: str, mtime_ns: int) -> tuple[tuple[str, str], ...]:
    direct: dict[str, set[str]] = {}
    for item in _relation_items(path, mtime_ns):
        into = item.get("merged_into")
        pages = item.get("pages")
        if not isinstance(into, str) or not isinstance(pages, list):
            continue
        for old in pages:
            if isinstance(old, str) and old != into:
                direct.setdefault(old, set()).add(into)
    # A chain (A merged into B, later B into C) leaves a page that linked to A
    # linking to C, so A is paired with every page down its chain: a review
    # written before either merge matches with C put back to A, one written
    # between them with C put back to B (that pair comes from B's own chain).
    pairs: set[tuple[str, str]] = set()
    for old in direct:
        seen = {old}
        frontier = list(direct[old])
        while frontier:
            new = frontier.pop()
            if new in seen:
                continue
            seen.add(new)
            pairs.add((old, new))
            frontier.extend(direct.get(new, ()))
    return tuple(sorted(pairs))


def merge_pairs(relations_file: Path = RELATIONS_FILE) -> tuple[tuple[str, str], ...]:
    """(absorbed Type/slug, Type/slug its links now name) for every recorded merge.

    Read from the `same` items `merge_pages.py record` writes to `relations.yml`
    (`pages` plus `merged_into`). An unreadable or missing file gives no pairs,
    which only means no rewrite is forgiven — the check falls back to plain
    hash comparison.
    """
    try:
        mtime_ns = relations_file.stat().st_mtime_ns
    except OSError:
        return ()
    return _merge_pairs_cached(str(relations_file), mtime_ns)


@lru_cache(maxsize=4)
def _rename_predecessors_cached(path: str, mtime_ns: int) -> dict[str, tuple[str, ...]]:
    direct: dict[str, list[str]] = {}
    for item in _relation_items(path, mtime_ns):
        if not item.get("renamed_at"):
            continue
        into = item.get("merged_into")
        pages = item.get("pages")
        if not isinstance(into, str) or not isinstance(pages, list):
            continue
        for old in pages:
            if isinstance(old, str) and old != into and old not in direct.setdefault(into, []):
                direct[into].append(old)
    # A page renamed twice (A to B, later B to C) reads both A's and B's records.
    result: dict[str, tuple[str, ...]] = {}
    for new in direct:
        seen = {new}
        order: list[str] = []
        frontier = list(direct[new])
        while frontier:
            old = frontier.pop(0)
            if old in seen:
                continue
            seen.add(old)
            order.append(old)
            frontier.extend(direct.get(old, ()))
        result[new] = tuple(order)
    return result


def rename_predecessors(relations_file: Path = RELATIONS_FILE) -> dict[str, tuple[str, ...]]:
    """Type/slug -> every earlier Type/slug it was renamed from, nearest first.

    Read from the items `rename_page.py apply` appends (`relation: same` with
    `merged_into` and `renamed_at`). A plain merge item has no `renamed_at` and is
    not followed: the kept page was regenerated, so Pass 4 recorded it anew.
    """
    try:
        mtime_ns = relations_file.stat().st_mtime_ns
    except OSError:
        return {}
    return _rename_predecessors_cached(str(relations_file), mtime_ns)


def load_page_records(page_rel: str) -> list[dict]:
    """`load_records()` plus the records left under the slugs the page was renamed from.

    The records stay where they were written (they name the page they judged), so
    a renamed page would otherwise have none and read as `UNREVIEWED:` although
    Pass 4 checked its text. Each inherited record carries
    `_renamed_from` (the old Type/slug) so a staleness line can say why the text
    differs. Only `kind: ai` records are inherited: the rename withdraws a
    person's sign-off. Only entity pages are renamed; a view page reads its own
    directory.
    """
    records = load_records(page_rel)
    prefix = ENTITY_DIR.as_posix() + "/"
    if not page_rel.startswith(prefix):
        return records
    parts = page_rel[len(prefix):].split("/")
    if len(parts) != 3 or not parts[2].endswith(".md"):
        return records
    lang, type_name, slug = parts[0], parts[1], parts[2][: -len(".md")]
    olds = rename_predecessors().get(f"{type_name}/{slug}")
    if not olds:
        return records
    inherited: list[dict] = []
    # Oldest slug first, so a tie in `record_sort_key()` keeps the earlier record earlier.
    for old in reversed(olds):
        for record in load_records(f"{prefix}{lang}/{old}.md"):
            # Only the machine's checks carry over. A human record is a person's
            # sign-off on the text they read under the old title, which
            # `rename_page.py` withdraws (`review_status: pending`); inheriting it
            # would count the renamed page as human-reviewed.
            if record.get("kind") != "ai":
                continue
            record["_renamed_from"] = old
            inherited.append(record)
    return sorted(inherited + records, key=lambda r: record_sort_key(Path(r["_file"])))


def _undo_rewrite(text: str, old: str, new: str) -> str:
    # Mirrors rewrite_merged_links.py's swap(), which keeps the display text of
    # `[[Type/slug|表示名]]` and changes only the target.
    return WIKILINK_RE.sub(
        lambda m: retarget_wikilink(m, old) if f"{m.group(1)}/{m.group(2)}" == new else m.group(0), text
    )


def matches_recorded_content(page: Path, recorded_hash: str) -> bool:
    """Whether the page still holds the text a record with `recorded_hash` judged.

    Besides the page as it stands, it accepts the page with one merge's link
    rewrite undone: `rewrite_merged_links.py` turns `[[Type/old]]` into
    `[[Type/new]]` after a person decided the two are the same concept, and the
    claim around the link did not change. Each merge is tried as one full
    replacement of `[[new]]` by `[[old]]` — partial replacements are not tried,
    so a page that already linked to both before the merge still reads as
    changed. Raises `RecordError` / `OSError` when the page cannot be hashed.
    """
    if compute_page_content_hash(page) == recorded_hash:
        return True
    pairs = merge_pairs()
    if not pairs:
        return False
    text = page.read_text(encoding="utf-8-sig")
    for old, new in pairs:
        variant = _undo_rewrite(text, old, new)
        if variant != text and compute_content_hash(variant, page) == recorded_hash:
            return True
    return False


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
            changed = not matches_recorded_content(page, recorded_hash)
        except (RecordError, OSError):
            changed = False
        if changed:
            reason = f"page content changed since {record.get('reviewed_at', 'the review')}"
            renamed_from = record.get("_renamed_from")
            if renamed_from:
                # The usual cause is the rename's own title change; say so, so the
                # line is not read as an edit someone has to go and find.
                reason += f"; the review was of {renamed_from}, before the rename"
            reasons.append(reason)

    reviewed = source_versions(record.get("reviewed_sources") or [])
    current = source_versions(page_source_entries(fm))
    for identity, version in reviewed.items():
        if identity not in current:
            reasons.append(f"source no longer on the page: {identity}")
        elif version and current[identity] and version != current[identity]:
            reasons.append(f"source changed: {identity}")
    return reasons


def latest_discarded(records: list[dict]) -> dict | None:
    """The newest record whose page was never written, or None.

    `standing_review()` deliberately skips these — a discarded record judged a
    draft that no longer exists on disk. That is exactly what is wanted here:
    a page listed in `failed_pages` was never written, so the discarded record
    is the only thing that says why.
    """
    for record in reversed(records):
        if record.get("result") == "discarded":
            return record
    return None


def _one_line(value: object) -> str:
    """Collapse a finding's free text onto one line.

    Every line this mode prints is one record, so an embedded newline would
    split it in two and a caller reading line by line would take the second
    half for a separate finding.
    """
    return " ".join(str(value).split())


def _where(finding: dict) -> str:
    """Say what `source_lines` counts lines in, or nothing if it has none.

    `source_file` itself is never printed: for a source document it holds a path
    under `.wikicommit/.cache/`, which is gitignored and machine-local, so it
    means nothing in another clone or after the cache is cleared. Which *kind* of
    file it names is decided as Pass 4 check 8 does — a path inside the entity or
    view tree is another page, anything else is the source text.
    """
    lines = finding.get("source_lines")
    if not lines:
        return ""
    source_file = str(finding.get("source_file") or "")
    # `ACCEPTED_PREFIXES` includes the legacy `.wikicommit/wiki/` prefix.
    if source_file.startswith(ACCEPTED_PREFIXES):
        return f" at lines {_one_line(lines)} of another page"
    return f" at lines {_one_line(lines)} of the extracted source text"


def print_discarded_reasons(page_rels: list[str]) -> int:
    """Print why each page was discarded, for `/wikicommit-merge` Step 9.

    The management file's `## Failure Reason` section is deleted on the `partial`
    branch, the ordinary shape of a failure, so the reason has to come from the
    `result: discarded` review record the same run wrote.

    `NO_RECORD:` says the record tree holds nothing for this page (a failure
    from before the tree existed, or no `.wikicommit/review/`) — "no reason was
    recorded", which is not the same as "reason unknown".
    """
    with_reason = 0
    for page_rel in page_rels:
        if not page_rel.startswith(ACCEPTED_PREFIXES):
            # Same contract as `record_review.py` and
            # `reset_review_on_content_change.py`: a path outside the two page trees
            # is a caller error and must not come back as `NO_RECORD:`, which Step 9
            # would write into an Issue as "no reason was recorded". It cannot simply
            # be passed through either: `record_dir_for()` strips the `.wikicommit/`
            # prefix *by length*, so a path that does not carry it resolves to a
            # silently wrong directory, and one shorter than the prefix raises.
            print(
                f"ERROR: {page_rel}: expected a page under"
                f" {ENTITY_DIR.as_posix()}/ or {VIEW_DIR.as_posix()}/"
            )
            continue
        try:
            records = load_records(page_rel)
        except (RecordError, OSError, ValueError) as err:
            # Still exit 0 with the other pages reported: one malformed
            # `failed_pages` entry must not cost the whole Issue its reason.
            print(f"WARNING: {page_rel}: {err}", file=sys.stderr)
            print(f"NO_RECORD: {page_rel}")
            continue
        record = latest_discarded(records)
        if record is None:
            print(f"NO_RECORD: {page_rel}")
            continue
        with_reason += 1
        reviewed_at = record.get("reviewed_at") or "unknown date"
        attempts = record.get("attempts") or 1
        print(f"REASON: {page_rel} (recorded {reviewed_at}, attempts={attempts})")
        findings = record.get("findings")
        if not isinstance(findings, list) or not findings:
            # A discarded record with no findings still dates the discard, which
            # is more than `unknown` said.
            print("  (the record names no finding)")
            continue
        # A discarded record holds every round flattened together, and each round
        # can raise a different defect; without the round number three attempts
        # read as three simultaneous problems. Single-round records omit it.
        rounds = {f.get("round", 1) for f in findings if isinstance(f, dict)}
        multi_round = len(rounds) > 1
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            kind = _one_line(finding.get("type") or "FINDING")
            instruction = _one_line(finding.get("instruction") or "(no instruction recorded)")
            prefix = f"round {_one_line(finding.get('round', 1))} " if multi_round else ""
            print(f"  {prefix}{kind}{_where(finding)}: {instruction}")
    print(f"SUMMARY: pages={len(page_rels)}, with_reason={with_reason}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report review coverage across the wiki's pages."
    )
    parser.add_argument(
        "--discarded-reason",
        dest="discarded_reason",
        metavar="<page>",
        # `*` rather than `+`: for a source that failed in Pass 1 `failed_pages` is
        # empty and the flag arrives with no values. `+` would exit 2, which the
        # caller cannot tell from "no such mode"; the real answer is `pages=0`.
        nargs="*",
        help=(
            "Print why each named page was discarded, taken from the newest "
            "`result: discarded` review record, and stop without scanning "
            "anything else. Used by /wikicommit-merge Step 9, whose only other "
            "source of a reason is deleted on the `partial` branch."
        ),
    )
    args = parser.parse_args()

    # `is not None`, not truthiness: with `nargs="*"` an empty list means the flag
    # was given with no pages, which selects this mode just as much as a full list
    # does. Falling through to the default full scan there would answer a different
    # question than the one that was asked.
    if args.discarded_reason is not None:
        return print_discarded_reasons(args.discarded_reason)

    if not REVIEW_DIR.exists():
        # Distinguish "no wiki has been reviewed yet" from "everything came back
        # zero": only the first means there was nothing to look at.
        print(
            "SUMMARY: pages=0, ai_reviewed=0, human_reviewed=0, human_notes=0,"
            " findings=0, models=0"
        )
        print(f"NOTE: {REVIEW_DIR.as_posix()}/ does not exist yet; no reviews have been recorded.")
        return 0

    pages = collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)
    retracted = collect_retracted_identities()

    total = 0
    ai_reviewed = 0
    human_reviewed = 0
    human_notes = 0
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
        records = load_page_records(page_rel)

        # The one deliberate exception to the standing rule: a running tally over
        # the whole history, discarded reviews included.
        total_findings += sum(len(r.get("findings") or []) for r in records)

        # Credited before the `continue` below, because the page this matters most
        # for is the one with nothing but discarded records.
        newest_ai = latest_by_kind(records, "ai")
        if newest_ai is not None and newest_ai.get("result") == "discarded":
            model = str(newest_ai.get("model") or "(unrecorded)")
            by_model.setdefault(model, [0, 0, 0, 0])[3] += 1

        # Everything below reads the standing record — the newest one that judged
        # the page as it now stands. A page can hold records and still
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
            # The reason is read off `result`, not off the empty hash: a record a
            # human wrote by hand can lack `page_content_hash` without having been
            # discarded.
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
        standing_human = standing_review(records, kind="human")
        if standing_human is not None:
            human_reviewed += 1
            # The note is the only trace that the page was read rather than just
            # closed. Presence, not content: a one-word note counts as one.
            if standing_human.get("_body"):
                human_notes += 1

        # `RISKY:` reads exactly one record, the standing one. Summing over the
        # immutable history would keep every page that was ever retried on the
        # list forever, until it selects nothing. A page that passed on round two
        # still shows: its standing record carries `attempts: 2`.
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

            # `check_retracted_sources.py` already reports pages that still name a
            # retracted source. What only a review
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
        f" human_reviewed={human_reviewed}, human_notes={human_notes},"
        f" findings={total_findings}, models={len(by_model)}"
    )
    for model in sorted(by_model):
        page_count, finding_count, retried, discarded = by_model[model]
        # `discarded` is what keeps a quiet `RISKY:` legible rather than
        # contradictory: the first three numbers describe verdicts
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
