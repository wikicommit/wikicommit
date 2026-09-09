#!/usr/bin/env python3
"""
wikicommit-init: Initialize .wikicommit/ directory structure in a repository.

Usage:
    python init.py [--primary-lang en] [--targets en zh] [--no-overwrite] [--repo-root .]
"""

import argparse
import importlib.util
import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

import _root_outputs

_LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]+)*$")


def _read_template_version(templates_dir: Path) -> str:
    """Read WikiCommit's own version from templates/scripts/_version.py.

    That module is the only version source that reaches an installed wiki
    repository (`.claude-plugin/plugin.json` stays behind in the distribution
    repository — see the module's own docstring, Issue #577), so the stamp
    written into `.wikicommit/config.yml` has to come from there. It is loaded
    by path rather than imported by name because `templates/scripts/` is a
    payload directory, not a package on `sys.path`.
    """
    version_path = templates_dir / "scripts" / "_version.py"
    spec = importlib.util.spec_from_file_location("_wikicommit_version", version_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {version_path}")
    module = importlib.util.module_from_spec(spec)
    # Suppress bytecode caching for this one load: exec_module() otherwise
    # writes templates/scripts/__pycache__/_version.cpython-*.pyc into the
    # installed Skill tree, and copy_tree() below would then copy that cache
    # into the freshly initialized `.wikicommit/scripts/`. copy_tree() prunes
    # __pycache__ as well, so this is belt-and-braces: it also keeps init.py
    # from writing into the Skill directory at all.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return str(module.VERSION)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize WikiCommit directory structure"
    )
    parser.add_argument(
        "--primary-lang",
        default="en",
        metavar="LANG",
        help="Primary language code (ISO 639-1, default: en)",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=[],
        metavar="LANG",
        help="Translation target language codes (e.g. --targets en zh)",
    )
    parser.add_argument(
        "--theme",
        default="",
        metavar="TEXT",
        help="Free-text description of the wiki's theme, used by wikicommit-generate's "
        "exclude judgment (default: empty, which disables the judgment)",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip files that already exist",
    )
    parser.add_argument(
        "--update-theme",
        default=None,
        metavar="TEXT",
        help="Rewrite only the theme field of an already-existing .wikicommit/config.yml "
        "(#374 — --theme has no effect on a repeat run, since --no-overwrite always skips "
        "an existing config.yml wholesale; this is the explicit, single-field alternative). "
        "Runs standalone and ignores every other flag except --repo-root; config.yml must "
        "already exist.",
    )
    parser.add_argument(
        "--update-version",
        default=None,
        metavar="VERSION",
        help="Rewrite only the wikicommit_version field of an already-existing "
        ".wikicommit/config.yml (Issue #713 — the field records the version this "
        "repository was last brought in step with, and /wikicommit-update restamps it). "
        "Runs standalone and ignores every other flag except --repo-root.",
    )
    parser.add_argument(
        "--add-config-keys",
        nargs="+",
        default=None,
        metavar="KEY",
        help="Append top-level keys the template has and .wikicommit/config.yml lacks, "
        "carrying each key's commented example across with it (Issue #713). Only appends, "
        "never rewrites an existing value. Runs standalone and ignores every other flag "
        "except --repo-root.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        metavar="PATH",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--repo-url",
        default=None,
        metavar="URL",
        help="This repository's own GitHub URL, substituted into quartz.config.yaml's footer "
        "links (Issue #557). Omit it when no GitHub remote can be resolved: the footer's GitHub "
        "entry is then dropped rather than left pointing at upstream Quartz. Ignored without --quartz.",
    )
    parser.add_argument(
        "--quartz",
        action="store_true",
        help="Generate Quartz v5 local build/preview setup (quartz.config.yaml, package.json, "
        "prebuild-symlinks.cjs, quartz-plugins/) at the repository root",
    )
    parser.add_argument(
        "--quartz-pages",
        action="store_true",
        help="Additionally generate automatic GitHub Pages publishing setup "
        "(.github/workflows/deploy.yml). Requires --quartz.",
    )
    return parser.parse_args()


# Matches quartz.config.yaml's footer `links:` mapping together with its single
# `GitHub: {REPO_URL}` entry, so the placeholder-less rewrite below can collapse both
# in one substitution. Matching them as one unit (rather than deleting the entry and
# separately rewriting the first `links:` in the file) keeps the rewrite anchored to
# this exact mapping even if another plugin's options grow a `links:` key later.
_FOOTER_LINKS_BLOCK_RE = re.compile(
    r"^(?P<indent>[ ]*)links:[ ]*\r?\n[ ]*GitHub:[ ]*\{REPO_URL\}[ ]*\r?\n",
    re.MULTILINE,
)


