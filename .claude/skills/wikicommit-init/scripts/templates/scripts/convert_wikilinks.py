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
tree mirroring .wikicommit/source/ 1:1 — one page per ingest management
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
import sys
from pathlib import Path
from urllib.parse import quote

import yaml

from _frontmatter import parse_frontmatter_and_body_text, parse_frontmatter_cached
from _wikilink import WIKILINK_RE, parse_wiki_path


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


def load_primary_lang(repo_root: Path) -> str:
    # Fallback is "en" to match init.py's --primary-lang default (Issue #159 changed the
    # tool-wide default from "ja"; Issue #376 brought this fallback in line with it). Only
    # reached for a config.yml missing/malformed enough to lack an explicit primary_lang —
    # every config.yml init.py generates always has one.
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return "en"
        translation = data.get("translation") or {}
        return str(translation.get("primary_lang", "en") or "en")
    except Exception:
        return "en"


def load_translation_targets(repo_root: Path) -> list[str]:
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        translation = data.get("translation") or {}
        targets = translation.get("targets") or []
        if not isinstance(targets, list):
            return []
        return [str(t) for t in targets]
    except Exception:
        return []


def load_theme(repo_root: Path) -> str:
    """Return .wikicommit/config.yml's top-level `theme` (Issue #407: embedded on
    the build-generated content/index.md so WikiCommitBanner can show it site-wide).
    Empty string (the config.yml default) means "not configured" and is the
    caller's cue to omit the field entirely — same convention as an unset theme
    disabling wikicommit-generate's theme-mismatch check (DesignDoc-data.md §3.3)."""
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return ""
        return str(data.get("theme") or "")
    except Exception:
        return ""


def _yaml_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def existing_lang_targets(source_dir: Path, targets: list[str]) -> list[str]:
    """Filter targets to languages with at least one non-removed content page."""
    result = []
    for t in targets:
        for md_path in (source_dir / t).rglob("*.md"):
            if md_path.name == "index.md" or is_removed(md_path):
                continue
            result.append(t)
            break
    return result


ROOT_INDEX_LABELS = {
    "ja": {"top": "Wiki トップ", "select": "言語を選択", "sources": "情報源一覧"},
}
DEFAULT_ROOT_INDEX_LABELS = {"top": "Wiki Home", "select": "Select language", "sources": "Sources"}


def compute_langs(primary_lang: str, targets: list[str]) -> list[str]:
    """Return primary_lang followed by targets (deduped), preserving order."""
    return list(dict.fromkeys([primary_lang] + [t for t in targets if t != primary_lang]))


