"""Tests for dev/review-evals/ (Issue #1081): the sampling and tally helpers.

These run against a synthetic pilot tree; nothing here reaches the network.
"""

import csv
import importlib.util
import json
from pathlib import Path

import pytest
from _publication import is_development_repository

HERE = Path(__file__).parent.parent / "dev" / "review-evals"

# dev/ is not published, so the published snapshot has nothing to test here.
# The skip has to happen before the module-level loads below, which would
# otherwise fail at collection (a pytestmark is evaluated too late for that).
if not is_development_repository():
    pytest.skip(
        "published snapshot: dev/review-evals/ is intentionally not published",
        allow_module_level=True,
    )


def _load(name):
    spec = importlib.util.spec_from_file_location(f"review_evals_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_scripts_under_test_exist():
    for name in ("sample", "tally", "label"):
        assert (HERE / f"{name}.py").is_file(), (
            f"{HERE / name}.py is missing from the development repository. If it moved, "
            "follow it here rather than letting these tests skip themselves away."
        )


sample = _load("sample")
tally = _load("tally")
label = _load("label")


def test_wilson_interval_matches_the_worked_example():
    lo, hi = tally.wilson(24, 30)
    assert round(lo, 2) == 0.63 and round(hi, 2) == 0.90


def test_wilson_does_not_break_at_zero_or_all():
    assert tally.wilson(0, 10)[0] == 0.0 and tally.wilson(0, 10)[1] > 0
    assert tally.wilson(10, 10)[1] == 1.0 and tally.wilson(10, 10)[0] < 1
    assert tally.wilson(0, 0) == (0.0, 1.0)


def test_risky_rule_matches_check_review_coverage():
    assert sample.is_risky({"attempts": 2, "findings": []})
    assert sample.is_risky({"attempts": 1, "findings": [{"type": "X"}]})
    assert not sample.is_risky({"attempts": 1, "findings": []})
    assert not sample.is_risky(None)


def test_cache_path_maps_to_its_management_file():
    assert sample.management_file_for(".wikicommit/.cache/ingest-fetch/example.com/a.md") == \
        Path(".wikicommit/source/url/example.com/a.md")
    assert sample.management_file_for(".wikicommit/.cache/extract-path/raw/p.pdf.md") == \
        Path(".wikicommit/source/path/raw/p.pdf.md")
    assert sample.management_file_for("raw/notes.md") is None


def _page(root, rel, fm, body="Body.\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm}---\n\n{body}", encoding="utf-8")
    return p


def test_sample_splits_strata_hides_the_key_and_skips_unverifiable_findings(tmp_path):
    import hashlib

    root = tmp_path / "pilot"
    raw = root / "raw" / "notes.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("line one\nline two\n", encoding="utf-8")
    raw_hash = "sha256:" + hashlib.sha256(raw.read_bytes()).hexdigest()
    src = f"sources:\n  - type: path\n    path: raw/notes.md\n    hash: {raw_hash}\n"
    _page(root, ".wikicommit/entity/en/Person/a.md", 'title: "A"\nlang: en\ntype: "schema:Person"\n' + src)
    _page(root, ".wikicommit/entity/en/Person/b.md", 'title: "B"\nlang: en\ntype: "schema:Person"\n' + src)
    import os
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / ".wikicommit" / "scripts"))
    from record_review import compute_page_content_hash
    cwd = os.getcwd()
    os.chdir(root)
    try:
        page_hash = compute_page_content_hash(Path(".wikicommit/entity/en/Person/b.md"))
    finally:
        os.chdir(cwd)
    rev = root / ".wikicommit/review/entity/en/Person"
    common = (f"kind: ai\nstage: generate-pass4\nmodel: m\npage_content_hash: '{page_hash}'\n"
              f"reviewed_sources:\n  - type: path\n    path: raw/notes.md\n    hash: {raw_hash}\n")
    _page(rev, "a/20260901-000000-ai.md", common + "attempts: 2\nresult: pass\nfindings:\n"
          "  - round: 1\n    type: HALLUCINATION\n    claim: Claim one\n    source_file: raw/notes.md\n"
          "    source_lines: L1-L2\n    instruction: SECRET-INSTRUCTION\n"
          "  - round: 1\n    type: MISSING_SOURCE\n    claim: Claim two\n    source_file: ''\n"
          "  - round: 1\n    type: CONTRADICTION\n    claim: Claim three\n"
          "    source_file: .wikicommit/entity/en/Person/b.md\n    source_lines: L1\n"
          "  - round: 2\n    type: HALLUCINATION\n    claim: Later round\n    source_file: raw/notes.md\n"
          "    source_lines: L1\n", "")
    _page(rev, "b/20260901-000000-ai.md", common + "attempts: 1\nresult: pass\nfindings: []\n", "")
    out = tmp_path / "out"
    assert sample.main([str(root), "--out-dir", str(out), "--no-fetch"]) == 0

    items = list(csv.DictReader(open(out / "items.csv", encoding="utf-8")))
    key = {r["item_id"]: r for r in csv.DictReader(open(out / "key.csv", encoding="utf-8"))}
    assert {r["claim"] for r in items if r["unit"] == "finding"} == {"Claim one"}
    assert "SECRET-INSTRUCTION" not in (out / "items.csv").read_text(encoding="utf-8")
    assert "stratum" not in items[0] and "model" not in items[0]
    assert sorted(k["stratum"] for k in key.values()) == ["A", "B"]
    strata = json.loads((out / "strata.json").read_text(encoding="utf-8"))
    assert strata["risky"] == 1 and strata["not_risky"] == 1
    assert strata["skipped_a"]["no_source_file"] == 1
    assert strata["skipped_a"]["cross_page"] == 1


