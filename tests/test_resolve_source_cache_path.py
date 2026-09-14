"""Tests for .claude/skills/wikicommit-ask/scripts/resolve_source_cache_path.py

The reader half of the extraction cache. Issue #470 built it for `type: url`
sources; Issue #885 widened it to `type: path`, which is the half that matters
most — `--include-source` had been reading the *raw* file for those, so a
`.docx`/`.epub`/scanned PDF arrived as garbled bytes, and the Skill said so as a
known limitation. Without a reader, writing the cache would have landed as the
empty receptacle Issue #553 forbids.

The assertions that matter are about identity: the cache path is derived from the
management file actually on disk, never re-derived from the identifier, so
repositories carrying management files under any of the older naming schemes
(Issues #191 / #192 / #572 / #573 — none of which is ever auto-migrated) still
resolve.

Issue #918 added a second thing the resolver reads from that management file: a
`status: retracted` answers the call before the cache is looked up at all. The
ordering is the whole guard — a retracted source with no cache would otherwise
return the ordinary miss, and on the `type: path` route the caller answers a miss
by reading the raw file.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPT = REPO / ".claude/skills/wikicommit-ask/scripts/resolve_source_cache_path.py"

sys.path.insert(0, str(REPO / "tools"))
from check_skill_md_lines import instruction_files  # noqa: E402


def _generate_instructions() -> str:
    """Every instruction `.md` `wikicommit-generate` can reach, concatenated.

    Imported rather than restated so this cannot drift from the size metric and
    the two blocking scanners — the single definition made in Issue #887, and the
    reason these assertions survived Issue #911 moving each pass into
    `references/`.
    """
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in instruction_files(REPO / ".claude/skills/wikicommit-generate")
    )

_spec = importlib.util.spec_from_file_location("resolve_source_cache_path", SCRIPT)
resolver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver)


def _url_source(root: Path, mgmt_rel: str, url: str, status: str | None = None) -> Path:
    """Register a `type: url` source at an arbitrary management path.

    `mgmt_rel` is relative to `.wikicommit/source/url/` and is deliberately a
    parameter: the point of the real-directory scan is that it does not care
    whether the name matches what today's derivation would produce.

    `status` is optional because the ordinary case is a management file whose
    status says nothing about the resolver's job; only `retracted` does
    (Issue #918).
    """
    mgmt = root / ".wikicommit/source/url" / mgmt_rel
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    status_line = f"status: {status}\n" if status else ""
    mgmt.write_text(
        f"---\nsource:\n  type: url\n  url: {url}\n  hash: sha256:ab12\n{status_line}---\n",
        encoding="utf-8",
    )
    return mgmt


def _path_source(root: Path, mgmt_rel: str, source_path: str, status: str | None = None) -> Path:
    mgmt = root / ".wikicommit/source/path" / mgmt_rel
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    status_line = f"status: {status}\n" if status else ""
    mgmt.write_text(
        f"---\nsource:\n  type: path\n  path: {source_path}\n  hash: sha256:ab12\n{status_line}---\n",
        encoding="utf-8",
    )
    return mgmt


def _write(root: Path, rel: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("extracted text\n", encoding="utf-8")
    return p


# ── type: url (Issue #470, unchanged behaviour) ───────────────────────────────

def test_url_resolves_through_the_management_file_on_disk(tmp_path):
    _url_source(tmp_path, "example.com/article.md", "https://example.com/article")
    _write(tmp_path, ".wikicommit/.cache/ingest-fetch/example.com/article.md")

    got = resolver.resolve_url("https://example.com/article", tmp_path)
    assert got == tmp_path / ".wikicommit/.cache/ingest-fetch/example.com/article.md"


def test_url_resolves_a_legacy_flat_management_file(tmp_path):
    """Pre-Issue-#191 naming is never auto-migrated, so re-deriving the filename
    from the URL would call a cache that exists missing."""
    _url_source(tmp_path, "example-com-article.md", "https://example.com/article")
    _write(tmp_path, ".wikicommit/.cache/ingest-fetch/example-com-article.md")

    got = resolver.resolve_url("https://example.com/article", tmp_path)
    assert got == tmp_path / ".wikicommit/.cache/ingest-fetch/example-com-article.md"


def test_url_returns_none_when_the_cache_is_absent(tmp_path):
    _url_source(tmp_path, "example.com/article.md", "https://example.com/article")
    assert resolver.resolve_url("https://example.com/article", tmp_path) is None


def test_url_returns_none_when_no_source_is_registered(tmp_path):
    assert resolver.resolve_url("https://example.com/article", tmp_path) is None


# ── type: path (Issue #885) ──────────────────────────────────────────────────

def test_path_resolves_the_extraction_cache(tmp_path):
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    got = resolver.resolve_path("raw/paper.pdf", tmp_path)
    assert got == tmp_path / ".wikicommit/.cache/extract-path/raw/paper.pdf.md"


def test_path_keeps_the_trailing_md_so_two_extensions_stay_distinct(tmp_path):
    """The writer's rule, asserted from the reading side.

    If either half dropped and re-added the extension, `paper.pdf` would be
    handed `paper.docx`'s extracted text — the Issue #573 collision, moved into
    the cache layer where nothing checks hashes.
    """
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf")
    _path_source(tmp_path, "raw/paper.docx.md", "raw/paper.docx")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.docx.md")

    pdf = resolver.resolve_path("raw/paper.pdf", tmp_path)
    docx = resolver.resolve_path("raw/paper.docx", tmp_path)
    assert pdf is not None and docx is not None
    assert pdf != docx


def test_path_resolves_a_legacy_extension_stripped_management_file(tmp_path):
    """Pre-Issue-#573 naming replaced the extension and is never auto-migrated."""
    _path_source(tmp_path, "raw/paper.md", "raw/paper.pdf")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.md")

    got = resolver.resolve_path("raw/paper.pdf", tmp_path)
    assert got == tmp_path / ".wikicommit/.cache/extract-path/raw/paper.md"


def test_path_returns_none_when_the_cache_is_absent(tmp_path):
    """The `.md`/`.txt` case, and every clean checkout: the caller falls back to
    reading the raw file."""
    _path_source(tmp_path, "notes.md.md", "notes.md")
    assert resolver.resolve_path("notes.md", tmp_path) is None


def test_path_returns_none_when_no_source_is_registered(tmp_path):
    assert resolver.resolve_path("raw/nope.pdf", tmp_path) is None


def test_the_two_trees_do_not_reach_into_each_other(tmp_path):
    """A url identifier must not resolve through the path tree, or vice versa —
    they are separate scans against separate roots for separate cache trees."""
    _path_source(tmp_path, "example.com/article.md", "example.com/article")
    _write(tmp_path, ".wikicommit/.cache/extract-path/example.com/article.md")

    assert resolver.resolve_url("https://example.com/article", tmp_path) is None
    assert resolver.resolve_path("example.com/article", tmp_path) is not None


# ── Retracted sources (Issue #918) ───────────────────────────────────────────
#
# `status: retracted` is the one thing a machine cannot conclude on its own: the
# evidence-bound rule (Issue #442) makes the source the yardstick, never the thing
# being judged, so only a person can write it. Ingestion already stops re-registering
# and re-queueing such a source; the reference side had no guard at all, and
# `--include-source` was injecting the withdrawn document as answer grounding.

def test_url_retracted_returns_the_marker_not_a_path(tmp_path):
    mgmt = _url_source(
        tmp_path, "example.com/listing.md", "https://example.com/listing", status="retracted"
    )
    _write(tmp_path, ".wikicommit/.cache/ingest-fetch/example.com/listing.md")

    got = resolver.resolve_url("https://example.com/listing", tmp_path)
    assert isinstance(got, resolver.Retracted)
    assert got.management_file == mgmt


def test_path_retracted_returns_the_marker_not_a_path(tmp_path):
    mgmt = _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf", status="retracted")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    got = resolver.resolve_path("raw/paper.pdf", tmp_path)
    assert isinstance(got, resolver.Retracted)
    assert got.management_file == mgmt


def test_retracted_is_answered_before_the_cache_is_looked_up(tmp_path):
    """The case the whole guard turns on.

    With no cache on disk the resolver's ordinary answer is None, and for a
    `type: path` source the caller reads the *raw file* on None — so checking the
    status after the cache lookup would let exactly the withdrawn document
    through, and only for the sources that were never cached.
    """
    _url_source(
        tmp_path, "example.com/listing.md", "https://example.com/listing", status="retracted"
    )
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf", status="retracted")

    assert isinstance(
        resolver.resolve_url("https://example.com/listing", tmp_path), resolver.Retracted
    )
    assert isinstance(resolver.resolve_path("raw/paper.pdf", tmp_path), resolver.Retracted)


def test_a_retracted_marker_is_not_a_path(tmp_path):
    """`Retracted` must not be usable as somewhere to look.

    Returning a `Path` subclass, or the management file itself, would leave a
    caller that skipped the type check reading a file — and the management file
    quotes the source's own summary, so the read would look plausible.
    """
    _url_source(
        tmp_path, "example.com/listing.md", "https://example.com/listing", status="retracted"
    )
    got = resolver.resolve_url("https://example.com/listing", tmp_path)
    assert not isinstance(got, Path)


def test_other_statuses_resolve_normally(tmp_path):
    """Only `retracted` is read here.

    `failed` / `excluded` / `partial` / `outdated` / `generated` describe how
    ingestion went, not whether the document can be trusted; reading them would
    put a second interpretation of `status` on the reference side.
    """
    for i, status in enumerate(("generated", "partial", "excluded", "failed", "outdated")):
        _path_source(tmp_path, f"raw/p{i}.pdf.md", f"raw/p{i}.pdf", status=status)
        _write(tmp_path, f".wikicommit/.cache/extract-path/raw/p{i}.pdf.md")

        got = resolver.resolve_path(f"raw/p{i}.pdf", tmp_path)
        assert got == tmp_path / f".wikicommit/.cache/extract-path/raw/p{i}.pdf.md", status


def test_an_unparseable_management_file_is_not_skipped_in_silence(tmp_path, capsys):
    """A broken management file must not turn the guard off quietly.

    `status: retracted` is hand-written and nothing validates a source management
    file, so a typo made while writing the retraction is the likeliest way this
    frontmatter breaks. Skipping it silently returns the ordinary miss — and on
    the `type: path` route the caller answers a miss by reading the raw file, so
    the withdrawn document reaches the answer anyway.
    """
    mgmt = tmp_path / ".wikicommit/source/path/raw/paper.pdf.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        "---\nsource:\n  type: path\n   path: raw/paper.pdf\nstatus: retracted\n---\n",
        encoding="utf-8",
    )

    assert resolver.resolve_path("raw/paper.pdf", tmp_path) is None
    err = capsys.readouterr().err
    assert str(mgmt) in err
    assert "retracted" in err


