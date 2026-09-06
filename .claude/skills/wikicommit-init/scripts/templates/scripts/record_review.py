#!/usr/bin/env python3
"""record_review.py — persist one review verdict as an immutable record (Issue #750).

`wikicommit-generate` Pass 4 runs eight distinct checks over every page it
generates — evidence binding (Issue #442), granular fact verification and
naming-vs-inventing (Issue #451), secondary citations (Issue #473),
attribution correctness and unattributed single-source formulations (Issue
#429), source-vs-source disagreement and one-hop cross-page contradiction
(Issue #566) — and then throws the verdict away. Pass 4 step 1 says so in as
many words: the agent-to-agent JSON is "never written to disk or Git".

The consequence is that a page which passed cleanly on the first attempt and a
page that was caught hallucinating and only passed on the second look are
byte-identical on disk. The only thing that survives is `failed_pages`, which
records the reviews that *could not* be salvaged — not the ones that worked.

Four things follow from that, and this script exists to stop all four:

- `## Failure Reason` already admits the gap in its own prescribed wording
  ("that detail is agent-to-agent only and is not persisted here").
- `/wikicommit-fix` silently invalidates the AI review. It rewrites a page's
  prose and `reset_review_on_content_change.py` sends `review_status` back to
  `pending` (Issue #724) — but the machine-side verdict, made against the old
  text, was never recorded, so nothing can notice it has gone stale.
- Risk-based sampling has no input. How many retries a page took and what was
  found in them is precisely the blueprint for deciding which pages a human
  should read, and it evaporated when the run ended.
- Bias cannot be measured, and measurement cannot be built retroactively: a
  period with no records is permanently blank.

## One review is one file, and files are never edited

The record for a page lives in a per-page directory and each review writes a
new file into it:

    .wikicommit/review/entity/ja/Person/yamada-taro/
    ├── 20260905-142233-ai.md      generate Pass 4
    ├── 20260907-091510-ai.md      wikicommit-review, a different model
    └── 20260908-103302-human.md   a human

Create-only beats appending to one file per page on four counts. There is no
read-modify-write, so the round-trip that cost this repository a config file's
worth of comments (Issue #713) cannot happen here. Git merges are trivial
because two branches adding two reviews add two different files. Several
reviewers over one page — the shape a multi-perspective review takes — is
expressed by construction. And a human can read and write these, which
calibration requires: comparing human findings against machine findings means
a human has to be able to read the machine's.

The filename is `<YYYYMMDD>-<HHMMSS>-<kind>.md`, following the existing
`wikicommit/merge-<YYYYMMDD>-<HHMMSS>` branch convention. **The model ID is
deliberately not in the filename**: a runtime reports itself as e.g.
`claude-opus-5[1m]` (Issue #559 saw that exact spelling in real page data) and
square brackets are glob metacharacters.

Records outlive their pages. A deleted page keeps its review history, so this
tree is not a strict mirror of the wiki, and a directory is created for a page
that was never written at all (`result: discarded`) — that being the single
most valuable record here, it is the design rather than an edge case.

## The frontmatter is the record; the body is for prose

Findings go in frontmatter, not in the body. Putting them in the body would
force the aggregation script to parse prose, which is the failure mode Issue
#474 named. The body is for what has no structured home: a human's one-line
observation, an Issue close comment.

`source_quote` is dropped even when the caller passes it. It is verbatim
source text, and systematically accumulating excerpts across a whole wiki is a
different act from quoting one in a page — this project already treats a
source's terms as a matter of fact rather than assumption (`sources[].license`,
Issue #558 / #570), and the same reasoning applies to its own records.
`source_file` plus `source_lines` is enough to go back and look. Dropping it
here rather than in the calling instructions means the guarantee does not
depend on an agent following prose, and it also removes the only path by which
raw source text could enter these records at all — shrinking both the
prompt-injection surface and the file size.

`page_content_hash` uses **the same six-field ignore list** as
`reset_review_on_content_change.py`, imported rather than restated. That is
what makes "is this verdict still valid for the page as it stands?" a
deterministic question, which calibration needs to ask. It is empty for
`result: discarded`, where the page was never written and no hash exists;
an empty hash means exactly that, and staleness checks skip it.

`reviewed_sources` records the source versions the review actually saw, in
full rather than as a digest. The reason it must be a full list is
`check_ingest_freshness.py`, which does not monitor `type: url` sources at all
(URL freshness is re-checked only by re-running `/wikicommit-generate <url>`) —
for a URL source, this record is the only place in the repository that captures which version was in front of a
reviewer. A view page records its `derived_from` entries in the same slot.

`findings` holds **every round**, flat, each tagged with `round:`. Pass 4
retries up to `generate.max_retries` and each round can turn up a different
defect (Issue #571 saw three rounds find three different problems); recording
only the last round would give a page that failed once and was fixed an empty
`findings` list, erasing the one signal most worth having. Flat rather than
nested because every aggregation — totals, counts by `type`, the highest round
reached — is then a single filter. `attempts` is stated separately because it
cannot be recovered from `max(round)` when the final round found nothing.

## Relationship to the agent-to-agent review JSON

That JSON stays agent-to-agent, and stays free to gain fields. What is
persisted is a **projection** of it, and that projection is a compatibility
surface. Do not read "this format may change freely" onto this file (Issue
#750).

Usage:
    python .wikicommit/scripts/record_review.py <page> \\
        --kind ai --stage generate-pass4 \\
        --model "<runtime-reported model id>" \\
        --attempts 2 --result pass \\
        [--skill-blob <hash>] [--reviewer <login>] \\
        [--note <text> | --note-file <path>] \\
        [--sources-from <source management file>]... \\
        [--json <path>|-]

    <page> is a page under `.wikicommit/entity/` or `.wikicommit/view/`. It
    does not have to exist on disk: `result: discarded` is exactly the case
    where it does not.

Exit code:
    0 = a record was written
    1 = bad arguments, a page outside the two trees, unreadable/malformed
        JSON, or the record could not be written
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter, parse_frontmatter_and_body_text
from _version import get_version
from _wikilink import ENTITY_DIR, LEGACY_ENTITY_PREFIX, VIEW_DIR
from reset_review_on_content_change import BOOKKEEPING_FIELDS

REVIEW_DIR = Path(".wikicommit/review")

KINDS = ("ai", "human")

# Which caller produced the record. Every value here is a real call site; a new one
# has to be added deliberately rather than passed as free text, because
# check_review_coverage.py groups by it.
STAGES = ("generate-pass4", "review-skill", "synthesize-step5.5", "issue-close")

# `pass` / `fail` are the subagent's own verdict. `discarded` is the outcome Pass 4
# step 5 reaches when the retry budget runs out: the page was never written, which is
# why it is a third value rather than a flavour of `fail`.
RESULTS = ("pass", "fail", "discarded")

FINDING_TYPES = ("HALLUCINATION", "CONTRADICTION", "MISSING_SOURCE")

# Projected from §4.6's issue entries, in this order. `source_quote` is absent by
# design (see the module docstring); anything else §4.6 grows later is dropped here
# until it is added deliberately.
FINDING_FIELDS = (
    "round",
    "type",
    "claim",
    "source_file",
    "source_lines",
    "instruction",
    "page_at_fault",
)

ACCEPTED_PREFIXES = (
    f"{ENTITY_DIR.as_posix()}/",
    f"{VIEW_DIR.as_posix()}/",
    LEGACY_ENTITY_PREFIX,
)


class RecordError(Exception):
    """A condition the caller has to fix; main() turns it into an ERROR line."""


def _repo_relative(raw: str) -> str:
    """Normalize an argument into a repository-relative POSIX path.

    Same contract as `reset_review_on_content_change.py`: these scripts run with the
    repository root as cwd, so only an absolute path needs rebasing.
    """
    path = Path(raw)
    if path.is_absolute():
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def record_dir_for(page_rel: str) -> Path:
    """Map a page path to the directory its review records live in.

    `.wikicommit/entity/ja/Person/x.md` -> `.wikicommit/review/entity/ja/Person/x`
    `.wikicommit/view/ja/agent-loop.md` -> `.wikicommit/review/view/ja/agent-loop`

    The `.wikicommit/` prefix is stripped and the `.md` suffix dropped, so the two
    trees stay distinguishable under one root and a page name can never collide with
    a directory of another tree.

    A page still on the pre-Issue-#477 `.wikicommit/wiki/` prefix is filed under
    `entity/` rather than a third `wiki/` subtree: the record is about the page, and
    a repository that later runs `git mv` should not end up with its history split
    across two directories.
    """
    rel = page_rel
    if rel.startswith(LEGACY_ENTITY_PREFIX):
        rel = ENTITY_DIR.as_posix() + "/" + rel[len(LEGACY_ENTITY_PREFIX):]
    without_root = rel[len(".wikicommit/"):]
    return REVIEW_DIR / Path(without_root).with_suffix("")


def compute_page_content_hash(page_path: Path) -> str:
    """Hash a page's content, ignoring the six bookkeeping fields.

    Shares `BOOKKEEPING_FIELDS` with `reset_review_on_content_change.py` rather than
    restating the list, because the two answer the same question from opposite ends:
    that script asks whether a page changed since a human signed off, this one
    records the state a reviewer saw so the same question can be asked later. Two
    copies of the list would drift, and the drift would show up as records that
    quietly report the wrong staleness.

    The serialization is `yaml.safe_dump` with sorted keys followed by the body
    normalized the same way that script normalizes it, so the digest depends on the
    values rather than on key order or line endings.
    """
    text = page_path.read_text(encoding="utf-8-sig")
    fm, err, body = parse_frontmatter_and_body_text(text)
    if err:
        raise RecordError(f"{page_path}: {err}")
    content_fields = {k: v for k, v in (fm or {}).items() if k not in BOOKKEEPING_FIELDS}
    canonical = yaml.safe_dump(
        content_fields, sort_keys=True, allow_unicode=True, default_flow_style=False
    )
    canonical += "\n" + body.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reviewed_sources_for(page_path: Path) -> list[dict]:
    """Snapshot the sources a review of this page had in front of it.

    An entity page contributes its `sources[]` verbatim; a view page contributes its
    `derived_from` entries, which occupy the same slot for a page whose evidence is
    other pages rather than external documents.

    This duplicates the page's own frontmatter at the moment of writing, and that is
    the point: the page's copy is the current value, this one is the value at review
    time — the same relationship a translation page's `source_commit` has to its
    original.
    """
    fm, err = parse_frontmatter(page_path)
    if err or not fm:
        return []
    for key in ("sources", "derived_from"):
        value = fm.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    return []


def sources_from_management_files(paths: list[str]) -> list[dict]:
    """Build `reviewed_sources` from source management files.

    Only used when the page itself is not on disk — `result: discarded` is the case
    that matters. Without this a discarded page's record, the most valuable kind,
    would say nothing about which source versions produced it, and there is no page
    left to read them off.
    """
    entries: list[dict] = []
    for raw in paths:
        mgmt = Path(_repo_relative(raw))
        fm, err = parse_frontmatter(mgmt)
        if err or not fm:
            print(f"WARNING: {raw}: could not read source management file; skipped", file=sys.stderr)
            continue
        source = fm.get("source")
        if isinstance(source, dict):
            entries.append(dict(source))
    return entries


def project_findings(payload: dict) -> list[dict]:
    """Project §4.6's `issues` array into the persisted `findings` list.

    Fields outside `FINDING_FIELDS` are dropped — `source_quote` above all, which is
    dropped here rather than left to the caller so that the guarantee does not rest
    on an agent following an instruction.

    A `round` the caller did not set defaults to 1. Pass 4 hands one review round at
    a time, so a caller recording a single round has nothing to say about it, while
    one recording several must number them.
    """
    issues = payload.get("issues")
    if issues is None:
        return []
    if not isinstance(issues, list):
        raise RecordError("`issues` must be a list")

    findings = []
    for i, issue in enumerate(issues):
        if not isinstance(issue, dict):
            raise RecordError(f"issues[{i}] must be a mapping")
        finding = {}
        for field in FINDING_FIELDS:
            if field == "round":
                finding["round"] = issue.get("round", 1)
                continue
            value = issue.get(field)
            # Keep empty strings that carry meaning: synthesize's MISSING_SOURCE
            # deliberately leaves `source_file` empty (Issue #674), and dropping the
            # key would make that indistinguishable from a caller that forgot it.
            if value is None:
                continue
            finding[field] = value
        f_type = finding.get("type")
        if f_type is not None and f_type not in FINDING_TYPES:
            print(
                f"WARNING: issues[{i}]: unknown type {f_type!r}"
                f" (expected one of {', '.join(FINDING_TYPES)}); recorded as-is",
                file=sys.stderr,
            )
        findings.append(finding)
    return findings


def load_payload(spec: str | None) -> dict:
    """Read the §4.6 JSON from a path or stdin (`-`). Absent means no findings."""
    if spec is None:
        return {}
    try:
        raw = sys.stdin.read() if spec == "-" else Path(spec).read_text(encoding="utf-8")
    except OSError as e:
        raise RecordError(f"could not read --json {spec}: {e}") from e
    raw = raw.strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RecordError(f"--json {spec} is not valid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise RecordError("--json payload must be a JSON object")
    return payload


def record_sort_key(path: Path) -> tuple[str, int]:
    """Order records chronologically.

    The filename is `<YYYYMMDD>-<HHMMSS>-<kind>[-<n>].md`, and both time components
    are zero-padded and fixed-width, so plain lexical order over the name would be
    chronological — except for the collision suffix. `...-ai-2.md` sorts *before*
    `...-ai.md` because `-` precedes `.`, which would make a reader taking the last
    filename pick the oldest record of that second rather than the newest.

    Rather than change the documented filename, both sides share this key: the
    writer to allocate, `check_review_coverage.py` to decide which record is
    current. An unexpected name (a hand-written file) sorts last on its own name,
    which keeps it visible instead of silently reordering the real records.
    """
    stem = path.stem
    parts = stem.split("-")
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
        seq = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1
        return (f"{parts[0]}-{parts[1]}", seq)
    return (stem, 0)


def allocate_record_path(directory: Path, stamp: str, kind: str) -> Path:
    """Pick a filename inside `directory`, never overwriting an existing record.

    A same-second collision is close to impossible in practice — Pass 4 runs
    sequentially with an LLM call between pages — but "close to impossible" is not a
    behaviour, so the second record in a second gets `-2`, and so on. Overwriting is
    never an option: these files are immutable by contract.

    That suffix is why `record_sort_key()` exists: it does not sort lexically after
    the unsuffixed name.
    """
    candidate = directory / f"{stamp}-{kind}.md"
    if not candidate.exists():
        return candidate
    for n in range(2, 1000):
        candidate = directory / f"{stamp}-{kind}-{n}.md"
        if not candidate.exists():
            return candidate
    raise RecordError(f"{directory}: could not allocate a record filename for {stamp}-{kind}")


def build_record(args, payload: dict, page_path: Path, page_rel: str) -> tuple[dict, list[dict]]:
    """Assemble the record's frontmatter mapping and its findings."""
    findings = project_findings(payload)

    page_exists = page_path.is_file()
    if args.result == "discarded":
        # No page was written, so there is no content to hash. An empty hash means
        # exactly that, and check_review_coverage.py skips staleness on it.
        content_hash = ""
    elif page_exists:
        content_hash = compute_page_content_hash(page_path)
    else:
        raise RecordError(
            f"{page_rel}: page does not exist on disk"
            f" (only --result discarded may name a page that was never written)"
        )

    if args.sources_from:
        reviewed_sources = sources_from_management_files(args.sources_from)
    elif page_exists:
        reviewed_sources = reviewed_sources_for(page_path)
    else:
        reviewed_sources = []

    record: dict = {
        "page": page_rel,
        "kind": args.kind,
        "stage": args.stage,
    }
    # Only the field that applies to this kind is written. Shipping the other one
    # empty would leave a key that is permanently empty on every record of that kind —
    # the shape Issue #553 rules out.
    if args.kind == "ai":
        record["model"] = args.model
    elif args.reviewer:
        record["reviewer"] = args.reviewer

    record["reviewed_at"] = args.reviewed_at or datetime.now().strftime("%Y-%m-%d")
    if args.skill_blob:
        # Absent for `stage: issue-close`, where the reviewer is a human and no
        # SKILL.md governed the judgment (Issue #750 検討事項 5).
        record["skill_blob"] = args.skill_blob
    record["wikicommit_version"] = get_version()
    record["page_content_hash"] = content_hash
    record["reviewed_sources"] = reviewed_sources
    record["attempts"] = args.attempts
    record["result"] = args.result
    record["findings"] = findings
    return record, findings


