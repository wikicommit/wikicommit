#!/usr/bin/env python3
"""Convert [[Type/slug]] WikiLinks to relative Markdown links for the Quartz build.

Usage:
    python .wikicommit/scripts/convert_wikilinks.py \
        --source .wikicommit/entity/ \
        --output content/ \
        [--primary-lang ja]

Mirrors every .md file under --source into --output, rewriting [[Type/slug]]
WikiLinks into relative Markdown links ([Type/slug](../Type/slug.md)). Links
that cannot be resolved are left untouched and reported as warnings.

Also generates a build-time-only, language-independent content/sources/
tree mirroring .wikicommit/source/ 1:1 — one page per source management
file, plus a content/sources/index.md landing page (Issue #476, replacing
the old per-language content/<lang>/sources.md aggregation keyed off each
page's own `sources` frontmatter — see generate_source_pages()). Like
generate_root_index()'s content/index.md, none of this is LLM-authored wiki
content and all of it is excluded from the review_status /
validate_frontmatter.py quality gate contract.

Exit code: always 0 (unresolved links are warnings only; check_wikilinks.py
is responsible for blocking on broken links during the quality gate).
"""

import argparse
import json
import os
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

import yaml

from _frontmatter import parse_frontmatter_and_body_text, parse_frontmatter_cached
from _wikilink import (
    VIEW_DIR,
    VIEW_TYPE_SEGMENT,
    WIKILINK_RE,
    collect_view_pages,
    load_primary_lang,
    other_types_for_slug,
    parse_view_path,
    parse_wiki_path,
)
# Issue #751: the AI review record is a second input tree for this build. Both
# helpers are imported rather than reimplemented — check_review_coverage.py
# answers "is this verdict still valid?" for the operator and this script asks
# the same question for the reader, and two copies of that judgement would
# drift into a banner that contradicts `/wikicommit-status`.
from _groups import load_group_file
from check_review_coverage import (
    latest_by_kind,
    load_records,
    matches_recorded_content,
    stale_reasons,
    standing_verdict,
)
from record_review import ACCEPTED_PREFIXES, REVIEW_DIR, RecordError

# The finding types `.wikicommit/review-rules.md` defines, in the order the
# overview lists them. Anything else a record carries — a missing `type`, or a
# value outside this set — is counted under OTHER_FINDING_TYPE rather than
# guessed into one of these (Issue #1063).
FINDING_TYPES = ("HALLUCINATION", "CONTRADICTION", "MISSING_SOURCE")
OTHER_FINDING_TYPE = "OTHER"


# The page trees this script reserves directly under `content/` (Issue #957).
#
# Both are build-generated: `sources/` mirrors `.wikicommit/source/` (Issue #476)
# and `overview/` is the survey page (Issue #585). Neither is an entity path, so
# both publishing plugins have to know them by name — the graph to keep
# `overview/` out of the language facet, the explorer to keep both out of the
# Type folders. Issue #585 registered `overview` with neither, and the symptom in
# each case was silent: a fake language in one control bar, a stray folder in the
# other. `tests/test_publish_reserved_trees.py` now asserts that every name here
# appears in all three plugin sources.
#
# Deliberately not listed: `tags/` is written by Quartz, not by this script (the
# explorer drops it through `filterFn`, not `sortTier`), and `assets/` holds no
# `.md` at all, so neither plugin ever sees a node or a folder for it.
SOURCES_DIR_NAME = "sources"
OVERVIEW_DIR_NAME = "overview"
RESERVED_PUBLISH_TREES = (SOURCES_DIR_NAME, OVERVIEW_DIR_NAME)


# Stamped onto the published copy of a page, never onto the page itself
# (Issue #751). Naming them apart from `reviewed_by` is deliberate: that field
# is the human who closed the tracking Issue (Issue #663), and a reader must
# not read one as the other.
AI_REVIEW_MODEL_FIELD = "ai_review_model"
AI_REVIEW_AT_FIELD = "ai_review_at"
# Written only for a translation checked against its original page (Issue
# #1031), so every other page publishes byte-for-byte as before.
AI_REVIEW_STAGE_FIELD = "ai_review_stage"
TRANSLATE_CHECK_STAGE = "translate-check"


def load_ai_review(src_path: Path, repo_root: Path, page_fm: dict | None = None) -> dict | None:
    """The AI review verdict that still stands for `src_path`, or None.

    Returns `{"model", "reviewed_at", "findings"}` for the newest `kind: ai`
    record whose `page_content_hash` still matches the page on disk.

    Four ways this returns None, and all four must publish the page exactly as
    it published before this feature existed:

    - **No record.** The page predates Issue #750; a record cannot be made
      retroactively, so the blank is permanent and honest.
    - **The verdict is not a pass.** See below.
    - **The verdict is stale.** `/wikicommit-fix` rewrote the page after the
      review, or a source it was judged against changed or left the page, so
      the verdict was made against material that is no longer there. This is
      the reason Issue #751 stamps at publish time instead of copying the
      verdict into the page's own frontmatter: a copy cannot notice it has gone
      stale, which is the failure Issue #705 already cost this repository once.
    - **The record is unreadable**, or the page's own frontmatter will not
      parse. A build must not fail over an annotation.

    `standing_verdict()` — not simply the last record — because a
    `result: discarded` record carries an empty hash and describes a page that
    was never written, so it says nothing about the file being published here.

    Only a `result: pass` verdict is published. `standing_verdict()` answers
    "which record is the current one", which is all `/wikicommit-status` needs
    to measure staleness against — but `wikicommit-review` records
    `--result fail` when its fact-check found something, against a page that is
    still on disk. Publishing that as "checked against sources" would put a
    passing badge on the one page whose latest check failed, and count its
    unfixed findings among those "raised and fixed before publishing". An older
    `pass` is not fallen back to either: a later failure does not stop applying
    because an earlier check once succeeded.
    """
    try:
        page_rel = src_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (ValueError, OSError):
        page_rel = src_path.as_posix()

    # record_dir_for() strips a fixed `.wikicommit/` prefix, so a page reached
    # through some other --source root would map to a nonsense directory rather
    # than to no directory. No record can exist for such a page anyway: every
    # writer of the tree refuses a path outside these prefixes.
    if not page_rel.startswith(ACCEPTED_PREFIXES):
        return None

    try:
        record = standing_verdict(load_records(page_rel))
    except OSError as e:
        print(f"WARNING: {src_path}: review records could not be read: {e}")
        return None
    if record is None or str(record.get("result") or "") != "pass":
        return None

    # The same comparison `/wikicommit-status` makes, including its tolerance
    # for a merge's link rewrite, so the banner and `STALE_REVIEW:` agree.
    try:
        unchanged = matches_recorded_content(src_path, str(record.get("page_content_hash") or ""))
    except (RecordError, OSError, ValueError) as e:
        print(f"WARNING: {src_path}: the page content hash could not be computed: {e}")
        return None
    if not unchanged:
        return None
    # The other half of staleness, borrowed rather than restated: a source that
    # changed or left the page moved the evidence out from under the verdict
    # even though the prose is untouched (`sources` is one of the bookkeeping
    # fields the hash above ignores). Reimplementing only the hash comparison
    # here is what would produce the banner that contradicts
    # `/wikicommit-status`, which is the drift the shared import exists to
    # avoid. Fails closed: a page whose own frontmatter would not parse reaches
    # this with an empty mapping, so every reviewed source reads as gone.
    if stale_reasons(src_path, page_fm or {}, record):
        return None

    model = str(record.get("model") or "").strip()
    reviewed_at = str(record.get("reviewed_at") or "").strip()
    if not model or not reviewed_at:
        # A record this incomplete cannot produce the line the banner renders,
        # and half a line ("reviewed on <blank>") is worse than none.
        return None
    # _yaml_quote() escapes quotes and backslashes but cannot escape a line
    # break, so a value containing one would end the frontmatter's own line and
    # write whatever followed as further keys — on every page that record
    # covers. Records are written by another process, so this is checked here
    # rather than assumed.
    if any(ch in model or ch in reviewed_at for ch in ("\n", "\r")):
        print(f"WARNING: {src_path}: a review record value contains a line break, so it is not displayed")
        return None

    return {
        "model": model,
        "reviewed_at": reviewed_at,
        # Issue #1031: what the page was checked against. `translate-check`
        # compared a translation with its original page, not with sources, and
        # every reader-facing surface has to say so rather than fold it into
        # "checked against sources".
        "stage": str(record.get("stage") or ""),
        "findings_by_type": count_findings_by_type(record.get("findings")),
    }


def count_findings_by_type(findings: object) -> dict[str, int]:
    """Tally a record's findings by `type`, leaving out the ones about other pages.

    A `page_at_fault: other` entry reports that a *neighbouring* page looks wrong
    (a non-blocking cross-page finding); nothing was rewritten on this page for
    it, so counting it among the findings "raised and fixed before publishing"
    would overstate what the check did here (Issue #1063). Only the exact string
    `other` is dropped: drifted values such as `this` / `self` are about this
    page and stay counted.
    """
    counts: dict[str, int] = {}
    if not isinstance(findings, list):
        return counts
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if str(finding.get("page_at_fault") or "") == "other":
            continue
        kind = str(finding.get("type") or "")
        key = kind if kind in FINDING_TYPES else OTHER_FINDING_TYPE
        counts[key] = counts.get(key, 0) + 1
    return counts


def count_unpublished_pages(repo_root: Path) -> int:
    """How many pages the review threw away before they were ever published.

    A page counts when its newest `kind: ai` record is `result: discarded` and
    the page is not on disk. A discarded `action: update` does not count: the
    earlier version stays published, so "not published" would be false for it.
    Neither does a page discarded once and passed on a later run — its newest
    record is the pass. Entity and view pages alike (synthesize Step 5.5 also
    discards).

    This is the one tally on the overview that is not a by-product of the page
    walk: a page that is not on disk is never reached by it, so the record tree
    is walked once more (Issue #1063). Records are read with the same helpers
    `/wikicommit-status` uses, relative to the working directory, as
    load_ai_review() does.
    """
    root = repo_root / REVIEW_DIR
    if not root.is_dir():
        return 0
    count = 0
    for directory in sorted({p.parent for p in root.rglob("*.md")}):
        page_rel = f".wikicommit/{directory.relative_to(root).as_posix()}.md"
        if not page_rel.startswith(ACCEPTED_PREFIXES) or (repo_root / page_rel).exists():
            continue
        try:
            latest = latest_by_kind(load_records(page_rel), "ai")
        except OSError as e:
            print(f"WARNING: {directory}: review records could not be read: {e}")
            continue
        if latest is not None and str(latest.get("result") or "") == "discarded":
            count += 1
    return count


def inject_frontmatter_lines(content: str, lines: list[str]) -> str:
    """Insert `lines` at the end of `content`'s frontmatter block.

    Textual insertion rather than a YAML round-trip: this runs over every wiki
    page, and `yaml.safe_load` + `yaml.dump` would reformat quoting, reorder
    keys and drop comments across the whole published site — the same round-trip
    that cost this repository a config file's worth of comments (Issue #713).

    A page with no frontmatter, or with an unterminated one, is returned
    unchanged. Those are `validate_frontmatter.py`'s to report; a publish step
    inventing a frontmatter block for them would be a bigger change than the
    annotation is worth.
    """
    if not lines or not content.startswith("---"):
        return content
    newline = "\r\n" if content.startswith("---\r\n") else "\n"
    first = content.find(newline)
    if first == -1:
        return content
    if content[:first].strip() != "---":
        return content
    closing = content.find(f"{newline}---", first)
    if closing == -1:
        return content
    insertion = "".join(f"{newline}{line}" for line in lines)
    return content[:closing] + insertion + content[closing:]


def load_frontmatter(path: Path) -> dict | None:
    """Return path's frontmatter as a dict, or None if unreadable/not a mapping.

    Delegates to _frontmatter.parse_frontmatter_cached(), which caches the
    (dict, error) parse result per path for the run: is_removed() and
    generate_source_pages() (looking up each generated_pages[] entry's title)
    both re-read the same wiki pages across the two directory walks in
    main(), and is_removed() in particular is called once per WikiLink (many
    links can point at the same target across many source files).
    """
    fm, err = parse_frontmatter_cached(path)
    return None if err else fm


def is_removed(path: Path) -> bool:
    """Return True if path's frontmatter has status: removed."""
    fm = load_frontmatter(path)
    return bool(fm) and fm.get("status") == "removed"


def _config_section(repo_root: Path, key: str) -> dict:
    """Return .wikicommit/config.yml's top-level `key` as a dict, or {} if the
    file is missing/unreadable/not a mapping, or `key` is absent or not a
    mapping itself.

    Every load_*() below reads the same file with the same tolerance, so they
    share one reader instead of each carrying its own try/except: an empty dict
    here reproduces each caller's own fallback ("en" / [] / {}) through the
    .get() default it already had.
    """
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    section = data.get(key)
    return section if isinstance(section, dict) else {}


def load_translation_targets(repo_root: Path) -> list[str]:
    targets = _config_section(repo_root, "translation").get("targets") or []
    if not isinstance(targets, list):
        return []
    return [str(t) for t in targets]


def load_site_description(repo_root: Path) -> dict[str, str]:
    """Return .wikicommit/config.yml's top-level `site_description` as a
    {lang: text} mapping (Issue #671: the reader-facing counterpart to `theme`).

    `theme` tells the LLM what this wiki's subject scope is — one string, read by
    wikicommit-generate Pass 2c and wikicommit-collect, never by a reader
    (Issue #670). This one is written *for* readers, so it needs one entry per
    language they might arrive in. The two are deliberately independent: no rule
    derives either from the other, and both may be absent.

    Tolerant like load_theme() was: anything that is not a mapping of
    language code to non-empty string is dropped, and a missing/unreadable
    config yields {}. A malformed description must not take the whole build
    down — the caller simply omits the line, which is also what an unset
    field does.

    Internal whitespace is collapsed to single spaces, not just stripped at the
    ends. The main rendering site is one Markdown list item per language, so a
    value carrying its own newlines (a YAML `|` block is a natural way to write
    three sentences) would otherwise be pasted verbatim into that item: a blank
    line inside it terminates the language list, leaving the remaining languages
    in a second list with a stray paragraph between. One line in, one line out.
    """
    result = {}
    for lang, text in _config_section(repo_root, "site_description").items():
        if isinstance(lang, str) and isinstance(text, str) and text.split():
            result[lang] = " ".join(text.split())
    return result


def _yaml_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def existing_lang_targets(
    source_dir: Path, targets: list[str], view_dir: Path | None = None
) -> list[str]:
    """Filter targets to languages with at least one non-removed content page.

    Both input trees count (Issue #675): a language whose only pages are view
    pages still publishes under `content/<lang>/View/`, and dropping it here
    would leave those pages reachable by direct URL alone, with no entry in the
    root index's language list.
    """
    roots = [source_dir] + ([view_dir] if view_dir is not None else [])
    result = []
    for t in targets:
        if any(
            not (md_path.name == "index.md" or is_removed(md_path))
            for root in roots
            for md_path in (root / t).rglob("*.md")
        ):
            result.append(t)
    return result


# The four *_LABELS dicts below (root index, source type, source page,
# overview) ship ten languages: en (the DEFAULT_* fallback beside each one) and
# ja, de, es, fr, it, ru, zh, pt, pl as entries (Issue #1017). **The set is
# fixed by an external standard, not by which wikis happen to exist**: it is the
# ten languages the Wikipedia portal (wikipedia.org) lists. Before #1017 these
# dicts held ja only, and "add a language when a wiki in it appears" answered
# every new language with "because a pilot happened to use it". Do not widen the
# set past these ten on the same reasoning.
#
# **The non-English entries were produced by an LLM from the English.** Most
# keys are plain labels ("Sources", "Type", "Total pages"). A minority carry
# claims — counts_note, ai_counts_note, licensing, reviewed_note,
# retracted_notice — and each was translated to say no more than the English
# says ("checked against sources" as compared, not verified). If a translation
# reads stronger than the English, fix the translation; the English is
# canonical.
#
# **A partial language is not an option.** These dicts are read with bracket
# access, so one missing key raises KeyError and fails the build. That is a
# guarantee, not a defect — a language is complete or absent, never
# half-rendered. The one exception is SOURCE_TYPE_LABELS, whose values are
# looked up with .get(source_type, source_type) and degrade to the bare type
# string instead. `tests/test_ui_translation_completeness.py` checks every
# entry against the DEFAULT_* keys and placeholders, so a gap is caught before
# a build hits it.
#
# **The language set is kept in step elsewhere**: all four dicts here, the four
# WikiCommit Quartz plugins' locales and init.py's WIKICOMMIT_UI_LANGS.
# `tests/test_ui_language_fallback_disclosure.py` fails if they disagree —
# adding to one dict and not the rest would otherwise be silent (that wiki
# would get a translated root index and English source pages).
#
# **A language outside the ten renders in English**, per surface, via the
# DEFAULT_* dict.
#
# **The published pages do not say that the fallback happened** (Issue #825).
# The question was whether a reader should be told, rather than being shown
# English as if it were the site's language, and the answer is no. Three
# reasons, in the order they decide it:
#
#   - **A notice would not restore what was lost.** The English string *is* the
#     canonical wording — the other language's entry would be a translation of
#     it — so a reader who can read English has already received the claim, and
#     learning that Korean was intended changes nothing about what this wiki
#     vouches for. A reader who cannot read English cannot read the notice
#     either.
#   - **A language-independent marker only restates what is already visible.**
#     A flag or an `(en)` tag says "this is English", which is exactly what
#     English text in a Korean page already says. That was the point of
#     leaving it in English: the failure is visible without help.
#   - **It would be a standing notice on every surface of every page**, one
#     nobody can act on — a reader cannot supply the missing labels. That is the
#     shape a reader stops seeing, and it would buy the fade at the cost of
#     weight on the banner, where two Issues already hold the line against
#     adding any.
#
# **The operator is told instead, once**, by `init.py` when they choose a
# primary_lang this project has no labels for. They are the one person who can
# act on it, and telling them costs the published pages nothing. Do not read
# this as "the fallback is fine and needs no disclosure" — it is disclosed, to
# the party that can do something with it.
ROOT_INDEX_LABELS = {
    "ja": {
        "top": "Wiki トップ",
        "select": "言語を選択",
        "sources": "情報源一覧",
        "overview": "Wiki 全体の俯瞰",
        # Issue #730: appended to each language's link. The whole string,
        # leading separator included, lives in the label because the word order
        # differs per language and there is no separator that reads right in
        # both (Japanese wants none before a full-width parenthesis).
        "counts": "（{pages} ページ / 人が読んで確認 {reviewed}）",
        # Japanese does not inflect for number, so this is the same string. It
        # is spelled out rather than defaulted so that every label set answers
        # the singular case explicitly.
        "counts_one": "（{pages} ページ / 人が読んで確認 {reviewed}）",
        # Issue #730 carries Issue #664's note across: without the two
        # frontmatter fields the banner renders nothing, and the note would
        # vanish with it. A bare "reviewed 0" reads as "nobody cares about this
        # project", which is the opposite of the honesty the count is there for.
        # Kept consistent with the overview page's wording, since the root index
        # links straight to it.
        # Issue #800: says that the human number is partial *by design*, which is
        # what turns it from a backlog into a stated design. Saying only "not a
        # guarantee of correctness" left the reader nothing to draw from the
        # number at all. Sampling vocabulary stays out (Issue #769): whether
        # RISKY: actually selects well is still unmeasured, and the word alone
        # would imply a formal sampling design exists.
        "counts_note": "ページは LLM が生成した時点で公開されます。"
                       "出典との照合は機械が行い、"
                       "「人が読んで確認」はそのうち人が最後まで読み、"
                       "明らかな問題を見つけなかった件数です。"
                       "人による確認は設計上一部のページのみであり、"
                       "この数字が総数に達することは目指していません。"
                       "網羅的な品質保証でもありません。",
        # Issue #769: the same line with the AI count in it. Kept as separate
        # templates rather than assembled from fragments because word order and
        # the parenthesis style differ per language, which is why `counts`
        # carries its own leading separator (Issue #730) in the first place.
        # The AI count comes first: it is the full-coverage number, and
        # "read by a person" is the sample taken out of it — the same order the
        # overview page uses.
        "counts_ai": "（{pages} ページ / 出典と照合 {ai_reviewed} / 人が読んで確認 {reviewed}）",
        "counts_ai_one": "（{pages} ページ / 出典と照合 {ai_reviewed} / 人が読んで確認 {reviewed}）",
        # Issue #769: a separate key, emitted only when some page actually
        # carries a standing verdict. Worded like the overview page's
        # `ai_reviewed_note`: it names what the check does *not* cover, because
        # stating only what it does would rebuild, facing the other way, the
        # overstatement Issue #740 removed from `reviewed`.
        "ai_counts_note": "「出典と照合」は生成時に、ページの記述をその出典と"
                          "照合した件数です。照合しているのは出典との一致だけで、"
                          "網羅性・実在の人物や組織への影響・"
                          "読者自身の知識との食い違いは見ていません。",
        "licensing": "各ページの利用条件は、そのページが生成された出典ごとに異なります。"
                     "サイト全体に単一のライセンスはありません。",
    },
    "de": {
        "top": "Wiki-Startseite",
        "select": "Sprache wählen",
        "sources": "Quellen",
        "overview": "Übersicht",
        "counts": " ({pages} Seiten / {reviewed} von einer Person gelesen und durchgesehen)",
        "counts_one": " ({pages} Seite / {reviewed} von einer Person gelesen und durchgesehen)",
        "counts_note": "Seiten werden veröffentlicht, sobald ein LLM sie generiert. Der Abgleich mit den Quellen erfolgt maschinell; „von einer Person gelesen und durchgesehen“ gibt an, wie viele Seiten seitdem jemand vollständig gelesen hat, ohne dass etwas offensichtlich Falsches aufgefallen ist. Nur ein Teil der Seiten wird von einer Person gelesen, und das ist so gewollt — diese Zahl soll die Gesamtzahl nicht erreichen, und sie ist keine vollständige Qualitätsgarantie.",
        "counts_ai": " ({pages} Seiten / {ai_reviewed} mit Quellen abgeglichen / {reviewed} von einer Person gelesen und durchgesehen)",
        "counts_ai_one": " ({pages} Seite / {ai_reviewed} mit Quellen abgeglichen / {reviewed} von einer Person gelesen und durchgesehen)",
        "ai_counts_note": "„Mit Quellen abgeglichen“ gibt an, wie viele Seiten bei ihrer Generierung mit ihren eigenen Quellen verglichen wurden. Dieser Abgleich prüft nur die Übereinstimmung mit diesen Quellen und nichts anderes — nicht die Vollständigkeit, nicht die Auswirkungen auf reale Personen und Organisationen, nicht Widersprüche zu dem, was Sie wissen.",
        "licensing": "Die Nutzungsbedingungen unterscheiden sich von Seite zu Seite, je nach den Quellen, aus denen die Seite generiert wurde. Es gibt keine einheitliche Lizenz für die gesamte Website.",
    },
    "es": {
        "top": "Inicio de la wiki",
        "select": "Seleccionar idioma",
        "sources": "Fuentes",
        "overview": "Panorama general",
        "counts": " ({pages} páginas / {reviewed} leídas y revisadas por una persona)",
        "counts_one": " ({pages} página / {reviewed} leídas y revisadas por una persona)",
        "counts_note": "Las páginas se publican en cuanto un LLM las genera. El cotejo con las fuentes lo hace una máquina; «leídas y revisadas por una persona» es cuántas páginas ha leído después alguien de principio a fin sin que nada saltara a la vista como claramente erróneo. Por diseño, solo algunas páginas las lee una persona: esta cifra no pretende llegar al total y no es una garantía completa de calidad.",
        "counts_ai": " ({pages} páginas / {ai_reviewed} cotejadas con las fuentes / {reviewed} leídas y revisadas por una persona)",
        "counts_ai_one": " ({pages} página / {ai_reviewed} cotejadas con las fuentes / {reviewed} leídas y revisadas por una persona)",
        "ai_counts_note": "«Cotejadas con las fuentes» es cuántas páginas se compararon con sus propias fuentes al generarse. Ese cotejo abarca la concordancia con esas fuentes y nada más: ni la exhaustividad, ni el efecto sobre personas y organizaciones reales, ni los conflictos con lo que tú sabes.",
        "licensing": "Las condiciones de uso varían según la página, en función de las fuentes a partir de las que se generó cada una. No hay una licencia única que cubra todo el sitio.",
    },
    "fr": {
        "top": "Accueil du wiki",
        "select": "Choisir la langue",
        "sources": "Sources",
        "overview": "Vue d'ensemble",
        "counts": " ({pages} pages / {reviewed} lues et examinées par une personne)",
        "counts_one": " ({pages} page / {reviewed} lue(s) et examinée(s) par une personne)",
        "counts_note": "Les pages sont publiées dès qu'un LLM les génère. La comparaison avec les sources est effectuée par une machine ; « lues et examinées par une personne » indique combien de pages quelqu'un a depuis lues en entier sans que rien de manifestement faux n'ait été relevé. Seules certaines pages sont lues par une personne, par choix — ce nombre n'a pas vocation à atteindre le total, et ce n'est pas une garantie de qualité complète.",
        "counts_ai": " ({pages} pages / {ai_reviewed} comparées aux sources / {reviewed} lues et examinées par une personne)",
        "counts_ai_one": " ({pages} page / {ai_reviewed} comparée(s) aux sources / {reviewed} lue(s) et examinée(s) par une personne)",
        "ai_counts_note": "« Comparées aux sources » indique combien de pages ont été comparées à leurs propres sources lors de leur génération. Cette comparaison porte sur la concordance avec ces sources et rien d'autre — ni l'exhaustivité, ni l'effet sur des personnes et organisations réelles, ni les contradictions avec ce que vous savez.",
        "licensing": "Les conditions d'utilisation varient d'une page à l'autre, selon les sources à partir desquelles chaque page a été générée. Aucune licence unique ne couvre l'ensemble du site.",
    },
    "it": {
        "top": "Home del wiki",
        "select": "Seleziona la lingua",
        "sources": "Fonti",
        "overview": "Panoramica",
        "counts": " ({pages} pagine / lette e controllate da una persona: {reviewed})",
        "counts_one": " ({pages} pagina / lette e controllate da una persona: {reviewed})",
        "counts_note": "Le pagine vengono pubblicate non appena un LLM le genera. Il confronto con le fonti è eseguito da una macchina; \"lette e controllate da una persona\" indica quante pagine qualcuno ha poi letto per intero senza notare nulla di palesemente sbagliato. Per scelta, solo alcune pagine vengono lette da una persona: questo numero non è pensato per raggiungere il totale e non è una garanzia di qualità completa.",
        "counts_ai": " ({pages} pagine / confrontate con le fonti: {ai_reviewed} / lette e controllate da una persona: {reviewed})",
        "counts_ai_one": " ({pages} pagina / confrontate con le fonti: {ai_reviewed} / lette e controllate da una persona: {reviewed})",
        "ai_counts_note": "\"Confrontate con le fonti\" indica quante pagine sono state confrontate con le proprie fonti al momento della generazione. Il confronto riguarda solo la concordanza con quelle fonti e nient'altro: non la completezza, non gli effetti su persone e organizzazioni reali, non i contrasti con ciò che sai.",
        "licensing": "Le condizioni d'uso variano da pagina a pagina, in base alle fonti da cui ciascuna pagina è stata generata. Non esiste un'unica licenza per l'intero sito.",
    },
    "pl": {
        "top": "Strona główna wiki",
        "select": "Wybierz język",
        "sources": "Źródła",
        "overview": "Przegląd",
        "counts": " (stron: {pages} / przeczytane i sprawdzone przez człowieka: {reviewed})",
        "counts_one": " (strona: {pages} / przeczytane i sprawdzone przez człowieka: {reviewed})",
        "counts_note": "Strony są publikowane od razu po wygenerowaniu przez LLM. Porównanie ze źródłami wykonuje maszyna; „przeczytane i sprawdzone przez człowieka” oznacza, ile stron ktoś od tego czasu przeczytał w całości, nie zauważając niczego wyraźnie błędnego. Z założenia człowiek czyta tylko część stron — ta liczba nie ma osiągnąć łącznej liczby stron i nie stanowi pełnej gwarancji jakości.",
        "counts_ai": " (stron: {pages} / porównane ze źródłami: {ai_reviewed} / przeczytane i sprawdzone przez człowieka: {reviewed})",
        "counts_ai_one": " (strona: {pages} / porównane ze źródłami: {ai_reviewed} / przeczytane i sprawdzone przez człowieka: {reviewed})",
        "ai_counts_note": "„Porównane ze źródłami” oznacza, ile stron w chwili generowania porównano z ich własnymi źródłami. To porównanie obejmuje wyłącznie zgodność z tymi źródłami — nie kompletność, nie wpływ na rzeczywiste osoby i organizacje, nie sprzeczności z tym, co wiesz.",
        "licensing": "Warunki korzystania różnią się między stronami i zależą od źródeł, z których dana strona została wygenerowana. Nie ma jednej licencji obejmującej całą witrynę.",
    },
    "pt": {
        "top": "Início do Wiki",
        "select": "Selecionar idioma",
        "sources": "Fontes",
        "overview": "Visão geral",
        "counts": " ({pages} páginas / {reviewed} lidas e conferidas por uma pessoa)",
        "counts_one": " ({pages} página / {reviewed} lidas e conferidas por uma pessoa)",
        "counts_note": "As páginas são publicadas assim que um LLM as gera. A conferência com as fontes é feita por máquina; \"lidas e conferidas por uma pessoa\" é quantas páginas alguém leu depois até o fim sem que nada obviamente errado chamasse a atenção. Por design, apenas algumas páginas são lidas por uma pessoa — este número não pretende chegar ao total e não é uma garantia completa de qualidade.",
        "counts_ai": " ({pages} páginas / {ai_reviewed} conferidas com as fontes / {reviewed} lidas e conferidas por uma pessoa)",
        "counts_ai_one": " ({pages} página / {ai_reviewed} conferidas com as fontes / {reviewed} lidas e conferidas por uma pessoa)",
        "ai_counts_note": "\"Conferidas com as fontes\" é quantas páginas foram comparadas com suas próprias fontes quando foram geradas. Essa conferência cobre a concordância com essas fontes e nada mais — não a completude, não o efeito sobre pessoas e organizações reais, não conflitos com o que você sabe.",
        "licensing": "Os termos de uso variam por página, conforme as fontes a partir das quais cada página foi gerada. Não há uma licença única que cubra o site inteiro.",
    },
    "ru": {
        "top": "Главная вики",
        "select": "Выберите язык",
        "sources": "Источники",
        "overview": "Обзор",
        "counts": " (страниц: {pages} / прочитано и проверено человеком: {reviewed})",
        "counts_one": " ({pages} страница / прочитано и проверено человеком: {reviewed})",
        "counts_note": "Страницы публикуются сразу после того, как их сгенерировала LLM. Сверку с источниками выполняет машина; «прочитано и проверено человеком» — это число страниц, которые кто-то затем прочитал целиком и не заметил ничего явно неверного. Человек читает лишь часть страниц, и так задумано: это число не должно достигать общего количества и не является полной гарантией качества.",
        "counts_ai": " (страниц: {pages} / сверено с источниками: {ai_reviewed} / прочитано и проверено человеком: {reviewed})",
        "counts_ai_one": " ({pages} страница / сверено с источниками: {ai_reviewed} / прочитано и проверено человеком: {reviewed})",
        "ai_counts_note": "«Сверено с источниками» — это число страниц, которые при генерации сравнивались со своими собственными источниками. Эта проверка охватывает только согласованность с этими источниками и ничего больше — не полноту, не влияние на реальных людей и организации, не противоречия с тем, что знаете вы.",
        "licensing": "Условия использования различаются от страницы к странице — в зависимости от источников, из которых сгенерирована каждая страница. Единой лицензии на весь сайт нет.",
    },
    "zh": {
        "top": "Wiki 首页",
        "select": "选择语言",
        "sources": "来源",
        "overview": "概览",
        "counts": "（{pages} 个页面 / 经人阅读并检查 {reviewed}）",
        "counts_one": "（{pages} 个页面 / 经人阅读并检查 {reviewed}）",
        "counts_note": "页面在 LLM 生成后即会发布。与来源的比对由机器完成；“经人阅读并检查”是指此后有人从头读完、且未发现明显问题的页面数。按照设计，只有部分页面会由人阅读——这个数字并不以达到总数为目标，也不是完整的质量保证。",
        "counts_ai": "（{pages} 个页面 / 已与来源比对 {ai_reviewed} / 经人阅读并检查 {reviewed}）",
        "counts_ai_one": "（{pages} 个页面 / 已与来源比对 {ai_reviewed} / 经人阅读并检查 {reviewed}）",
        "ai_counts_note": "“已与来源比对”是指在生成时与其自身来源进行过比对的页面数。该比对只涵盖与这些来源是否一致，不涉及其他方面——不涉及内容是否完整，不涉及对真实人物和组织的影响，也不涉及与你所了解情况的冲突。",
        "licensing": "各页面的使用条款因其生成所依据的来源而异。本站没有适用于整个网站的单一许可证。",
    },
}
DEFAULT_ROOT_INDEX_LABELS = {
    "top": "Wiki Home",
    "select": "Select language",
    "sources": "Sources",
    "overview": "Overview",
    "counts": " ({pages} pages / {reviewed} read and checked by a person)",
    "counts_one": " ({pages} page / {reviewed} read and checked by a person)",
    "counts_note": "Pages are published as soon as an LLM generates them. The check "
                   "against sources is run by machine; \"read and checked "
                   "by a person\" is how many pages someone has since read all the "
                   "way through without anything obviously wrong standing out. Only "
                   "some pages are read by a person, by design — this number is not "
                   "meant to reach the total, and it is not a complete quality "
                   "guarantee.",
    "counts_ai": " ({pages} pages / {ai_reviewed} checked against sources / "
                 "{reviewed} read and checked by a person)",
    "counts_ai_one": " ({pages} page / {ai_reviewed} checked against sources / "
                     "{reviewed} read and checked by a person)",
    "ai_counts_note": "\"Checked against sources\" is how many pages were compared "
                      "against their own sources when they were generated. That check "
                      "covers agreement with those sources and nothing else — not "
                      "completeness, not the effect on real people and organizations, "
                      "not conflicts with what you know.",
    "licensing": "Terms of use differ per page, following the sources each page was "
                 "generated from. There is no single license covering the whole site.",
}