def generate_root_index(
    output_dir: Path,
    primary_lang: str,
    langs: list[str],
    total_pages: int,
    reviewed_pages: int,
    theme: str,
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

    total_pages/reviewed_pages/theme (Issue #407) are embedded as custom
    frontmatter fields so the WikiCommitBanner Quartz component can render a
    site-wide summary (total page count, reviewed count, theme) on this page
    without re-deriving them from `allFiles` at render time — this script
    already walks every wiki page once in main(), so computing the aggregate
    here avoids a second, TSX-side pass that would have to duplicate the same
    index.md/removed-page exclusions. `theme` is omitted from the frontmatter
    entirely when empty (config.yml's "not configured" sentinel), matching
    the reader-facing "空文字列の場合は非表示" requirement in the original
    Issue.

    The "sources" entry point links to content/sources/ — a single,
    language-independent tree (ingest itself has no `lang` concept) built by
    generate_source_pages(), not one link per lang like the old per-language
    content/<lang>/sources.md this replaced (Issue #476).
    """
    out_path = output_dir / "index.md"
    labels = ROOT_INDEX_LABELS.get(primary_lang, DEFAULT_ROOT_INDEX_LABELS)

    # review_status: reviewed — this is a build-generated navigation page, not
    # LLM-authored wiki content, so it should not show the wikicommit-banner
    # "unreviewed" warning (which defaults to pending when the field is absent).
    lines = [
        "---",
        'title: "Wiki"',
        "review_status: reviewed",
        f"wikicommit_page_count: {total_pages}",
        f"wikicommit_reviewed_count: {reviewed_pages}",
    ]
    if theme:
        lines.append(f"wikicommit_theme: {_yaml_quote(theme)}")
    lines += [
        "---",
        "",
        f"[{labels['top']} ({primary_lang})](./{primary_lang}/)",
    ]
    if len(langs) > 1:
        lines += ["", f"## {labels['select']}", ""]
        lines += [f"- [{lang}](./{lang}/)" for lang in langs]
    lines += ["", f"[{labels['sources']}](./sources/)"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generating root index: {out_path}")


def _dot_relpath(target: str, start: str) -> str:
    """posixpath.relpath(), prefixed with "./" unless it already starts with
    ".." — shared by relative_link() and generated_page_link() so both
    relative-Markdown-link builders normalize the same way."""
    rel = posixpath.relpath(target, start=start)
    return rel if rel.startswith("..") else f"./{rel}"


def relative_link(current_lang: str, current_type: str, target_lang: str, target_type: str, slug: str) -> str:
    """Return the relative Markdown path from a <lang>/<type>/ page to <target_lang>/<target_type>/<slug>.md."""
    current_dir = posixpath.join(current_lang, current_type)
    target_path = posixpath.join(target_lang, target_type, f"{slug}.md")
    return _dot_relpath(target_path, current_dir)


# Ingest management files (.wikicommit/source/) only ever carry
# source.type: path / url / wikicommit (docs/DesignDoc-data.md §4.3) — unlike
# a wiki page's own `sources[]` entries, which can additionally be `manual`
# (a human assertion with no backing management file to mirror here).
SOURCE_TYPE_ORDER = ["path", "url", "wikicommit"]

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
        "generated_pages": "生成されたページ",
        "no_generated_pages": "生成されたページはまだありません。",
        "empty": "登録されている情報源はありません。",
    },
}
DEFAULT_SOURCE_PAGE_LABELS = {
    "index_title": "Sources",
    "type": "Type",
    "original": "Original",
    "status": "Status",
    "summary": "Summary",
    "no_summary": "(not yet generated)",
    "generated_pages": "Generated pages",
    "no_generated_pages": "No pages generated yet.",
    "empty": "No sources have been registered yet.",
}

# Matches the old (pre-Issue #405) Japanese heading alongside the current
# fixed-English one, so a management file that predates that change (no
# automatic migration — docs/DesignDoc-data.md §4.3) still renders its
# Summary body instead of falling back to "not yet generated".
SUMMARY_HEADING_RE = re.compile(r"^## (?:Summary|サマリ)\r?\n(.*?)(?=\n## |\Z)", re.DOTALL | re.MULTILINE)


def parse_summary_section(body: str) -> str | None:
    """Return the ingest management file's `## Summary` section body text, or
    None if absent/empty (docs/DesignDoc-data.md §4.3)."""
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
    """
    current_dir = posixpath.join("sources", mgmt_rel.parent.as_posix())
    return _dot_relpath(wiki_rel, current_dir)


_ENTITY_PREFIX_RE = re.compile(r"^\.wikicommit/(?:entity|wiki)/")


def normalize_wiki_rel(wiki_path: str) -> str | None:
    """Strip a generated_pages[] entry's `.wikicommit/entity/` prefix (or the
    pre-Issue-#477 `.wikicommit/wiki/` prefix — management files generated
    before that rename keep their old entries verbatim, no auto-migration,
    docs/DesignDoc-data.md §4.3's coexistence precedent) and validate the
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


def render_source_label(source: dict) -> str:
    """Render an ingest management file's `source:` entry as a Markdown
    link/label. Only `path`/`url`/`wikicommit` are handled — management
    files are never `type: manual` (docs/DesignDoc-data.md §4.3; `manual` is
    only valid on a wiki page's own `sources[]`, which this function does
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
) -> None:
    """Write one content/sources/<mgmt_rel> page mirroring an ingest
    management file: its type, original link, ingest status, `## Summary`
    body, and generated_pages[] (as plain Markdown links, not WikiLinks —
    these pages sit outside the WikiLink graph, a known limitation accepted
    in Issue #476)."""
    status = fm.get("status") or "pending"

    lines = [
        "---",
        f"title: {_yaml_quote(str(title))}",
        "review_status: reviewed",
        "---",
        "",
        f"**{labels['type']}**: {source.get('type', '')}",
        "",
        f"**{labels['original']}**: {render_source_label(source)}",
        "",
        f"**{labels['status']}**: {status}",
        "",
        f"## {labels['summary']}",
        "",
        parse_summary_section(body) or labels["no_summary"],
        "",
        f"## {labels['generated_pages']}",
        "",
    ]

    generated_pages = fm.get("generated_pages")
    page_lines = []
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
    lines += page_lines if page_lines else [labels["no_generated_pages"]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Generating source page: {out_path}")


def _write_sources_index(out_path: Path, entries: list[dict], labels: dict, type_labels: dict) -> None:
    """Write content/sources/index.md: a landing page grouping every mirrored
    source page by type, so links from generate_root_index() never dead-end
    (same invariant the old content/<lang>/sources.md upheld)."""
    # Every entry["type"] is already one of SOURCE_TYPE_ORDER — filtered by
    # generate_source_pages() before appending — so a plain lookup suffices.
    groups: dict[str, list[dict]] = {t: [] for t in SOURCE_TYPE_ORDER}
    for entry in entries:
        groups[entry["type"]].append(entry)

    lines = ["---", f'title: "{labels["index_title"]}"', "review_status: reviewed", "---", ""]
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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Generating sources index: {out_path}")


def _write_source_dir_index(out_path: Path, title: str, subdirs: list[str], files: list[dict], labels: dict) -> None:
    """Write an index.md for one intermediate directory under content/sources/
    (e.g. content/sources/url/ or content/sources/url/<host>/), listing its
    immediate subdirectories and mirrored source pages as plain relative
    links (Issue #493)."""
    lines = ["---", f"title: {_yaml_quote(title)}", "review_status: reviewed", "---", ""]
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
    file's own repo-relative path (docs/DesignDoc-data.md §4.3), which can be
    nested just as deeply (e.g. `path/raw/paper-2024.md`) and would hit the
    same underlying bug.

    `already_written` is the set of content/sources/ paths generate_source_pages()
    already wrote a real mirrored source page to (one per ingest management
    file, via _write_source_page()). A management file whose own mirrored
    path happens to end in `index.md` — a `type: path` source for a
    repo file literally named `index.*` (e.g. `src/index.js`), or a
    `type: url` source sanitized from a URL whose path is `/index`
    (docs/DesignDoc-data.md §4.3 documents this exact `/index` collision
    class, previously solved once already at the bare-domain-vs-path layer
    for Issue #213) — produces an intermediate-directory index_rel identical
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


def generate_source_pages(output_dir: Path, ingest_dir: Path, entity_dir: Path, primary_lang: str) -> set[Path]:
    """Mirror .wikicommit/source/ into content/sources/, one page per ingest
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

    content/sources/ is a single language-independent tree (ingest itself
    has no `lang` concept), unlike content/<lang>/ which exists once per
    language.

    Returns the set of repo-relative Path objects written (for main()'s
    stale-cleanup pass). Always writes at least content/sources/index.md,
    even with zero registered sources, so the root index's "sources" link
    never dead-ends.
    """
    labels = SOURCE_PAGE_LABELS.get(primary_lang, DEFAULT_SOURCE_PAGE_LABELS)
    type_labels = SOURCE_TYPE_LABELS.get(primary_lang, DEFAULT_SOURCE_TYPE_LABELS)
    written: set[Path] = set()
    entries: list[dict] = []

    if ingest_dir.is_dir():
        for mgmt_file in sorted(ingest_dir.rglob("*.md")):
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

            mgmt_rel = mgmt_file.relative_to(ingest_dir)
            title = str(source.get("path") or source.get("url") or mgmt_rel.as_posix())
            out_rel = Path("sources") / mgmt_rel
            _write_source_page(output_dir / out_rel, fm, body, source, title, entity_dir, mgmt_rel, labels)
            written.add(out_rel)

            entries.append({"type": source["type"], "rel": mgmt_rel.as_posix(), "title": title})

    index_rel = Path("sources") / "index.md"
    _write_sources_index(output_dir / index_rel, entries, labels, type_labels)
    written.add(index_rel)
    written |= _write_source_dir_indexes(output_dir, entries, type_labels, labels, already_written=written)
    return written


def convert_file(src_path: Path, rel_path: Path, source_dir: Path, output_dir: Path, primary_lang: str) -> tuple[int, int]:
    """Convert one file's WikiLinks and write it to output_dir. Return (converted, unresolved) counts for this file's links."""
    unresolved = 0

    resolved = parse_wiki_path(src_path, source_dir)
    lang, current_type = (resolved[0], resolved[1]) if resolved else (None, None)

    try:
        content = src_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"WARNING: {src_path}: ファイルを読み込めませんでした: {e}")
        return 0, 0

    def replace(m: re.Match) -> str:
        nonlocal unresolved
        type_name, slug = m.group(1), m.group(2)

        if lang is None or current_type is None:
            unresolved += 1
            print(f"WARNING: [[{type_name}/{slug}]] not resolved in {src_path}")
            return f"{type_name}/{slug}"

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

    out_path = output_dir / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_content, encoding="utf-8")
    print(f"Converting: {src_path} → {out_path}")

    return 1, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert [[Type/slug]] WikiLinks to relative Markdown links for the Quartz build."
    )
    parser.add_argument("--source", required=True, metavar="DIR", help="Input directory (.wikicommit/entity/)")
    parser.add_argument("--output", required=True, metavar="DIR", help="Output directory (Quartz content/)")
    parser.add_argument("--primary-lang", default=None, metavar="LANG",
                        help="Cross-language fallback base language (defaults to .wikicommit/config.yml)")
    args = parser.parse_args()

    repo_root = Path.cwd()
    source_dir = Path(args.source)
    output_dir = Path(args.output)
    primary_lang = args.primary_lang or load_primary_lang(repo_root)

    converted = 0
    unresolved_links = 0
    skipped_removed = 0
    total_pages = 0
    reviewed_pages = 0
    written_rel_paths: set[Path] = set()

    for src_path in sorted(source_dir.rglob("*.md")):
        if is_removed(src_path):
            skipped_removed += 1
            print(f"Skipping (status: removed): {src_path}")
            continue
        # Site-wide page/reviewed counts (Issue #407) exclude Type index.md
        # pages — they're auto-generated navigation, not wiki content — the
        # same exclusion check_orphans.py/check_expires.py/etc. already apply.
        if src_path.name != "index.md":
            total_pages += 1
            if (load_frontmatter(src_path) or {}).get("review_status") == "reviewed":
                reviewed_pages += 1
        rel_path = src_path.relative_to(source_dir)
        file_converted, file_unresolved = convert_file(src_path, rel_path, source_dir, output_dir, primary_lang)
        converted += file_converted
        unresolved_links += file_unresolved
        if file_converted:
            written_rel_paths.add(rel_path)

    targets = existing_lang_targets(source_dir, load_translation_targets(repo_root))
    langs = compute_langs(primary_lang, targets)
    ingest_dir = repo_root / ".wikicommit" / "source"
    written_rel_paths |= generate_source_pages(output_dir, ingest_dir, source_dir, primary_lang)
    generate_root_index(output_dir, primary_lang, langs, total_pages, reviewed_pages, load_theme(repo_root))
    written_rel_paths.add(Path("index.md"))

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
            if rel_path not in written_rel_paths:
                out_path.unlink()
                removed_stale += 1
                print(f"Removing stale build output: {out_path}")

    print(
        f"SUMMARY: converted={converted}, unresolved_links={unresolved_links}, "
        f"skipped_removed={skipped_removed}, removed_stale={removed_stale}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