def _apply_footer_repo_url(config_content: str, repo_url: str | None) -> str:
    """Resolve quartz.config.yaml's `{REPO_URL}` footer placeholder (Issue #557).

    The footer plugin ships with Quartz's own repository as its GitHub link, which
    points every generated wiki's most prominent link at the upstream SSG instead of
    at the wiki being read — the entry point for the whole "read the wiki → open an
    Issue → close the review-tracking Issue" path. pageTitle already gets a
    per-repository default for the same reason; this extends that to the footer.

    With a URL, substitute it. Without one (no GitHub remote, or a local-only
    repository), drop the `GitHub:` entry entirely and collapse the now-empty mapping
    to `links: {}` — leaving a literal `{REPO_URL}` in a config file would be worse
    than having no link, and restoring the upstream Quartz URL is the very defect
    being fixed. `links: {}` is what the plugin already treats as "no links"
    (`opts?.links ?? []`), so the footer still renders, minus the list.

    A template with no `{REPO_URL}` placeholder left (already resolved, or reshaped)
    is returned unchanged rather than rewritten on a guess.
    """
    if repo_url:
        return config_content.replace("{REPO_URL}", yaml.dump(repo_url, default_style='"').strip())

    return _FOOTER_LINKS_BLOCK_RE.sub(lambda m: f"{m.group('indent')}links: {{}}\n", config_content)


# `primary_lang` (ISO 639-1) -> the BCP 47 tag quartz.config.yaml's `locale` takes
# (Issue #771). The values are exactly the locale files shipped by the three
# community-derived plugins that draw the site chrome (explorer / graph / search);
# `tests/test_init.py` checks that every one of them still exists in all three, so a
# locale dropped upstream fails here rather than silently falling back at build time.
#
# This is NOT the same table as `LANG_TO_LOCALE` in the WikiCommit plugins' own
# `src/i18n/index.ts`. That one lists the languages *WikiCommit itself* has written
# translations for (two: en, ja); this one lists what the community plugins already
# translate (28). Naming them alike would make them look like two copies to keep in
# sync, which they are not.
#
# Where a language has several regional locales, the one covering the most readers is
# chosen: `en` -> en-US (not en-GB), `zh` -> zh-CN (not zh-TW), `pt` -> pt-BR. A wiki
# that wants a regional variant edits the one line by hand. `no` is mapped alongside
# `nb` because the macrolanguage code is what people actually type for Norwegian.
QUARTZ_LOCALE_BY_PRIMARY_LANG = {
    "ar": "ar-SA", "ca": "ca-ES", "cs": "cs-CZ", "de": "de-DE", "en": "en-US",
    "es": "es-ES", "fa": "fa-IR", "fi": "fi-FI", "fr": "fr-FR", "he": "he-IL",
    "hu": "hu-HU", "id": "id-ID", "it": "it-IT", "ja": "ja-JP", "kk": "kk-KZ",
    "ko": "ko-KR", "lt": "lt-LT", "nb": "nb-NO", "nl": "nl-NL", "no": "nb-NO",
    "pl": "pl-PL", "pt": "pt-BR", "ro": "ro-RO", "ru": "ru-RU", "th": "th-TH",
    "tr": "tr-TR", "uk": "uk-UA", "vi": "vi-VN", "zh": "zh-CN",
}

# Quartz falls back to en-US for an unknown locale anyway, but writing the fallback
# explicitly keeps the generated config a real value rather than a tag no plugin has.
DEFAULT_QUARTZ_LOCALE = "en-US"


# The languages WikiCommit has written its *own* labels for (Issue #825). Kept
# apart from QUARTZ_LOCALE_BY_PRIMARY_LANG above for the reason stated there:
# that table is what the community plugins already translate (28 languages),
# this one is what this project translates (2), and they move for different
# reasons.
#
# It exists to tell the operator, once, at the moment they pick a primary_lang
# this project has no labels for. **That is the whole of the disclosure**: the
# published site says nothing about the fallback, and the decision not to tell
# the reader is recorded beside ROOT_INDEX_LABELS in
# templates/scripts/convert_wikilinks.py. The operator is told instead because
# they are the one person who can act on it — by writing the labels, or by
# accepting English chrome knowingly — and because telling them costs the
# published pages nothing.
#
# The set is duplicated rather than imported: this script is the one that
# *creates* .wikicommit/, so at the moment it runs, the tree it would import
# from does not exist yet. `tests/test_ui_language_fallback_disclosure.py`
# checks it against every surface the notice names — the plugins' own
# LANG_TO_LOCALE / locales and convert_wikilinks.py's *_LABELS dicts — so the
# copies cannot drift apart silently.
WIKICOMMIT_UI_LANGS = ("en", "ja")