def test_a_management_file_without_frontmatter_is_skipped_quietly(tmp_path):
    """Not an error — the warning above is for a block that fails to parse."""
    stray = tmp_path / ".wikicommit/source/path/README.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("just prose, no frontmatter\n", encoding="utf-8")
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    assert resolver.resolve_path("raw/paper.pdf", tmp_path) is not None


def test_a_status_free_management_file_resolves_normally(tmp_path):
    """Every management file written before Issue #737 lacks the field entirely."""
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    assert resolver.resolve_path("raw/paper.pdf", tmp_path) is not None


# ── CLI contract ─────────────────────────────────────────────────────────────

def _run(root: Path, identifier: str, *args: str) -> subprocess.CompletedProcess:
    # The script imports `_frontmatter` from `.wikicommit/scripts` relative to cwd.
    scripts = root / ".wikicommit/scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    target = scripts / "_frontmatter.py"
    if not target.exists():
        target.write_text(
            (REPO / ".wikicommit/scripts/_frontmatter.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=identifier + "\n",
        capture_output=True, text=True, cwd=root, check=False,
    )


def test_cli_reads_the_identifier_from_stdin_not_argv(tmp_path):
    """`sources[].path`/`[].url` are only format-validated, never verified safe as
    shell arguments, so they stay off the command line entirely."""
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    ok = _run(tmp_path, "raw/paper.pdf", "--type", "path")
    assert ok.returncode == 0
    assert ok.stdout.strip() == ".wikicommit/.cache/extract-path/raw/paper.pdf.md"


def test_cli_defaults_to_url_so_the_existing_call_site_is_unchanged(tmp_path):
    _url_source(tmp_path, "example.com/article.md", "https://example.com/article")
    _write(tmp_path, ".wikicommit/.cache/ingest-fetch/example.com/article.md")

    got = _run(tmp_path, "https://example.com/article")
    assert got.returncode == 0
    assert got.stdout.strip() == ".wikicommit/.cache/ingest-fetch/example.com/article.md"


def test_cli_exits_one_and_prints_nothing_when_unresolved(tmp_path):
    got = _run(tmp_path, "raw/nope.pdf", "--type", "path")
    assert got.returncode == 1
    assert got.stdout.strip() == ""


def test_cli_exits_two_and_names_the_management_file_when_retracted(tmp_path):
    """Exit 2, not 1.

    Exit 1 already folds two meanings together, and on the `type: path` route the
    caller answers it by reading the raw file. The path it prints is where the
    `## Retraction Reason` a person wrote lives (Issue #737) — the only place the
    *why* exists, since no enum carries it.
    """
    mgmt = _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf", status="retracted")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    got = _run(tmp_path, "raw/paper.pdf", "--type", "path")
    assert got.returncode == 2
    assert got.stdout.startswith("RETRACTED: raw/paper.pdf (")
    assert str(mgmt.relative_to(tmp_path)) in got.stdout


def test_cli_exits_two_for_a_retracted_url_source_too(tmp_path):
    _url_source(
        tmp_path, "example.com/listing.md", "https://example.com/listing", status="retracted"
    )

    got = _run(tmp_path, "https://example.com/listing")
    assert got.returncode == 2
    assert got.stdout.startswith("RETRACTED: https://example.com/listing (")


def test_cli_never_prints_a_cache_path_alongside_the_retracted_line(tmp_path):
    """A caller reading stdout for a path must not find one to read."""
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf", status="retracted")
    _write(tmp_path, ".wikicommit/.cache/extract-path/raw/paper.pdf.md")

    got = _run(tmp_path, "raw/paper.pdf", "--type", "path")
    assert ".wikicommit/.cache/" not in got.stdout


def test_cli_exits_two_even_with_no_cache_on_disk(tmp_path):
    """The exit-1 fallback is precisely what must not run here."""
    _path_source(tmp_path, "raw/paper.pdf.md", "raw/paper.pdf", status="retracted")

    got = _run(tmp_path, "raw/paper.pdf", "--type", "path")
    assert got.returncode == 2


def test_cli_rejects_an_unknown_type(tmp_path):
    got = _run(tmp_path, "raw/paper.pdf", "--type", "manual")
    assert got.returncode != 0


def test_cli_usage_error_on_empty_stdin(tmp_path):
    got = _run(tmp_path, "", "--type", "path")
    assert got.returncode == 1
    assert "Usage:" in got.stderr


# ── Writer and reader stay paired (Issue #553's rule, Issue #885's instance) ──

def test_the_generate_skill_both_writes_and_checks_the_path_cache():
    """A cache nobody writes does nothing; a cache nobody validates is worse than
    nothing, because a stale extraction reads as a fresh one."""
    # Read every instruction file, not just SKILL.md: Pass 1 — which is where both
    # commands are called — moved into references/pass1-extract.md (Issue #911).
    text = _generate_instructions()
    assert "--check-path-cache" in text
    assert "--path-cache-path" in text


def test_the_ask_skill_reads_the_path_cache():
    """The consumer half. Without it, Issue #885 lands as the empty receptacle
    Issue #553 forbids — bytes written to disk that nothing ever opens.
    """
    text = (REPO / ".claude/skills/wikicommit-ask/SKILL.md").read_text(encoding="utf-8")
    assert "resolve_source_cache_path.py --type path" in text, (
        "wikicommit-ask no longer resolves a type: path source's extraction cache, "
        "so the cache wikicommit-generate writes has no reader"
    )


def test_the_regenerate_mode_prefers_the_path_cache():
    """The mode where the cache is worth the most: the source has not changed, the
    generation rules have, and re-running an OCR pass is pure cost."""
    text = (REPO / ".claude/skills/wikicommit-generate/references/regenerate.md").read_text(encoding="utf-8")
    assert "--check-path-cache" in text


def test_nothing_hands_the_path_cache_to_write_hash():
    """`source.hash` means the raw file for a `type: path` source.

    Overwriting it with an extracted-text hash would leave
    `check_ingest_freshness.py` reporting "no change" for a file that changed —
    silently, and for that source from then on. The instruction files say so; this
    checks that no call site does it anyway.
    """
    for path in instruction_files(REPO / ".claude/skills/wikicommit-generate"):
        rel = path.relative_to(REPO)
        for line in path.read_text(encoding="utf-8").splitlines():
            if "--write-hash" not in line:
                continue
            assert "extract-path" not in line, (
                f"{rel} hands an extraction cache to --write-hash: {line.strip()}"
            )


def test_the_ask_skill_handles_the_retracted_exit_code_on_both_routes():
    """The consumer half of Issue #918.

    A guard that resolves to exit 2 and a Skill that only branches on 0/1 falls
    into the "could not retrieve" note and, on the `type: path` route, reads the
    raw file — the same injection, reached by a different line. Both routes are
    checked separately because the two branches are written independently and one
    can lose the handling without the other noticing.
    """
    text = (REPO / ".claude/skills/wikicommit-ask/SKILL.md").read_text(encoding="utf-8")
    # Backticks and line wrapping are formatting, not meaning: flatten both so a
    # reflowed paragraph does not read as a removed branch.
    flat = " ".join(text.replace("`", "").split())

    path_call = "resolve_source_cache_path.py --type path"
    url_call = "resolve_source_cache_path.py --type url"
    # The `manual` bullet closes the per-route list; everything after it — the
    # shared retraction paragraphs and the Step 6 note — belongs to neither
    # route. Each half has to stop before it, or the shared prose satisfies both
    # assertions on its own and this test can no longer fail (which is the state
    # the url half was in: partitioning on `url_call` alone left the whole tail
    # of the document inside `url_branch`).
    shared_tail = "- type: manual → skip"
    for marker in (path_call, url_call, shared_tail):
        assert flat.count(marker) == 1, marker

    path_branch = flat.partition(path_call)[2].partition(url_call)[0]
    url_branch = flat.partition(url_call)[2].partition(shared_tail)[0]

    for name, half in (("type: path", path_branch), ("type: url", url_branch)):
        assert "exit code 2" in half, (
            f"the {name} route of wikicommit-ask no longer branches on the retracted "
            "exit code, so a withdrawn source can still ground an answer"
        )
    assert "retracted" in flat