def compute_langs(
    primary_lang: str, targets: list[str], published_langs: list[str] | None = None
) -> list[str]:
    """Return primary_lang, then targets, then any other language that actually
    has published pages (deduped, first occurrence wins).

    `targets` is the set of languages this wiki declared it translates into, and
    existing_lang_targets() narrows it to those that really have pages (Issue
    #190). `published_langs` closes the opposite gap (Issue #731): a language
    can have real pages without appearing in `targets` at all, and the root
    index is the only entry point that was deriving its language list from
    `targets` alone, so those pages were published but unreachable from the
    front door. The pipeline produces this state itself — `/wikicommit-translate
    <page> --lang <lang>` writes a translation without touching config.yml, and
    its own error message points at that option as the alternative to editing
    `targets` — and it also arises from hand-added pages, from changing
    `primary_lang` later, and from removing a language from `targets` after its
    translations exist.

    Union rather than replacement: existing_lang_targets() admits a language on
    the strength of any non-removed `.md` under it, including one whose path
    never resolves to `<lang>/<Type>/<slug>.md`, whereas `published_langs` is
    built from resolved, published pages only. Dropping the targets side would
    therefore remove languages that are linked today. (Both cover the view tree,
    so that is not the difference between them.)

    Ordering keeps existing sites stable: `targets` is written by a person, so
    its order is theirs to keep, and discovered languages follow it (the caller
    sorts them) rather than interleaving.
    """
    ordered = [primary_lang] + list(targets) + list(published_langs or [])
    return list(dict.fromkeys(lang for lang in ordered if lang))


