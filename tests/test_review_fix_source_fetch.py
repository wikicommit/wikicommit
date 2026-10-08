"""`wikicommit-review` / `wikicommit-fix` read a source's text, not a summary (Issue #1047).

Both Skills used to re-read a URL source with the agent's web-fetch tool, which in
Claude Code returns a model-written summary — so a review checked the page against a
summary while its record claimed the page's recorded hash. The route is now the
extraction cache first (`resolve_source_cache_path.py`), then `add_source.py
--fetch-url` into `.wikicommit/.cache/refetch/`.

Since Issue #1190 the per-entry part (cache before fetch, fetch into `refetch/`,
settle, retraction) is `--obtain`, and since Issue #1211 the whole list is one
command, `--obtain-sources`, which each SKILL.md calls with the page whose `sources`
it settled on (the shared prose procedure it replaced is gone). The ordering is
asserted on the script's behaviour; the prose only on calling it and on what to do
with each line it prints.
"""

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
TEXTS = {
    name: (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    for name in ("wikicommit-review", "wikicommit-fix")
}
LABELS = {"wikicommit-review": "review", "wikicommit-fix": "fix"}

_SCRIPT = SKILLS / "wikicommit-init" / "scripts" / "templates" / "scripts" / "resolve_source_cache_path.py"
_spec = importlib.util.spec_from_file_location("resolve_source_cache_path_obtain", _SCRIPT)
resolver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver)

COMMAND = ".wikicommit/scripts/resolve_source_cache_path.py --obtain-sources"


def test_the_shared_procedure_is_gone():
    """Issue #1211: nothing is left for a shared prose file to carry."""
    assert not (SKILLS / "wikicommit-ask" / "shared").exists()
    for text in TEXTS.values():
        assert "shared/source-fetch.md" not in text


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_each_skill_gets_its_sources_with_one_command(name):
    text = TEXTS[name]
    assert f"{COMMAND} --label {LABELS[name]}" in text, (
        f"{name} must call --obtain-sources with its own label, so review and fix never share a scratch file"
    )
    for line in ("READ: [<n>]", "EXTRACT: [<n>]", "RETRACTED: [<n>]", "UNAVAILABLE: [<n>]", "MANUAL: [<n>]"):
        assert line in text, f"{name} no longer says what to do on `{line}`"
    assert f"rm -f .wikicommit/.cache/refetch/{LABELS[name]}-*.md" in text


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_network_unavailable_is_reported_as_the_environment(name):
    assert "say the reason is the environment" in TEXTS[name]


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_the_agents_own_web_fetch_tool_is_ruled_out(name):
    assert "Never use your own web-fetch tool" in TEXTS[name]


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_each_skill_says_not_to_read_an_outside_path(name):
    assert "do not open that path yourself" in TEXTS[name]


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_extraction_is_routed_through_generates_table(name):
    assert "../wikicommit-generate/references/text-extraction-routing.md" in TEXTS[name]


def test_review_records_a_version_mismatch_in_the_note_not_as_a_finding():
    text = TEXTS["wikicommit-review"]
    assert "whose hash differs from the one this page records" in text
    assert "Do not raise it as a finding" in text
    assert "version-mismatch lines from Step 4 item 1" in text


# ── what `--obtain` does (the ordering the prose used to carry) ───────────────

_URL = "https://example.com/article"
_CACHE = ".wikicommit/.cache/ingest-fetch/example.com/article.md"
_BODY = "fetched body\n"
_HASH = "sha256:" + hashlib.sha256(_BODY.encode("utf-8")).hexdigest()


def _url_source(root: Path, source_hash: str = _HASH, status: str = "generated") -> Path:
    mgmt = root / ".wikicommit/source/url/example.com/article.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        f"---\nsource:\n  type: url\n  url: {_URL}\n  hash: {source_hash}\nstatus: {status}\n---\n",
        encoding="utf-8",
    )
    return mgmt


def _path_source(root: Path, rel: str, source_hash: str) -> Path:
    mgmt = root / ".wikicommit/source/path" / f"{rel}.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        f"---\nsource:\n  type: path\n  path: {rel}\n  hash: {source_hash}\nstatus: generated\n---\n",
        encoding="utf-8",
    )
    return mgmt


class _Fetcher:
    """Stands in for `add_source.py --fetch-url`; records every call."""

    def __init__(self, code: int = 0, body: str = _BODY):
        self.code, self.body, self.calls = code, body, []

    def __call__(self, url, output, repo_root):
        self.calls.append((url, output))
        if self.code == 0:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(self.body, encoding="utf-8")
            return 0, f"FETCHED: {output}"
        return self.code, "NETWORK_UNAVAILABLE: ..." if self.code == 3 else "ERROR: ..."


