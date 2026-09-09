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
    other_types_for_slug,
    parse_view_path,
    parse_wiki_path,
)
# Issue #751: the AI review record is a second input tree for this build. Both
# helpers are imported rather than reimplemented — check_review_coverage.py
# answers "is this verdict still valid?" for the operator and this script asks
# the same question for the reader, and two copies of that judgement would
# drift into a banner that contradicts `/wikicommit-status`.
from check_review_coverage import load_records, stale_reasons, standing_verdict
from record_review import ACCEPTED_PREFIXES, RecordError, compute_page_content_hash


# Stamped onto the published copy of a page, never onto the page itself
# (Issue #751). Naming them apart from `reviewed_by` is deliberate: that field
# is the human who closed the tracking Issue (Issue #663), and a reader must
# not read one as the other.
AI_REVIEW_MODEL_FIELD = "ai_review_model"
AI_REVIEW_AT_FIELD = "ai_review_at"


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

    try:
        current_hash = compute_page_content_hash(src_path)
    except (RecordError, OSError, ValueError) as e:
        print(f"WARNING: {src_path}: the page content hash could not be computed: {e}")
        return None
    if str(record.get("page_content_hash") or "") != current_hash:
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

    findings = record.get("findings")
    return {
        "model": model,
        "reviewed_at": reviewed_at,
        "findings": len(findings) if isinstance(findings, list) else 0,
    }


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


def load_primary_lang(repo_root: Path) -> str:
    # Fallback is "en" to match init.py's --primary-lang default (Issue #159 changed the
    # tool-wide default from "ja"; Issue #376 brought this fallback in line with it). Only
    # reached for a config.yml missing/malformed enough to lack an explicit primary_lang —
    # every config.yml init.py generates always has one.
    translation = _config_section(repo_root, "translation")
    return str(translation.get("primary_lang", "en") or "en")


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
# overview) ship two languages: Japanese here, English in the DEFAULT_*
# fallback beside each one. **That is not a claim that two is the right
# number** — no record exists of anyone deciding on these two. What has been
# decided is the other half: when to add a third.
#
# **Adding one is blocked on verification, not on translation.** A translation
# can be produced for any of these strings at any time. What this project has
# no way to do is check that the result says what the English says, and the
# cost of getting that wrong is not uniform across the keys:
#
#   - Most keys are plain labels ("Sources", "Type", "Total pages"). A clumsy
#     translation is clumsy and nothing more.
#   - A minority carry claims — counts_note, ai_counts_note, licensing,
#     reviewed_note, retracted_notice. Those sentences say what this wiki does
#     and does not vouch for, what its sources permit, and why a source was
#     dropped. Several of them exist specifically to keep this wiki from
#     overstating what it knows.
#
# **The second kind fails invisibly.** Left in English it fails visibly: a
# reader who cannot read it knows they cannot. Mistranslated slightly stronger,
# it reads fine and the reader believes something this wiki deliberately does
# not say — and nobody here can see that it happened.
#
# **A partial language is not an option today.** These dicts are read with
# bracket access, so one missing key raises KeyError and fails the build. That
# is a guarantee, not a defect — a language is complete or absent, never
# half-rendered. The one exception is SOURCE_TYPE_LABELS, whose values are
# looked up with .get(source_type, source_type) and degrade to the bare type
# string instead.
#
# **To add a language**, add it to all four dicts in the same change as the
# translations themselves. There is no registry to keep in step (they are keyed
# by primary_lang directly, unlike the Quartz plugins' LANG_TO_LOCALE), but
# they are four independent dicts, so adding to one and not the rest is silent:
# that wiki gets a translated root index and English source pages.
#
# **A language with no entry renders in English**, per surface, via the
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
#     learning that Italian was intended changes nothing about what this wiki
#     vouches for. A reader who cannot read English cannot read the notice
#     either.
#   - **A language-independent marker only restates what is already visible.**
#     A flag or an `(en)` tag says "this is English", which is exactly what
#     English text in an Italian page already says. That was the point of
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
    lines += ["", f"[{labels['sources']}](./sources/)"]
    # Issue #585: the overview page is the other build-generated entry point
    # (aggregate counts, hubs, gaps, source breakdown), so the root index is
    # the one place both are reachable from.
    lines += ["", f"[{labels['overview']}](./overview/)"]
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