def ui_language_notice(primary_lang: str) -> str | None:
    """One line for an operator whose primary_lang has no WikiCommit labels.

    Returns None for a language this project translates, so the common case
    prints nothing at all. The wording states what will be in English and what
    will not, because the split is not obvious: page bodies and the Quartz
    chrome around them do follow the chosen language, and only WikiCommit's own
    additions fall back.
    """
    lang = (primary_lang or "").strip().lower()
    if lang in WIKICOMMIT_UI_LANGS:
        return None
    return (
        f"NOTE: WikiCommit ships its own labels in {'/'.join(WIKICOMMIT_UI_LANGS)} only, "
        f"so on a {lang!r} wiki the review banner, sources box, page properties and the "
        "generated index/overview pages render in English. Page bodies and Quartz's own "
        "chrome still follow " + repr(lang) + ". Published pages do not say that this "
        "happened, so this notice is the only place it is stated."
    )


def quartz_locale_for(primary_lang: str) -> str:
    """Resolve quartz.config.yaml's `{LOCALE}` from `primary_lang` (Issue #771).

    Before this, the template carried a hard-coded `locale: en-US` that init never
    substituted, so a Japanese wiki shipped with its body text and banner in Japanese
    and its sidebar, search and graph in English — the translations existed, they were
    simply never reached. An unmapped language stays en-US rather than being guessed
    at: an invented tag would leave the chrome in English regardless while making the
    config claim otherwise.
    """
    return QUARTZ_LOCALE_BY_PRIMARY_LANG.get((primary_lang or "").strip().lower(),
                                             DEFAULT_QUARTZ_LOCALE)


_THEME_LINE_RE = re.compile(r"^theme:.*$", re.MULTILINE)


_VERSION_LINE_RE = re.compile(r"^wikicommit_version:.*$", re.MULTILINE)


def _read_config(repo_root: Path) -> tuple[Path, str] | None:
    """The config.yml path and its text, or None after printing why not."""
    config_path = repo_root / ".wikicommit" / "config.yml"
    if not config_path.is_file():
        print(f"ERROR: {config_path} does not exist (run wikicommit-init first)", file=sys.stderr)
        return None
    return config_path, config_path.read_text(encoding="utf-8")


def _update_version(repo_root: Path, version: str) -> int:
    """Rewrite only the `wikicommit_version:` line of an existing config.yml (Issue #713).

    The field records the version this repository was last brought in step with, so an
    update has to restamp it — and it is the only writer that ever does (init stamps it
    once on creation and then skips config.yml wholesale forever after).

    Text-level, exactly like `_update_theme()` above, and for a reason that outweighs the
    convenience of a YAML round-trip: config.yml ships commented-out worked examples that
    are the only documentation for the fields they describe (`site_description`'s per-
    language example, added by Issue #671, is a key the template deliberately does not
    ship — only the comment shows the shape). `yaml.safe_load` + `yaml.dump` discards
    every one of them, so a repository that ran an update would silently lose the
    instructions for the fields it had not filled in yet.
    """
    read = _read_config(repo_root)
    if read is None:
        return 1
    config_path, content = read
    try:
        new_line = f'wikicommit_version: "{version}"'
        if _VERSION_LINE_RE.search(content):
            # Lambda replacement rather than a raw string, for the same reason
            # _update_theme() gives: re.sub interprets backslash escapes in a string
            # replacement.
            content = _VERSION_LINE_RE.sub(lambda _m: new_line, content, count=1)
        else:
            # A config.yml created before Issue #577 has no stamp at all. Prepend rather
            # than append: the template carries it as the first line, and keeping that
            # position means a stamped file looks the same however it got stamped.
            content = new_line + "\n" + content
        config_path.write_text(content, encoding="utf-8")
        print(f"UPDATED: {config_path.relative_to(repo_root)} (wikicommit_version)")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