def _obtain(root, fetcher, source_type="url", identifier=_URL, page_hash=_HASH):
    return resolver.obtain(source_type, identifier, "review", 1, page_hash, root, fetch=fetcher)


def test_cache_is_used_before_any_fetch(tmp_path):
    _url_source(tmp_path)
    (tmp_path / _CACHE).parent.mkdir(parents=True)
    (tmp_path / _CACHE).write_text(_BODY, encoding="utf-8")
    fetcher = _Fetcher()
    got = _obtain(tmp_path, fetcher)
    assert got["result"] == "READ" and got["file"] == tmp_path / _CACHE
    assert got["page"] == "match"
    assert fetcher.calls == [], "fetched although the extraction cache was there"


def test_fetch_lands_in_refetch_and_is_settled_into_the_cache(tmp_path):
    mgmt = _url_source(tmp_path)
    before = mgmt.read_text(encoding="utf-8")
    fetcher = _Fetcher()
    got = _obtain(tmp_path, fetcher)
    assert fetcher.calls[0][1] == tmp_path / ".wikicommit/.cache/refetch/review-1.md"
    assert got == {"result": "READ", "file": tmp_path / _CACHE, "page": "match"}
    assert mgmt.read_text(encoding="utf-8") == before, "a management file was written"


def test_a_fetch_that_is_not_placed_is_read_from_the_scratch_file(tmp_path):
    _url_source(tmp_path, source_hash="sha256:" + "0" * 64)
    got = _obtain(tmp_path, _Fetcher(), page_hash="sha256:" + "1" * 64)
    scratch = tmp_path / ".wikicommit/.cache/refetch/review-1.md"
    assert got == {"result": "READ", "file": scratch, "page": "mismatch"}
    assert not (tmp_path / _CACHE).exists()


def test_a_stale_scratch_file_is_never_taken_for_this_fetch(tmp_path):
    _url_source(tmp_path)
    scratch = tmp_path / ".wikicommit/.cache/refetch/review-1.md"
    scratch.parent.mkdir(parents=True)
    scratch.write_text("left by an earlier run\n", encoding="utf-8")
    got = _obtain(tmp_path, _Fetcher(code=1))
    assert got["result"] == "UNAVAILABLE" and got["reason"] == "fetch"
    assert not scratch.exists()


def test_network_unavailable_is_the_environment(tmp_path):
    _url_source(tmp_path)
    got = _obtain(tmp_path, _Fetcher(code=3))
    assert got["result"] == "UNAVAILABLE" and got["reason"] == "environment"


def test_a_retracted_source_is_never_fetched(tmp_path):
    _url_source(tmp_path, status="retracted")
    fetcher = _Fetcher()
    got = _obtain(tmp_path, fetcher)
    assert got["result"] == "RETRACTED"
    assert fetcher.calls == []


def test_a_path_cache_is_used_only_while_the_file_is_the_extracted_version(tmp_path):
    raw = tmp_path / "raw/paper.pdf"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"pdf v1")
    v1 = "sha256:" + hashlib.sha256(b"pdf v1").hexdigest()
    _path_source(tmp_path, "raw/paper.pdf", v1)
    cache = tmp_path / ".wikicommit/.cache/extract-path/raw/paper.pdf.md"
    cache.parent.mkdir(parents=True)
    cache.write_text("extracted\n", encoding="utf-8")

    got = _obtain(tmp_path, _Fetcher(), "path", "raw/paper.pdf", v1)
    assert got == {"result": "READ", "file": cache, "page": "match"}

    raw.write_bytes(b"pdf v2")
    got = _obtain(tmp_path, _Fetcher(), "path", "raw/paper.pdf", v1)
    assert got == {"result": "EXTRACT", "file": raw}


def test_a_plain_text_path_source_is_read_raw(tmp_path):
    raw = tmp_path / "raw/notes.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("notes\n", encoding="utf-8")
    got = _obtain(tmp_path, _Fetcher(), "path", "raw/notes.md", "sha256:" + "0" * 64)
    assert got == {"result": "READ", "file": raw, "page": "mismatch"}


