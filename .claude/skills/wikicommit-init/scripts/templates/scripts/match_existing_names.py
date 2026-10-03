"""Does an entity Pass 2c just named already have a page under that name? (Issue #1096)

Pass 2c sets `action: update` only when an existing page has the same type and
the same slug. A source that calls a concept by a name an existing page carries
as an *alias* therefore gets a new page next to the old one — the type
templates tell the writer to put alternate names in `aliases` rather than a
page of their own, but nothing on the matching side read them back.

This script is that matching side. It takes the entities Pass 2c extracted
(JSON on stdin: a list of objects with `title` and `type`, optionally `aliases`)
and compares each name against the `title` and `aliases` of every page under
`.wikicommit/entity/<primary_lang>/`. The comparison is **string equality after
normalization** (NFKC, case-folded, runs of whitespace collapsed — the same
`normalize_name()` the other name checks use) and nothing else: two names that
merely mean the same thing are not matched here. Whether they are the same
concept is a person's call, not a generation-time one.

One line per entity:

    SAME: <n> "<title>" -> <path> (matched <title|alias> "<name>")
    AMBIGUOUS: <n> "<title>" -> <path>, <path> (same type; several pages answer to this name)
    OTHER_TYPE: <n> "<title>" -> <path> (type <Type>, not <Type>)
    NONE: <n> "<title>"
    SUMMARY: entities=<N>, same=<N>, ambiguous=<N>, other_type=<N>

`<n>` is the entity's index in the input list. An entity with one same-type
match *and* other-type matches gets both a SAME and an OTHER_TYPE line.

Only `primary_lang` pages are read: originals are written in `primary_lang`,
and a translation carries no `aliases` of its own (`/wikicommit-translate`
does not copy them), so its title is the original's name in another language.
`index.md` and `status: removed` pages are skipped.

Exit code: 0 always, except 2 when stdin is not a JSON list.
"""

import argparse
import json
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _wikilink import ENTITY_DIR, collect_entity_pages, load_primary_lang, normalize_name, parse_wiki_path


def _names(frontmatter: dict) -> list[tuple[str, str]]:
    names = []
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        names.append(("title", title.strip()))
    aliases = frontmatter.get("aliases")
    if isinstance(aliases, list):
        names.extend(("alias", a.strip()) for a in aliases if isinstance(a, str) and a.strip())
    return names


def build_index(lang: str, entity_dir: Path = ENTITY_DIR) -> dict[str, list[tuple[str, str, str, str]]]:
    """normalized name -> [(type, path, kind, name as written)] for `lang` pages."""
    index: dict[str, list[tuple[str, str, str, str]]] = {}
    for page in collect_entity_pages(entity_dir):
        parsed = parse_wiki_path(page, entity_dir)
        if parsed is None or parsed[0] != lang:
            continue
        frontmatter, _error = parse_frontmatter(page)
        if not isinstance(frontmatter, dict) or frontmatter.get("status") == "removed":
            continue
        seen = set()
        for kind, name in _names(frontmatter):
            key = normalize_name(name)
            if key in seen:
                continue
            seen.add(key)
            index.setdefault(key, []).append((parsed[1], page.as_posix(), kind, name))
    return index


def _type_name(value: object) -> str:
    return value.removeprefix("schema:") if isinstance(value, str) else ""


def match(entities: list, index: dict) -> list[str]:
    lines = []
    counts = {"same": 0, "ambiguous": 0, "other_type": 0}
    for n, entity in enumerate(entities):
        entity = entity if isinstance(entity, dict) else {}
        title = entity.get("title") if isinstance(entity.get("title"), str) else ""
        wanted = _type_name(entity.get("type"))
        aliases = entity.get("aliases")
        # 1 つの文字列で来た別名は 1 件として読む（反復すると 1 文字ずつの照合になる）。
        if isinstance(aliases, str):
            aliases = [aliases]
        if not isinstance(aliases, list):
            aliases = []
        names = [title] + [a for a in aliases if isinstance(a, str)]
        same: dict[str, tuple[str, str]] = {}
        other: dict[str, str] = {}
        for name in names:
            for page_type, path, kind, written in index.get(normalize_name(name), []) if name.strip() else []:
                if page_type == wanted:
                    same.setdefault(path, (kind, written))
                else:
                    other.setdefault(path, page_type)
        label = json.dumps(title, ensure_ascii=False)
        if len(same) == 1:
            path, (kind, written) = next(iter(same.items()))
            lines.append(f"SAME: {n} {label} -> {path} (matched {kind} {json.dumps(written, ensure_ascii=False)})")
            counts["same"] += 1
        elif len(same) > 1:
            lines.append(f"AMBIGUOUS: {n} {label} -> {', '.join(sorted(same))} (same type; several pages answer to this name)")
            counts["ambiguous"] += 1
        for path, page_type in sorted(other.items()):
            lines.append(f"OTHER_TYPE: {n} {label} -> {path} (type {page_type}, not {wanted or '?'})")
        if other:
            counts["other_type"] += 1
        if not same and not other:
            lines.append(f"NONE: {n} {label}")
    lines.append(
        f"SUMMARY: entities={len(entities)}, same={counts['same']}, "
        f"ambiguous={counts['ambiguous']}, other_type={counts['other_type']}"
    )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match extracted entity names against existing pages' titles and aliases."
    )
    parser.add_argument("--lang", help="Language directory to read (default: primary_lang).")
    args = parser.parse_args()
    try:
        entities = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"ERROR: stdin is not JSON: {exc}")
        return 2
    if not isinstance(entities, list):
        print("ERROR: stdin must be a JSON list of entities")
        return 2
    lang = args.lang or load_primary_lang()
    for line in match(entities, build_index(lang)):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