# What each `{NAME}` placeholder becomes when a key is *added* to an existing config.yml
# (Issue #713). These are the values a fresh init with no flags would write, which is
# exactly right here: a key the template has only just gained is inert until the user
# fills it in, and that is what "newly introduced" means. `{VERSION}` is resolved from
# the template rather than listed, since it changes every release.
#
# Copying a block across without substituting would be silently wrong rather than
# merely ugly: `theme: {THEME}` is valid YAML, and it parses as a *mapping* — so
# wikicommit-generate would read the wiki's theme as `{"THEME": None}` instead of a
# string, with nothing anywhere reporting a problem.
_CONFIG_PLACEHOLDER_DEFAULTS = {
    "{TARGETS}": "[]",
    "{PRIMARY_LANG}": "en",
    "{THEME}": '""',
}

_PLACEHOLDER_TOKEN_RE = re.compile(r"\{[A-Z][A-Z0-9_]*\}")


def _substitute_config_placeholders(block: list[str], version: str) -> list[str] | None:
    """`block` with its placeholders replaced by shipped defaults, or None if one is
    unknown — a literal placeholder written into a user's config is worse than not
    adding the key at all, so an unrecognized one refuses rather than guesses."""
    # `{VERSION}` substitutes *bare*, exactly as the full-init path at the bottom of
    # main() does, because the template already writes it inside quotes
    # (`wikicommit_version: "{VERSION}"`). Adding a second pair here produced
    # `wikicommit_version: ""0.2.0""`, which YAML rejects for the whole document — the
    # same `""""` trap check_distribution_freshness.py records against its own
    # placeholder substitute (Issue #712).
    defaults = dict(_CONFIG_PLACEHOLDER_DEFAULTS, **{"{VERSION}": version})
    out = []
    for line in block:
        for token in set(_PLACEHOLDER_TOKEN_RE.findall(line)):
            if token not in defaults:
                return None
            line = line.replace(token, defaults[token])
        out.append(line)
    return out