def test_line_ranges_reads_numbers_and_leaves_section_names_alone():
    assert label.line_ranges("12-15") == [(12, 15)]
    assert label.line_ranges("L1-L2") == [(1, 2)]
    assert label.line_ranges("646-660; 210-240") == [(646, 660), (210, 240)]
    assert label.line_ranges("44, 50") == [(44, 44), (50, 50)]
    assert label.line_ranges("1-232 (whole document; nearest at line 29)") == [(1, 232)]
    assert label.line_ranges("Section 4.2, opening para") == []
    assert label.line_ranges("") == []


def test_split_ref_separates_sources_from_the_line_reference():
    assert label.split_ref("https://a/x lines 12-15") == (["https://a/x"], "12-15")
    assert label.split_ref("https://a/x; https://b/y") == (["https://a/x", "https://b/y"], "")


def test_record_label_writes_only_that_row_and_rejects_unknown_labels(tmp_path):
    items = tmp_path / "items.csv"
    items.write_text(
        "item_id,unit,page,claim,source_ref,human_label,human_note,labeled_at\n"
        'i001,finding,p.md,"a, b",https://a lines 1,,,\n'
        "i002,page,q.md,,https://b,,,\n", encoding="utf-8")
    label.record_label(items, "i002", "ok", "fine", "2026-10-02")
    rows = {r["item_id"]: r for r in label.read_items(items)}
    assert (rows["i002"]["human_label"], rows["i002"]["human_note"], rows["i002"]["labeled_at"]) == \
        ("ok", "fine", "2026-10-02")
    assert rows["i001"]["human_label"] == "" and rows["i001"]["claim"] == "a, b"
    label.record_label(items, "i002", "defect", None, "2026-10-03")
    assert label.read_items(items)[1]["human_note"] == "fine"  # no --note keeps the old note
    with pytest.raises(ValueError):
        label.record_label(items, "i001", "maybe", None, "2026-10-02")
    with pytest.raises(KeyError):
        label.record_label(items, "i999", "ok", None, "2026-10-02")


def test_label_never_reads_the_key():
    assert "key.csv" not in (HERE / "label.py").read_text(encoding="utf-8").replace(
        "Nothing here reads key.csv.", "")


def test_pilot_identity_reads_the_github_remote(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "https://github.com/owner/wiki.git"], check=True)
    assert sample.pilot_identity(tmp_path)["repo"] == "owner/wiki"


def test_site_url_follows_the_published_layout():
    pilot = {"repo": "owner/wiki", "commit": "abc"}
    assert label.site_url(pilot, ".wikicommit/entity/en/BlogPosting/x-y.md") == \
        "https://owner.github.io/wiki/en/blogposting/x-y"
    assert label.site_url(pilot, ".wikicommit/view/ja/z.md") == "https://owner.github.io/wiki/ja/view/z"