def write_record(record: dict, body: str, directory: Path, stamp: str, kind: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = allocate_record_path(directory, stamp, kind)
    front = yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False)
    text = f"---\n{front}---\n"
    if body.strip():
        text += f"\n{body.strip()}\n"
    path.write_text(text, encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist one review verdict as an immutable record (Issue #750)."
    )
    parser.add_argument("page", help="page under .wikicommit/entity/ or .wikicommit/view/")
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--model", default="", help="runtime-reported model ID (--kind ai)")
    parser.add_argument("--reviewer", default="", help="GitHub login (--kind human)")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--result", required=True, choices=RESULTS)
    parser.add_argument("--skill-blob", default="", help="blob hash of the review instructions")
    parser.add_argument("--json", dest="json_spec", default=None, help="§4.6 JSON path, or - for stdin")
    parser.add_argument("--note", default="", help="prose body")
    parser.add_argument("--note-file", default=None, help="read the prose body from a file")
    parser.add_argument("--sources-from", action="append", default=[], metavar="MGMT",
                        help="source management file to take reviewed_sources from")
    parser.add_argument("--reviewed-at", default="", help="override the record date (tests)")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    try:
        page_rel = _repo_relative(args.page)
        if not page_rel.startswith(ACCEPTED_PREFIXES):
            raise RecordError(
                f"{args.page}: expected a page under {ENTITY_DIR.as_posix()}/ or"
                f" {VIEW_DIR.as_posix()}/"
            )
        if args.kind == "ai" and not args.model:
            # A record whose verdict cannot be attributed to a model is not usable
            # for the bias measurement this tree exists to make possible.
            raise RecordError("--kind ai requires --model")

        payload = load_payload(args.json_spec)

        body = args.note
        if args.note_file:
            try:
                body = Path(args.note_file).read_text(encoding="utf-8")
            except OSError as e:
                raise RecordError(f"could not read --note-file {args.note_file}: {e}") from e

        page_path = Path(page_rel)
        record, findings = build_record(args, payload, page_path, page_rel)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = write_record(record, body, record_dir_for(page_rel), stamp, args.kind)
    except RecordError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(
        f"RECORDED: {path} (page={page_rel}, result={args.result},"
        f" attempts={args.attempts}, findings={len(findings)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
