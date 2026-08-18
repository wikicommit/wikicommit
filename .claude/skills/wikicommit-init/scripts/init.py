#!/usr/bin/env python3
"""
wikicommit-init: Initialize .wikicommit/ directory structure in a repository.

Usage:
    python init.py [--primary-lang en] [--targets en zh] [--no-overwrite] [--repo-root .]
"""

import argparse
import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

_LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]+)*$")
_TEST_ARTIFACT_RE = re.compile(r"\.test\.tsx?$")


def _is_quartz_plugin_dev_artifact(rel_path: Path) -> bool:
    """vitest suites/config (#93) and eslint config (#94) are dev-only tooling
    for the template's own CI and are not needed by the generated site
    (dist/ is pre-built)."""
    return (
        rel_path.name in ("vitest.config.ts", "eslint.config.js")
        or _TEST_ARTIFACT_RE.search(rel_path.name) is not None
    )


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
        "--repo-root",
        default=".",
        metavar="PATH",
        help="Repository root path (default: current directory)",
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


_THEME_LINE_RE = re.compile(r"^theme:.*$", re.MULTILINE)


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

    for lang in [args.primary_lang] + (args.targets or []):
        if not _LANG_RE.match(lang):
            print(f"ERROR: invalid language code {lang!r} (expected ISO 639-1 e.g. 'ja')", file=sys.stderr)
            return 1

    if args.quartz_pages and not args.quartz:
        print("ERROR: --quartz-pages requires --quartz", file=sys.stderr)
        return 1

    created: list[str] = []
    skipped: list[str] = []

    def rel(path: Path) -> str:
        return str(path.relative_to(repo_root))

    def write_file(dest: Path, content: str, *, always_skip_existing: bool = False) -> None:
        # always_skip_existing mirrors copy_file's flag of the same name: root-level
        # files (e.g. quartz.config.yaml) must never be clobbered on repeat
        # `/wikicommit-init --quartz` runs, regardless of --no-overwrite.
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and (always_skip_existing or args.no_overwrite):
            reason = "already exists" if always_skip_existing else "--no-overwrite"
            print(f"SKIPPED: {rel(dest)} ({reason})")
            skipped.append(rel(dest))
            return
        dest.write_text(content, encoding="utf-8")
        print(f"CREATED: {rel(dest)}")
        created.append(rel(dest))

    def copy_file(src: Path, dest: Path, *, always_skip_existing: bool = False) -> None:
        # Root-level files (package.json, deploy.yml, quality gate configs) pass
        # always_skip_existing=True: an existing repo's own files must never be
        # clobbered, regardless of --no-overwrite. quartz.config.yaml is the one
        # root-level exception — it goes through write_file() instead (Issue #317),
        # since its pageTitle needs placeholder substitution rather than a raw copy.
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and (always_skip_existing or args.no_overwrite):
            reason = "already exists" if always_skip_existing else "--no-overwrite"
            print(f"SKIPPED: {rel(dest)} ({reason})")
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
        exclude: "Callable[[Path], bool] | None" = None,
    ) -> None:
        # os.walk() (rather than Path.rglob("*")) lets us prune node_modules/
        # before descending into it, instead of listing/stat-ing every file
        # inside it and filtering afterward (#211). node_modules is only
        # present if a local `npm install`/`npm ci` has been run inside a
        # template directory (e.g. to run its vitest suite); a fresh git
        # checkout never has it.
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d != "node_modules"]
            for filename in filenames:
                src_file = Path(dirpath) / filename
                if not src_file.is_file():
                    continue
                rel_path = src_file.relative_to(src_dir)
                if exclude is not None and exclude(rel_path):
                    continue
                dest_file = dest_dir / rel_path
                copy_file(src_file, dest_file, always_skip_existing=always_skip_existing)

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
            .replace("{TARGETS}", targets_yaml)
            .replace("{PRIMARY_LANG}", args.primary_lang)
            .replace("{THEME}", theme_yaml)
        )
        write_file(repo_root / ".wikicommit" / "config.yml", config_content)

        schema_src = templates_dir / "schema"
        if not schema_src.is_dir():
            print(f"ERROR: templates/schema/ not found at {schema_src}", file=sys.stderr)
            return 1
        copy_tree(schema_src, repo_root / ".wikicommit" / "schema")

        dirs = [
            repo_root / ".wikicommit" / "source" / "path",
            repo_root / ".wikicommit" / "source" / "url",
            repo_root / ".wikicommit" / "entity" / "assets",
            repo_root / ".wikicommit" / "entity" / args.primary_lang,
        ]
        for d in dirs:
            make_dir_with_gitkeep(d)

        scripts_src = templates_dir / "scripts"
        if not scripts_src.is_dir():
            print(f"ERROR: templates/scripts/ not found at {scripts_src}", file=sys.stderr)
            return 1
        copy_tree(scripts_src, repo_root / ".wikicommit" / "scripts")

        # Quality gate configs (lychee / markdownlint) are generated regardless
        # of the Quartz choice — wikicommit-merge depends on them unconditionally.
        copy_file(templates_dir / ".lychee.toml", repo_root / ".lychee.toml", always_skip_existing=True)
        copy_file(
            templates_dir / ".markdownlint.json",
            repo_root / ".markdownlint.json",
            always_skip_existing=True,
        )
        copy_file(templates_dir / ".gitignore", repo_root / ".gitignore", always_skip_existing=True)

        # Unlike deploy.yml (Quartz-only, below), this workflow backs the
        # review pipeline (wikicommit-merge → tracking Issue → Issue close),
        # which is unconditional on the Quartz publishing choice (Issue #313).
        copy_file(
            templates_dir / "workflows" / "review-issue-close-sync.yml",
            repo_root / ".github" / "workflows" / "review-issue-close-sync.yml",
            always_skip_existing=True,
        )

        if args.quartz:
            quartz_plugins_src = templates_dir / "quartz-plugins"
            if not quartz_plugins_src.is_dir():
                print(f"ERROR: templates/quartz-plugins/ not found at {quartz_plugins_src}", file=sys.stderr)
                return 1

            # pageTitle defaults to the repo directory name (Issue #317) rather than
            # a plain copy_file(), so a fresh --quartz init doesn't ship every wiki
            # with the literal template title "WikiCommit Wiki".
            quartz_config_template = (templates_dir / "quartz.config.yaml").read_text(encoding="utf-8")
            page_title_yaml = yaml.dump(repo_root.name, default_style='"', allow_unicode=True).strip()
            quartz_config_content = quartz_config_template.replace("{PAGE_TITLE}", page_title_yaml)
            write_file(
                repo_root / "quartz.config.yaml",
                quartz_config_content,
                always_skip_existing=True,
            )
            copy_file(templates_dir / "package.json", repo_root / "package.json", always_skip_existing=True)
            copy_file(
                templates_dir / "prebuild-symlinks.cjs",
                repo_root / "prebuild-symlinks.cjs",
                always_skip_existing=True,
            )
            copy_file(
                templates_dir / "repair-plugin-builds.cjs",
                repo_root / "repair-plugin-builds.cjs",
                always_skip_existing=True,
            )
            copy_file(
                templates_dir / "install-local-plugins.cjs",
                repo_root / "install-local-plugins.cjs",
                always_skip_existing=True,
            )

            # deploy.yml is the one piece that actually opts the repository into automatic
            # GitHub Pages publishing on every merge to main, so it is gated separately behind
            # --quartz-pages (Issue #335) — --quartz alone only sets up local build/preview.
            if args.quartz_pages:
                copy_file(
                    templates_dir / "workflows" / "deploy.yml",
                    repo_root / ".github" / "workflows" / "deploy.yml",
                    always_skip_existing=True,
                )

            # wikicommit-banner's "report an issue" link (Issue #245/#313) points at
            # ?template=report.md, which silently no-ops without this file. Distributed
            # only under --quartz since wikicommit-banner itself is a Quartz-only plugin
            # (Issue #339 — unlike review-issue-close-sync.yml above, which backs the
            # review pipeline unconditionally).
            copy_file(
                templates_dir / ".github" / "ISSUE_TEMPLATE" / "report.md",
                repo_root / ".github" / "ISSUE_TEMPLATE" / "report.md",
                always_skip_existing=True,
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
                always_skip_existing=True,
                exclude=_is_quartz_plugin_dev_artifact,
            )

        print(f"SUMMARY: created={len(created)}, skipped={len(skipped)}")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