def generate_root_index(
    output_dir: Path,
    primary_lang: str,
    langs: list[str],
    total_pages: int,
    reviewed_pages: int,
    site_description: dict[str, str] | None = None,
    lang_counts: dict[str, tuple[int, int, int]] | None = None,
    ai_reviewed_pages: int = 0,
) -> None:
    """Write a root content/index.md that links to the wiki top page(s).

    Quartz's FolderPage plugin deliberately skips generating a virtual index
    page for the content root (it filters out the "." folder), so without a
    real index.md the site root never gets an index.html. The content-index
    plugin's RSS feed defaults to the "index" slug regardless, so index.xml
    ends up as the only "index"-named file at the root and is what gets
    served for "/" (GitHub Issue #75).

    Always overwritten, like convert_file(). An earlier version skipped
    writing when content/index.md already existed, reasoning that
    .wikicommit/entity/ has no root-level page by design so a pre-existing file
    could only be a real mirrored page not to be clobbered. In practice that
    guard fired on the file this same function wrote on a previous local
    build (package.json's prebuild script never clears content/ between
    `npm run build`/`npm run preview` runs), permanently freezing this page's
    content — and because main()'s stale-cleanup treats a guard-skipped write
    the same as a real one, the frozen file was never swept up either
    (Issue #358).

    total_pages/reviewed_pages (Issue #407) are embedded as custom frontmatter
    fields so the WikiCommitBanner Quartz component can render a site-wide
    summary (total page count, reviewed count) on this page without re-deriving
    them from `allFiles` at render time — this script already walks every wiki
    page once in main(), so computing the aggregate here avoids a second,
    TSX-side pass that would have to duplicate the same index.md/removed-page
    exclusions.

    config.yml's `theme` was also embedded here (as `wikicommit_theme`) until
    Issue #670. It is an LLM-facing scope instruction — read by
    wikicommit-generate Pass 2c and wikicommit-collect, not by readers — held as
    a single string in whatever language it was written in, so on a multilingual
    site it reached every reader in one language, and it often carried
    source-selection prose aimed at the generator. A reader-facing site
    description belongs in a field written for readers; it is not this one.

    `site_description` (Issue #671) is that field: {lang: text}, rendered into
    the body rather than the frontmatter. Two reasons it is not another
    frontmatter field for the banner to draw. (1) It is a per-language mapping,
    which does not fit a single frontmatter string. (2) Putting each
    description directly under its own language's link removes the need for a
    "Description:" caption at all, so it sidesteps the banner i18n's two-locale
    limit — a description written in any language reaches that language's
    readers, whereas a caption could not. Languages with no entry simply get no
    description; an absent field reproduces the previous output exactly.

    `lang_counts` (Issue #730, extended by Issue #769) is
    {lang: (pages, reviewed, ai_reviewed)} counted from the pages this build
    published. On a multilingual wiki the two frontmatter fields above are
    omitted entirely and these per-language counts take their place in the body,
    one pair per language link. Two reasons the single
    site-wide total was wrong there. (1) Nobody experiences it: this page exists
    to choose a language, and the wiki behind each choice is one language's
    worth of pages — a translation is the same knowledge again, not more of it.
    (2) It dilutes the reviewed ratio: a fully reviewed original alongside two
    untouched translations reports one third, and that number was reframed by
    Issue #664 as a statement about the trust ladder, so translations drag it
    away from what it means to claim. Splitting pages but not reviewed counts
    would leave (2) intact, so both are split.

    `ai_reviewed_pages` (Issue #769) is the site-wide count of pages carrying a
    standing AI verdict, embedded as a third frontmatter field on a
    single-language wiki. It is omitted at zero rather than written as 0, and
    that is accuracy rather than tidiness: a wiki predating the review tree has
    no records (they are never created retroactively), which is not the same
    claim as "nothing was checked". On a multilingual wiki the per-language
    third number in `lang_counts` takes its place, for the same reason the other
    two are split there.

    Omitting the two fields is what suppresses the banner's site summary: it
    renders only when both are numbers, so no change to WikiCommitBanner.tsx is
    needed — but Issue #664's note explaining what "reviewed" counts is part of
    that same block and would disappear with it, so it is re-emitted here under
    the language list. A single-language wiki has no language list to hang any
    of this off, so it keeps both fields and the banner as before.

    The "sources" entry point links to content/sources/ — a single,
    language-independent tree (the source tree itself has no `lang` concept) built by
    generate_source_pages(), not one link per lang like the old per-language
    content/<lang>/sources.md this replaced (Issue #476).
    """
    out_path = output_dir / "index.md"
    labels = ROOT_INDEX_LABELS.get(primary_lang, DEFAULT_ROOT_INDEX_LABELS)

    # review_status: reviewed — this is a build-generated navigation page, not
    # LLM-authored wiki content, so it should not show the wikicommit-banner
    # "unreviewed" warning (which defaults to pending when the field is absent).
    counts = lang_counts or {}
    multilingual = len(langs) > 1
    lines = ["---", 'title: "Wiki"', "review_status: reviewed", "comments: false"]
    # Issue #730: on a multilingual wiki these two fields are left out, which is
    # exactly what stops the banner from drawing a site-wide total nobody is
    # about to read — it renders that block only when both are numbers. The
    # per-language counts below replace it.
    if not multilingual:
        lines += [
            f"wikicommit_page_count: {total_pages}",
            f"wikicommit_reviewed_count: {reviewed_pages}",
        ]
        # Issue #769: omitted at zero rather than written as 0, and this is
        # accuracy rather than tidiness. A wiki generated before review records
        # existed has none (they are not created retroactively), and a language
        # of nothing but translation pages has none either (the translation
        # quality check is deliberately not recorded). Both mean "no record",
        # while `checked against sources: 0` says "nothing was checked". The
        # overview page already omits its own line the same way. It also keeps
        # the output byte-identical on a repository with no records at all.
        if ai_reviewed_pages:
            lines.append(f"wikicommit_ai_reviewed_count: {ai_reviewed_pages}")
    lines += [
        "---",
        "",
        f"[{labels['top']} ({primary_lang})](./{primary_lang}/)",
    ]
    # Issue #671: the reader-facing site description, one line per language,
    # attached to that language's own link. Every entry in `langs` other than
    # primary_lang already stands on a language with at least one real page —
    # existing_lang_targets() filters the declared targets (Issue #190) and
    # main() derives the rest from pages this build actually wrote (Issue #731) —
    # so a description never adds a dead link there. primary_lang is exempt from
    # that filter (compute_langs() always prepends it), so on a wiki whose
    # primary_lang has no pages the description follows the link that is already
    # emitted for it — it does not create one.
    descriptions = site_description or {}
    if multilingual:
        lines += ["", f"## {labels['select']}", ""]
        for lang in langs:
            # A language with no resolvable page still gets 0/0 rather than a
            # bare link: existing_lang_targets() admits a language on any
            # non-removed .md under it, and primary_lang skips that filter
            # entirely (compute_langs() always prepends it), so both can reach
            # this list with nothing page_stats could count (Issue #730).
            pages, reviewed, ai_reviewed = counts.get(lang, (0, 0, 0))
            # Issue #769: counted per language for the same reason Issue #730
            # split pages and reviewed counts, and the reason holds harder here
            # — translation pages carry no record at all, so a site-wide figure
            # would be diluted by however many translations exist. A language
            # with no records keeps the two-number form (see the frontmatter
            # note above on why zero is omitted rather than printed).
            if ai_reviewed:
                template = labels["counts_ai_one"] if pages == 1 else labels["counts_ai"]
            else:
                template = labels["counts_one"] if pages == 1 else labels["counts"]
            entry = f"- [{lang}](./{lang}/)" + template.format(
                pages=pages, reviewed=reviewed, ai_reviewed=ai_reviewed
            )
            if lang in descriptions:
                entry += f" — {descriptions[lang]}"
            lines.append(entry)
        lines += ["", labels["counts_note"]]
        if any(ai for _, _, ai in counts.values()):
            lines += ["", labels["ai_counts_note"]]
    elif primary_lang in descriptions:
        # Single-language wiki: there is no language list to hang the
        # description off, so it goes under the top link instead.
        lines += ["", descriptions[primary_lang]]
    lines += ["", f"[{labels['sources']}](./{SOURCES_DIR_NAME}/)"]
    # Issue #585: the overview page is the other build-generated entry point
    # (aggregate counts, hubs, gaps, source breakdown), so the root index is
    # the one place both are reachable from.
    lines += ["", f"[{labels['overview']}](./{OVERVIEW_DIR_NAME}/)"]
    # Issue #645: the site-wide counterpart of the per-page attribution
    # WikiCommitSources renders (Issue #558). A reader who lands on one page sees
    # that page's sources and their terms inline; a reader looking at the site as
    # a whole arrives here, and had no signal that terms are per-page at all — the
    # risk being that they read the absence of a stated license as one blanket
    # license covering everything. Last, after both entry-point links, because it
    # qualifies the site rather than offering somewhere else to go; the full
    # wording lives on the sources index, which the link above reaches.
    lines += ["", labels["licensing"]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generating root index: {out_path}")


# The `custom/` segment in a custom type's name (`schema:custom/Decision`) is
# a machine-verification marker, not a folder a reader is meant to see: it is
# the one signal telling validate_frontmatter.py,
# check_property_wikilink_reinforcement.py and the wikicommit-jsonld plugin
# that this type is absent from the Schema.org vocabulary on purpose. Because
# .wikicommit/entity/ mirrors the type name into the directory tree, that
# marker also became a folder in the Explorer, the breadcrumbs, the Quartz
# folder page and the URL, where it means nothing (Issue #576).
#
# Publishing drops it, so custom types sit beside the standard ones in
# content/<lang>/<Type>/. Cutting here rather than in the Explorer fixes all
# four surfaces at once, and leaves the entity tree and every `type:` value
# untouched. The asymmetry that follows — custom/ required under
# .wikicommit/entity/, absent under content/ — is deliberate, not drift to be
# tidied away: removing it from the entity side would make rebuild_index.py
# write `type: schema:Decision`, which validate_frontmatter.py rejects as a
# type absent from the Schema.org vocabulary (Issue #512).
CUSTOM_TYPE_PREFIX = "custom/"


def flatten_custom_type(type_name: str) -> str:
    """Drop a type name's leading `custom/` for publishing.

    Only the first segment is removed: a hypothetical `custom/custom/Decision`
    publishes as `custom/Decision` rather than collapsing to `Decision`, which
    keeps the mapping injective and so keeps two distinct types from landing on
    one output path.
    """
    return type_name.removeprefix(CUSTOM_TYPE_PREFIX)


def flatten_entity_rel(rel_path: Path) -> Path:
    """Map a .wikicommit/entity/-relative page path to its content/-relative
    output path, dropping the `custom/` segment of a custom type's name.

    Returns rel_path unchanged for anything that is not <lang>/custom/<...>,
    including paths too short to be a page. Never use this to *read* from
    .wikicommit/entity/ — the on-disk tree keeps `custom/`, and a flattened
    path would resolve to a different file or none at all.
    """
    parts = rel_path.parts
    if len(parts) >= 4 and parts[1] == CUSTOM_TYPE_PREFIX.rstrip("/"):
        return Path(parts[0], *parts[2:])
    return rel_path


# Inline Markdown link/image targets: `](target)` and `](target "title")`.
# A target containing whitespace or `)` is left alone — the asset filename
# convention rules those out (no spaces; see sync_assets()), and guessing at
# them would be more likely to corrupt a link than to fix one.
_MD_LINK_TARGET_RE = re.compile(r'(!?\[[^\]]*\]\()([^)\s]+)((?:\s+"[^"]*")?\))')


def _rewrite_relative_target(target: str, src_dir: str, out_dir: str) -> str:
    """Re-express one relative link target for a page published from
    .wikicommit/entity/<src_dir>/ into content/<out_dir>/ (both POSIX
    directories relative to their own tree's root)."""
    if not target or target.startswith(("/", "#")) or "://" in target or target.startswith("mailto:"):
        return target
    path_part, sep, frag = target.partition("#")
    if not path_part:
        return target
    resolved = posixpath.normpath(posixpath.join(src_dir, path_part))
    if resolved.startswith(".."):
        # Already points outside the content root; there is no correct
        # rewrite, and the link was broken before this ran.
        return target
    # `resolved` names the target in the *entity* tree; the link has to name
    # where that target is published, so it gets the same flattening the
    # target page itself gets. Without this a link between two pages of the
    # same custom type (`[b](./b.md)`) would be re-aimed at
    # content/<lang>/custom/<Type>/, a directory publishing no longer creates.
    out_target = flatten_entity_rel(Path(resolved)).as_posix()
    if out_target == resolved and src_dir == out_dir:
        # Neither this page nor its target moved: leave the author's text
        # exactly as written rather than re-normalizing it.
        return target
    return _dot_relpath(out_target, out_dir) + sep + frag


def rewrite_relative_links(content: str, src_dir: str, out_dir: str) -> str:
    """Fix up body-relative Markdown links for a page published from
    .wikicommit/entity/<src_dir>/ into content/<out_dir>/.

    Flattening a custom type moves the page up one level, and a body written
    against the source tree — `![alt](../../../assets/diagram.png)`, the form
    a page uses to reach .wikicommit/entity/assets/ — is plain Markdown that
    convert_file()'s WikiLink substitution never touches.
    Without this pass those links would be copied out verbatim and break at
    exactly the moment flattening starts (Issue #589 made local images
    actually reach the published site, so this is a live breakage rather than
    a latent one).

    Every page is scanned, not just the flattened ones: a plain relative link
    *into* a custom type page breaks just as surely when written from a page
    that did not move (`[a](../custom/Decision/a.md)` on a Person page).
    _rewrite_relative_target() returns the author's text untouched whenever
    neither end moved, so a page with no custom type on either side comes out
    byte-identical.

    Run this before WikiLink substitution: afterwards the body also holds
    links relative to the *output* directory, which must not be adjusted a
    second time.
    """
    return _MD_LINK_TARGET_RE.sub(
        lambda m: m.group(1) + _rewrite_relative_target(m.group(2), src_dir, out_dir) + m.group(3),
        content,
    )


def _dot_relpath(target: str, start: str) -> str:
    """posixpath.relpath(), prefixed with "./" unless it already starts with
    ".." — shared by relative_link() and generated_page_link() so both
    relative-Markdown-link builders normalize the same way."""
    rel = posixpath.relpath(target, start=start)
    return rel if rel.startswith("..") else f"./{rel}"


def relative_link(current_lang: str, current_type: str, target_lang: str, target_type: str, slug: str) -> str:
    """Return the relative Markdown path from a <lang>/<type>/ page to <target_lang>/<target_type>/<slug>.md.

    Both type names are flattened (Issue #576): this builds a link between two
    pages as they sit in content/, so a `custom/` segment on either end would
    point at a directory the published tree does not have. Callers pass the
    entity type names; the existence checks they run beforehand use those
    unflattened names against .wikicommit/entity/, which is correct — only the
    link text is a content/ path.
    """
    current_dir = posixpath.join(current_lang, flatten_custom_type(current_type))
    target_path = posixpath.join(target_lang, flatten_custom_type(target_type), f"{slug}.md")
    return _dot_relpath(target_path, current_dir)


# Ingest management files (.wikicommit/source/) only ever carry
# source.type: path / url / wikicommit — unlike
# a wiki page's own `sources[]` entries, which can additionally be `manual`
# (a human assertion with no backing management file to mirror here).
SOURCE_TYPE_ORDER = ["path", "url", "wikicommit"]

# Ten languages; the note above ROOT_INDEX_LABELS says which and why. All
# four *_LABELS dicts have to hold the same set.
SOURCE_TYPE_LABELS = {
    "ja": {"path": "ファイル", "url": "URL", "wikicommit": "WikiCommit連携"},
    "de": {"path": "Dateien", "url": "URL", "wikicommit": "WikiCommit-Föderation"},
    "es": {"path": "Archivos", "url": "URL", "wikicommit": "Federación WikiCommit"},
    "fr": {"path": "Fichiers", "url": "URL", "wikicommit": "Fédération WikiCommit"},
    "it": {"path": "File", "url": "URL", "wikicommit": "Federazione WikiCommit"},
    "pl": {"path": "Pliki", "url": "URL", "wikicommit": "Federacja WikiCommit"},
    "pt": {"path": "Arquivos", "url": "URL", "wikicommit": "Federação WikiCommit"},
    "ru": {"path": "Файлы", "url": "URL", "wikicommit": "Федерация WikiCommit"},
    "zh": {"path": "文件", "url": "URL", "wikicommit": "WikiCommit 联合"},
}
DEFAULT_SOURCE_TYPE_LABELS = {"path": "Files", "url": "URL", "wikicommit": "WikiCommit federation"}

SOURCE_PAGE_LABELS = {
    "ja": {
        "index_title": "情報源一覧",
        "type": "種別",
        "original": "元リンク",
        "status": "ステータス",
        "summary": "概要",
        "no_summary": "（まだ生成されていません）",
        "license": "ライセンス",
        "retracted_notice": (
            "**この情報源は取り下げられました。** この Wiki はこの情報源を内容が信用できない"
            "と判断し、以後の取り込み対象から外しています。下記の「生成されたページ」は"
            "この情報源が使われていた当時に生成されたものです。"
        ),
        "retraction_reason": "取り下げの理由",
        "no_retraction_reason": "（理由の記載がありません）",
        "generated_pages": "生成されたページ",
        "no_generated_pages": "生成されたページはまだありません。",
        "empty": "登録されている情報源はありません。",
        "licensing_heading": "利用条件について",
        "licensing_body": (
            "この Wiki の各ページは、ここに挙げた情報源を LLM が要約・再構成したものです。"
            "利用条件は情報源ごとに異なり、サイト全体に適用される単一のライセンスはありません。"
            "あるページの利用条件を知るには、そのページ下部の出典欄に併記されたライセンスを"
            "参照してください。ライセンスが記録されていない情報源については、"
            "この Wiki は条件を把握していません（「制約が無い」という意味ではありません）。"
        ),
    },
    "de": {
        "index_title": "Quellen",
        "type": "Typ",
        "original": "Original",
        "status": "Status",
        "summary": "Zusammenfassung",
        "no_summary": "(noch nicht generiert)",
        "license": "Lizenz",
        "retracted_notice": "**Diese Quelle wurde zurückgezogen.** Dieses Wiki hat ihren Inhalt als unzuverlässig eingestuft und übernimmt nichts mehr aus ihr. Die unten unter „Generierte Seiten“ aufgeführten Seiten wurden verfasst, als sie noch verwendet wurde.",
        "retraction_reason": "Grund für die Zurückziehung",
        "no_retraction_reason": "(kein Grund angegeben)",
        "generated_pages": "Generierte Seiten",
        "no_generated_pages": "Noch keine Seiten generiert.",
        "empty": "Es wurden noch keine Quellen registriert.",
        "licensing_heading": "Zu den Nutzungsbedingungen",
        "licensing_body": "Jede Seite dieses Wikis ist eine von einem LLM erstellte Zusammenfassung und Neugliederung der hier aufgeführten Quellen. Die Nutzungsbedingungen unterscheiden sich von Quelle zu Quelle, und es gibt keine einheitliche Lizenz für die gesamte Website. Die Bedingungen einer Seite finden Sie in den Lizenzen, die unten auf dieser Seite neben ihren Quellen angezeigt werden. Ist für eine Quelle keine Lizenz erfasst, kennt dieses Wiki ihre Bedingungen nicht — was nicht bedeutet, dass es keine gibt.",
    },
    "es": {
        "index_title": "Fuentes",
        "type": "Tipo",
        "original": "Original",
        "status": "Estado",
        "summary": "Resumen",
        "no_summary": "(aún no generado)",
        "license": "Licencia",
        "retracted_notice": "**Esta fuente ha sido retirada.** Esta wiki consideró que su contenido no era fiable y ya no incorpora nada de ella. Las páginas que figuran abajo en «Páginas generadas» se escribieron mientras aún se usaba.",
        "retraction_reason": "Motivo de la retirada",
        "no_retraction_reason": "(no se registró ningún motivo)",
        "generated_pages": "Páginas generadas",
        "no_generated_pages": "Aún no se ha generado ninguna página.",
        "empty": "Aún no se ha registrado ninguna fuente.",
        "licensing_heading": "Sobre las condiciones de uso",
        "licensing_body": "Cada página de esta wiki es un resumen y una reorganización, hechos por un LLM, de las fuentes aquí enumeradas. Las condiciones de uso varían de una fuente a otra, y ninguna licencia única se aplica al sitio en su conjunto. Para conocer las condiciones de una página concreta, consulta las licencias que aparecen junto a sus fuentes al pie de esa página. Cuando una fuente no tiene licencia registrada, esta wiki desconoce sus condiciones, lo cual no equivale a que no las tenga.",
    },
    "fr": {
        "index_title": "Sources",
        "type": "Type",
        "original": "Original",
        "status": "Statut",
        "summary": "Résumé",
        "no_summary": "(pas encore généré)",
        "license": "Licence",
        "retracted_notice": "**Cette source a été retirée.** Ce wiki a jugé son contenu peu fiable et n'en importe plus rien. Les pages éventuellement listées sous « Pages générées » ci-dessous ont été rédigées alors qu'elle était encore utilisée.",
        "retraction_reason": "Motif du retrait",
        "no_retraction_reason": "(aucun motif enregistré)",
        "generated_pages": "Pages générées",
        "no_generated_pages": "Aucune page générée pour l'instant.",
        "empty": "Aucune source n'a encore été enregistrée.",
        "licensing_heading": "À propos des conditions d'utilisation",
        "licensing_body": "Chaque page de ce wiki est un résumé et une réorganisation, par un LLM, des sources listées ici. Les conditions d'utilisation varient d'une source à l'autre, et aucune licence unique ne s'applique au site dans son ensemble. Pour connaître les conditions d'une page donnée, lisez les licences indiquées à côté de ses sources en bas de cette page. Lorsqu'aucune licence n'est enregistrée pour une source, ce wiki ne connaît pas ses conditions — ce qui ne signifie pas qu'il n'y en a aucune.",
    },
    "it": {
        "index_title": "Fonti",
        "type": "Tipo",
        "original": "Originale",
        "status": "Stato",
        "summary": "Riepilogo",
        "no_summary": "(non ancora generato)",
        "license": "Licenza",
        "retracted_notice": "**Questa fonte è stata ritirata.** Questo wiki ne ha giudicato il contenuto inaffidabile e non la acquisisce più. Le pagine elencate più sotto in “Pagine generate” sono state scritte quando era ancora in uso.",
        "retraction_reason": "Motivo del ritiro",
        "no_retraction_reason": "(nessun motivo registrato)",
        "generated_pages": "Pagine generate",
        "no_generated_pages": "Nessuna pagina ancora generata.",
        "empty": "Non è ancora stata registrata alcuna fonte.",
        "licensing_heading": "Sulle condizioni d'uso",
        "licensing_body": "Ogni pagina di questo wiki è un riassunto e una riorganizzazione, fatti da un LLM, delle fonti elencate qui. Le condizioni d'uso variano da fonte a fonte e nessuna licenza unica si applica al sito nel suo insieme. Per conoscere le condizioni di una pagina, leggi le licenze indicate accanto alle sue fonti in fondo a quella pagina. Se per una fonte non è registrata alcuna licenza, questo wiki non ne conosce le condizioni, il che non equivale all'assenza di condizioni.",
    },
    "pl": {
        "index_title": "Źródła",
        "type": "Typ",
        "original": "Oryginał",
        "status": "Status",
        "summary": "Podsumowanie",
        "no_summary": "(jeszcze nie wygenerowano)",
        "license": "Licencja",
        "retracted_notice": "**To źródło zostało wycofane.** Ta wiki uznała jego treść za niewiarygodną i nie pobiera już z niego treści. Strony wymienione poniżej w sekcji „Wygenerowane strony” zostały napisane, gdy było jeszcze używane.",
        "retraction_reason": "Powód wycofania",
        "no_retraction_reason": "(nie zapisano powodu)",
        "generated_pages": "Wygenerowane strony",
        "no_generated_pages": "Nie wygenerowano jeszcze żadnych stron.",
        "empty": "Nie zarejestrowano jeszcze żadnych źródeł.",
        "licensing_heading": "O warunkach korzystania",
        "licensing_body": "Każda strona tej wiki jest streszczeniem i przeredagowaniem przez LLM wymienionych tu źródeł. Warunki korzystania różnią się między źródłami i żadna pojedyncza licencja nie obejmuje całej witryny. Aby poznać warunki dla danej strony, sprawdź licencje podane przy jej źródłach na dole tej strony. Jeśli dla źródła nie zapisano licencji, ta wiki nie zna jego warunków — co nie oznacza, że ich nie ma.",
    },
    "pt": {
        "index_title": "Fontes",
        "type": "Tipo",
        "original": "Original",
        "status": "Status",
        "summary": "Resumo",
        "no_summary": "(ainda não gerado)",
        "license": "Licença",
        "retracted_notice": "**Esta fonte foi retirada.** Este wiki julgou seu conteúdo não confiável e deixou de incorporar conteúdo dela. As páginas listadas em “Páginas geradas” abaixo foram escritas enquanto ela ainda estava em uso.",
        "retraction_reason": "Motivo da retirada",
        "no_retraction_reason": "(nenhum motivo registrado)",
        "generated_pages": "Páginas geradas",
        "no_generated_pages": "Nenhuma página gerada ainda.",
        "empty": "Nenhuma fonte foi registrada ainda.",
        "licensing_heading": "Sobre os termos de uso",
        "licensing_body": "Cada página deste wiki é um resumo e uma reorganização, feitos por um LLM, das fontes listadas aqui. Os termos de uso variam de fonte para fonte, e nenhuma licença única se aplica ao site como um todo. Para saber os termos de uma página, leia as licenças exibidas ao lado das fontes no fim dessa página. Quando uma fonte não tem licença registrada, este wiki não conhece seus termos — o que não é o mesmo que não haver termos.",
    },
    "ru": {
        "index_title": "Источники",
        "type": "Тип",
        "original": "Оригинал",
        "status": "Статус",
        "summary": "Краткое содержание",
        "no_summary": "(ещё не сгенерировано)",
        "license": "Лицензия",
        "retracted_notice": "**Этот источник отозван.** Эта вики сочла его содержание ненадёжным и больше не берёт из него материал. Страницы, перечисленные ниже в разделе «Сгенерированные страницы», были написаны, пока он ещё использовался.",
        "retraction_reason": "Причина отзыва",
        "no_retraction_reason": "(причина не записана)",
        "generated_pages": "Сгенерированные страницы",
        "no_generated_pages": "Сгенерированных страниц пока нет.",
        "empty": "Источники пока не зарегистрированы.",
        "licensing_heading": "Об условиях использования",
        "licensing_body": "Каждая страница этой вики — выполненные LLM пересказ и переработка перечисленных здесь источников. Условия использования у разных источников разные, и единой лицензии на весь сайт нет. Чтобы узнать условия для конкретной страницы, посмотрите лицензии, указанные рядом с её источниками внизу этой страницы. Если у источника лицензия не записана, эта вики не знает его условий — а это не то же самое, что их отсутствие.",
    },
    "zh": {
        "index_title": "来源",
        "type": "类型",
        "original": "原始链接",
        "status": "状态",
        "summary": "摘要",
        "no_summary": "（尚未生成）",
        "license": "许可证",
        "retracted_notice": "**此来源已被撤回。** 本 Wiki 判断其内容不可靠，不再从中获取内容。下方“生成的页面”中列出的页面，是在其仍被使用时撰写的。",
        "retraction_reason": "撤回原因",
        "no_retraction_reason": "（未记录原因）",
        "generated_pages": "生成的页面",
        "no_generated_pages": "尚未生成任何页面。",
        "empty": "尚未登记任何来源。",
        "licensing_heading": "关于使用条款",
        "licensing_body": "本 Wiki 的每个页面都是 LLM 对此处所列来源的概括和重新组织。使用条款因来源而异，没有适用于整个网站的单一许可证。要了解某个页面的使用条款，请查看该页面底部来源旁显示的许可证。对于未记录许可证的来源，本 Wiki 并不知道其条款——这并不等于没有任何条款。",
    },
}
DEFAULT_SOURCE_PAGE_LABELS = {
    "index_title": "Sources",
    "type": "Type",
    "original": "Original",
    "status": "Status",
    "summary": "Summary",
    "no_summary": "(not yet generated)",
    "license": "License",
    "retracted_notice": (
        "**This source has been retracted.** This wiki judged its content unreliable and "
        "no longer ingests from it. Any pages listed under \u201cGenerated pages\u201d below were "
        "written while it was still in use."
    ),
    "retraction_reason": "Reason for retraction",
    "no_retraction_reason": "(no reason recorded)",
    "generated_pages": "Generated pages",
    "no_generated_pages": "No pages generated yet.",
    "empty": "No sources have been registered yet.",
    "licensing_heading": "About terms of use",
    "licensing_body": (
        "Every page in this wiki is an LLM summary and reorganization of the sources "
        "listed here. Terms of use differ from source to source, and no single license "
        "applies to the site as a whole. To find the terms for a given page, read the "
        "licenses shown beside its sources at the bottom of that page. Where a source "
        "has no license recorded, this wiki does not know its terms — which is not the "
        "same as there being none."
    ),
}

# Matches the old (pre-Issue #405) Japanese heading alongside the current
# fixed-English one, so a management file that predates that change (no
# automatic migration) still renders its
# Summary body instead of falling back to "not yet generated".
SUMMARY_HEADING_RE = re.compile(r"^## (?:Summary|サマリ)\r?\n(.*?)(?=\n## |\Z)", re.DOTALL | re.MULTILINE)


RETRACTION_REASON_HEADING_RE = re.compile(
    r"^## Retraction Reason\r?\n(.*?)(?=\n## |\Z)", re.DOTALL | re.MULTILINE
)


def parse_retraction_reason_section(body: str) -> str | None:
    """Return the management file's `## Retraction Reason` section body, or None
    if absent/empty (Issue #737).

    Unlike `## Summary`, this heading has no pre-Issue #405 Japanese variant to
    accept: the section is new, and management-file headings have been fixed
    English since then.
    """
    m = RETRACTION_REASON_HEADING_RE.search(body)
    if not m:
        return None
    text = m.group(1).strip()
    return text or None


def parse_summary_section(body: str) -> str | None:
    """Return the source management file's `## Summary` section body text, or
    None if absent/empty."""
    m = SUMMARY_HEADING_RE.search(body)
    if not m:
        return None
    text = m.group(1).strip()
    return text or None


def generated_page_link(wiki_rel: str, mgmt_rel: Path) -> str:
    """Convert an already-normalized .wikicommit/entity/-relative path (e.g.
    "ja/Person/yamada-taro.md", as returned by normalize_wiki_rel()) into a
    relative Markdown link from its mirrored content/sources/<mgmt_rel> page
    to the corresponding content/<lang>/<Type>/<slug>.md page convert_file()
    writes.

    A custom type's `custom/` segment is dropped here to match that output
    path (Issue #576).
    """
    current_dir = posixpath.join(SOURCES_DIR_NAME, mgmt_rel.parent.as_posix())
    # The caller resolved the page on disk with the unflattened path; the link
    # has to name where convert_file() actually wrote it (Issue #576).
    return _dot_relpath(flatten_entity_rel(Path(wiki_rel)).as_posix(), current_dir)


_ENTITY_PREFIX_RE = re.compile(r"^\.wikicommit/(?:entity|wiki)/")


def normalize_wiki_rel(wiki_path: str) -> str | None:
    """Strip a generated_pages[] entry's `.wikicommit/entity/` prefix (or the
    pre-Issue-#477 `.wikicommit/wiki/` prefix — management files generated
    before that rename keep their old entries verbatim, with old and new forms
    allowed to coexist rather than being auto-migrated) and validate the
    remainder is a plain same-tree relative path, returning None if not.

    Strips at most one prefix occurrence (single regex match, mirroring
    WikiCommitSources.tsx's `/^\\.wikicommit\\/(entity|wiki)\\//` — not two
    chained `.removeprefix()` calls, which would silently strip a
    double-prefixed value like `.wikicommit/entity/.wikicommit/wiki/ja/foo.md`
    down to `ja/foo.md` instead of leaving it as the clearly-malformed
    `.wikicommit/wiki/ja/foo.md` a hand-edited garbage entry should produce.

    Guards against a malformed entry (hand-edited garbage, an absolute-
    looking path, or a `..`-escaping path) reaching `entity_dir / wiki_rel` in
    _write_source_page(): Path.__truediv__ silently discards the left-hand
    side when the right-hand side looks absolute (e.g. `Path("a") /
    "/etc/passwd" == Path("/etc/passwd")`), which would otherwise make
    load_frontmatter() read from an unintended location on disk instead of
    failing safely.
    """
    rel = _ENTITY_PREFIX_RE.sub("", wiki_path.strip().removeprefix("./"), count=1)
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return None
    return rel


def _escape_md_link_text(text: str) -> str:
    """Escape `[`/`]`/`"` so a title/path/url containing them can't
    prematurely terminate a generated Markdown link's text span, or (for
    WikiLinks embedded inside a double-quoted frontmatter value, e.g.
    `affiliation: "[[Organization/companya]]"`) break out of the enclosing
    YAML string. `\\"` is a valid CommonMark backslash escape (renders as a
    literal `"`), so this is safe in body Markdown too."""
    return text.replace("[", "\\[").replace("]", "\\]").replace('"', '\\"')


def path_href(path: str) -> str | None:
    """Return a GitHub blob URL for a `type: path` source.path, or None if
    GITHUB_REPOSITORY (set by GitHub Actions) is unavailable.

    Kept in sync by hand with pathHref() in
    quartz-plugins/wikicommit-sources/src/components/WikiCommitSources.tsx
    (Issue #212), including the `main` branch assumption — that component
    renders a different, per-page sources box at render time (TSX/Quartz),
    while this script runs at build time (Python), so the two can't share
    one function.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    return f"https://github.com/{repo}/blob/main/{quote(path)}"


def url_host(url) -> str | None:
    """Return a `url`/`wikicommit` source's lower-cased host without a leading
    "www.", or None when it has none (Issue #585's per-host source breakdown).

    Normalizing the same way check_extraction_quality.py's _domain_of() does
    keeps "example.com" and "www.example.com" from splitting one publisher
    into two rows; subdomains are left alone, since ja./en.wikipedia.org being
    counted separately is information, not noise.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        host = urlsplit(url.strip()).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def render_source_label(source: dict) -> str:
    """Render an source management file's `source:` entry as a Markdown
    link/label. Only `path`/`url`/`wikicommit` are handled — management
    files are never `type: manual` (`manual` is only valid on a wiki page's
    own `sources[]`, which this function does
    not render)."""
    source_type = source.get("type")
    if source_type == "path":
        path = source.get("path", "")
        href = path_href(path)
        return f"[{_escape_md_link_text(path)}]({href})" if href else f"`{path}`"
    if source_type in ("url", "wikicommit"):
        url = source.get("url", "")
        return f"[{_escape_md_link_text(url)}]({url})"
    return ""


def _write_source_page(
    out_path: Path, fm: dict, body: str, source: dict, title: str, entity_dir: Path, mgmt_rel: Path, labels: dict
) -> list[str]:
    """Write one content/sources/<mgmt_rel> page mirroring a source
    management file: its type, original link, registration status, `## Summary`
    body, and generated_pages[] (as plain Markdown links, not WikiLinks —
    these pages sit outside the WikiLink graph, a known limitation accepted
    in Issue #476).

    Returns the .wikicommit/entity/-relative paths of the generated_pages[]
    entries it actually linked — the ones that survived normalization plus the
    exists/not-removed filter below. generate_source_pages() feeds these into
    the overview page's source x type cross-tab (Issue #585) so that tally is
    built from the same filter as the links, rather than a second, drifting
    copy of it."""
    status = fm.get("status") or "pending"

    lines = [
        "---",
        f"title: {_yaml_quote(str(title))}",
        "review_status: reviewed",
        "comments: false",
        "---",
        "",
        f"**{labels['type']}**: {source.get('type', '')}",
        "",
        f"**{labels['original']}**: {render_source_label(source)}",
        "",
        f"**{labels['status']}**: {status}",
        "",
    ]

    # Issue #558: mirror the management file's source.license here too, so the
    # public source page states the same terms the per-page sources box does.
    # Absent/blank means "unknown", which is not the same as "unrestricted", so
    # the line is omitted entirely rather than rendered empty.
    license_id = source.get("license")
    if isinstance(license_id, str) and license_id.strip():
        lines += [f"**{labels['license']}**: {license_id.strip()}", ""]

    # Issue #737: a retracted source keeps its public page rather than losing it.
    # "This wiki used this source and then withdrew it" is a record worth
    # publishing, and keeping it is what GitOps asks for. Note this is the
    # opposite requirement from a `status: removed` page, which is never written
    # into content/ at all (Issue #271) precisely so it stops being reachable —
    # here nothing needs to become unreachable, so what is needed is not deletion
    # but a statement on the page itself. The bare `status: retracted` line above
    # is a field value; on its own it does not tell a reader what it means for
    # the pages this source produced.
    if status == "retracted":
        lines += [
            labels["retracted_notice"],
            "",
            f"## {labels['retraction_reason']}",
            "",
            parse_retraction_reason_section(body) or labels["no_retraction_reason"],
            "",
        ]

    lines += [
        f"## {labels['summary']}",
        "",
        parse_summary_section(body) or labels["no_summary"],
        "",
        f"## {labels['generated_pages']}",
        "",
    ]

    generated_pages = fm.get("generated_pages")
    page_lines = []
    linked_wiki_rels: list[str] = []
    if isinstance(generated_pages, list):
        for wiki_path in generated_pages:
            if not isinstance(wiki_path, str) or not wiki_path:
                continue
            wiki_rel = normalize_wiki_rel(wiki_path)
            if wiki_rel is None:
                continue
            target = entity_dir / wiki_rel
            # Skip a generated_pages[] entry whose target page was removed or
            # deleted since generation — main()'s stale-cleanup pass sweeps
            # such pages out of content/, so linking to one here would be a
            # dead link on the published site (unlike is_removed()'s other
            # call sites, which only need frontmatter, this also has to
            # confirm the file exists at all).
            if not target.is_file() or is_removed(target):
                continue
            link = generated_page_link(wiki_rel, mgmt_rel)
            page_title = (load_frontmatter(target) or {}).get("title") or wiki_rel
            page_lines.append(f"- [{_escape_md_link_text(str(page_title))}]({link})")
            linked_wiki_rels.append(wiki_rel)
    lines += page_lines if page_lines else [labels["no_generated_pages"]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Generating source page: {out_path}")
    return linked_wiki_rels


def _write_sources_index(out_path: Path, entries: list[dict], labels: dict, type_labels: dict) -> None:
    """Write content/sources/index.md: a landing page grouping every mirrored
    source page by type, so links from generate_root_index() never dead-end
    (same invariant the old content/<lang>/sources.md upheld)."""
    # Every entry["type"] is already one of SOURCE_TYPE_ORDER — filtered by
    # generate_source_pages() before appending — so a plain lookup suffices.
    groups: dict[str, list[dict]] = {t: [] for t in SOURCE_TYPE_ORDER}
    for entry in entries:
        groups[entry["type"]].append(entry)

    lines = ["---", f'title: "{labels["index_title"]}"', "review_status: reviewed",
             "comments: false", "---", ""]
    has_entries = any(groups.values())
    for source_type in SOURCE_TYPE_ORDER:
        items = groups[source_type]
        if not items:
            continue
        lines += [f"## {type_labels.get(source_type, source_type)}", ""]
        for item in sorted(items, key=lambda e: e["rel"]):
            lines.append(f"- [{_escape_md_link_text(item['title'])}](./{item['rel']})")
        lines.append("")
    if not has_entries:
        lines.append(labels["empty"])

    # Issue #645: the site-wide licensing notice (layer 2) lives here rather than
    # in the Quartz footer. The footer plugin takes only a label -> URL mapping, so
    # prose would need a fork or a new component — out of proportion to two
    # sentences — and a footer *link* would need an absolute URL, which is not
    # knowable at init time (baseUrl becomes <owner>.github.io/<repo> on a GitHub
    # Pages project site, so a root-relative href breaks on the default shape).
    # This page is where a reader asking "where did this come from, and under what
    # terms" arrives, and the root index points here. It complements, and does not
    # replace, the per-source notice WikiCommitSources renders on each page
    # (Issue #558) — that one stays the operative attribution.
    #
    # Shown unconditionally, including when no source is registered yet: the
    # statement is about how this wiki works, not about the current contents.
    if lines and lines[-1] != "":
        lines.append("")
    lines += [f"## {labels['licensing_heading']}", "", labels["licensing_body"]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Generating sources index: {out_path}")


def _write_source_dir_index(out_path: Path, title: str, subdirs: list[str], files: list[dict], labels: dict) -> None:
    """Write an index.md for one intermediate directory under content/sources/
    (e.g. content/sources/url/ or content/sources/url/<host>/), listing its
    immediate subdirectories and mirrored source pages as plain relative
    links (Issue #493)."""
    lines = ["---", f"title: {_yaml_quote(title)}", "review_status: reviewed",
             "comments: false", "---", ""]
    for sub in subdirs:
        lines.append(f"- [{_escape_md_link_text(sub)}](./{sub}/)")
    for item in files:
        lines.append(f"- [{_escape_md_link_text(item['title'])}](./{item['rel']})")
    if not subdirs and not files:
        lines.append(labels["empty"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Generating source directory index: {out_path}")


def _write_source_dir_indexes(
    output_dir: Path, entries: list[dict], type_labels: dict, labels: dict, already_written: set[Path]
) -> set[Path]:
    """Write an index.md for every intermediate directory under
    content/sources/ (e.g. content/sources/url/, content/sources/url/<host>/)
    so Explorer navigation into them doesn't 404 (Issue #493).

    Every other folder WikiCommit generates under content/
    (entity/<lang>/<Type>/ via rebuild_index.py, the content/ root via
    generate_root_index(), content/sources/ itself via _write_sources_index())
    already writes its own index.md explicitly instead of relying on Quartz's
    `folder-page` plugin to auto-generate one — that plugin is enabled in
    quartz.config.yaml but turned out not to do so for this tree, the first
    place WikiCommit-generated content actually depended on it. This applies
    the same established "write index.md explicitly" pattern one or more
    levels deeper.

    Generalized over every source type in SOURCE_TYPE_ORDER rather than
    hardcoded to `url`: `type: path` management files mirror the ingested
    file's own repo-relative path, which can be
    nested just as deeply (e.g. `path/raw/paper-2024.md`) and would hit the
    same underlying bug.

    `already_written` is the set of content/sources/ paths generate_source_pages()
    already wrote a real mirrored source page to (one per source management
    file, via _write_source_page()). A management file whose own mirrored
    path happens to end in `index.md` — a `type: path` source for a
    repo file literally named `index.*` (e.g. `src/index.js`), or a
    `type: url` source sanitized from a URL whose path is `/index`
    (the same `/index` collision class already solved once at the
    bare-domain-vs-path layer for Issue #213) — produces an
    intermediate-directory index_rel identical
    to that real page's own path. Skipping the generic directory listing for
    any such path avoids silently overwriting the real source page with a
    bare subdirectory/file listing (the real page already satisfies
    Explorer's need for an index.md there, so there is nothing to fill in).
    """
    all_dirs: set[Path] = set()
    for entry in entries:
        d = Path(entry["rel"]).parent
        while d != Path("."):
            all_dirs.add(d)
            d = d.parent

    written: set[Path] = set()
    for d in all_dirs:
        index_rel = Path(SOURCES_DIR_NAME) / d / "index.md"
        if index_rel in already_written:
            written.add(index_rel)
            continue
        subdirs = sorted(p.name for p in all_dirs if p.parent == d)
        files = sorted(
            ({"title": e["title"], "rel": Path(e["rel"]).name} for e in entries if Path(e["rel"]).parent == d),
            key=lambda e: e["rel"],
        )
        # Top-level type directories (path/, url/, wikicommit/) get their
        # localized label as title, same as _write_sources_index()'s section
        # headings; deeper directories (host names, repo subpaths) have no
        # translation to look up, so use the literal directory name.
        title = type_labels.get(d.name, d.name) if d.parent == Path(".") else d.name
        _write_source_dir_index(output_dir / index_rel, title, subdirs, files, labels)
        written.add(index_rel)
    return written


def generate_source_pages(
    output_dir: Path, mgmt_dir: Path, entity_dir: Path, primary_lang: str
) -> tuple[set[Path], dict]:
    """Mirror .wikicommit/source/ into content/sources/, one page per source
    management file, plus a content/sources/index.md landing page (Issue
    #476). Replaces the old per-language content/<lang>/sources.md
    aggregation (built by walking wiki pages and reading back each page's own
    `sources` frontmatter) with a direct mirror of the management-file tree:
    a management file's own `status`/`generated_pages`/`## Summary` are
    already the authoritative record of what it produced, so walking
    .wikicommit/source/ directly is both simpler (design docs' "反転" —
    Issue #476) and surfaces sources with zero generated_pages (status:
    excluded/pending/failed) that the old backlink-based aggregation could
    never reach, since they have no page `sources:` entry pointing back at
    them.

    content/sources/ is a single language-independent tree (the source tree
    itself has no `lang` concept), unlike content/<lang>/ which exists once per
    language.

    Returns (written, stats): the set of repo-relative Path objects written
    (for main()'s stale-cleanup pass), and the aggregate breakdown the
    overview page renders (Issue #585) — counts per source type, per registration
    `status`, per URL host, and the source-type x page-type cross-tab. The
    aggregation rides along on this walk rather than repeating it: this is
    already the only pass over .wikicommit/source/, and management files are
    the authoritative record of what each source produced.

    Always writes at least content/sources/index.md, even with zero
    registered sources, so the root index's "sources" link never dead-ends.
    """
    labels = SOURCE_PAGE_LABELS.get(primary_lang, DEFAULT_SOURCE_PAGE_LABELS)
    type_labels = SOURCE_TYPE_LABELS.get(primary_lang, DEFAULT_SOURCE_TYPE_LABELS)
    written: set[Path] = set()
    entries: list[dict] = []
    stats: dict = {
        "type_counts": {},        # source.type -> management file count
        "status_counts": {},      # registration status -> management file count
        "host_counts": {},        # URL host -> management file count
        # source.lang (ISO 639-1) -> management file count; None for a file
        # that carries no language yet (Issue #989) but has finished a run
        "lang_counts": {},
        # management files with no language that have never finished a run
        # (empty `last_generated_at`) — the queue, not old intake (Issue #1135)
        "lang_unprocessed": 0,
        "type_x_page_type": {},   # source.type -> {published page type -> page count}
        # source.url / source.path -> this source's page under content/sources/
        # (Issue #1006). Keyed by the identity string the management file
        # records, not by the derived file name (Issue #572 / #573), so the
        # overview can link a hub concentration to the page listing it.
        "page_for_source": {},
    }

    if mgmt_dir.is_dir():
        for mgmt_file in sorted(mgmt_dir.rglob("*.md")):
            try:
                content = mgmt_file.read_text(encoding="utf-8-sig")
            except OSError as e:
                print(f"WARNING: {mgmt_file}: could not read management file: {e}")
                continue
            fm, err, body = parse_frontmatter_and_body_text(content)
            if err or not isinstance(fm, dict):
                print(f"WARNING: {mgmt_file}: {err or 'frontmatter is not a mapping'} — skipped in content/sources/")
                continue
            source = fm.get("source")
            if not isinstance(source, dict) or source.get("type") not in SOURCE_TYPE_ORDER:
                continue

            mgmt_rel = mgmt_file.relative_to(mgmt_dir)
            title = str(source.get("path") or source.get("url") or mgmt_rel.as_posix())
            out_rel = Path(SOURCES_DIR_NAME) / mgmt_rel
            linked_wiki_rels = _write_source_page(
                output_dir / out_rel, fm, body, source, title, entity_dir, mgmt_rel, labels
            )
            written.add(out_rel)

            source_type = source["type"]
            entries.append({"type": source_type, "rel": mgmt_rel.as_posix(), "title": title})
            for ident in (source.get("url"), source.get("path")):
                if isinstance(ident, str) and ident:
                    stats["page_for_source"].setdefault(ident, out_rel)

            stats["type_counts"][source_type] = stats["type_counts"].get(source_type, 0) + 1
            status_key = str(fm.get("status") or "pending")
            stats["status_counts"][status_key] = stats["status_counts"].get(status_key, 0) + 1
            host = url_host(source.get("url")) if source_type in ("url", "wikicommit") else None
            if host:
                stats["host_counts"][host] = stats["host_counts"].get(host, 0) + 1
            # Issue #989: a missing or empty source.lang is counted under None and
            # shown as its own "not recorded" row — never dropped. Dropping it would
            # make a wiki of mostly English sources, only a few of them re-read since
            # the field was added, look as if every source were in those few
            # languages.
            raw_lang = source.get("lang")
            # YAML 1.1 reads an unquoted `lang: no` (Norwegian, a valid ISO 639-1
            # code) as the boolean False; without this it would be counted as
            # "false". Pass 2a writes the code unquoted, so this is reachable.
            if raw_lang is False:
                raw_lang = "no"
            lang_key = (str(raw_lang).strip().lower() or None) if raw_lang is not None else None
            # Issue #1135: an empty lang means one of two things. A source that has
            # never finished a run (`add_source.py` writes `last_generated_at:`
            # empty and only a completed run fills it — the same test
            # reconcile_ingest_status.py uses) is still in the queue; calling it
            # "taken in before this was recorded" would tell a new wiki's readers
            # it has old intake. Only a source that has run without a language
            # is "not recorded". `excluded` is the exception to the date test:
            # Pass 4 writes it at the end of a completed run but, unlike
            # `generated`/`partial`, never writes `last_generated_at`, so a
            # language-less `excluded` source was processed before the field
            # existed — not queued.
            if (
                lang_key is None
                and not fm.get("last_generated_at")
                and status_key != "excluded"
            ):
                stats["lang_unprocessed"] += 1
            else:
                stats["lang_counts"][lang_key] = stats["lang_counts"].get(lang_key, 0) + 1
            per_page_type = stats["type_x_page_type"].setdefault(source_type, {})
            for wiki_rel in linked_wiki_rels:
                resolved = parse_wiki_path(entity_dir / wiki_rel, entity_dir)
                if resolved is None:
                    continue
                page_type = flatten_custom_type(resolved[1])
                per_page_type[page_type] = per_page_type.get(page_type, 0) + 1

    index_rel = Path(SOURCES_DIR_NAME) / "index.md"
    _write_sources_index(output_dir / index_rel, entries, labels, type_labels)
    written.add(index_rel)
    written |= _write_source_dir_indexes(output_dir, entries, type_labels, labels, already_written=written)
    return written, stats


# ── Wiki-wide overview page (Issue #585) ───────────────────────────────────────
#
# A reader or operator arriving at the published site has no single place that
# answers "what knowledge is in here, and what is missing?". The pieces exist,
# scattered: the root index carries three numbers (Issue #407), content/sources/
# shows one source at a time (Issue #476), each type's index.md lists that type
# alone, and /wikicommit-status's orphan/wanted tallies never leave the console.
#
# Like generate_root_index() and generate_source_pages(), this is a
# build-generated page: it has no file under .wikicommit/entity/ and is
# rewritten from scratch on every build. That is deliberate. Its content is
# recomputed aggregate, not something a human reviews once — putting it under
# .wikicommit/entity/ would subject numbers that change every build to
# review_status, a review-tracking Issue (Issue #313) and the wikicommit-merge
# quality gate.
#
# Everything here is derived from data main() and generate_source_pages()
# already collect. In particular nothing calls check_ingest_freshness.py, which
# rewrites management files (`status: outdated`) as a side effect: a build must
# never modify the repository it is building. `expires_at` is likewise left to
# /wikicommit-status, since "today" would freeze at build time and quietly go
# stale until the next deploy.

# Ten languages; the note above ROOT_INDEX_LABELS says which and why. All
# four *_LABELS dicts have to hold the same set.
OVERVIEW_LABELS = {
    "ja": {
        "title": "Wiki 全体の俯瞰",
        "totals": "全体の数字",
        "total_pages": "総ページ数",
        "reviewed": "人が読んで確認",
        # Issue #664: the bare count reads as "nobody cares about this project"
        # to a first-time reader. The number stays — hiding it would give up the
        # honesty it was added for — and this line says what it counts.
        # Issue #800: says the human number is partial *by design*, matching the
        # root index's `counts_note` word for word in substance. Sampling
        # vocabulary stays out (Issue #769).
        "reviewed_note": (
            "ページは LLM が生成した時点で公開されます。"
            "出典との照合は機械が行い、"
            "「人が読んで確認」はそのうち人が最後まで読み、"
            "明らかな問題を見つけなかった件数です。"
            "人による確認は設計上一部のページのみであり、"
            "この数字が総数に達することは目指していません。"
            "網羅的な品質保証でもありません。"
        ),
        # Issue #751: a separate key from `reviewed`, never a reuse of it.
        # Issue #664, and then Issue #740, deliberately made that one name the
        # human reader out loud ("人が読んだページ"); putting
        # the machine's count behind the same label would put back the ambiguity
        # it removed. The wording says what was compared, not that the page is
        # correct — Pass 4 checks fidelity to the sources and nothing else
        # (Issue #722 on completeness, Issue #723 on harm and on the reader's
        # own knowledge).
        "ai_reviewed": "出典と照合済み（AI）",
        # Issue #1030: the subject is pages generated from sources, not every
        # page — a translation inherits its sources and is not checked.
        "ai_reviewed_note": (
            "出典から生成されたページは、生成時にその記述を出典と照合しています。"
            "照合しているのは出典との一致だけで、"
            "網羅性・実在の人物や組織への影響・読者自身の知識との食い違いは見ていません。"
        ),
        # Issue #1030: shown only when the wiki has translation pages. They are
        # left out of the ratio above (they carry no record of their own), and
        # saying so where it happens keeps a reader from assuming they are part
        # of it.
        "translation_pages": "翻訳ページ",
        "translation_pages_value": "{n}（原文との照合は記録されていません）",
        "translation_pages_note": "翻訳ページはこの照合の対象外であり、上の割合にも含めていません。",
        "translation_checked": "原文と照合済み（AI）",
        "translation_checked_note": "翻訳ページは、翻訳したときに訳文を原文ページと照合しています。照合しているのは原文との一致（意味・用語・加筆や訳漏れが無いこと）だけで、原文ページ自体が正しいかは見ていません。この照合が入る前に翻訳されたページには記録がありません。",
        "ai_findings": "うち指摘を受けて書き直された箇所",
        # Issue #1063: reader-facing names for review-rules.md's finding types,
        # never the enum names themselves.
        "finding_type_HALLUCINATION": "出典に書かれていない記述",
        "finding_type_CONTRADICTION": "出典と食い違う記述",
        "finding_type_MISSING_SOURCE": "手元に無い文書に依拠した記述",
        "finding_type_OTHER": "その他",
        # Issue #1063: a count only, never page names — naming a page that was
        # withheld would publish the heading of what was decided not to publish.
        "unpublished": "検査を通らず公開されなかったページ",
        "unpublished_note": (
            "生成の過程で出典に照らして直せなかったページは公開していません。"
            "この数は Wiki の欠陥ではなく、検査が働いた記録です。"
        ),
        "type_count": "型数",
        "by_lang": "言語別ページ数",
        "translation_coverage": "翻訳カバレッジ",
        "hubs": "知識の中心",
        "hubs_desc": "他のページから参照されている回数が多いページ。",
        "backlinks": "被リンク数",
        # Issue #990: a separate key from `sources` (the `## Sources` heading),
        # never a reuse of it — the same rule Issue #664 / #751 set for
        # `reviewed` and `ai_reviewed`.
        "sources_count": "情報源",
        "sources_count_note": (
            "「情報源」はそのページに記録されている出典の件数であり、"
            "独立した裏付けの数ではありません。"
            "ある文書そのものについてのページは、構造上 1 件になります。"
            "少ないことは劣っていることを意味しません。"
        ),
        # Issue #1006
        "hub_concentration": "上位 {n} 件のうち、次の情報源だけに立つもの:",
        "hub_concentration_count": "{n} 件",
        "hub_concentration_note": (
            "ここに挙がるのは、上の一覧で情報源が 1 件のページのうち、"
            "同じ情報源を共有しているものです。判定ではありません。"
            "ある文書そのものについてのページや、1 つの文書を主題とする Wiki では、"
            "集中するのが正しい形です。"
        ),
        "col_status": "ステータス",
        "col_host": "ホスト",
        "by_type": "型別の傾向",
        "col_type": "型",
        "col_pages": "ページ数",
        "col_reviewed": "人が読んで確認",
        "col_avg_backlinks": "平均被リンク数",
        "col_orphans": "孤立",
        "gaps": "知識の不足",
        "wanted": "参照されているが存在しないページ",
        "wanted_desc": "他のページから WikiLink で参照されているが、まだ書かれていないページ。",
        "referenced_by": "参照元",
        "orphans": "どこからも参照されていないページ",
        "sources": "情報源の内訳",
        "by_source_type": "種別別",
        "by_status": "ステータス別",
        "by_host": "ホスト別（URL ソース）",
        # Issue #989
        "by_source_lang": "言語別",
        "col_source_lang": "言語",
        "source_lang_unknown": "未記録",
        "source_lang_unprocessed": "未処理",
        "source_lang_note": (
            "ソースの抽出テキストが主として書かれている言語（生成時に LLM が判断）。"
            "ページは常にこの Wiki の主言語で書かれるため、"
            "主言語以外の行があるのは正常であり、"
            "そのソースから書かれたページは要約・翻訳を経ていることを意味します。"
            "「未記録」はこの記録が始まる前に取り込まれ、まだ読み直されていないソースです。"
            "「未処理」は登録されたがまだ一度も処理を終えていないソース（取り込み待ちの列）です。"
        ),
        "cross_tab": "情報源の種別 × 生成されたページの型",
        "col_source_type": "情報源の種別",
        "col_total": "合計",
        "tags": "タグ",
        "col_tag": "タグ",
        "col_count": "件数",
        "manual_note": "manual（ページの sources[] のみ。管理ファイルを持たない）",
        "none": "該当なし。",
        "more": "ほか {n} 件",
        "empty": "まだページがありません。",
    },
    "de": {
        "title": "Übersicht",
        "totals": "Auf einen Blick",
        "total_pages": "Seiten insgesamt",
        "reviewed": "Von einer Person gelesen und durchgesehen",
        "reviewed_note": "Seiten werden veröffentlicht, sobald ein LLM sie generiert. Der Abgleich mit den Quellen erfolgt maschinell; „von einer Person gelesen und durchgesehen“ gibt an, wie viele Seiten seitdem jemand vollständig gelesen hat, ohne dass etwas offensichtlich Falsches aufgefallen ist. Nur ein Teil der Seiten wird von einer Person gelesen, und das ist so gewollt — diese Zahl soll die Gesamtzahl nicht erreichen, und sie ist keine vollständige Qualitätsgarantie.",
        "ai_reviewed": "Mit Quellen abgeglichen (AI)",
        "ai_reviewed_note": "Jede aus Quellen generierte Seite wird bei ihrer Generierung mit diesen Quellen abgeglichen. Dieser Abgleich prüft nur die Übereinstimmung mit diesen Quellen und nichts anderes — nicht die Vollständigkeit, nicht die Auswirkungen auf reale Personen und Organisationen, nicht Widersprüche zu dem, was Sie wissen.",
        "translation_pages": "Übersetzungsseiten",
        "translation_pages_value": "{n} (kein Abgleich mit dem Original erfasst)",
        "translation_pages_note": "Übersetzungsseiten fallen nicht unter diesen Abgleich und sind im obigen Anteil nicht enthalten.",
        "translation_checked": "Mit dem Original abgeglichen (AI)",
        "translation_checked_note": "Jede Übersetzungsseite wird bei der Übersetzung mit der Seite abgeglichen, aus der sie übersetzt wurde. Dieser Abgleich prüft nur die Übereinstimmung mit dem Original — Bedeutung, Begriffe, nichts hinzugefügt oder ausgelassen — und nicht, ob das Original selbst stimmt. Seiten, die vor Einführung dieses Abgleichs übersetzt wurden, haben keinen Eintrag.",
        "ai_findings": "Vor der Veröffentlichung beanstandete und behobene Stellen",
        "finding_type_HALLUCINATION": "Aussagen, die in den Quellen nicht stehen",
        "finding_type_CONTRADICTION": "Aussagen, die den Quellen widersprechen",
        "finding_type_MISSING_SOURCE": "Aussagen, die sich auf ein Dokument stützen, das nicht unter den Quellen ist",
        "finding_type_OTHER": "Sonstiges",
        "unpublished": "Zurückgehaltene Seiten, die den Abgleich nicht bestanden haben",
        "unpublished_note": "Eine Seite, die während ihrer Generierung nicht mit ihren Quellen in Einklang gebracht werden konnte, wird nicht veröffentlicht. Diese Zahl zeigt, dass der Abgleich greift, und ist kein Mangel des Wikis.",
        "type_count": "Verwendete Typen",
        "by_lang": "Seiten pro Sprache",
        "translation_coverage": "Übersetzungsabdeckung",
        "hubs": "Wissensknoten",
        "hubs_desc": "Die Seiten, auf die andere Seiten am häufigsten verlinken.",
        "backlinks": "Backlinks",
        "sources_count": "Erfasste Quellen",
        "sources_count_note": "„Erfasste Quellen“ ist die Zahl der auf der Seite erfassten Quellen, nicht die Zahl unabhängiger Bestätigungen. Eine Seite über ein bestimmtes Dokument hat naturgemäß genau eine — weniger ist nicht schlechter.",
        "hub_concentration": "Von den Top {n} stützen sich diese allein auf eine Quelle:",
        "hub_concentration_count": "{n} Knoten",
        "hub_concentration_note": "Aufgeführt sind die obigen Knoten mit nur einer erfassten Quelle, die sich diese Quelle teilen. Das ist keine Bewertung: Eine Seite über ein bestimmtes Dokument oder ein Wiki, dessen Thema ein einzelnes Dokument ist, ist konzentriert, weil es so sein soll.",
        "col_status": "Status",
        "col_host": "Host",
        "by_type": "Nach Typ",
        "col_type": "Typ",
        "col_pages": "Seiten",
        "col_reviewed": "Gelesen + durchgesehen",
        "col_avg_backlinks": "Ø Backlinks",
        "col_orphans": "Verwaist",
        "gaps": "Lücken",
        "wanted": "Verlinkt, aber nicht geschrieben",
        "wanted_desc": "Seiten, auf die andere Seiten verlinken, die aber noch nicht existieren.",
        "referenced_by": "Verlinkt von",
        "orphans": "Seiten, auf die nichts verlinkt",
        "sources": "Quellen",
        "by_source_type": "Nach Typ",
        "by_status": "Nach Status",
        "by_host": "Nach Host (URL-Quellen)",
        "by_source_lang": "Nach Sprache",
        "col_source_lang": "Sprache",
        "source_lang_unknown": "Nicht erfasst",
        "source_lang_unprocessed": "Noch nicht verarbeitet",
        "source_lang_note": "Die Sprache, in der der extrahierte Text einer Quelle überwiegend geschrieben ist, wie vom LLM bei der Generierung eingeschätzt. Seiten werden immer in der Hauptsprache dieses Wikis geschrieben, daher ist eine Zeile für eine andere Sprache zu erwarten: Die aus diesen Quellen geschriebenen Seiten haben eine zusammenfassende Übersetzung durchlaufen. „Nicht erfasst“ zählt Quellen, die übernommen wurden, bevor dies erfasst wurde, und seitdem nicht erneut gelesen wurden. „Noch nicht verarbeitet“ zählt registrierte Quellen, deren Verarbeitung noch nie abgeschlossen wurde (die Warteschlange).",
        "cross_tab": "Quellentyp x Typ der generierten Seite",
        "col_source_type": "Quellentyp",
        "col_total": "Gesamt",
        "tags": "Tags",
        "col_tag": "Tag",
        "col_count": "Anzahl",
        "manual_note": "manual (nur sources[] der Seite; keine Verwaltungsdatei)",
        "none": "Keine.",
        "more": "und {n} weitere",
        "empty": "Noch keine Seiten.",
    },
    "es": {
        "title": "Panorama general",
        "totals": "De un vistazo",
        "total_pages": "Total de páginas",
        "reviewed": "Leídas y revisadas por una persona",
        "reviewed_note": "Las páginas se publican en cuanto un LLM las genera. El cotejo con las fuentes lo hace una máquina; «leídas y revisadas por una persona» es cuántas páginas ha leído después alguien de principio a fin sin que nada saltara a la vista como claramente erróneo. Por diseño, solo algunas páginas las lee una persona: esta cifra no pretende llegar al total y no es una garantía completa de calidad.",
        "ai_reviewed": "Cotejadas con las fuentes (AI)",
        "ai_reviewed_note": "Cada página generada a partir de fuentes se coteja con esas fuentes al generarse. Ese cotejo abarca la concordancia con esas fuentes y nada más: ni la exhaustividad, ni el efecto sobre personas y organizaciones reales, ni los conflictos con lo que tú sabes.",
        "translation_pages": "Páginas traducidas",
        "translation_pages_value": "{n} (no consta ningún cotejo con el original)",
        "translation_pages_note": "Las páginas traducidas quedan fuera de este cotejo y no se incluyen en la proporción anterior.",
        "translation_checked": "Cotejadas con el original (AI)",
        "translation_checked_note": "Cada página traducida se coteja, al traducirse, con la página de la que se tradujo. Ese cotejo abarca solo la concordancia con el original —significado, términos, nada añadido ni omitido— y no si el original es correcto. Las páginas traducidas antes de que existiera este cotejo no tienen registro.",
        "ai_findings": "Observaciones planteadas y corregidas antes de publicar",
        "finding_type_HALLUCINATION": "Afirmaciones que las fuentes no hacen",
        "finding_type_CONTRADICTION": "Afirmaciones que contradicen las fuentes",
        "finding_type_MISSING_SOURCE": "Afirmaciones basadas en un documento que no está entre las fuentes",
        "finding_type_OTHER": "Otras",
        "unpublished": "Páginas retenidas por no superar el cotejo",
        "unpublished_note": "Una página que no pudo ajustarse a sus fuentes durante su generación no se publica. Esto cuenta el cotejo en funcionamiento, no un defecto de la wiki.",
        "type_count": "Tipos en uso",
        "by_lang": "Páginas por idioma",
        "translation_coverage": "Cobertura de traducción",
        "hubs": "Núcleos de conocimiento",
        "hubs_desc": "Las páginas a las que más enlazan otras páginas.",
        "backlinks": "Enlaces entrantes",
        "sources_count": "Fuentes registradas",
        "sources_count_note": "«Fuentes registradas» es el número de fuentes registradas en la página, no el número de confirmaciones independientes. Una página sobre un documento concreto tiene exactamente una por construcción: tener menos no es peor.",
        "hub_concentration": "De los {n} primeros, estos se apoyan en una sola fuente:",
        "hub_concentration_count": "{n} núcleos",
        "hub_concentration_note": "Aquí figuran los núcleos anteriores con una sola fuente registrada que comparten esa fuente. No es un veredicto: una página sobre un documento concreto, o una wiki cuyo tema es un único documento, está concentrada porque así debe ser.",
        "col_status": "Estado",
        "col_host": "Host",
        "by_type": "Por tipo",
        "col_type": "Tipo",
        "col_pages": "Páginas",
        "col_reviewed": "Leídas + revisadas",
        "col_avg_backlinks": "Media de enlaces entrantes",
        "col_orphans": "Huérfanas",
        "gaps": "Lagunas",
        "wanted": "Referenciadas pero no escritas",
        "wanted_desc": "Páginas a las que enlazan otras páginas y que aún no existen.",
        "referenced_by": "Referenciada por",
        "orphans": "Páginas a las que nada enlaza",
        "sources": "Fuentes",
        "by_source_type": "Por tipo",
        "by_status": "Por estado",
        "by_host": "Por host (fuentes URL)",
        "by_source_lang": "Por idioma",
        "col_source_lang": "Idioma",
        "source_lang_unknown": "No registrado",
        "source_lang_unprocessed": "Aún sin procesar",
        "source_lang_note": "El idioma en el que está escrito principalmente el texto extraído de una fuente, según lo juzgó el LLM al generar. Las páginas se escriben siempre en el idioma principal de esta wiki, así que es normal que haya una fila para otro idioma: las páginas escritas a partir de esas fuentes pasaron por una traducción resumida. «No registrado» cuenta las fuentes incorporadas antes de que esto se registrara y que no se han vuelto a leer desde entonces. «Aún sin procesar» cuenta las fuentes registradas cuyo procesamiento todavía no ha terminado nunca (la cola).",
        "cross_tab": "Tipo de fuente x tipo de página generada",
        "col_source_type": "Tipo de fuente",
        "col_total": "Total",
        "tags": "Etiquetas",
        "col_tag": "Etiqueta",
        "col_count": "Recuento",
        "manual_note": "manual (solo sources[] de la página; sin archivo de gestión)",
        "none": "Ninguna.",
        "more": "y {n} más",
        "empty": "Aún no hay páginas.",
    },
    "fr": {
        "title": "Vue d'ensemble",
        "totals": "En bref",
        "total_pages": "Nombre total de pages",
        "reviewed": "Lues et examinées par une personne",
        "reviewed_note": "Les pages sont publiées dès qu'un LLM les génère. La comparaison avec les sources est effectuée par une machine ; « lues et examinées par une personne » indique combien de pages quelqu'un a depuis lues en entier sans que rien de manifestement faux n'ait été relevé. Seules certaines pages sont lues par une personne, par choix — ce nombre n'a pas vocation à atteindre le total, et ce n'est pas une garantie de qualité complète.",
        "ai_reviewed": "Comparées aux sources (AI)",
        "ai_reviewed_note": "Chaque page générée à partir de sources est comparée à ces sources lors de sa génération. Cette comparaison porte sur la concordance avec ces sources et rien d'autre — ni l'exhaustivité, ni l'effet sur des personnes et organisations réelles, ni les contradictions avec ce que vous savez.",
        "translation_pages": "Pages traduites",
        "translation_pages_value": "{n} (aucune comparaison avec l'original n'est enregistrée)",
        "translation_pages_note": "Les pages traduites ne sont pas concernées par cette comparaison et sont exclues du ratio ci-dessus.",
        "translation_checked": "Comparées à l'original (AI)",
        "translation_checked_note": "Chaque page traduite est comparée, lors de sa traduction, à la page dont elle est traduite. Cette comparaison porte uniquement sur la concordance avec l'original — sens, termes, rien d'ajouté ni d'omis — et non sur l'exactitude de l'original lui-même. Les pages traduites avant l'existence de cette comparaison n'ont pas d'enregistrement.",
        "ai_findings": "Problèmes relevés et corrigés avant publication",
        "finding_type_HALLUCINATION": "Affirmations absentes des sources",
        "finding_type_CONTRADICTION": "Affirmations qui contredisent les sources",
        "finding_type_MISSING_SOURCE": "Affirmations reposant sur un document absent des sources",
        "finding_type_OTHER": "Autre",
        "unpublished": "Pages retenues faute d'avoir passé la comparaison",
        "unpublished_note": "Une page qui n'a pas pu être mise en accord avec ses sources lors de sa génération n'est pas publiée. Ce chiffre montre la comparaison à l'œuvre, pas un défaut du wiki.",
        "type_count": "Types utilisés",
        "by_lang": "Pages par langue",
        "translation_coverage": "Couverture des traductions",
        "hubs": "Pôles de connaissance",
        "hubs_desc": "Les pages vers lesquelles les autres pages pointent le plus.",
        "backlinks": "Rétroliens",
        "sources_count": "Sources enregistrées",
        "sources_count_note": "« Sources enregistrées » est le nombre de sources enregistrées sur la page, et non le nombre de confirmations indépendantes. Une page consacrée à un document particulier en a exactement une par construction — moins n'est pas pire.",
        "hub_concentration": "Parmi les {n} premiers, ceux-ci reposent sur une seule source :",
        "hub_concentration_count": "{n} pôles",
        "hub_concentration_note": "Figurent ici les pôles ci-dessus qui n'ont qu'une seule source enregistrée et qui partagent cette source. Ce n'est pas un verdict : une page consacrée à un document particulier, ou un wiki dont le sujet est un seul document, est concentré parce qu'il doit l'être.",
        "col_status": "Statut",
        "col_host": "Hôte",
        "by_type": "Par type",
        "col_type": "Type",
        "col_pages": "Pages",
        "col_reviewed": "Lues + examinées",
        "col_avg_backlinks": "Rétroliens moy.",
        "col_orphans": "Orphelines",
        "gaps": "Lacunes",
        "wanted": "Référencées mais non rédigées",
        "wanted_desc": "Pages vers lesquelles d'autres pages pointent mais qui n'existent pas encore.",
        "referenced_by": "Référencée par",
        "orphans": "Pages vers lesquelles rien ne pointe",
        "sources": "Sources",
        "by_source_type": "Par type",
        "by_status": "Par statut",
        "by_host": "Par hôte (sources URL)",
        "by_source_lang": "Par langue",
        "col_source_lang": "Langue",
        "source_lang_unknown": "Non enregistrée",
        "source_lang_unprocessed": "Pas encore traitée",
        "source_lang_note": "La langue dans laquelle le texte extrait d'une source est principalement rédigé, telle qu'évaluée par le LLM lors de la génération. Les pages sont toujours rédigées dans la langue principale de ce wiki ; une ligne pour une autre langue est donc normale : les pages rédigées à partir de ces sources sont passées par une traduction résumée. « Non enregistrée » compte les sources importées avant que cette information ne soit enregistrée et qui n'ont pas été relues depuis. « Pas encore traitée » compte les sources enregistrées dont le traitement n'a encore jamais abouti (la file d'attente).",
        "cross_tab": "Type de source x type de page générée",
        "col_source_type": "Type de source",
        "col_total": "Total",
        "tags": "Étiquettes",
        "col_tag": "Étiquette",
        "col_count": "Nombre",
        "manual_note": "manual (sources[] de la page uniquement ; pas de fichier de gestion)",
        "none": "Aucun.",
        "more": "et {n} de plus",
        "empty": "Aucune page pour l'instant.",
    },
    "it": {
        "title": "Panoramica",
        "totals": "In sintesi",
        "total_pages": "Pagine totali",
        "reviewed": "Lette e controllate da una persona",
        "reviewed_note": "Le pagine vengono pubblicate non appena un LLM le genera. Il confronto con le fonti è eseguito da una macchina; \"lette e controllate da una persona\" indica quante pagine qualcuno ha poi letto per intero senza notare nulla di palesemente sbagliato. Per scelta, solo alcune pagine vengono lette da una persona: questo numero non è pensato per raggiungere il totale e non è una garanzia di qualità completa.",
        "ai_reviewed": "Confrontate con le fonti (AI)",
        "ai_reviewed_note": "Ogni pagina generata da fonti viene confrontata con quelle fonti al momento della generazione. Il confronto riguarda solo la concordanza con quelle fonti e nient'altro: non la completezza, non gli effetti su persone e organizzazioni reali, non i contrasti con ciò che sai.",
        "translation_pages": "Pagine tradotte",
        "translation_pages_value": "{n} (non è registrato alcun confronto con l'originale)",
        "translation_pages_note": "Le pagine tradotte sono escluse da questo confronto e non rientrano nella proporzione qui sopra.",
        "translation_checked": "Confrontate con l'originale (AI)",
        "translation_checked_note": "Ogni pagina tradotta viene confrontata, al momento della traduzione, con la pagina da cui è tradotta. Il confronto riguarda solo la concordanza con l'originale — significato, termini, nulla aggiunto od omesso — e non se l'originale sia corretto. Le pagine tradotte prima che esistesse questo confronto non hanno alcuna registrazione.",
        "ai_findings": "Rilievi segnalati e corretti prima della pubblicazione",
        "finding_type_HALLUCINATION": "Affermazioni che le fonti non fanno",
        "finding_type_CONTRADICTION": "Affermazioni in contrasto con le fonti",
        "finding_type_MISSING_SOURCE": "Affermazioni basate su un documento che non è tra le fonti",
        "finding_type_OTHER": "Altro",
        "unpublished": "Pagine non pubblicate perché non hanno superato il confronto",
        "unpublished_note": "Una pagina che durante la generazione non è stato possibile rendere coerente con le proprie fonti non viene pubblicata. Questo numero registra il confronto al lavoro, non un difetto del wiki.",
        "type_count": "Tipi in uso",
        "by_lang": "Pagine per lingua",
        "translation_coverage": "Copertura delle traduzioni",
        "hubs": "Pagine centrali",
        "hubs_desc": "Le pagine più collegate dalle altre pagine.",
        "backlinks": "Collegamenti in entrata",
        "sources_count": "Fonti registrate",
        "sources_count_note": "\"Fonti registrate\" è il numero di fonti registrate sulla pagina, non il numero di conferme indipendenti. Una pagina su un documento specifico ne ha per costruzione esattamente una: averne meno non è peggio.",
        "hub_concentration": "Delle prime {n}, queste poggiano su un'unica fonte:",
        "hub_concentration_count": "{n} pagine centrali",
        "hub_concentration_note": "Qui sono elencate le pagine centrali qui sopra con una sola fonte registrata che condividono quella fonte. Non è un giudizio: una pagina su un documento specifico, o un wiki il cui argomento è un solo documento, è concentrata perché è giusto che lo sia.",
        "col_status": "Stato",
        "col_host": "Host",
        "by_type": "Per tipo",
        "col_type": "Tipo",
        "col_pages": "Pagine",
        "col_reviewed": "Lette + controllate",
        "col_avg_backlinks": "Media collegamenti in entrata",
        "col_orphans": "Orfane",
        "gaps": "Lacune",
        "wanted": "Citate ma non scritte",
        "wanted_desc": "Pagine collegate da altre pagine che non esistono ancora.",
        "referenced_by": "Citata da",
        "orphans": "Pagine che nessuna pagina collega",
        "sources": "Fonti",
        "by_source_type": "Per tipo",
        "by_status": "Per stato",
        "by_host": "Per host (fonti URL)",
        "by_source_lang": "Per lingua",
        "col_source_lang": "Lingua",
        "source_lang_unknown": "Non registrata",
        "source_lang_unprocessed": "Non ancora elaborata",
        "source_lang_note": "La lingua in cui è scritto principalmente il testo estratto da una fonte, secondo il giudizio dell'LLM al momento della generazione. Le pagine sono sempre scritte nella lingua principale di questo wiki, quindi una riga per un'altra lingua è normale: le pagine scritte da quelle fonti sono passate per una traduzione riassuntiva. \"Non registrata\" conta le fonti acquisite prima che questo dato venisse registrato e non più rilette da allora. \"Non ancora elaborata\" conta le fonti registrate la cui elaborazione non si è mai ancora conclusa (la coda).",
        "cross_tab": "Tipo di fonte x tipo di pagina generata",
        "col_source_type": "Tipo di fonte",
        "col_total": "Totale",
        "tags": "Tag",
        "col_tag": "Tag",
        "col_count": "Conteggio",
        "manual_note": "manual (solo sources[] della pagina; nessun file di gestione)",
        "none": "Nessuna.",
        "more": "e altre {n}",
        "empty": "Ancora nessuna pagina.",
    },
    "pl": {
        "title": "Przegląd",
        "totals": "W skrócie",
        "total_pages": "Łączna liczba stron",
        "reviewed": "Przeczytane i sprawdzone przez człowieka",
        "reviewed_note": "Strony są publikowane od razu po wygenerowaniu przez LLM. Porównanie ze źródłami wykonuje maszyna; „przeczytane i sprawdzone przez człowieka” oznacza, ile stron ktoś od tego czasu przeczytał w całości, nie zauważając niczego wyraźnie błędnego. Z założenia człowiek czyta tylko część stron — ta liczba nie ma osiągnąć łącznej liczby stron i nie stanowi pełnej gwarancji jakości.",
        "ai_reviewed": "Porównane ze źródłami (AI)",
        "ai_reviewed_note": "Każda strona wygenerowana ze źródeł jest w chwili generowania porównywana z tymi źródłami. To porównanie obejmuje wyłącznie zgodność z tymi źródłami — nie kompletność, nie wpływ na rzeczywiste osoby i organizacje, nie sprzeczności z tym, co wiesz.",
        "translation_pages": "Strony tłumaczeń",
        "translation_pages_value": "{n} (nie zapisano porównania z oryginałem)",
        "translation_pages_note": "Strony tłumaczeń nie podlegają temu porównaniu i nie są wliczane do powyższego odsetka.",
        "translation_checked": "Porównane z oryginałem (AI)",
        "translation_checked_note": "Każda strona tłumaczenia jest w chwili tłumaczenia porównywana ze stroną, z której ją przetłumaczono. To porównanie obejmuje wyłącznie zgodność z oryginałem — znaczenie, terminy, nic dodanego ani pominiętego — a nie to, czy sam oryginał jest poprawny. Strony przetłumaczone przed wprowadzeniem tego porównania nie mają zapisu.",
        "ai_findings": "Uwagi zgłoszone i poprawione przed publikacją",
        "finding_type_HALLUCINATION": "Stwierdzenia, których źródła nie zawierają",
        "finding_type_CONTRADICTION": "Stwierdzenia sprzeczne ze źródłami",
        "finding_type_MISSING_SOURCE": "Stwierdzenia oparte na dokumencie spoza źródeł",
        "finding_type_OTHER": "Inne",
        "unpublished": "Strony wstrzymane, bo nie przeszły porównania",
        "unpublished_note": "Strona, której podczas generowania nie udało się uzgodnić z jej źródłami, nie jest publikowana. Ta liczba pokazuje działanie porównania, a nie wadę wiki.",
        "type_count": "Używane typy",
        "by_lang": "Strony według języka",
        "translation_coverage": "Pokrycie tłumaczeniami",
        "hubs": "Węzły wiedzy",
        "hubs_desc": "Strony, do których inne strony linkują najczęściej.",
        "backlinks": "Linki zwrotne",
        "sources_count": "Zapisane źródła",
        "sources_count_note": "„Zapisane źródła” to liczba źródeł zapisanych na stronie, a nie liczba niezależnych potwierdzeń. Strona o jednym konkretnym dokumencie z założenia ma dokładnie jedno — mniej nie znaczy gorzej.",
        "hub_concentration": "Spośród pierwszych pozycji (liczba: {n}) te opierają się tylko na jednym źródle:",
        "hub_concentration_count": "węzły: {n}",
        "hub_concentration_note": "Wymieniono tu te z powyższych węzłów, które mają jedno zapisane źródło, wspólne z innymi. To nie jest ocena: strona o jednym konkretnym dokumencie albo wiki, której tematem jest jeden dokument, jest skoncentrowana, bo tak powinna.",
        "col_status": "Status",
        "col_host": "Host",
        "by_type": "Według typu",
        "col_type": "Typ",
        "col_pages": "Strony",
        "col_reviewed": "Przeczytane + sprawdzone",
        "col_avg_backlinks": "Śr. linków zwrotnych",
        "col_orphans": "Osierocone",
        "gaps": "Luki",
        "wanted": "Przywoływane, ale nienapisane",
        "wanted_desc": "Strony, do których linkują inne strony, a które jeszcze nie istnieją.",
        "referenced_by": "Przywoływane przez",
        "orphans": "Strony, do których nic nie linkuje",
        "sources": "Źródła",
        "by_source_type": "Według typu",
        "by_status": "Według statusu",
        "by_host": "Według hosta (źródła URL)",
        "by_source_lang": "Według języka",
        "col_source_lang": "Język",
        "source_lang_unknown": "Nie zapisano",
        "source_lang_unprocessed": "Jeszcze nieprzetworzone",
        "source_lang_note": "Język, w którym głównie napisany jest tekst wyodrębniony ze źródła, według oceny LLM w chwili generowania. Strony są zawsze pisane w podstawowym języku tej wiki, więc wiersz dla innego języka jest normalny: strony napisane z tych źródeł przeszły tłumaczenie połączone ze streszczeniem. „Nie zapisano” obejmuje źródła pobrane, zanim zaczęto to zapisywać, i od tego czasu nieprzeczytane ponownie. „Jeszcze nieprzetworzone” obejmuje zarejestrowane źródła, których przetwarzanie nigdy jeszcze się nie zakończyło (kolejka).",
        "cross_tab": "Typ źródła x typ wygenerowanej strony",
        "col_source_type": "Typ źródła",
        "col_total": "Razem",
        "tags": "Tagi",
        "col_tag": "Tag",
        "col_count": "Liczba",
        "manual_note": "manual (tylko sources[] strony; brak pliku zarządzającego)",
        "none": "Brak.",
        "more": "i inne (liczba: {n})",
        "empty": "Brak stron.",
    },
    "pt": {
        "title": "Visão geral",
        "totals": "Em resumo",
        "total_pages": "Total de páginas",
        "reviewed": "Lidas e conferidas por uma pessoa",
        "reviewed_note": "As páginas são publicadas assim que um LLM as gera. A conferência com as fontes é feita por máquina; \"lidas e conferidas por uma pessoa\" é quantas páginas alguém leu depois até o fim sem que nada obviamente errado chamasse a atenção. Por design, apenas algumas páginas são lidas por uma pessoa — este número não pretende chegar ao total e não é uma garantia completa de qualidade.",
        "ai_reviewed": "Conferidas com as fontes (AI)",
        "ai_reviewed_note": "Cada página gerada a partir de fontes é conferida com essas fontes quando é gerada. Essa conferência cobre a concordância com essas fontes e nada mais — não a completude, não o efeito sobre pessoas e organizações reais, não conflitos com o que você sabe.",
        "translation_pages": "Páginas de tradução",
        "translation_pages_value": "{n} (nenhuma conferência com o original está registrada)",
        "translation_pages_note": "As páginas de tradução ficam fora desta conferência e não entram na proporção acima.",
        "translation_checked": "Conferidas com o original (AI)",
        "translation_checked_note": "Cada página de tradução é conferida, ao ser traduzida, com a página da qual foi traduzida. Essa conferência cobre apenas a concordância com o original — sentido, termos, nada acrescentado nem omitido — e não se o original está correto. Páginas traduzidas antes desta conferência existir não têm registro.",
        "ai_findings": "Apontamentos feitos e corrigidos antes da publicação",
        "finding_type_HALLUCINATION": "Afirmações que as fontes não fazem",
        "finding_type_CONTRADICTION": "Afirmações que contradizem as fontes",
        "finding_type_MISSING_SOURCE": "Afirmações apoiadas em um documento que não está entre as fontes",
        "finding_type_OTHER": "Outros",
        "unpublished": "Páginas retidas por não passarem na conferência",
        "unpublished_note": "Uma página que não pôde ser alinhada às suas fontes durante a geração não é publicada. Este número registra a conferência em funcionamento, não um defeito do wiki.",
        "type_count": "Tipos em uso",
        "by_lang": "Páginas por idioma",
        "translation_coverage": "Cobertura de tradução",
        "hubs": "Centros de conhecimento",
        "hubs_desc": "As páginas mais linkadas por outras páginas.",
        "backlinks": "Backlinks",
        "sources_count": "Fontes registradas",
        "sources_count_note": "\"Fontes registradas\" é o número de fontes registradas na página, não o número de confirmações independentes. Uma página sobre um documento específico tem exatamente uma, por construção — ter menos não é pior.",
        "hub_concentration": "Dos {n} primeiros, estes se apoiam em uma única fonte:",
        "hub_concentration_count": "{n} centros",
        "hub_concentration_note": "Aqui aparecem os centros acima com uma única fonte registrada que compartilham essa fonte. Isto não é um veredito: uma página sobre um documento específico, ou um wiki cujo assunto é um único documento, é concentrado porque deve ser.",
        "col_status": "Status",
        "col_host": "Host",
        "by_type": "Por tipo",
        "col_type": "Tipo",
        "col_pages": "Páginas",
        "col_reviewed": "Lidas + conferidas",
        "col_avg_backlinks": "Média de backlinks",
        "col_orphans": "Órfãs",
        "gaps": "Lacunas",
        "wanted": "Referenciadas mas não escritas",
        "wanted_desc": "Páginas linkadas por outras páginas que ainda não existem.",
        "referenced_by": "Referenciada por",
        "orphans": "Páginas sem nenhum link apontando para elas",
        "sources": "Fontes",
        "by_source_type": "Por tipo",
        "by_status": "Por status",
        "by_host": "Por host (fontes de URL)",
        "by_source_lang": "Por idioma",
        "col_source_lang": "Idioma",
        "source_lang_unknown": "Não registrado",
        "source_lang_unprocessed": "Ainda não processado",
        "source_lang_note": "O idioma em que o texto extraído de uma fonte está escrito predominantemente, conforme julgado pelo LLM no momento da geração. As páginas são sempre escritas no idioma principal deste wiki, então uma linha para outro idioma é esperada: as páginas escritas a partir dessas fontes passaram por uma tradução com resumo. \"Não registrado\" conta as fontes incorporadas antes de este registro existir e que não foram relidas desde então. \"Ainda não processado\" conta as fontes registradas cujo processamento ainda nunca foi concluído (a fila).",
        "cross_tab": "Tipo de fonte x tipo de página gerada",
        "col_source_type": "Tipo de fonte",
        "col_total": "Total",
        "tags": "Tags",
        "col_tag": "Tag",
        "col_count": "Quantidade",
        "manual_note": "manual (apenas sources[] da página; sem arquivo de gerenciamento)",
        "none": "Nenhum.",
        "more": "e mais {n}",
        "empty": "Nenhuma página ainda.",
    },
    "ru": {
        "title": "Обзор",
        "totals": "Коротко",
        "total_pages": "Всего страниц",
        "reviewed": "Прочитано и проверено человеком",
        "reviewed_note": "Страницы публикуются сразу после того, как их сгенерировала LLM. Сверку с источниками выполняет машина; «прочитано и проверено человеком» — это число страниц, которые кто-то затем прочитал целиком и не заметил ничего явно неверного. Человек читает лишь часть страниц, и так задумано: это число не должно достигать общего количества и не является полной гарантией качества.",
        "ai_reviewed": "Сверено с источниками (AI)",
        "ai_reviewed_note": "Каждая страница, сгенерированная из источников, при генерации сверяется с этими источниками. Эта проверка охватывает только согласованность с этими источниками и ничего больше — не полноту, не влияние на реальных людей и организации, не противоречия с тем, что знаете вы.",
        "translation_pages": "Страницы-переводы",
        "translation_pages_value": "{n} (сверка с оригиналом не записана)",
        "translation_pages_note": "Страницы-переводы не входят в эту проверку и не учитываются в доле выше.",
        "translation_checked": "Сверено с оригиналом (AI)",
        "translation_checked_note": "Каждая страница-перевод при переводе сверяется со страницей, с которой она переведена. Эта сверка охватывает только согласованность с оригиналом — смысл, термины, ничего не добавлено и не пропущено — и не то, верен ли сам оригинал. У страниц, переведённых до появления этой сверки, записи нет.",
        "ai_findings": "Замечания, выявленные и исправленные до публикации",
        "finding_type_HALLUCINATION": "Утверждения, которых нет в источниках",
        "finding_type_CONTRADICTION": "Утверждения, противоречащие источникам",
        "finding_type_MISSING_SOURCE": "Утверждения, опирающиеся на документ, которого нет среди источников",
        "finding_type_OTHER": "Прочее",
        "unpublished": "Страницы, не опубликованные, потому что не прошли проверку",
        "unpublished_note": "Страница, которую при генерации не удалось привести в согласие с её источниками, не публикуется. Это число показывает работу проверки, а не дефект вики.",
        "type_count": "Используемых типов",
        "by_lang": "Страниц по языкам",
        "translation_coverage": "Охват переводами",
        "hubs": "Узлы знаний",
        "hubs_desc": "Страницы, на которые чаще всего ссылаются другие страницы.",
        "backlinks": "Обратные ссылки",
        "sources_count": "Записано источников",
        "sources_count_note": "«Записано источников» — это число источников, записанных на странице, а не число независимых подтверждений. У страницы об одном конкретном документе по определению ровно один источник — меньше не значит хуже.",
        "hub_concentration": "Из первых {n} только на одном источнике держатся:",
        "hub_concentration_count": "узлов: {n}",
        "hub_concentration_note": "Здесь перечислены узлы из списка выше с единственным записанным источником, у которых этот источник общий. Это не приговор: страница об одном конкретном документе или вики, предмет которой — один документ, сосредоточены на одном источнике, потому что так и должно быть.",
        "col_status": "Статус",
        "col_host": "Хост",
        "by_type": "По типам",
        "col_type": "Тип",
        "col_pages": "Страниц",
        "col_reviewed": "Прочитано + проверено",
        "col_avg_backlinks": "Ср. обратных ссылок",
        "col_orphans": "Страницы-сироты",
        "gaps": "Пробелы",
        "wanted": "Упоминаются, но не написаны",
        "wanted_desc": "Страницы, на которые ссылаются другие страницы, но которых ещё нет.",
        "referenced_by": "Ссылаются",
        "orphans": "Страницы, на которые никто не ссылается",
        "sources": "Источники",
        "by_source_type": "По типам",
        "by_status": "По статусу",
        "by_host": "По хостам (URL-источники)",
        "by_source_lang": "По языкам",
        "col_source_lang": "Язык",
        "source_lang_unknown": "Не записано",
        "source_lang_unprocessed": "Ещё не обработано",
        "source_lang_note": "Язык, на котором в основном написан извлечённый текст источника, по оценке LLM при генерации. Страницы всегда пишутся на основном языке этой вики, поэтому строка для другого языка ожидаема: страницы, написанные по таким источникам, прошли через перевод с пересказом. «Не записано» — источники, взятые до того, как это начали записывать, и с тех пор не перечитанные. «Ещё не обработано» — зарегистрированные источники, обработка которых ещё ни разу не была завершена (очередь).",
        "cross_tab": "Тип источника × тип сгенерированной страницы",
        "col_source_type": "Тип источника",
        "col_total": "Итого",
        "tags": "Теги",
        "col_tag": "Тег",
        "col_count": "Количество",
        "manual_note": "manual (только sources[] страницы; файла управления нет)",
        "none": "Нет.",
        "more": "и ещё {n}",
        "empty": "Страниц пока нет.",
    },
    "zh": {
        "title": "概览",
        "totals": "总体数字",
        "total_pages": "页面总数",
        "reviewed": "经人阅读并检查",
        "reviewed_note": "页面在 LLM 生成后即会发布。与来源的比对由机器完成；“经人阅读并检查”是指此后有人从头读完、且未发现明显问题的页面数。按照设计，只有部分页面会由人阅读——这个数字并不以达到总数为目标，也不是完整的质量保证。",
        "ai_reviewed": "已与来源比对（AI）",
        "ai_reviewed_note": "每个根据来源生成的页面，在生成时都会与这些来源进行比对。该比对只涵盖与这些来源是否一致，不涉及其他方面——不涉及内容是否完整，不涉及对真实人物和组织的影响，也不涉及与你所了解情况的冲突。",
        "translation_pages": "翻译页面",
        "translation_pages_value": "{n}（未记录与原文的比对）",
        "translation_pages_note": "翻译页面不在此比对范围内，也未计入上面的比例。",
        "translation_checked": "已与原文比对（AI）",
        "translation_checked_note": "每个翻译页面在翻译时都会与其原文页面进行比对。该比对只涵盖与原文是否一致（含义、术语、无增添无遗漏），不涉及原文本身是否正确。在此比对出现之前翻译的页面没有记录。",
        "ai_findings": "发布前被指出并修正的问题",
        "finding_type_HALLUCINATION": "来源中没有的陈述",
        "finding_type_CONTRADICTION": "与来源相矛盾的陈述",
        "finding_type_MISSING_SOURCE": "依据不在来源之列的文档的陈述",
        "finding_type_OTHER": "其他",
        "unpublished": "因未通过检查而未发布的页面",
        "unpublished_note": "在生成过程中无法与其来源保持一致的页面不会发布。这个数字记录的是检查在发挥作用，而不是 Wiki 的缺陷。",
        "type_count": "使用中的类型数",
        "by_lang": "各语言页面数",
        "translation_coverage": "翻译覆盖率",
        "hubs": "知识中心",
        "hubs_desc": "被其他页面链接最多的页面。",
        "backlinks": "反向链接",
        "sources_count": "记录的来源数",
        "sources_count_note": "“记录的来源数”是页面上记录的来源数量，而不是独立佐证的数量。关于某一特定文档的页面，按结构只会有一个——数量少并不代表更差。",
        "hub_concentration": "在前 {n} 个中，以下仅依赖于单一来源：",
        "hub_concentration_count": "{n} 个知识中心",
        "hub_concentration_note": "此处列出的是上面列表中只记录了一个来源、且共用同一来源的知识中心。这并不是判定：关于某一特定文档的页面，或以单一文档为主题的 Wiki，本来就应当集中于该来源。",
        "col_status": "状态",
        "col_host": "主机",
        "by_type": "按类型",
        "col_type": "类型",
        "col_pages": "页面数",
        "col_reviewed": "经人阅读并检查",
        "col_avg_backlinks": "平均反向链接数",
        "col_orphans": "孤立页面",
        "gaps": "缺口",
        "wanted": "被引用但尚未撰写",
        "wanted_desc": "被其他页面链接但尚不存在的页面。",
        "referenced_by": "被引用于",
        "orphans": "没有任何页面链接的页面",
        "sources": "来源",
        "by_source_type": "按类型",
        "by_status": "按状态",
        "by_host": "按主机（URL 来源）",
        "by_source_lang": "按语言",
        "col_source_lang": "语言",
        "source_lang_unknown": "未记录",
        "source_lang_unprocessed": "尚未处理",
        "source_lang_note": "来源的提取文本主要使用的语言，由 LLM 在生成时判断。页面始终以本 Wiki 的主要语言撰写，因此出现其他语言的行属于正常情况：根据这些来源撰写的页面经过了概括性的翻译。“未记录”统计的是在开始记录此项之前导入、此后尚未重新读取的来源。“尚未处理”统计的是已登记但尚未完成过一次处理的来源（待处理队列）。",
        "cross_tab": "来源类型 × 生成页面类型",
        "col_source_type": "来源类型",
        "col_total": "合计",
        "tags": "标签",
        "col_tag": "标签",
        "col_count": "数量",
        "manual_note": "manual（仅页面的 sources[]；无管理文件）",
        "none": "无。",
        "more": "另有 {n} 个",
        "empty": "尚无页面。",
    },
}
DEFAULT_OVERVIEW_LABELS = {
    "title": "Overview",
    "totals": "At a glance",
    "total_pages": "Total pages",
    "reviewed": "Read and checked by a person",
    "reviewed_note": (
        "Pages are published as soon as an LLM generates them. The check against sources "
        "is run by machine; \"read and checked by a person\" is how many pages "
        "someone has since read all the way through without anything obviously "
        "wrong standing out. Only some pages are read by a person, by design — this "
        "number is not meant to reach the total, and it is not a complete quality "
        "guarantee."
    ),
    "ai_reviewed": "Checked against sources (AI)",
    "ai_reviewed_note": (
        "Each page generated from sources is checked against those sources when it is "
        "generated. That check "
        "covers agreement with those sources and nothing else — not completeness, not "
        "the effect on real people and organizations, not conflicts with what you know."
    ),
    "translation_pages": "Translation pages",
    "translation_pages_value": "{n} (no check against the original is recorded)",
    "translation_pages_note": (
        "Translation pages are outside this check and are left out of the ratio above."
    ),
    # Issue #1031: a translation is checked against its original page, never
    # against sources, so it gets its own line and its own caption — adding it
    # to "checked against sources" would claim a comparison it never made.
    "translation_checked": "Checked against the original (AI)",
    "translation_checked_note": (
        "Each translation page is checked against the page it was translated from when "
        "it is translated. That check covers agreement with the original — meaning, "
        "terms, nothing added or dropped — and not whether the original itself is right. "
        "Pages translated before this check existed carry no record."
    ),
    "ai_findings": "Findings raised and fixed before publishing",
    "finding_type_HALLUCINATION": "Statements the sources do not make",
    "finding_type_CONTRADICTION": "Statements that contradict the sources",
    "finding_type_MISSING_SOURCE": "Statements resting on a document not among the sources",
    "finding_type_OTHER": "Other",
    "unpublished": "Pages withheld because they did not pass the check",
    "unpublished_note": (
        "A page that could not be brought in line with its sources while it was being "
        "generated is not published. This counts the check at work, not a defect in the wiki."
    ),
    "type_count": "Types in use",
    "by_lang": "Pages per language",
    "translation_coverage": "Translation coverage",
    "hubs": "Knowledge hubs",
    "hubs_desc": "The pages other pages link to most.",
    "backlinks": "Backlinks",
    # Not "Sources": that is already the `## Sources` heading.
    "sources_count": "Sources recorded",
    "sources_count_note": (
        "\"Sources recorded\" is the number of sources recorded on the page, not the number "
        "of independent confirmations. A page about one particular document has "
        "exactly one by construction — fewer is not worse."
    ),
    # Issue #1006
    "hub_concentration": "Of the top {n}, these stand on one source alone:",
    "hub_concentration_count": "{n} hubs",
    "hub_concentration_note": (
        "Listed here are the hubs above with a single recorded source that share that "
        "source. This is not a verdict: a page about one particular document, or a wiki "
        "whose subject is one document, is concentrated because it should be."
    ),
    "col_status": "Status",
    "col_host": "Host",
    "by_type": "By type",
    "col_type": "Type",
    "col_pages": "Pages",
    "col_reviewed": "Read + checked",
    "col_avg_backlinks": "Avg. backlinks",
    "col_orphans": "Orphans",
    "gaps": "Gaps",
    "wanted": "Referenced but not written",
    "wanted_desc": "Pages other pages link to that do not exist yet.",
    "referenced_by": "Referenced by",
    "orphans": "Pages nothing links to",
    "sources": "Sources",
    "by_source_type": "By type",
    "by_status": "By status",
    "by_host": "By host (URL sources)",
    "by_source_lang": "By language",
    "col_source_lang": "Language",
    "source_lang_unknown": "Not recorded",
    "source_lang_unprocessed": "Not processed yet",
    "source_lang_note": (
        "The language a source's extracted text is mainly written in, as judged by the "
        "LLM at generation time. Pages are always written in this wiki's primary "
        "language, so a row for another language is expected: the pages written from "
        "those sources went through a summarizing translation. \"Not recorded\" counts "
        "sources taken in before this was recorded that have not been re-read since. "
        "\"Not processed yet\" counts registered sources that have never finished a "
        "run (the queue)."
    ),
    "cross_tab": "Source type x generated page type",
    "col_source_type": "Source type",
    "col_total": "Total",
    "tags": "Tags",
    "col_tag": "Tag",
    "col_count": "Count",
    "manual_note": "manual (page sources[] only; no management file)",
    "none": "None.",
    "more": "and {n} more",
    "empty": "No pages yet.",
}

# Top-N caps. The initial overview is a single content/overview/index.md with
# `##` sections (splitting it across pages is explicitly out of scope until it
# stops fitting), so every ranked list is bounded rather than left to grow with
# the wiki.
OVERVIEW_HUB_LIMIT = 20
OVERVIEW_WANTED_LIMIT = 20
OVERVIEW_ORPHAN_LIMIT = 20
OVERVIEW_HOST_LIMIT = 20
OVERVIEW_TAG_LIMIT = 30


def _pct(part: int, whole: int) -> str:
    """Render part/whole as a whole-number percentage, or "-" when whole is 0."""
    return "-" if whole <= 0 else f"{round(part * 100 / whole)}%"


def overview_link(out_rel_path: Path) -> str:
    """Relative Markdown link from content/overview/index.md to a published page."""
    return _dot_relpath(out_rel_path.as_posix(), OVERVIEW_DIR_NAME)


def _escape_table_cell(text: str) -> str:
    """Escape a value for a GFM table cell.

    A single `|` in a tag, host or type name would otherwise split the row into
    extra columns and shift every value after it. `\\|` is the escape GFM
    defines for this, and it works inside a code span too, which is how most of
    these cells are rendered. Newlines would end the row outright, so they
    collapse to spaces.
    """
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    return (
        ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
        + ["| " + " | ".join(_escape_table_cell(c) for c in r) + " |" for r in rows]
        + [""]
    )


def _truncated(items: list, limit: int, labels: dict) -> tuple[list, str | None]:
    """Return (items[:limit], a "and N more" line or None)."""
    if len(items) <= limit:
        return items, None
    return items[:limit], labels["more"].format(n=len(items) - limit)


def _hub_concentration_lines(shown_pages: list[dict], source_stats: dict, labels: dict) -> list[str]:
    """Lines reporting that several of the shown hubs stand on one source alone
    (Issue #1006).

    Issue #990 put a source count on each hub row, but a column of "1"s cannot
    say that seven of them are the *same* 1. This groups the one-source hubs
    by that source's identity and reports each source holding two or more.

    Only one-source hubs are counted. Counting every hub a source appears on
    would light up a healthy wiki's main article (a novel's Wikipedia entry is
    on most of its hubs alongside other sources), which is not concentration.
    Translation and view pages carry no identity (`source_ids` is None) and are
    outside the count, as they are outside the per-row figure.

    A report, not a verdict — the lead note says why, in the same register as
    `sources_count_note`. The rows are not marked (marking is a verdict, Issue
    #990); the reader follows the link to the source page, which lists the
    pages it generated. Nothing is emitted when no source holds two, not even
    "none": an absence of concentration is not a finding.
    """
    counts: dict[str, int] = {}
    for p in shown_pages:
        ids = p.get("source_ids")
        # A hand-written `url: [a, b]` or `path: 2024` is not an identity: an
        # unhashable value would crash the build here, and a non-string one in
        # _escape_md_link_text below.
        if p.get("source_count") != 1 or not ids or not isinstance(ids[0], str) or not ids[0]:
            continue
        counts[ids[0]] = counts.get(ids[0], 0) + 1
    shared = sorted(((i, n) for i, n in counts.items() if n >= 2), key=lambda x: (-x[1], x[0]))
    if not shared:
        return []
    page_for_source = source_stats.get("page_for_source", {})
    out = ["", labels["hub_concentration_note"], "", labels["hub_concentration"].format(n=len(shown_pages)), ""]
    for ident, n in shared:
        text = _escape_md_link_text(ident)
        target = page_for_source.get(ident)
        shown = f"[{text}]({overview_link(target)})" if target is not None else text
        out.append(f"- {shown} — {labels['hub_concentration_count'].format(n=n)}")
    return out


def generate_overview_page(
    output_dir: Path,
    primary_lang: str,
    page_stats: list[dict],
    referrers: dict[str, set[str]],
    removed_keys: set[str],
    source_stats: dict,
    unpublished_pages: int = 0,
) -> Path:
    """Write content/overview/index.md and return its output-dir-relative path.

    `page_stats` is one entry per page this build actually published (index.md
    pages included, flagged), `referrers` maps each `Type/slug` key to the set
    of `Type/slug` keys linking at it, `removed_keys` holds the keys of pages
    skipped as `status: removed`, and `source_stats` is what
    generate_source_pages() tallied.

    Counting is by key, not by page: a WikiLink carries no language, so a page
    and its translations are one node here. Every count would otherwise double
    the moment a wiki gains a second language, without a single new link having
    been written. Each key is represented by its primary-language page wherever
    one page has to stand in for the node (hub rows, referrer links).

    Three deliberate differences from check_orphans.py / check_wanted_pages.py,
    which compute the same graph over .wikicommit/entity/:

    - Removed pages contribute no outbound links here. They are not published,
      so a link only they make cannot be followed by any reader of this site.
      A page kept alive solely by a removed page's link is therefore an orphan
      on this page while check_orphans.py still counts it as referenced.
    - A wanted key whose slug exists under a different Type is dropped rather
      than listed. Issue #563 established that such a link is a Type typo, not
      a missing page; telling a reader to write a page that already exists is
      worse than saying nothing. check_wanted_pages.py reports those as
      TYPE_MISMATCH for the operator, which is the right audience for them.
    - A page's link to itself is not a backlink to itself, so a page whose only
      inbound link is its own is an orphan here. check_orphans.py counts it as
      referenced.

    One page kind reaches neither: a .md that does not resolve to
    <lang>/<Type>/<slug>.md has no key to place it under, so it is absent from
    every tally here while still counting toward the root index's
    wikicommit_page_count (Issue #407). Such a file is not a wiki page in the
    sense the rest of the pipeline uses.
    """
    labels = OVERVIEW_LABELS.get(primary_lang, DEFAULT_OVERVIEW_LABELS)

    content_pages = [p for p in page_stats if not p["is_index"]]
    total_pages = len(content_pages)
    reviewed_pages = sum(1 for p in content_pages if p["review_status"] == "reviewed")

    backlink_count = {p["key"]: len(referrers.get(p["key"], set()) - {p["key"]}) for p in content_pages}

    lines = [
        "---",
        f"title: {_yaml_quote(labels['title'])}",
        # Build-generated navigation, not LLM-authored wiki content, so it must
        # not carry WikiCommitBanner's "unreviewed" warning (which defaults to
        # pending when the field is absent) — same as content/index.md and
        # every content/sources/ page.
        "review_status: reviewed",
        # comments: false — giscus (github:quartz-community/comments) renders into
        # afterBody on every page, and these navigation and aggregation pages have
        # nothing for a reader to respond to (Issue #741). The plugin skips a page
        # whose frontmatter says so, and this is the same place, and the same
        # reasoning, as the review_status stamp above: decided by the side that
        # writes the page, not guessed from a slug at render time (Issue #580).
        "comments: false",
        "---",
        "",
    ]

    if not content_pages:
        lines += [labels["empty"]]
        out_rel = Path(OVERVIEW_DIR_NAME) / "index.md"
        out_path = output_dir / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
        print(f"Generating overview: {out_path}")
        return out_rel

    # ── 1. At a glance ────────────────────────────────────────────────────────
    pages_by_lang: dict[str, list[dict]] = {}
    pages_by_type: dict[str, list[dict]] = {}
    keys_by_lang: dict[str, set[str]] = {}
    for p in content_pages:
        pages_by_lang.setdefault(p["lang"], []).append(p)
        pages_by_type.setdefault(p["type"], []).append(p)
        keys_by_lang.setdefault(p["lang"], set()).add(p["key"])

    # Issue #751: the site-wide numbers live here, never on the page banner.
    # "2 findings" beside one page reads as "this page is bad" when it means the
    # opposite — a finding was raised and the page was rewritten until it passed.
    # Aggregated, the same number says the check has teeth.
    # Issue #1030: the ratio is taken over pages that can carry a check against
    # sources at all. A translation inherits its sources (translated_from) and
    # wikicommit-translate writes no review record (Issue #750), so counting it
    # in the denominator made every translation lower the figure. Numerator and
    # denominator are narrowed together — a translation that does carry an AI
    # record (/wikicommit-review run on it) would otherwise push the ratio past
    # 100%. Split on translated_from, not on language (Issue #769 split the root
    # index by language for a different purpose): a language can hold both
    # originals and translations.
    checkable_pages = [p for p in content_pages if not p["is_translation"]]
    translation_count = total_pages - len(checkable_pages)
    # Issue #1031: a translation's own check is against its original page, so
    # it is counted on its own line, never added to the one above.
    translation_checked = [
        p for p in content_pages
        if p["is_translation"] and (p.get("ai_review") or {}).get("stage") == TRANSLATE_CHECK_STAGE
    ]
    ai_reviewed = [p for p in checkable_pages if p.get("ai_review")]
    ai_models = sorted({p["ai_review"]["model"] for p in ai_reviewed})
    # The total, not the number of pages carrying one: what this number is for
    # is showing that the check has teeth, and a page caught three times says
    # more about that than a page caught once.
    findings_by_type: dict[str, int] = {}
    for p in ai_reviewed:
        for kind, n in p["ai_review"]["findings_by_type"].items():
            findings_by_type[kind] = findings_by_type.get(kind, 0) + n
    ai_findings_total = sum(findings_by_type.values())

    lang_summary = ", ".join(f"{lang} {len(ps)}" for lang, ps in sorted(pages_by_lang.items()))
    lines += [
        f"## {labels['totals']}",
        "",
        f"- **{labels['total_pages']}**: {total_pages}",
    ]
    # Omitted entirely on a wiki whose pages all predate the record tree, rather
    # than shown as a zero: "0 / 95 checked" reads as a failed check, when the
    # truth is that the check ran and left no record to count (Issue #750 —
    # records cannot be made retroactively).
    if ai_reviewed:
        model_note = f" ({', '.join(ai_models)})" if ai_models else ""
        lines.append(
            f"- **{labels['ai_reviewed']}**: {len(ai_reviewed)} / {len(checkable_pages)} "
            f"({_pct(len(ai_reviewed), len(checkable_pages))}){model_note}"
        )
        if ai_findings_total:
            lines.append(f"- **{labels['ai_findings']}**: {ai_findings_total}")
            # The breakdown sums to the total by construction (same records, same
            # exclusion), and must: a reader would take a mismatch to mean one of
            # the two is wrong. Types with no findings are not listed.
            for kind in (*FINDING_TYPES, OTHER_FINDING_TYPE):
                if findings_by_type.get(kind):
                    lines.append(f"  - {labels['finding_type_' + kind]}: {findings_by_type[kind]}")
    # Issue #1031 replaces Issue #1030's "no check is recorded" line once any
    # translation carries a check; until then that line stays, and it is still
    # emitted only beside the sources line (a wiki with no records at all keeps
    # its output unchanged).
    if translation_count and translation_checked:
        lines.append(
            f"- **{labels['translation_checked']}**: {len(translation_checked)} / {translation_count} "
            f"({_pct(len(translation_checked), translation_count)})"
        )
    elif translation_count and ai_reviewed:
        lines.append(
            f"- **{labels['translation_pages']}**: "
            + labels["translation_pages_value"].format(n=translation_count)
        )
    if unpublished_pages:
        lines.append(f"- **{labels['unpublished']}**: {unpublished_pages}")
    lines += [
        f"- **{labels['reviewed']}**: {reviewed_pages} / {total_pages} ({_pct(reviewed_pages, total_pages)})",
        f"- **{labels['type_count']}**: {len(pages_by_type)}",
        f"- **{labels['by_lang']}**: {lang_summary}",
    ]

    # Coverage counts Type/slug keys rather than raw page totals, so a target
    # language that has pages the primary language lacks cannot read as more
    # than fully translated.
    primary_keys = keys_by_lang.get(primary_lang, set())
    coverage = [
        f"{lang} {len(keys & primary_keys)} / {len(primary_keys)} ({_pct(len(keys & primary_keys), len(primary_keys))})"
        for lang, keys in sorted(keys_by_lang.items())
        if lang != primary_lang
    ]
    if coverage:
        lines.append(f"- **{labels['translation_coverage']}**: {', '.join(coverage)}")
    # The caption goes after the last bullet, not in the middle of the list:
    # translation coverage is appended conditionally above, so emitting the note
    # with the other totals would split the list on every multi-language wiki and
    # leave the coverage bullet reading as if the caption introduced it.
    lines += ["", labels["reviewed_note"], ""]
    # Says what the machine check actually compared. Without it "checked against
    # sources" is read as "verified", which is the same over-claim Issue #740 is
    # correcting on the human side — made once in each direction is still twice.
    if ai_reviewed:
        lines += [labels["ai_reviewed_note"], ""]
        if translation_count:
            lines += [labels["translation_pages_note"], ""]
    if translation_checked:
        lines += [labels["translation_checked_note"], ""]
    if unpublished_pages:
        lines += [labels["unpublished_note"], ""]

    # ── 2. Knowledge hubs ─────────────────────────────────────────────────────
    # One row per key, not per page: a key's backlink count is language-neutral
    # (WikiLinks carry no lang), so listing every translation of a hub would
    # repeat the same number down the table. The primary-language page is the
    # link target when it exists.
    best_page_for_key: dict[str, dict] = {}
    for p in sorted(content_pages, key=lambda e: (e["lang"] != primary_lang, e["lang"], e["out_rel"].as_posix())):
        best_page_for_key.setdefault(p["key"], p)

    hub_keys = sorted(
        (k for k in best_page_for_key if backlink_count.get(k, 0) > 0),
        key=lambda k: (-backlink_count[k], k),
    )
    lines += [f"## {labels['hubs']}", "", labels["hubs_desc"], ""]
    shown_hubs, more_hubs = _truncated(hub_keys, OVERVIEW_HUB_LIMIT, labels)
    if shown_hubs:
        # Issue #990: said once, before the rows, because the number is easy to
        # misread as a verdict — see `sources_count_note`.
        lines += [labels["sources_count_note"], ""]
        for key in shown_hubs:
            p = best_page_for_key[key]
            # Issue #990: the source count is omitted, not written as 0, on a
            # page that does not carry its own sources[] (translation, view).
            n_sources = p["source_count"]
            sources_part = (
                f" / {labels['sources_count']}: {n_sources}" if n_sources is not None else ""
            )
            lines.append(
                f"- [{_escape_md_link_text(p['title'])}]({overview_link(p['out_rel'])})"
                f" — {labels['backlinks']}: {backlink_count[key]}{sources_part}"
            )
        if more_hubs:
            lines.append(f"- {more_hubs}")
        lines += _hub_concentration_lines(
            [best_page_for_key[k] for k in shown_hubs], source_stats, labels
        )
    else:
        lines.append(labels["none"])
    lines.append("")

    # ── 3. By type ────────────────────────────────────────────────────────────
    lines += [f"## {labels['by_type']}", ""]
    rows = []
    for type_name, ps in sorted(pages_by_type.items()):
        counts = [backlink_count.get(p["key"], 0) for p in ps]
        reviewed = sum(1 for p in ps if p["review_status"] == "reviewed")
        rows.append([
            f"`{type_name}`",
            str(len(ps)),
            f"{reviewed} ({_pct(reviewed, len(ps))})",
            f"{sum(counts) / len(counts):.1f}",
            # Same exclusion the orphan list below applies, so this column and
            # that list never contradict each other (Issue #675).
            str(sum(1 for p in ps if not p["is_view"] and backlink_count.get(p["key"], 0) == 0)),
        ])
    lines += _md_table(
        [labels["col_type"], labels["col_pages"], labels["col_reviewed"],
         labels["col_avg_backlinks"], labels["col_orphans"]],
        rows,
    )

    # ── 4. Gaps ───────────────────────────────────────────────────────────────
    existing_keys = {p["key"] for p in page_stats} | removed_keys
    # index.md pages are left out for the same reason build_slug_type_index()
    # leaves them out: every Type has one, so matching a link's slug against
    # `index` says nothing about whether its Type segment is wrong.
    # Same shape build_slug_type_index() returns, so the Type-typo test below is
    # the shared other_types_for_slug() rather than a second copy of it
    # (Issue #677). Built from this build's published set instead of a rescan of
    # `.wikicommit/entity/` — that difference is the point (see this function's
    # docstring), and it is exactly what the parameterized index allows.
    slug_index: dict[str, set[str]] = {}
    for p in content_pages:
        slug_index.setdefault(p["slug"], set()).add(p["type_raw"])

    wanted: list[tuple[str, list[dict]]] = []
    for key in sorted(referrers):
        if key in existing_keys:
            continue
        type_name, _, slug = key.rpartition("/")
        if other_types_for_slug(type_name, slug, slug_index):
            continue  # Type typo, not a missing page (Issue #563)
        # Referrers come straight out of the graph rather than a rescan of every
        # page per key, and are counted in the same unit as the hub ranking:
        # one entry per referring *key*, represented by its primary-language
        # page. A referrer key can only have come from a published page, so
        # best_page_for_key always has it.
        refs = [best_page_for_key[k] for k in sorted(referrers[key]) if k in best_page_for_key]
        refs.sort(key=lambda e: e["out_rel"].as_posix())
        if refs:
            wanted.append((key, refs))
    wanted.sort(key=lambda e: (-len(e[1]), e[0]))

    # The section description says "WikiLink" in words rather than showing the
    # `[[Type/slug]]` form: this is the one remaining place a literal `[[` could
    # reach the published page, and Quartz's Obsidian-flavored-markdown pass
    # would be the one deciding what to do with it.
    lines += [f"## {labels['gaps']}", "", f"### {labels['wanted']}", "", labels["wanted_desc"], ""]
    shown_wanted, more_wanted = _truncated(wanted, OVERVIEW_WANTED_LIMIT, labels)
    if shown_wanted:
        for key, refs in shown_wanted:
            # Rendered as code, never as [[Type/slug]]: by definition nothing
            # backs this key, so emitting a WikiLink would leave an unresolved
            # link on the published page. The links point at the referrers.
            ref_links = ", ".join(
                f"[{_escape_md_link_text(r['title'])}]({overview_link(r['out_rel'])})" for r in refs
            )
            lines.append(f"- `{key}` — {labels['referenced_by']}: {ref_links}")
        if more_wanted:
            lines.append(f"- {more_wanted}")
    else:
        lines.append(labels["none"])

    # View pages are left out for the same reason `check_orphans.py` does not
    # walk the view tree at all (Issue #675): a view page is unlinked the moment
    # it is written — nothing but its own language index points at one — so every
    # view page in every wiki would sit in this list permanently, which is how a
    # report stops being read. Their outbound links still count toward everyone
    # else's backlinks; only their eligibility as a finding is removed.
    orphans = sorted(
        (
            p for p in content_pages
            if not p["is_view"] and backlink_count.get(p["key"], 0) == 0
        ),
        key=lambda e: e["out_rel"].as_posix(),
    )
    lines += ["", f"### {labels['orphans']}", ""]
    shown_orphans, more_orphans = _truncated(orphans, OVERVIEW_ORPHAN_LIMIT, labels)
    if shown_orphans:
        for p in shown_orphans:
            lines.append(f"- [{_escape_md_link_text(p['title'])}]({overview_link(p['out_rel'])})")
        if more_orphans:
            lines.append(f"- {more_orphans}")
    else:
        lines.append(labels["none"])
    lines.append("")

    # ── 5. Sources ────────────────────────────────────────────────────────────
    lines += [f"## {labels['sources']}", "", f"### {labels['by_source_type']}", ""]
    type_counts = source_stats.get("type_counts", {})
    # `manual` never appears in .wikicommit/source/ — it is only valid on a wiki
    # page's own sources[], with no management file behind it — so it is counted
    # in its own unit (pages asserting one) and labelled to say so, rather than
    # printed as a silent 0 next to management-file counts.
    manual_pages = sum(1 for p in content_pages if p["has_manual_source"])
    source_rows = [[f"`{t}`", str(type_counts[t])] for t in SOURCE_TYPE_ORDER if type_counts.get(t)]
    if manual_pages:
        source_rows.append([labels["manual_note"], str(manual_pages)])
    lines += _md_table([labels["col_source_type"], labels["col_count"]], source_rows) if source_rows \
        else [labels["none"], ""]

    status_counts = source_stats.get("status_counts", {})
    lines += [f"### {labels['by_status']}", ""]
    lines += _md_table(
        [labels["col_status"], labels["col_count"]],
        [[f"`{s}`", str(n)] for s, n in sorted(status_counts.items(), key=lambda e: (-e[1], e[0]))],
    ) if status_counts else [labels["none"], ""]

    host_counts = source_stats.get("host_counts", {})
    lines += [f"### {labels['by_host']}", ""]
    if host_counts:
        hosts = sorted(host_counts.items(), key=lambda e: (-e[1], e[0]))
        shown_hosts, more_hosts = _truncated(hosts, OVERVIEW_HOST_LIMIT, labels)
        lines += _md_table(
            [labels["col_host"], labels["col_count"]],
            [[f"`{h}`", str(n)] for h, n in shown_hosts]
            + ([[more_hosts, ""]] if more_hosts else []),
        )
    else:
        lines += [labels["none"], ""]

    # Issue #989: which languages the wiki's knowledge stands on. Hosts cannot
    # answer this — a host does not say its language, and the per-host table is
    # truncated at OVERVIEW_HOST_LIMIT exactly where the few non-English hosts
    # sit — while the number of languages is small, so this table is never cut.
    # The unrecorded row always comes last, whatever its size.
    lang_counts = source_stats.get("lang_counts", {})
    lang_unprocessed = source_stats.get("lang_unprocessed", 0)
    lines += [f"### {labels['by_source_lang']}", ""]
    if lang_counts or lang_unprocessed:
        lines += [labels["source_lang_note"], ""]
        known = sorted(
            ((k, n) for k, n in lang_counts.items() if k is not None), key=lambda e: (-e[1], e[0])
        )
        lang_rows = [[f"`{k}`", str(n)] for k, n in known]
        # Issue #1135: sources never processed yet are the queue, kept apart from
        # "not recorded" (processed before the field existed).
        if lang_unprocessed:
            lang_rows.append([labels["source_lang_unprocessed"], str(lang_unprocessed)])
        if lang_counts.get(None):
            lang_rows.append([labels["source_lang_unknown"], str(lang_counts[None])])
        lines += _md_table([labels["col_source_lang"], labels["col_count"]], lang_rows)
    else:
        lines += [labels["none"], ""]

    # Aggregated at the source-*type* level rather than per management file:
    # a row per source would make this table grow without bound on a wiki with
    # hundreds of sources, and content/sources/<mgmt> already answers "what did
    # this one source produce?" one source at a time.
    cross = source_stats.get("type_x_page_type", {})
    present_types = sorted({t for per in cross.values() for t in per})
    lines += [f"### {labels['cross_tab']}", ""]
    if present_types:
        header = [labels["col_source_type"]] + [f"`{t}`" for t in present_types] + [labels["col_total"]]
        cross_rows = []
        for source_type in SOURCE_TYPE_ORDER:
            per = cross.get(source_type)
            if not per:
                continue
            cells = [str(per.get(t, 0)) for t in present_types]
            cross_rows.append([f"`{source_type}`"] + cells + [str(sum(per.values()))])
        lines += _md_table(header, cross_rows)
    else:
        lines += [labels["none"], ""]

    # ── 6. Tags ───────────────────────────────────────────────────────────────
    tag_counts: dict[str, int] = {}
    for p in content_pages:
        for tag in p["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    lines += [f"## {labels['tags']}", ""]
    if tag_counts:
        ranked = sorted(tag_counts.items(), key=lambda e: (-e[1], e[0]))
        shown_tags, more_tags = _truncated(ranked, OVERVIEW_TAG_LIMIT, labels)
        lines += _md_table(
            [labels["col_tag"], labels["col_count"]],
            [[f"`{t}`", str(n)] for t, n in shown_tags] + ([[more_tags, ""]] if more_tags else []),
        )
    else:
        lines += [labels["none"], ""]

    out_rel = Path(OVERVIEW_DIR_NAME) / "index.md"
    out_path = output_dir / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Generating overview: {out_path}")
    return out_rel


def convert_file(
    src_path: Path, rel_path: Path, source_dir: Path, output_dir: Path, primary_lang: str,
    out_rel_path: Path | None = None, view_dir: Path | None = None, is_view: bool = False,
    ai_review: dict | None = None,
) -> tuple[int, int, set[str]]:
    """Convert one file's WikiLinks and write it to output_dir. Return
    (converted, unresolved, link_keys) — the first two counting this file's
    links, the third the set of `Type/slug` keys it references.

    link_keys is the page's outbound edge list for the overview page's link
    graph (Issue #585). It is collected here, during the substitution pass
    that already reads the file and already runs WIKILINK_RE over it, rather
    than in a second walk: check_orphans.py and check_wanted_pages.py each
    build this same graph from their own full re-read, and adding a third one
    inside the build would be the most expensive of the three (it runs on
    every deploy).

    `rel_path` is the page's path relative to its own tree's root.
    `out_rel_path` is where it is written under output_dir; it defaults to
    `rel_path` and differs for a custom type, whose `custom/` segment
    publishing drops (Issue #576), and for a view page, which gains a `View`
    segment it does not have on disk (Issue #675). main() computes it once and
    passes it here *and* into its stale-cleanup write set — the two must be the
    same value, or the cleanup pass deletes this file in the same run that
    wrote it (Issue #271).

    `is_view` says which tree `src_path` belongs to; `view_dir` is the view
    tree's root, needed either way to resolve `[[View/<slug>]]` links written
    from an ordinary page.

    `ai_review` is what load_ai_review() found for this page, stamped into the
    published copy's frontmatter and nowhere else (Issue #751). main() looks it
    up so the overview's site-wide tally and this stamp read one lookup, and so
    the two can never disagree about which pages carry a standing verdict.
    """
    unresolved = 0
    link_keys: set[str] = set()
    if out_rel_path is None:
        out_rel_path = rel_path

    resolved = (
        parse_view_path(src_path, view_dir)
        if is_view and view_dir is not None
        else parse_wiki_path(src_path, source_dir)
    )
    # A view page reports `View` as its type, which is exactly the directory it
    # publishes into — so relative_link() below, and every link written *to* it,
    # need no view-specific case.
    lang, current_type = (resolved[0], resolved[1]) if resolved else (None, None)

    try:
        content = src_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"WARNING: {src_path}: could not be read: {e}")
        return 0, 0, link_keys

    # Before WikiLink substitution, never after: this pass adjusts links that
    # are relative to the *source* directory, and substitution inserts links
    # that are already relative to the output directory.
    # For a view page the two are deliberately the same, making this a no-op:
    # a view page's relative targets are written as they will appear under
    # content/ (`../../assets/x.png`, exactly what an entity page at the same
    # published depth writes). Rewriting them would need a mapping between two
    # sibling trees with different roots — `.wikicommit/view/` and
    # `.wikicommit/entity/assets/` — which is a different problem from the
    # within-one-tree depth change this function exists for (Issue #675).
    src_link_dir = out_rel_path.parent if is_view else rel_path.parent
    content = rewrite_relative_links(
        content, src_link_dir.as_posix(), out_rel_path.parent.as_posix()
    )

    def replace(m: re.Match) -> str:
        nonlocal unresolved
        type_name, slug = m.group(1), m.group(2)
        # Recorded whether or not the link resolves: an unresolved one is
        # exactly what the overview's "gaps" section is looking for.
        link_keys.add(f"{type_name}/{slug}")

        if lang is None or current_type is None:
            unresolved += 1
            print(f"WARNING: [[{type_name}/{slug}]] not resolved in {src_path}")
            return f"{type_name}/{slug}"

        # `View` is the reserved segment naming the view tree, whose pages sit
        # directly under <lang>/ with no type directory (Issue #675).
        if type_name == VIEW_TYPE_SEGMENT and view_dir is not None:
            same_lang_target = view_dir / lang / f"{slug}.md"
            primary_target = view_dir / primary_lang / f"{slug}.md"
        else:
            same_lang_target = source_dir / lang / type_name / f"{slug}.md"
            primary_target = source_dir / primary_lang / type_name / f"{slug}.md"

        if same_lang_target.exists() and not is_removed(same_lang_target):
            link_path = relative_link(lang, current_type, lang, type_name, slug)
            target_fm = load_frontmatter(same_lang_target)
        elif lang != primary_lang and primary_target.exists() and not is_removed(primary_target):
            link_path = relative_link(lang, current_type, primary_lang, type_name, slug)
            target_fm = load_frontmatter(primary_target)
        else:
            unresolved += 1
            print(f"WARNING: [[{type_name}/{slug}]] not resolved in {src_path}")
            return f"{type_name}/{slug}"

        title = (target_fm or {}).get("title") or f"{type_name}/{slug}"
        return f"[{_escape_md_link_text(title)}]({link_path})"

    new_content = WIKILINK_RE.sub(replace, content)

    # The published copy carries the verdict; `.wikicommit/entity/` does not.
    # That asymmetry is the point of Issue #751 — the record tree stays the one
    # place the verdict lives, so it cannot go stale here, and no new
    # validate_frontmatter.py rule is needed for a field wiki pages never hold.
    if ai_review is not None:
        stamp = [
            f"{AI_REVIEW_MODEL_FIELD}: {_yaml_quote(ai_review['model'])}",
            f"{AI_REVIEW_AT_FIELD}: {_yaml_quote(ai_review['reviewed_at'])}",
        ]
        if ai_review.get("stage") == TRANSLATE_CHECK_STAGE:
            stamp.append(f"{AI_REVIEW_STAGE_FIELD}: {_yaml_quote(TRANSLATE_CHECK_STAGE)}")
        new_content = inject_frontmatter_lines(new_content, stamp)

    out_path = output_dir / out_rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_content, encoding="utf-8")
    print(f"Converting: {src_path} → {out_path}")

    return 1, unresolved, link_keys


ASSETS_DIR_NAME = "assets"

# Faithful port of slugifyFilePath from @quartz-community/utils (the function
# Quartz's builtin Assets emitter runs on every file it copies from content/
# to public/). Used only to warn when an asset's published name would differ
# from the path a page body has to write to reach it — see sync_assets().
# Kept as an exact port rather than an
# approximating "safe characters" regex because the real rules are narrower
# and stranger than they look: non-ASCII and underscores survive untouched, a
# file extension keeps its original case while the stem is lowercased, and two
# renames have nothing to do with characters at all (`_index` → `index`, and a
# file whose name repeats its parent directory becomes `index`).
_ASSET_EXT_RE = re.compile(r"\.[A-Za-z0-9]+$")


def _quartz_slugify_segment(segment: str) -> str:
    segment = re.sub(r"\s", "-", segment)
    segment = segment.replace("&", "-and-").replace("%", "-percent")
    segment = re.sub(r"[?#<>:\"|*]", "", segment)
    return segment.lower()


def quartz_asset_slug(rel_posix_path: str) -> str:
    """Return the name Quartz will publish `content/<rel_posix_path>` under."""
    fp = rel_posix_path.lstrip("/").rstrip("/")
    match = _ASSET_EXT_RE.search(fp)
    ext = match.group(0) if match else ""
    without_ext = fp[: len(fp) - len(ext)] if ext else fp
    # Case-sensitive, exactly like Quartz's `[".md", ".html", undefined].includes(ext)`:
    # a `.MD` attachment keeps its extension there, so treating it case-insensitively
    # here would report a rename that never happens.
    final_ext = "" if ext in (".md", ".html") else ext

    slug = "/".join(_quartz_slugify_segment(seg) for seg in without_ext.split("/"))
    slug = slug.rstrip("/")
    if slug == "_index" or slug.endswith("/_index"):
        slug = slug[: -len("_index")] + "index"
    segments = slug.split("/")
    if len(segments) >= 2 and segments[-1] == segments[-2]:
        segments[-1] = "index"
        slug = "/".join(segments)
    return slug + final_ext


def is_in_assets(path: Path, root: Path) -> bool:
    """True if path lives under root/assets/."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return rel.parts[:1] == (ASSETS_DIR_NAME,)


def sync_assets(source_dir: Path, output_dir: Path) -> tuple[int, int]:
    """Mirror .wikicommit/entity/assets/ into content/assets/ (Issue #589).

    Quartz's builtin Assets emitter copies everything under content/ that isn't
    a .md to the published site, and it is registered unconditionally (not via
    quartz.config.yaml's plugins list), so putting a file here is all that is
    needed to publish it. Nothing in the pipeline did that before, which meant
    the recommended relative-path form for local images resolved to a 404 on
    the published site — that recommendation had been verified by placing files
    directly into content/ rather than going through this script.

    One non-obvious dependency this relies on: Quartz's Assets emitter globs
    with `gitignore: true`, and the distributed .gitignore lists `content/`.
    That only fails to hide the assets because `npm run build` runs
    `npx quartz build` from inside the quartz/ submodule, so the glob's cwd is
    quartz/content (a symlink created by prebuild-symlinks.cjs) and the
    gitignore scan starts inside the submodule's own repo rather than the wiki
    repo's. Pointing the build at the repo-root content/ instead would make
    globby match nothing and silently publish no assets at all (verified
    directly against globby).

    Only the assets/ subtree is mirrored, not every non-.md file under
    source_dir: assets/ is the one place for shared images and attachments,
    and limiting the copy there avoids
    publishing whatever else happens to sit next to a page (editor backups, a
    stray source PDF, .DS_Store).

    Note that Quartz's Assets emitter excludes `**/*.md`, so a .md placed under
    assets/ is copied here but then rendered by Quartz as an ordinary page
    rather than served as a downloadable attachment (the warning below says so
    explicitly instead of suggesting a rename, which cannot help: every .md
    loses its extension). It is still excluded from this script's own page
    conversion (see main()), so it is only ever written once.

    Returns (copied, removed_stale).
    """
    src_assets = source_dir / ASSETS_DIR_NAME
    out_assets = output_dir / ASSETS_DIR_NAME

    copied_rel: set[Path] = set()
    copied = 0
    if src_assets.is_dir():
        for asset_path in sorted(src_assets.rglob("*")):
            if not asset_path.is_file():
                continue
            rel_path = asset_path.relative_to(src_assets)
            # Slugify the content/-relative path, not the assets/-relative one:
            # slugifyFilePath's "a file repeating its parent directory becomes
            # index" rule looks at the last two segments, and for a top-level
            # asset the second-to-last segment is `assets` itself (so
            # assets/assets.png publishes as assets/index.png).
            content_rel = f"{ASSETS_DIR_NAME}/{rel_path.as_posix()}"
            published = quartz_asset_slug(content_rel)
            if published != content_rel:
                ext_match = _ASSET_EXT_RE.search(content_rel)
                ext = ext_match.group(0) if ext_match else ""
                if ext and published + ext == content_rel:
                    # The only difference is the dropped .md/.html extension,
                    # which slugifyFilePath always drops — so, unlike the
                    # character-level renames below, there is no name the file
                    # could be given that would make the two match.
                    print(
                        f"WARNING: {asset_path}: Quartz always strips the {ext} "
                        f"extension, publishing this at {published}, so a page linking "
                        f"to it by the path it has here would 404. Keep only "
                        f"attachments Quartz serves verbatim under assets/."
                    )
                else:
                    print(
                        f"WARNING: {asset_path}: Quartz will publish this as "
                        f"{published}, so a page linking to it by the path it has "
                        f"here would 404. Rename it to match."
                    )
            dest = out_assets / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset_path, dest)
            copied_rel.add(rel_path)
            copied += 1

    # Same stale-cleanup contract as pages (Issue #271), scoped to
    # content/assets/ so this never deletes anything another tool wrote
    # elsewhere under content/.
    removed_stale = 0
    if out_assets.is_dir():
        for out_path in sorted(out_assets.rglob("*")):
            if not out_path.is_file():
                continue
            if out_path.relative_to(out_assets) not in copied_rel:
                out_path.unlink()
                removed_stale += 1
                print(f"Removing stale build output: {out_path}")

    return copied, removed_stale


# The Explorer's group manifest (Issue #1035). Written at the content/ root so
# Quartz's Assets emitter publishes it next to contentIndex.json; the explorer's
# inline script fetches it and files each grouped page under a virtual folder.
GROUP_MANIFEST_NAME = "wikicommit-groups.json"


def write_group_manifest(output_dir: Path, page_stats: list[dict]) -> bool:
    """Publish `.wikicommit/groups/` for the Explorer, without touching any page.

    Why a separate file rather than a frontmatter field on each published page:
    the Explorer builds its tree in the browser from contentIndex.json, and
    Quartz's content index carries a fixed set of fields (slug, title, links,
    tags, ...) — an injected frontmatter key would never reach it. A field
    nobody can read is a receiver without a consumer (Issue #553), so the
    membership goes here instead, keyed the way contentIndex.json keys pages.

    Keys are published slugs: `<lang>/<Type>` lowercased the way Quartz
    slugifies (a custom type already flattened, Issue #576) and the page slug
    likewise, so the client compares strings without re-deriving anything.
    Labels are resolved per language here, so the client never sees the file's
    shape. The page's URL does not change — the folder is virtual.

    Returns True when the manifest was written. With no usable group file the
    manifest is removed rather than left behind from an earlier local build, so
    a wiki without groups publishes exactly what it did before.
    """
    folders: dict[str, dict] = {}
    loaded: dict[str, object] = {}
    for stat in page_stats:
        if stat["is_index"] or stat.get("is_view"):
            continue
        type_raw = stat["type_raw"]
        if type_raw not in loaded:
            group_file, errors = load_group_file(type_raw)
            if errors:
                print(f"WARNING: groups file for {type_raw} is invalid ({errors[0]}) — published without groups")
            loaded[type_raw] = group_file
        group_file = loaded[type_raw]
        if group_file is None:
            continue
        key = group_file.group_of().get(stat["slug"])
        if key is None:
            continue
        folder_key = "/".join(
            _quartz_slugify_segment(seg) for seg in [stat["lang"], *stat["type"].split("/")]
        )
        folder = folders.setdefault(folder_key, {"groups": {}, "pages": {}})
        group = next(g for g in group_file.groups if g.key == key)
        folder["groups"][key] = group.label_for(stat["lang"])
        folder["pages"][_quartz_slugify_segment(stat["slug"])] = key
    out_path = output_dir / GROUP_MANIFEST_NAME
    if not folders:
        if out_path.exists():
            out_path.unlink()
            print(f"Removing stale build output: {out_path}")
        return False
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"version": 1, "folders": folders}, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    return True


# The AI-facing index of the published site (llmstxt.org). Written at the
# content/ root next to GROUP_MANIFEST_NAME: it is not a `.md`, so Quartz's
# builtin Assets emitter copies it to public/ under the same name — the slug
# rules quartz_asset_slug() ports keep a lowercase name with a non-.md
# extension unchanged.
LLMS_TXT_NAME = "llms.txt"
# How many pages the "Key pages" section lists. The whole wiki would push the
# file past the few-to-tens of KB the convention expects (a pilot wiki holds
# over 1,000 pages across two languages); the Type folders listed under "Index"
# reach the rest.
LLMS_KEY_PAGES_LIMIT = 50
# A description longer than this is cut at a word boundary. properties.description
# is meant to be 2-3 sentences, so this only bounds the file when one is not.
LLMS_DESCRIPTION_MAX_CHARS = 300


def load_site_meta(repo_root: Path) -> tuple[str | None, str | None]:
    """Return (pageTitle, baseUrl) from quartz.config.yaml, either None when unusable.

    Read at build time rather than passed in: `.github/workflows/deploy.yml`
    rewrites `baseUrl` to the Pages URL in the checkout just before `npm run
    build`, so this is the one place the published URL is known. A value still
    holding an init placeholder (`{PAGE_TITLE}`) is treated as absent.
    """
    config_path = repo_root / "quartz.config.yaml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None, None
    configuration = data.get("configuration") if isinstance(data, dict) else None
    if not isinstance(configuration, dict):
        return None, None

    def _clean(value: object) -> str | None:
        if not isinstance(value, str) or not value.strip() or "{" in value:
            return None
        return value.strip()

    return _clean(configuration.get("pageTitle")), _clean(configuration.get("baseUrl"))


def site_url(base_url: str | None, out_rel: str) -> str:
    """Return the published URL of `content/<out_rel>` (a page, or a folder ending in `/`).

    Absolute when a baseUrl is known — llms.txt is fetched on its own, often by
    a tool that does not resolve relative links. Quartz's `baseUrl` carries no
    scheme (Quartz itself prefixes `https://`); a localhost preview is served
    over plain http. Without a baseUrl the link is relative to the site root,
    which is where this file is published.
    """
    is_folder = out_rel.endswith("/")
    slug = quartz_asset_slug(out_rel.rstrip("/")) if out_rel.strip("/") else ""
    if is_folder and slug:
        slug += "/"
    elif slug == "index" or slug.endswith("/index"):
        slug = slug[: -len("index")]
    path = quote(slug, safe="/")
    if not base_url:
        return f"./{path}"
    base = re.sub(r"^https?://", "", base_url).rstrip("/")
    scheme = "http" if base.startswith(("localhost", "127.0.0.1")) else "https"
    return f"{scheme}://{base}/{path}"


def _llms_description(text: object) -> str:
    """One line of plain text: WikiLinks reduced to their slug, whitespace collapsed."""
    if not isinstance(text, str):
        return ""
    plain = " ".join(WIKILINK_RE.sub(lambda m: m.group(2), text).split())
    if len(plain) > LLMS_DESCRIPTION_MAX_CHARS:
        cut = plain[:LLMS_DESCRIPTION_MAX_CHARS]
        # Back off to a word boundary only when one is near the end: CJK text
        # has no spaces between words, so a description such as
        # "acme のエンジニア。……" has its only space near the start, and backing
        # off to it would keep a single word of a 300-character limit.
        boundary = cut.rfind(" ")
        if boundary >= LLMS_DESCRIPTION_MAX_CHARS * 4 // 5:
            cut = cut[:boundary]
        plain = cut.rstrip() + "…"
    return plain


def generate_llms_txt(
    output_dir: Path,
    repo_root: Path,
    primary_lang: str,
    page_stats: list[dict],
    referrers: dict[str, set[str]],
    published: set[Path],
    other_langs: list[str],
    has_sources: bool,
) -> Path:
    """Write content/llms.txt — the site's index for an AI that has not cloned the repository.

    `/wikicommit-ask` and `/wikicommit-search` need a checkout; a reader working
    elsewhere (another project, a chat client with no shell) can only be handed
    page URLs one at a time. This file tells such an AI what the wiki covers and
    where its pages are, so it can fetch only the ones it needs. Like the
    overview, it is build output: never committed, never LLM-authored.

    Shape (llmstxt.org): H1 with the site name, the primary language's
    site_description as the summary blockquote, one paragraph on how the pages
    were made and checked, then `## Index` (one line per Type folder),
    `## Key pages` (the most linked-to pages, at most LLMS_KEY_PAGES_LIMIT) and
    `## Optional` (the overview and the source list).

    Only primary_lang pages are listed: a translation answers the same question
    as its original, and listing both would double the file for no new reach.
    Review state is stated once in the preamble rather than on every line — each
    published page shows its own state at the top, which is where an AI that
    follows a link reads it.

    The links point at the published HTML pages, not at raw Markdown: the
    repository may be private, and the raw files carry `[[Type/slug]]` WikiLinks
    that only this build resolves.
    """
    site_title, base_url = load_site_meta(repo_root)
    descriptions = load_site_description(repo_root)

    pages = [
        p for p in page_stats
        if p["lang"] == primary_lang and not p["is_index"] and p["out_rel"] in published
    ]
    type_counts: dict[str, tuple[str, int]] = {}
    for p in pages:
        folder = p["out_rel"].parent.as_posix() + "/"
        _, count = type_counts.get(p["type"], (folder, 0))
        type_counts[p["type"]] = (folder, count + 1)

    lines = [f"# {site_title or 'Wiki'}", ""]
    if primary_lang in descriptions:
        lines += [f"> {descriptions[primary_lang]}", ""]
    lines.append(
        "The pages of this wiki are generated by an LLM from source documents. "
        "Every page is checked against its sources by a machine when it is generated; "
        "only some pages have been read through by a person (a sample, by design). "
        "Each page states its review status at the top."
    )
    lines.append("")
    scope = f"The lists below cover the {len(pages)} pages in `{primary_lang}`"
    if other_langs:
        scope += f"; the site also has pages in {', '.join(f'`{lang}`' for lang in other_langs)}"
    lines += [scope + ".", ""]

    lines += ["## Index", ""]
    for type_name, (folder, count) in sorted(type_counts.items(), key=lambda kv: (-kv[1][1], kv[0])):
        noun = "page" if count == 1 else "pages"
        lines.append(f"- [{_escape_md_link_text(type_name)}]({site_url(base_url, folder)}): {count} {noun}")
    lines.append("")

    ranked = sorted(pages, key=lambda p: (-len(referrers.get(p["key"], ())), p["title"], p["key"]))
    lines += ["## Key pages", ""]
    for p in ranked[:LLMS_KEY_PAGES_LIMIT]:
        entry = f"- [{_escape_md_link_text(p['title'])}]({site_url(base_url, p['out_rel'].as_posix())})"
        description = _llms_description(p.get("description"))
        lines.append(f"{entry}: {description}" if description else entry)
    lines.append("")

    lines += [
        "## Optional",
        "",
        f"- [Overview]({site_url(base_url, OVERVIEW_DIR_NAME + '/')}): "
        "page counts by type, language and source, and the most linked-to pages",
    ]
    if has_sources:
        lines.append(
            f"- [Sources]({site_url(base_url, SOURCES_DIR_NAME + '/')}): "
            "the source documents this wiki was generated from"
        )

    out_path = output_dir / LLMS_TXT_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(LLMS_TXT_NAME)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert [[Type/slug]] WikiLinks to relative Markdown links for the Quartz build."
    )
    parser.add_argument("--source", required=True, metavar="DIR", help="Input directory (.wikicommit/entity/)")
    parser.add_argument("--output", required=True, metavar="DIR", help="Output directory (Quartz content/)")
    parser.add_argument("--view-source", default=str(VIEW_DIR), metavar="DIR",
                        help="View tree input directory (default: .wikicommit/view/). "
                             "Skipped silently when it does not exist, so a wiki with no "
                             "view pages needs no change to how this is invoked.")
    parser.add_argument("--primary-lang", default=None, metavar="LANG",
                        help="Cross-language fallback base language (defaults to .wikicommit/config.yml)")
    args = parser.parse_args()

    repo_root = Path.cwd()
    source_dir = Path(args.source)
    output_dir = Path(args.output)
    view_dir = Path(args.view_source)
    primary_lang = args.primary_lang or load_primary_lang(repo_root)

    converted = 0
    unresolved_links = 0
    skipped_removed = 0
    total_pages = 0
    reviewed_pages = 0
    ai_reviewed_pages = 0
    written_rel_paths: set[Path] = set()
    # Overview accumulators (Issue #585), filled by the same single walk that
    # already computes total_pages/reviewed_pages: one entry per published page,
    # and the inbound edge list keyed by Type/slug.
    page_stats: list[dict] = []
    referrers: dict[str, set[str]] = {}
    removed_keys: set[str] = set()

    # Two passes so that flattening (Issue #576) can never let a custom type
    # quietly overwrite a standard one. Custom types are Schema.org-absent by
    # definition, so `custom/Decision` and a standard `Decision` cannot both
    # exist today — but a name Schema.org adds later, installed alongside an
    # existing custom type of the same name, would land both on one output
    # path. Deciding that up front, over the whole set, keeps the outcome
    # independent of the order rglob happens to return files in.
    pages: list[tuple[Path, Path, Path, bool]] = []  # (src_path, rel_path, out_rel_path, is_view)
    claimed_by: dict[Path, Path] = {}               # out_rel_path -> src_path that won it

    for src_path in sorted(source_dir.rglob("*.md")):
        # assets/ is the asset subtree, copied
        # verbatim below rather than converted. A .md that happens to live
        # there would otherwise be both converted as a page and copied as an
        # asset, writing two different files from one source (Issue #589).
        if is_in_assets(src_path, source_dir):
            continue
        if is_removed(src_path):
            skipped_removed += 1
            print(f"Skipping (status: removed): {src_path}")
            # Keyed but not published: a link pointing here is a link at a page
            # deliberately taken down, which check_wikilinks.py already blocks
            # as an ERROR. The overview must not re-report it as a page nobody
            # has written yet — the fix is to drop the link, not to write it.
            removed = parse_wiki_path(src_path, source_dir)
            if removed is not None:
                removed_keys.add(f"{removed[1]}/{removed[2]}")
            continue
        rel_path = src_path.relative_to(source_dir)
        pages.append((src_path, rel_path, flatten_entity_rel(rel_path), False))

    # Second input tree (Issue #675): view pages sit at <lang>/<slug>.md on disk
    # and publish to <lang>/View/<slug>.md, gaining the segment that makes
    # `[[View/<slug>]]` resolve and keeps the language first — the three Quartz
    # plugins that read the first path segment as the language are unchanged.
    view_page_count = 0
    for src_path in collect_view_pages(view_dir, include_index=True):
        if is_removed(src_path):
            skipped_removed += 1
            print(f"Skipping (status: removed): {src_path}")
            removed = parse_view_path(src_path, view_dir)
            if removed is not None:
                removed_keys.add(f"{removed[1]}/{removed[2]}")
            continue
        resolved_view = parse_view_path(src_path, view_dir)
        if resolved_view is None:
            print(
                f"WARNING: {src_path}: not a <lang>/<slug>.md path under {view_dir} — skipped"
            )
            continue
        view_lang, _, view_slug = resolved_view
        pages.append((
            src_path,
            src_path.relative_to(view_dir),
            Path(view_lang, VIEW_TYPE_SEGMENT, f"{view_slug}.md"),
            True,
        ))
        view_page_count += 1

    # An unflattened page always keeps its own path; only a flattened one can
    # be displaced, and it is skipped rather than silently overwriting or
    # being overwritten. A WARNING is the right strength here: dropping one
    # page from the published site should not fail a whole build, and the
    # remedy (rename the custom type) is the author's, not the script's.
    #
    # Three passes rather than two, in decreasing strength of claim: an entity
    # page publishing to its own path, then a view page (`View` is a reserved
    # Type segment, so an entity type literally named `View` is the anomaly —
    # but it is still on disk, so it keeps what it already had and the view page
    # is the one reported), then a custom type that had to be flattened to get
    # here.
    for src_path, rel_path, out_rel_path, is_view in pages:
        if not is_view and rel_path == out_rel_path:
            claimed_by[out_rel_path] = src_path
    for src_path, rel_path, out_rel_path, is_view in pages:
        if is_view and out_rel_path not in claimed_by:
            claimed_by[out_rel_path] = src_path
    for src_path, rel_path, out_rel_path, is_view in pages:
        if not is_view and rel_path != out_rel_path and out_rel_path not in claimed_by:
            claimed_by[out_rel_path] = src_path

    for src_path, rel_path, out_rel_path, is_view in pages:
        if claimed_by.get(out_rel_path) != src_path:
            remedy = (
                "`View` is a reserved Type segment for the view tree; rename the entity type "
                "that collides with it."
                if is_view
                else "Rename the custom type so the two no longer collide once the custom/ "
                "segment is dropped."
            )
            print(
                f"WARNING: {src_path}: publishes to {output_dir / out_rel_path}, already claimed by "
                f"{claimed_by[out_rel_path]} — skipped. {remedy}"
            )
            continue
        # Site-wide page/reviewed counts (Issue #407) exclude Type index.md
        # pages — they're auto-generated navigation, not wiki content — the
        # same exclusion check_orphans.py/check_expires.py/etc. already apply.
        fm = load_frontmatter(src_path) or {}
        is_index = src_path.name == "index.md"
        # One lookup per page, shared by the published stamp and the overview's
        # site-wide tally (Issue #751). Index pages are excluded: they are
        # build-generated navigation that no model reviewed, and
        # rebuild_index.py already stamps them `review_status: reviewed` for
        # exactly that reason (Issue #580).
        ai_review = None if is_index else load_ai_review(src_path, repo_root, fm)
        if not is_index:
            total_pages += 1
            if fm.get("review_status") == "reviewed":
                reviewed_pages += 1
            # Issue #769: counted in this walk rather than from page_stats so
            # that all three site-wide numbers cover the same set of pages. A
            # page whose path never resolves to <lang>/<Type>/<slug>.md is
            # published, stamped with its verdict by convert_file() below, and
            # counted in total_pages — but it never reaches page_stats, so
            # tallying there would report "1 of 2 checked" for a wiki where
            # both pages carry one, and "no record at all" for a wiki whose
            # only page does. That is the misreading this count exists to
            # remove, pointed the other way.
            # Issue #1031: a translation checked against its original is not a
            # page checked against sources, so it is not counted here — the
            # frontmatter field this feeds is labelled "checked against sources".
            if ai_review and not fm.get("translated_from"):
                ai_reviewed_pages += 1
        file_converted, file_unresolved, link_keys = convert_file(
            src_path, rel_path, source_dir, output_dir, primary_lang,
            out_rel_path=out_rel_path, view_dir=view_dir, is_view=is_view,
            ai_review=ai_review,
        )
        converted += file_converted
        unresolved_links += file_unresolved
        if file_converted:
            written_rel_paths.add(out_rel_path)

        resolved = (
            parse_view_path(src_path, view_dir) if is_view else parse_wiki_path(src_path, source_dir)
        )
        if resolved is None:
            # No <lang>/<Type>/<slug>.md to key this page by, so it has no place
            # in the overview's per-type/per-language tallies or its link graph.
            continue
        page_lang, page_type, page_slug = resolved
        key = f"{page_type}/{page_slug}"
        sources = fm.get("sources")
        page_stats.append({
            "out_rel": out_rel_path,
            "lang": page_lang,
            # Published pages drop a custom type's `custom/` segment (Issue
            # #576), and this page is published, so the reader-facing tallies
            # use the flattened name. type_raw keeps the entity-side name for
            # the Type-typo check, which compares against WikiLink Type
            # segments — those are never flattened.
            "type": flatten_custom_type(page_type),
            "type_raw": page_type,
            "slug": page_slug,
            "key": key,
            "title": str(fm.get("title") or key),
            # Read by generate_llms_txt() only (Issue #1117).
            "description": (
                fm["properties"].get("description")
                if isinstance(fm.get("properties"), dict) else None
            ),
            "review_status": fm.get("review_status"),
            # A scalar `tags:` value would otherwise iterate character by
            # character and register one tag per letter.
            "tags": [
                str(t) for t in (fm.get("tags") if isinstance(fm.get("tags"), list) else [])
                if isinstance(t, (str, int, float))
            ],
            "is_index": is_index,
            # None when no verdict stands for this page — no record at all, or
            # one made against text that has since changed (Issue #751).
            "ai_review": ai_review,
            # Read by the overview's orphan reporting only: a view page is
            # unlinked at birth, so it is never a meaningful orphan finding
            # (Issue #675).
            "is_view": is_view,
            # Issue #1030: a translation is left out of the overview's "checked
            # against sources" ratio — it has no sources of its own to check.
            "is_translation": bool(fm.get("translated_from")),
            "has_manual_source": isinstance(sources, list) and any(
                isinstance(e, dict) and e.get("type") == "manual" for e in sources
            ),
            # Issue #990: how many sources the page stands on, derived from the
            # sources[] already read above (no extra I/O). None — never 0 — for
            # a translation (it inherits sources from its parent) and a view
            # page (derived_from, not sources; a different thing to count), so
            # the hubs row can drop the figure instead of implying "no source".
            "source_count": (
                len(sources)
                if isinstance(sources, list) and not is_view and not fm.get("translated_from")
                else None
            ),
            # Issue #1006: which sources, not only how many, so the overview can
            # tell that several one-source hubs stand on the *same* document.
            # Same sources[] as above (no extra I/O), same None cases as
            # source_count. The identity is `url` / `path` as recorded (Issue
            # #572 / #573); a `manual` entry has neither and yields None.
            "source_ids": (
                [
                    (e.get("url") or e.get("path")) if isinstance(e, dict) else None
                    for e in sources
                ]
                if isinstance(sources, list) and not is_view and not fm.get("translated_from")
                else None
            ),
        })
        # Type index.md pages link to every page of their type, which would make
        # each of those pages look referenced and hide every real orphan — the
        # same exclusion check_orphans.py applies when building `referenced`.
        if not is_index:
            for link_key in link_keys:
                referrers.setdefault(link_key, set()).add(key)

    targets = existing_lang_targets(source_dir, load_translation_targets(repo_root), view_dir)
    # Issue #731: languages that actually published pages, taken from page_stats
    # rather than by listing .wikicommit/entity/*/ — that directory also holds
    # the language-neutral assets/ tree, and entries whose path never resolved
    # to <lang>/<Type>/<slug>.md never reach page_stats at all.
    #
    # Type index.md pages are excluded for the same reason existing_lang_targets()
    # excludes them (Issue #190): rebuild_index.py leaves one behind after the
    # last page of a type is removed, and a language whose only remaining files
    # are those would get a front-door link into an empty tree. Removed pages
    # never reach page_stats at all, so they need no exclusion here.
    #
    # written_rel_paths is the gate that keeps this list free of dead links, the
    # same guarantee existing_lang_targets() gives the targets side: a page whose
    # source could not be read is still keyed into page_stats (the overview
    # tallies it), but convert_file() wrote nothing for it, so a language whose
    # only page failed that way would otherwise get a language-list entry
    # pointing at a content/<lang>/ directory this build never created. At this
    # point the set holds converted pages only — source pages and the root index
    # are added below.
    published_langs = sorted({
        p["lang"] for p in page_stats
        if not p["is_index"] and p["out_rel"] in written_rel_paths
    })
    langs = compute_langs(primary_lang, targets, published_langs)
    mgmt_dir = repo_root / ".wikicommit" / "source"
    source_written, source_stats = generate_source_pages(output_dir, mgmt_dir, source_dir, primary_lang)
    written_rel_paths |= source_written
    # Issue #730: per-language (pages, reviewed) from the same page_stats the
    # overview page tallies, so the two build-generated pages agree. Type index
    # pages are excluded here as everywhere; view pages are counted, since they
    # are published pages of that language like any other.
    # Deliberately not named `pages`/`reviewed`: `pages` above holds this
    # function's (src_path, rel_path, out_rel_path, is_view) list, and rebinding
    # it to an int here would leave any later use of it broken in a way neither
    # ruff nor the tests would catch.
    lang_counts: dict[str, tuple[int, int, int]] = {}
    for stat in page_stats:
        if stat["is_index"]:
            continue
        lang_pages, lang_reviewed, lang_ai = lang_counts.get(stat["lang"], (0, 0, 0))
        lang_counts[stat["lang"]] = (
            lang_pages + 1,
            lang_reviewed + (1 if stat["review_status"] == "reviewed" else 0),
            # `ai_review` is already resolved once per page above and shared with
            # the published stamp and the overview tally (Issue #751), so
            # counting it here adds no walk (Issue #769).
            # Issue #1031: translations are left out for the same reason as the
            # site-wide count above — split on translated_from, since a language
            # can hold both originals and translations.
            lang_ai + (1 if stat["ai_review"] and not stat["is_translation"] else 0),
        )
    generate_root_index(
        output_dir, primary_lang, langs, total_pages, reviewed_pages,
        load_site_description(repo_root), lang_counts, ai_reviewed_pages,
    )
    written_rel_paths.add(Path("index.md"))
    written_rel_paths.add(
        generate_overview_page(
            output_dir, primary_lang, page_stats, referrers, removed_keys, source_stats,
            count_unpublished_pages(repo_root),
        )
    )

    # Remove stale .md files left over from a previous run that this run did
    # not (re)write: pages set to status: removed, deleted source files, or
    # pages moved/renamed since. Without this, repeated local builds (e.g.
    # `npm run preview`) accumulate residue that keeps removed pages
    # reachable by direct URL even though they're no longer linked (Issue
    # #271). CI builds start from a fresh checkout so output_dir is normally
    # empty there, but this also guards ad hoc/incremental invocations.
    removed_stale = 0
    if output_dir.exists():
        for out_path in sorted(output_dir.rglob("*.md")):
            rel_path = out_path.relative_to(output_dir)
            if is_in_assets(out_path, output_dir):
                # Assets have their own write set and their own cleanup below;
                # they are never members of written_rel_paths, so letting them
                # reach this loop would delete every asset just copied.
                continue
            if rel_path not in written_rel_paths:
                out_path.unlink()
                removed_stale += 1
                print(f"Removing stale build output: {out_path}")

    generate_llms_txt(
        output_dir, repo_root, primary_lang, page_stats, referrers, written_rel_paths,
        [lang for lang in published_langs if lang != primary_lang], bool(source_written),
    )
    write_group_manifest(output_dir, page_stats)
    copied_assets, removed_stale_assets = sync_assets(source_dir, output_dir)

    print(
        f"SUMMARY: converted={converted}, unresolved_links={unresolved_links}, "
        f"skipped_removed={skipped_removed}, removed_stale={removed_stale}, "
        f"assets={copied_assets}, removed_stale_assets={removed_stale_assets}, "
        f"view_pages={view_page_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