# Two languages, and the note above ROOT_INDEX_LABELS says why adding a
# third is gated on verification rather than translation. All four
# *_LABELS dicts have to gain the language in the same change.
SOURCE_TYPE_LABELS = {
    "ja": {"path": "ファイル", "url": "URL", "wikicommit": "WikiCommit連携"},
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
    current_dir = posixpath.join("sources", mgmt_rel.parent.as_posix())
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
        index_rel = Path("sources") / d / "index.md"
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
        "type_x_page_type": {},   # source.type -> {published page type -> page count}
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
            out_rel = Path("sources") / mgmt_rel
            linked_wiki_rels = _write_source_page(
                output_dir / out_rel, fm, body, source, title, entity_dir, mgmt_rel, labels
            )
            written.add(out_rel)

            source_type = source["type"]
            entries.append({"type": source_type, "rel": mgmt_rel.as_posix(), "title": title})

            stats["type_counts"][source_type] = stats["type_counts"].get(source_type, 0) + 1
            status_key = str(fm.get("status") or "pending")
            stats["status_counts"][status_key] = stats["status_counts"].get(status_key, 0) + 1
            host = url_host(source.get("url")) if source_type in ("url", "wikicommit") else None
            if host:
                stats["host_counts"][host] = stats["host_counts"].get(host, 0) + 1
            per_page_type = stats["type_x_page_type"].setdefault(source_type, {})
            for wiki_rel in linked_wiki_rels:
                resolved = parse_wiki_path(entity_dir / wiki_rel, entity_dir)
                if resolved is None:
                    continue
                page_type = flatten_custom_type(resolved[1])
                per_page_type[page_type] = per_page_type.get(page_type, 0) + 1

    index_rel = Path("sources") / "index.md"
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

# Two languages, and the note above ROOT_INDEX_LABELS says why adding a
# third is gated on verification rather than translation. All four
# *_LABELS dicts have to gain the language in the same change.
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
        "ai_reviewed_note": (
            "生成時に、ページの記述をその出典と照合しています。"
            "照合しているのは出典との一致だけで、"
            "網羅性・実在の人物や組織への影響・読者自身の知識との食い違いは見ていません。"
        ),
        "ai_findings": "うち指摘を受けて書き直された箇所",
        "type_count": "型数",
        "by_lang": "言語別ページ数",
        "translation_coverage": "翻訳カバレッジ",
        "hubs": "知識の中心",
        "hubs_desc": "他のページから参照されている回数が多いページ。",
        "backlinks": "被リンク数",
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
        "Every page is checked against its own sources when it is generated. That check "
        "covers agreement with those sources and nothing else — not completeness, not "
        "the effect on real people and organizations, not conflicts with what you know."
    ),
    "ai_findings": "Findings raised and fixed before publishing",
    "type_count": "Types in use",
    "by_lang": "Pages per language",
    "translation_coverage": "Translation coverage",
    "hubs": "Knowledge hubs",
    "hubs_desc": "The pages other pages link to most.",
    "backlinks": "Backlinks",
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

OVERVIEW_DIR_NAME = "overview"


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


def generate_overview_page(
    output_dir: Path,
    primary_lang: str,
    page_stats: list[dict],
    referrers: dict[str, set[str]],
    removed_keys: set[str],
    source_stats: dict,
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
    ai_reviewed = [p for p in content_pages if p.get("ai_review")]
    ai_models = sorted({p["ai_review"]["model"] for p in ai_reviewed})
    # The total, not the number of pages carrying one: what this number is for
    # is showing that the check has teeth, and a page caught three times says
    # more about that than a page caught once.
    ai_findings_total = sum(p["ai_review"]["findings"] for p in ai_reviewed)

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
            f"- **{labels['ai_reviewed']}**: {len(ai_reviewed)} / {total_pages} "
            f"({_pct(len(ai_reviewed), total_pages)}){model_note}"
        )
        if ai_findings_total:
            lines.append(f"- **{labels['ai_findings']}**: {ai_findings_total}")
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
        for key in shown_hubs:
            p = best_page_for_key[key]
            lines.append(
                f"- [{_escape_md_link_text(p['title'])}]({overview_link(p['out_rel'])})"
                f" — {labels['backlinks']}: {backlink_count[key]}"
            )
        if more_hubs:
            lines.append(f"- {more_hubs}")
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
        new_content = inject_frontmatter_lines(new_content, [
            f"{AI_REVIEW_MODEL_FIELD}: {_yaml_quote(ai_review['model'])}",
            f"{AI_REVIEW_AT_FIELD}: {_yaml_quote(ai_review['reviewed_at'])}",
        ])

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
                "that collides with it (Issue #675)."
                if is_view
                else "Rename the custom type so the two no longer collide once the custom/ "
                "segment is dropped (Issue #576)."
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
            if ai_review:
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
            "has_manual_source": isinstance(sources, list) and any(
                isinstance(e, dict) and e.get("type") == "manual" for e in sources
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
            lang_ai + (1 if stat["ai_review"] else 0),
        )
    generate_root_index(
        output_dir, primary_lang, langs, total_pages, reviewed_pages,
        load_site_description(repo_root), lang_counts, ai_reviewed_pages,
    )
    written_rel_paths.add(Path("index.md"))
    written_rel_paths.add(
        generate_overview_page(
            output_dir, primary_lang, page_stats, referrers, removed_keys, source_stats
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