def _add_config_keys(repo_root: Path, templates_dir: Path, keys: list[str]) -> int:
    """Append top-level keys the template has and this config.yml lacks (Issue #713).

    Takes the block verbatim from the template — the key, and the comment lines directly
    above it. Those comments are the field's only documentation on the installed side, so
    carrying the key without them would deliver a setting nobody can use.

    Only ever appends, and only keys that are genuinely absent: an update proposes what
    the template gained, and a value the user already set is theirs. Nested keys are not
    handled — a key is added whole or not at all, so a new sub-key under an existing
    `translation:` is left to the human, who can see it in the diff the update shows.
    """
    read = _read_config(repo_root)
    if read is None:
        return 1
    template_path = templates_dir / "config.yml"
    if not template_path.is_file():
        print(f"ERROR: {template_path} does not exist", file=sys.stderr)
        return 1
    config_path, content = read
    try:
        template_lines = template_path.read_text(encoding="utf-8").splitlines()
        existing = {
            m.group(1)
            for m in re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*):", content, re.MULTILINE)
        }
        added: list[str] = []
        for key in keys:
            if key in existing:
                print(f"SKIPPED: {key} (already present)")
                continue
            block = _template_key_block(template_lines, key)
            if block is None:
                print(f"SKIPPED: {key} (not a top-level key in the template)")
                continue
            block = _substitute_config_placeholders(block, _read_template_version(templates_dir))
            if block is None:
                print(f"SKIPPED: {key} (its template block holds a placeholder with no known default)")
                continue
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n" + "\n".join(block) + "\n"
            added.append(key)
            # `existing` is a snapshot of the file as it was read, so a key repeated in
            # `keys` would otherwise be appended twice. YAML accepts a duplicate mapping
            # key silently (last one wins) while `_update_theme()` rewrites the *first*,
            # so the two would disagree with nothing reporting it.
            existing.add(key)
        if added:
            # Refuse to write a config.yml that no longer parses. Every consumer reads
            # this file with yaml.safe_load, and a document-level parse error takes the
            # whole file down — `primary_lang`, `theme`, `targets` and all — rather than
            # just the key being added. Reporting here is the difference between one
            # setting not arriving and the repository's configuration going dark.
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                print(
                    f"ERROR: adding {', '.join(added)} would leave "
                    f"{config_path.relative_to(repo_root)} unparseable, so nothing was "
                    f"written: {e}",
                    file=sys.stderr,
                )
                return 1
            config_path.write_text(content, encoding="utf-8")
            print(f"UPDATED: {config_path.relative_to(repo_root)} ({', '.join(added)})")
        print(f"SUMMARY: added={len(added)}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _template_key_block(template_lines: list[str], key: str) -> list[str] | None:
    """The template lines defining top-level `key`, with the comments above it.

    Returns None when `key` is not a top-level key there. The block runs from the first
    comment line of the contiguous comment run immediately above the key, through the
    key's own indented continuation lines.
    """
    start = None
    for i, line in enumerate(template_lines):
        if re.match(rf"^{re.escape(key)}:", line):
            start = i
            break
    if start is None:
        return None
    end = start + 1
    while end < len(template_lines):
        line = template_lines[end]
        if line.strip() == "" or line.startswith((" ", "\t")) or line.lstrip().startswith("#"):
            end += 1
            continue
        break
    # Trim trailing blank/comment lines: a comment run at the end belongs to whatever
    # key comes next, not to this one.
    while end > start + 1 and (
        template_lines[end - 1].strip() == "" or template_lines[end - 1].lstrip().startswith("#")
    ):
        end -= 1
    head = start
    while head > 0 and template_lines[head - 1].lstrip().startswith("#"):
        head -= 1
    return template_lines[head:end]


def _update_theme(repo_root: Path, theme: str) -> int:
    """Rewrite only the `theme:` line of an already-existing config.yml (#374).

    Unlike write_file()'s --no-overwrite handling (which skips config.yml wholesale
    on a repeat init to protect the rest of the file), this is an explicit,
    single-field update the caller opted into by name — it always overwrites
    whatever theme value was previously there.
    """
    config_path = repo_root / ".wikicommit" / "config.yml"
    if not config_path.is_file():
        print(f"ERROR: {config_path} does not exist (run wikicommit-init first)", file=sys.stderr)
        return 1
    try:
        content = config_path.read_text(encoding="utf-8")
        theme_yaml = yaml.dump(theme, default_style='"', allow_unicode=True).strip()
        new_line = f"theme: {theme_yaml}"
        if _THEME_LINE_RE.search(content):
            # A lambda replacement (not the raw string) is required here: re.sub
            # interprets backslash escapes (\n, \\, ...) in a string replacement,
            # which would corrupt any YAML-escaped backslash/newline already
            # inside theme_yaml. set_frontmatter_field.py uses the same lambda
            # pattern for the identical reason (Issue #371).
            content = _THEME_LINE_RE.sub(lambda _m: new_line, content, count=1)
        else:
            # A config.yml created before #160 has no theme field at all; append
            # one. theme is a flat top-level key, so its position doesn't affect
            # parsing.
            if content and not content.endswith("\n"):
                content += "\n"
            content += ("\n" if content else "") + new_line + "\n"
        config_path.write_text(content, encoding="utf-8")
        print(f"UPDATED: {config_path.relative_to(repo_root)} (theme)")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    templates_dir = Path(__file__).parent / "templates"

    if args.update_theme is not None:
        return _update_theme(repo_root, args.update_theme)

    if args.update_version is not None:
        return _update_version(repo_root, args.update_version)

    if args.add_config_keys is not None:
        return _add_config_keys(repo_root, templates_dir, args.add_config_keys)

    for lang in [args.primary_lang] + (args.targets or []):
        if not _LANG_RE.match(lang):
            print(f"ERROR: invalid language code {lang!r} (expected ISO 639-1 e.g. 'ja')", file=sys.stderr)
            return 1

    if args.quartz_pages and not args.quartz:
        print("ERROR: --quartz-pages requires --quartz", file=sys.stderr)
        return 1

    # The same three-way split print_next_steps.py --variant takes: the guidance
    # and the generation both key off it, from the one list in _root_outputs.py.
    variant = "quartz_pages" if args.quartz_pages else ("quartz_only" if args.quartz else "none")

    created: list[str] = []
    skipped: list[str] = []

    def rel(path: Path) -> str:
        return str(path.relative_to(repo_root))

    def _flags(dest_rel: str) -> dict:
        """The copy flags declared for this repository-relative path (Issue #712).

        Ownership — "WikiCommit's payload" vs "the user may have edited this" — is
        recorded once, in _root_outputs.py, next to the variant and `git add` decisions
        for the same path. Restating it as a literal at each call site is what let
        `.wikicommit/config.yml` and `.wikicommit/schema/` end up with no flag at all,
        leaving --no-overwrite as the single thing standing between a re-init and the
        user's theme, targets and hand-edited type templates.

        An unlisted path falls back to the protective end rather than raising: this is
        the flag lookup for a copy that is about to happen either way, and refusing to
        copy is not better than copying without clobbering.
        """
        entry = _root_outputs.by_path(dest_rel)
        if entry is None:
            return {"always_skip_existing": True}
        return _root_outputs.copy_flags(entry)

    def write_file(
        dest: Path,
        content: str,
        *,
        always_skip_existing: bool = False,
        always_overwrite: bool = False,
    ) -> None:
        # Both flags mirror copy_file's of the same name, and for the same reason: the
        # ownership of each path is declared once in _root_outputs.py and reaches every
        # writer through _flags(). Accepting both here — even though every path this
        # function currently writes is `review` — keeps that lookup safe to use at any
        # call site, rather than leaving one writer that silently cannot express half
        # the policies.
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and (always_skip_existing or (args.no_overwrite and not always_overwrite)):
            reason = "already exists" if always_skip_existing else "--no-overwrite"
            print(f"SKIPPED: {rel(dest)} ({reason})")
            skipped.append(rel(dest))
            return
        dest.write_text(content, encoding="utf-8")
        print(f"CREATED: {rel(dest)}")
        created.append(rel(dest))

    def copy_file(
        src: Path,
        dest: Path,
        *,
        always_skip_existing: bool = False,
        always_overwrite: bool = False,
    ) -> None:
        # Root-level files (package.json, deploy.yml, quality gate configs) pass
        # always_skip_existing=True: an existing repo's own files must never be
        # clobbered, regardless of --no-overwrite. quartz.config.yaml is the one
        # root-level exception — it goes through write_file() instead (Issue #317),
        # since its pageTitle needs placeholder substitution rather than a raw copy.
        #
        # always_overwrite=True is the opposite end of the same ownership axis
        # (Issue #647): `.wikicommit/scripts/` is distribution payload, not the
        # user's content, so a re-init refreshes it even under --no-overwrite.
        # The two flags are mutually exclusive by construction — nothing passes
        # both — and always_skip_existing wins if one ever did, keeping the
        # "never clobber the user's own file" guarantee the stronger rule.
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and always_skip_existing:
            print(f"SKIPPED: {rel(dest)} (already exists)")
            skipped.append(rel(dest))
            return
        if dest.exists() and args.no_overwrite and not always_overwrite:
            print(f"SKIPPED: {rel(dest)} (--no-overwrite)")
            skipped.append(rel(dest))
            return
        # A destination that already *is* the source is a no-op, not a copy:
        # shutil.copy2() raises SameFileError, which the caller turns into an
        # ERROR that aborts the whole run before any root-level output is
        # written. This repository is exactly that case — `.wikicommit/schema`
        # and `.wikicommit/scripts` are symlinks into templates/ so that
        # dogfooding cannot drift from the distributed copy
        # (tests/test_template_mirror_sync.py) — and the always_overwrite path
        # above no longer skips past it.
        if dest.exists() and dest.samefile(src):
            print(f"SKIPPED: {rel(dest)} (already the same file as the template)")
            skipped.append(rel(dest))
            return
        shutil.copy2(src, dest)
        print(f"CREATED: {rel(dest)}")
        created.append(rel(dest))

    def copy_tree(
        src_dir: Path,
        dest_dir: Path,
        *,
        always_skip_existing: bool = False,
        always_overwrite: bool = False,
        exclude: "Callable[[Path], bool] | None" = None,
    ) -> None:
        # os.walk() (rather than Path.rglob("*")) lets us prune node_modules/
        # before descending into it, instead of listing/stat-ing every file
        # inside it and filtering afterward (#211). node_modules is only
        # present if a local `npm install`/`npm ci` has been run inside a
        # template directory (e.g. to run its vitest suite); a fresh git
        # checkout never has it. __pycache__ is pruned for the same reason:
        # in this development repository `.wikicommit/scripts` symlinks to
        # `templates/scripts`, so running any script leaves a whole directory
        # of .pyc files there that has no business being copied into a user's
        # wiki repository (Issue #577).
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d not in ("node_modules", "__pycache__")]
            for filename in filenames:
                src_file = Path(dirpath) / filename
                if not src_file.is_file():
                    continue
                rel_path = src_file.relative_to(src_dir)
                if exclude is not None and exclude(rel_path):
                    continue
                dest_file = dest_dir / rel_path
                copy_file(
                    src_file,
                    dest_file,
                    always_skip_existing=always_skip_existing,
                    always_overwrite=always_overwrite,
                )

    def make_dir_with_gitkeep(dir_path: Path) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        gitkeep = dir_path / ".gitkeep"
        if args.no_overwrite and gitkeep.exists():
            skipped.append(rel(gitkeep))
            return
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")
            print(f"CREATED: {rel(gitkeep)}")
            created.append(rel(gitkeep))

    try:
        config_template = (templates_dir / "config.yml").read_text(encoding="utf-8")
        # Quote each element to prevent YAML 1.1 boolean coercion (e.g. 'no' → False in PyYAML)
        targets_yaml = "[" + ", ".join(f'"{t}"' for t in args.targets) + "]" if args.targets else "[]"
        # yaml.dump handles all YAML-significant characters (quotes, backslashes,
        # newlines, control chars) correctly; manual backslash/quote-only escaping
        # left newlines silently folded to spaces and control chars unescaped
        # (producing a config.yml that fails to parse at all).
        theme_yaml = yaml.dump(args.theme, default_style='"', allow_unicode=True).strip()
        config_content = (
            config_template
            .replace("{VERSION}", _read_template_version(templates_dir))
            .replace("{TARGETS}", targets_yaml)
            .replace("{PRIMARY_LANG}", args.primary_lang)
            .replace("{THEME}", theme_yaml)
        )
        write_file(
            repo_root / ".wikicommit" / "config.yml",
            config_content,
            **_flags(".wikicommit/config.yml"),
        )

        schema_src = templates_dir / "schema"
        if not schema_src.is_dir():
            print(f"ERROR: templates/schema/ not found at {schema_src}", file=sys.stderr)
            return 1
        copy_tree(schema_src, repo_root / ".wikicommit" / "schema", **_flags(".wikicommit/schema"))

        dirs = [
            repo_root / ".wikicommit" / "source" / "path",
            repo_root / ".wikicommit" / "source" / "url",
            repo_root / ".wikicommit" / "entity" / "assets",
            repo_root / ".wikicommit" / "entity" / args.primary_lang,
            repo_root / ".wikicommit" / "view" / args.primary_lang,
            # Review records (Issue #750). Created empty, with no per-language or
            # per-tree subdirectory: record_review.py mirrors a page's own path under
            # here on demand, and which pages exist is not known at init time.
            repo_root / ".wikicommit" / "review",
        ]
        for d in dirs:
            make_dir_with_gitkeep(d)

        scripts_src = templates_dir / "scripts"
        if not scripts_src.is_dir():
            print(f"ERROR: templates/scripts/ not found at {scripts_src}", file=sys.stderr)
            return 1
        # update="overwrite" (Issue #647, now declared in _root_outputs.py per Issue
        # #712): `.wikicommit/scripts/` is WikiCommit's
        # own distribution payload — shared quality-gate scripts the Skills call, not
        # content the user authors — so a re-init refreshes it even under
        # --no-overwrite (which exists to protect the user's own files: config.yml,
        # schema/, entity pages, root-level configs).
        #
        # The concrete failure this fixes is `_version.py`, the one version source
        # that reaches an installed wiki repository (Issue #577). Left stale, it makes
        # `generated_with` / `translated_with` claim that pages built under the NEW
        # Skills were built under the OLD version — actively wrong, where a missing
        # stamp would merely have been uninformative, and wrong in exactly the way
        # that defeats the field's only use (grep + CHANGELOG to find pages worth
        # regenerating).
        #
        # The whole tree is refreshed rather than `_version.py` alone: exempting one
        # file would leave the version claiming to be new while the scripts it ships
        # alongside stayed old. Note that copy_tree() never deletes, so a script
        # renamed upstream still leaves its old name behind as an orphan here
        # (Issue #583) — refreshing does not make the tree an exact mirror.
        copy_tree(
            scripts_src,
            repo_root / ".wikicommit" / "scripts",
            **_flags(".wikicommit/scripts"),
        )

        # Every root-level output that is a verbatim copy comes from _root_outputs.py,
        # the same list print_next_steps.py builds its `git add` guidance from
        # (Issue #642). Which variant each file belongs to, and why, is recorded there
        # rather than here, so adding one is a single edit instead of two lists to keep
        # in step — the drift that shipped install-local-plugins.cjs without telling
        # anyone to commit it (Issue #556). The copy flags come from the same list's
        # `update` column (Issue #712): the user's own files are never clobbered, while
        # WikiCommit's own payload (the workflows, the *.cjs build scripts) is refreshed
        # even under --no-overwrite.
        # The rest of the root-level outputs are generated further down and cannot be
        # plain copies: config.yml and quartz.config.yaml substitute placeholders,
        # schema/scripts/quartz-plugins are directory trees, and entity/source are
        # created with a .gitkeep.
        for template_rel, dest_rel in _root_outputs.plain_copies(variant):
            copy_file(templates_dir / template_rel, repo_root / dest_rel, **_flags(dest_rel))

        if args.quartz:
            quartz_plugins_src = templates_dir / "quartz-plugins"
            if not quartz_plugins_src.is_dir():
                print(f"ERROR: templates/quartz-plugins/ not found at {quartz_plugins_src}", file=sys.stderr)
                return 1

            # pageTitle defaults to the repo directory name (Issue #317) rather than
            # a plain copy_file(), so a fresh --quartz init doesn't ship every wiki
            # with the literal template title "WikiCommit Wiki".
            #
            # pageTitleSuffix gets the same name with a " - " separator (Issue #679).
            # Quartz's Head.tsx builds <title> from the page's own frontmatter title
            # plus this suffix and nothing else, so with the previous empty default no
            # tab, og:title or twitter:title on the whole site carried the site's name
            # — the front page read simply "Wiki". pageTitle does not reach any of
            # those three; it goes to the sidebar heading and og:site_name. Quoting
            # through yaml.dump preserves the leading space, which a bare YAML scalar
            # would strip.
            quartz_config_template = (templates_dir / "quartz.config.yaml").read_text(encoding="utf-8")
            page_title_yaml = yaml.dump(repo_root.name, default_style='"', allow_unicode=True).strip()
            page_title_suffix_yaml = yaml.dump(
                f" - {repo_root.name}", default_style='"', allow_unicode=True
            ).strip()
            quartz_config_content = quartz_config_template.replace("{PAGE_TITLE}", page_title_yaml)
            quartz_config_content = quartz_config_content.replace(
                "{PAGE_TITLE_SUFFIX}", page_title_suffix_yaml
            )
            quartz_config_content = quartz_config_content.replace(
                "{LOCALE}", quartz_locale_for(args.primary_lang)
            )
            quartz_config_content = _apply_footer_repo_url(quartz_config_content, args.repo_url)
            quartz_config_path = repo_root / "quartz.config.yaml"
            quartz_config_is_new = not quartz_config_path.exists()
            write_file(
                quartz_config_path,
                quartz_config_content,
                **_flags("quartz.config.yaml"),
            )
            if quartz_config_is_new and not args.repo_url:
                # Without this line, dropping the footer's GitHub entry is completely
                # silent: the caller passes --repo-url as a `$(gh ...)` command
                # substitution, so an unresolvable remote only shows up as gh's own
                # stderr, and wikicommit-init's SKILL.md nonetheless requires the
                # agent to tell the user it happened (Issue #557).
                print(
                    f"NOTE: {rel(quartz_config_path)}: no --repo-url resolved, so the footer's "
                    "GitHub entry was dropped (links: {}) instead of being left pointing at "
                    "upstream Quartz. Add the link by hand once this repository has a GitHub remote."
                )
            # Quartz 固有の ignore パターンは --quartz 選択時のみ追記する。非 Quartz
            # リポジトリの content/ など無関係なディレクトリを誤って無視しないため、
            # 常設の .gitignore（上で copy_file 済み）には含めていない。
            quartz_gitignore_section = (templates_dir / "gitignore-quartz.txt").read_text(encoding="utf-8")
            gitignore_path = repo_root / ".gitignore"
            existing_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
            if "# Quartz build artifacts" not in existing_gitignore:
                with gitignore_path.open("a", encoding="utf-8") as f:
                    if existing_gitignore and not existing_gitignore.endswith("\n"):
                        f.write("\n")
                    f.write(("\n" if existing_gitignore else "") + quartz_gitignore_section)
                print(f"UPDATED: {rel(gitignore_path)} (Quartz ignore patterns)")

            # review_status バナー・JSON-LD 埋め込みを提供する Quartz カスタムプラグイン。
            # dist/ はコミット済みのビルド成果物（他の Quartz v5 コミュニティプラグインと同じ配布形態）
            # のため、npm install 不要でそのままコピーする。copy_tree はファイルシステムを直接
            # 走査するため git 管理外の node_modules/ も存在すればコピーしてしまう。加えて
            # vitest 関連ファイル（#93）・eslint 関連ファイル（#94）はテンプレート自身の CI 専用で
            # ありユーザーの Wiki には不要なため、copy_tree 側で明示的に除外する。
            copy_tree(
                quartz_plugins_src,
                repo_root / "quartz-plugins",
                exclude=_root_outputs.is_quartz_plugin_dev_artifact,
                **_flags("quartz-plugins"),
            )

        notice = ui_language_notice(args.primary_lang)
        if notice:
            print(notice)
        print(f"SUMMARY: created={len(created)}, skipped={len(skipped)}")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