def test_a_retracted_path_source_with_no_cache_does_not_fall_through_to_the_raw_file(tmp_path):
    raw = tmp_path / "raw/notes.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("notes\n", encoding="utf-8")
    mgmt = _path_source(tmp_path, "raw/notes.md", "sha256:ab")
    mgmt.write_text(mgmt.read_text(encoding="utf-8").replace("generated", "retracted"), encoding="utf-8")
    got = _obtain(tmp_path, _Fetcher(), "path", "raw/notes.md")
    assert got["result"] == "RETRACTED"


@pytest.mark.parametrize("form", ["absolute", "dotdot"])
def test_a_path_outside_the_repository_is_never_read(tmp_path, form):
    """Issue #1201: an absolute or `..` path is refused before anything is read,
    and before the existence check (so `missing` does not reveal the file)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret\n", encoding="utf-8")
    identifier = str(secret) if form == "absolute" else "../secret.txt"
    got = _obtain(repo, _Fetcher(), "path", identifier)
    assert got["result"] == "UNAVAILABLE" and got["reason"] == "outside"

    absent = str(tmp_path / "absent.txt") if form == "absolute" else "../absent.txt"
    got = _obtain(repo, _Fetcher(), "path", absent)
    assert got["reason"] == "outside", "existence outside the repository leaked as `missing`"


def test_a_symlink_pointing_outside_the_repository_is_never_read(tmp_path):
    repo = tmp_path / "repo"
    (repo / "raw").mkdir(parents=True)
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"secret")
    (repo / "raw/link.pdf").symlink_to(secret)
    (repo / "raw/link.md").symlink_to(secret)
    for rel in ("raw/link.pdf", "raw/link.md"):
        got = _obtain(repo, _Fetcher(), "path", rel)
        assert got["result"] == "UNAVAILABLE" and got["reason"] == "outside"


def test_a_symlink_pointing_inside_the_repository_is_read(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/notes.md").write_text("notes\n", encoding="utf-8")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/notes.md").symlink_to(tmp_path / "docs/notes.md")
    got = _obtain(tmp_path, _Fetcher(), "path", "raw/notes.md", "sha256:" + "0" * 64)
    # The target, not the link (Issue #1208): the extension is judged there too.
    assert got == {"result": "READ", "file": tmp_path / "docs/notes.md", "page": "mismatch"}


def test_review_takes_the_version_note_from_the_read_line():
    assert "`page=mismatch` means it differs" in TEXTS["wikicommit-review"]


def test_the_fetcher_it_calls_is_next_to_it_in_wikicommit_scripts():
    """A wrong path would turn every fetch into `UNAVAILABLE: fetch` (Issue #1210 moved both)."""
    assert resolver.ADD_SOURCE.is_file()
    assert resolver.ADD_SOURCE == (_SCRIPT.parent / "add_source.py").resolve()


def test_a_crashing_fetcher_is_reported_on_one_line(tmp_path, monkeypatch):
    fake = tmp_path / "add_source.py"
    fake.write_text(
        "import sys\nsys.stderr.write('Traceback (most recent call last):\\n  x\\n"
        "ModuleNotFoundError: No module named markitdown\\n')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(resolver, "ADD_SOURCE", fake)
    code, message = resolver.run_fetch(_URL, tmp_path / "out.md", tmp_path)
    assert code == 1
    assert message == "ModuleNotFoundError: No module named markitdown"


# ── --obtain-sources: every entry of the page the caller names (Issue #1211) ──


def _page(root: Path, sources_yaml: str, rel: str = ".wikicommit/entity/ja/Person/x.md") -> Path:
    page = root / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntitle: x\nsources:\n{sources_yaml}---\nbody\n", encoding="utf-8")
    return page


def test_every_entry_gets_one_result_in_order(tmp_path):
    _url_source(tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/notes.md").write_text("notes\n", encoding="utf-8")
    page = _page(
        tmp_path,
        f"  - type: url\n    url: {_URL}\n    hash: {_HASH}\n"
        "  - type: manual\n    author: a\n"
        "  - type: path\n    path: raw/notes.md\n    hash: sha256:00\n"
        "  - type: path\n    path: raw/gone.pdf\n"
        "  - type: url\n",
    )
    got = resolver.obtain_sources(page, "review", tmp_path, fetch=_Fetcher())
    assert [(e["index"], e["result"]) for e in got] == [
        (1, "READ"), (2, "MANUAL"), (3, "READ"), (4, "UNAVAILABLE"), (5, "UNAVAILABLE"),
    ]
    assert got[0]["page"] == "match", "the entry's own sources[].hash was not passed on"
    assert got[2]["page"] == "mismatch"
    assert got[3]["reason"] == "missing" and got[4]["reason"] == "invalid"


def test_a_retracted_entry_is_never_fetched_while_the_others_are(tmp_path):
    _url_source(tmp_path, status="retracted")
    page = _page(
        tmp_path,
        f"  - type: url\n    url: {_URL}\n    hash: {_HASH}\n"
        "  - type: url\n    url: https://example.com/other\n",
    )
    fetcher = _Fetcher()
    got = resolver.obtain_sources(page, "fix", tmp_path, fetch=fetcher)
    assert got[0]["result"] == "RETRACTED"
    assert [url for url, _ in fetcher.calls] == ["https://example.com/other"]
    assert fetcher.calls[0][1] == tmp_path / ".wikicommit/.cache/refetch/fix-2.md"


def test_a_previous_runs_scratch_files_are_cleared_first(tmp_path):
    refetch = tmp_path / ".wikicommit/.cache/refetch"
    refetch.mkdir(parents=True)
    (refetch / "review-7.md").write_text("old\n", encoding="utf-8")
    (refetch / "fix-1.md").write_text("other label\n", encoding="utf-8")
    page = _page(tmp_path, "  - type: manual\n    author: a\n")
    resolver.obtain_sources(page, "review", tmp_path, fetch=_Fetcher())
    assert not (refetch / "review-7.md").exists()
    assert (refetch / "fix-1.md").exists(), "another label's scratch file was touched"


def test_clearing_a_label_leaves_a_label_it_is_a_prefix_of(tmp_path):
    """`fix` must not clear `fix-x-1.md`: `<label>-*` alone would match it."""
    refetch = tmp_path / ".wikicommit/.cache/refetch"
    refetch.mkdir(parents=True)
    (refetch / "fix-x-1.md").write_text("other label\n", encoding="utf-8")
    page = _page(tmp_path, "  - type: manual\n    author: a\n")
    resolver.obtain_sources(page, "fix", tmp_path, fetch=_Fetcher())
    assert (refetch / "fix-x-1.md").exists()


def _cli(root: Path, stdin: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--obtain-sources", *args],
        input=stdin, capture_output=True, text=True, cwd=root, check=False,
    )


def test_the_cli_prints_one_line_per_entry_and_a_summary(tmp_path):
    _url_source(tmp_path, status="retracted")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/notes.md").write_text("notes\n", encoding="utf-8")
    page = _page(
        tmp_path,
        f"  - type: url\n    url: {_URL}\n"
        "  - type: path\n    path: raw/notes.md\n"
        "  - type: path\n    path: ../outside.md\n"
        "  - type: manual\n",
    )
    got = _cli(tmp_path, str(page.relative_to(tmp_path)), "--label", "review")
    assert got.returncode == 0, got.stderr
    assert got.stdout.splitlines() == [
        f"RETRACTED: [1] {_URL} (.wikicommit/source/url/example.com/article.md)",
        "READ: [2] raw/notes.md page=mismatch",
        "UNAVAILABLE: [3] outside ../outside.md (../outside.md resolves outside the repository)",
        "MANUAL: [4]",
        "SUMMARY: entries=4 read=1 extract=0 retracted=1 unavailable=1 manual=1",
    ]


@pytest.mark.parametrize(
    "stdin, args",
    [
        pytest.param("missing.md", ("--label", "review"), id="no-such-page"),
        pytest.param("../elsewhere.md", ("--label", "review"), id="page-outside"),
        pytest.param("page.md", ("--label", "../x"), id="bad-label"),
    ],
)
def test_the_cli_refuses_bad_input_with_exit_1(tmp_path, stdin, args):
    (tmp_path / "page.md").write_text("---\nsources: []\n---\n", encoding="utf-8")
    (tmp_path.parent / "elsewhere.md").write_text("---\nsources: []\n---\n", encoding="utf-8")
    got = _cli(tmp_path, stdin, *args)
    assert got.returncode == 1 and got.stdout == ""


def test_the_cli_accepts_a_translated_from_with_the_legacy_prefix(tmp_path):
    """A `translated_from` written before the `wiki/` -> `entity/` rename is
    handed over as stored; the page now lives under `entity/`."""
    _page(tmp_path, "  - type: manual\n")
    got = _cli(tmp_path, ".wikicommit/wiki/ja/Person/x.md", "--label", "review")
    assert got.returncode == 0, got.stderr
    assert got.stdout.splitlines()[0] == "MANUAL: [1]"


# ── Issue #1216: generate and review / fix use the same text for a linked source ─

_ADD_SOURCE = _SCRIPT.parent / "add_source.py"
_as_spec = importlib.util.spec_from_file_location("add_source_for_obtain", _ADD_SOURCE)
add_source = importlib.util.module_from_spec(_as_spec)
_as_spec.loader.exec_module(add_source)


def test_a_md_link_to_a_pdf_is_extracted_alike_and_the_cache_is_shared(tmp_path):
    """`raw/notes.md` -> `docs/scan.pdf`: Pass 1 (`--check-path-cache`) and
    review / fix (`--obtain`) both extract the PDF, and what Pass 1 caches is
    what a later review / fix reads."""
    (tmp_path / "docs").mkdir()
    pdf = tmp_path / "docs/scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 bytes")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/notes.md").symlink_to(pdf)
    digest = "sha256:" + hashlib.sha256(b"%PDF-1.4 bytes").hexdigest()
    mgmt = _path_source(tmp_path, "raw/notes.md", digest)
    mgmt_rel = mgmt.relative_to(tmp_path).as_posix()

    # Before any extraction: both sides name the PDF as the file to extract.
    result, _cache, _msg, extract = add_source.check_path_cache(mgmt_rel, tmp_path)
    assert result == "CACHE_STALE"
    assert extract == "docs/scan.pdf"
    assert _obtain(tmp_path, _Fetcher(), "path", "raw/notes.md", digest) == {"result": "EXTRACT", "file": pdf}

    # Pass 1 writes its extraction where --path-cache-path says.
    _r, cache_rel, _m = add_source.print_path_cache_path(mgmt_rel, tmp_path)
    (tmp_path / cache_rel).write_text("extracted text\n", encoding="utf-8")

    # A later review / fix reads that same extraction instead of extracting again.
    got = _obtain(tmp_path, _Fetcher(), "path", "raw/notes.md", digest)
    assert got == {"result": "READ", "file": tmp_path / cache_rel, "page": "match"}
    assert add_source.check_path_cache(mgmt_rel, tmp_path)[0] == "CACHE_VALID"


# ── --obtain-sources: a time budget and a network that is not there (Issue #1240) ──


class _Clock:
    """A clock that moves only when a fetch runs: each fetch takes `step` seconds."""

    def __init__(self, step: float):
        self.now, self.step = 0.0, step

    def __call__(self):
        return self.now


def _timed(clock: _Clock, fetcher):
    def fetch(url, output, repo_root):
        clock.now += clock.step
        return fetcher(url, output, repo_root)
    return fetch


def _urls(n: int) -> str:
    return "".join(f"  - type: url\n    url: https://example.com/{i}\n" for i in range(1, n + 1))


def test_no_new_fetch_starts_past_the_budget(tmp_path):
    page = _page(tmp_path, _urls(4))
    clock, fetcher = _Clock(step=30), _Fetcher()
    got = resolver.obtain_sources(page, "review", tmp_path, fetch=_timed(clock, fetcher), budget=45, clock=clock)
    assert [(e["index"], e["result"]) for e in got] == [(1, "READ"), (2, "READ"), (3, "CONTINUE")]
    assert len(fetcher.calls) == 2, "a fetch was started after the budget had run out"


def test_the_first_fetch_of_a_call_starts_whatever_the_budget(tmp_path):
    page = _page(tmp_path, _urls(2))
    clock, fetcher = _Clock(step=100), _Fetcher()
    got = resolver.obtain_sources(page, "review", tmp_path, fetch=_timed(clock, fetcher), budget=0, clock=clock)
    assert [(e["index"], e["result"]) for e in got] == [(1, "READ"), (2, "CONTINUE")]


def test_entries_that_need_no_fetch_are_answered_past_the_budget(tmp_path):
    _url_source(tmp_path)
    (tmp_path / _CACHE).parent.mkdir(parents=True)
    (tmp_path / _CACHE).write_text(_BODY, encoding="utf-8")
    page = _page(
        tmp_path,
        "  - type: url\n    url: https://example.com/1\n"
        f"  - type: url\n    url: {_URL}\n    hash: {_HASH}\n"
        "  - type: manual\n"
        "  - type: url\n    url: https://example.com/4\n",
    )
    clock, fetcher = _Clock(step=100), _Fetcher()
    got = resolver.obtain_sources(page, "review", tmp_path, fetch=_timed(clock, fetcher), budget=45, clock=clock)
    assert [(e["index"], e["result"]) for e in got] == [(1, "READ"), (2, "READ"), (3, "MANUAL"), (4, "CONTINUE")]


def test_a_resumed_call_keeps_the_scratch_files_the_earlier_call_named(tmp_path):
    refetch = tmp_path / ".wikicommit/.cache/refetch"
    refetch.mkdir(parents=True)
    for name in ("review-1.md", "review-2.md", "review-3.md"):
        (refetch / name).write_text("x\n", encoding="utf-8")
    page = _page(tmp_path, _urls(3))
    fetcher = _Fetcher(code=1)
    got = resolver.obtain_sources(page, "review", tmp_path, fetch=fetcher, start=3)
    assert [e["index"] for e in got] == [3]
    assert [url for url, _ in fetcher.calls] == ["https://example.com/3"]
    assert (refetch / "review-1.md").exists() and (refetch / "review-2.md").exists()
    assert not (refetch / "review-3.md").exists()


def test_after_two_environment_failures_in_a_row_the_rest_is_not_fetched(tmp_path):
    page = _page(tmp_path, _urls(4))
    fetcher = _Fetcher(code=3)
    got = resolver.obtain_sources(page, "review", tmp_path, fetch=fetcher)
    assert [(e["result"], e["reason"]) for e in got] == [("UNAVAILABLE", "environment")] * 4
    assert len(fetcher.calls) == 2
    assert got[2]["message"] == "not fetched: the network was unavailable for [1] and [2]"


def test_one_environment_failure_does_not_stop_the_rest(tmp_path):
    """A vanished domain's DNS failure looks like no network: one alone stops nothing."""
    page = _page(tmp_path, _urls(4))
    codes = iter([3, 0, 3, 0])
    calls = []

    def fetch(url, output, repo_root):
        calls.append(url)
        return _Fetcher(code=next(codes))(url, output, repo_root)

    got = resolver.obtain_sources(page, "review", tmp_path, fetch=fetch)
    assert len(calls) == 4
    assert [e["result"] for e in got] == ["UNAVAILABLE", "READ", "UNAVAILABLE", "READ"]


def test_a_fetch_failure_resets_the_environment_streak(tmp_path):
    page = _page(tmp_path, _urls(4))
    codes = iter([3, 1, 3, 0])
    calls = []

    def fetch(url, output, repo_root):
        calls.append(url)
        return _Fetcher(code=next(codes))(url, output, repo_root)

    resolver.obtain_sources(page, "review", tmp_path, fetch=fetch)
    assert len(calls) == 4


def test_the_cli_prints_continue_after_the_summary_and_resumes_with_from(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/notes.md").write_text("notes\n", encoding="utf-8")
    page = _page(
        tmp_path,
        "  - type: path\n    path: raw/notes.md\n"
        "  - type: url\n    url: https://example.invalid/a\n"
        "  - type: url\n    url: https://example.invalid/b\n",
    )
    rel = str(page.relative_to(tmp_path))
    # Budget 0: the first fetch still starts; the second is left for --from.
    got = _cli(tmp_path, rel, "--label", "review", "--budget", "0")
    assert got.returncode == 0, got.stderr
    lines = got.stdout.splitlines()
    assert lines[0] == "READ: [1] raw/notes.md page=mismatch"
    assert lines[1].startswith("UNAVAILABLE: [2] ")
    assert lines[2:] == [
        "SUMMARY: entries=2 read=1 extract=0 retracted=0 unavailable=1 manual=0",
        "CONTINUE: next=3",
    ]
    resumed = _cli(tmp_path, rel, "--label", "review", "--budget", "0", "--from", "3")
    assert resumed.returncode == 0, resumed.stderr
    lines = resumed.stdout.splitlines()
    assert lines[0].startswith("UNAVAILABLE: [3] ")
    assert lines[1:] == ["SUMMARY: entries=1 read=0 extract=0 retracted=0 unavailable=1 manual=0"]


@pytest.mark.parametrize("args", [("--from", "0"), ("--budget", "-1")], ids=["from-0", "negative-budget"])
def test_the_cli_refuses_a_bad_from_or_budget(tmp_path, args):
    (tmp_path / "page.md").write_text("---\nsources: []\n---\n", encoding="utf-8")
    got = _cli(tmp_path, "page.md", "--label", "review", *args)
    assert got.returncode == 1 and got.stdout == ""


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_each_skill_calls_again_with_from_on_continue(name):
    text = TEXTS[name]
    assert "CONTINUE: next=<n>" in text and "--from <n>" in text, (
        f"{name} does not say to call again with --from when the time budget runs out"
    )
