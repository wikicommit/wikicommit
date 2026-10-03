"""Group files: how the pages under one Type are shown in groups (Issue #1035).

A large Type (DefinedTerm passes 40 pages in the pilots) is one long list in its
`index.md` and in the Explorer. This module reads `.wikicommit/groups/<Type>.yml`,
which sorts that Type's pages into named groups **without touching any page**:

    groups:
      practice:
        label: {ja: 実践・手法, en: Practices}
        criterion: "Something the reader does"
        pages: [vibe-coding, spec-driven-development]
    unclassified_label: {ja: 未分類}     # optional

Why outside the page: grouping is how pages are *listed*, not what they *say*.
Writing it into a page's frontmatter (`tags` or a new key) would make every
grouping a content change, and `reset_review_on_content_change.py` (Issue #724)
would send every `reviewed` page it touched back to `pending` — 40 tracking
Issues for one reorganisation, and again for every regrouping.

Membership is by slug. A slug is language-neutral (Issue #193), so one file
covers every language: a translation lands in the same group as its original.
Only the label is per language (the same shape as `site_description`, Issue #671);
a language with no label shows the group key.

Three readers: `rebuild_index.py` (headings in the Type index),
`convert_wikilinks.py` (publishes the membership for the Explorer), and
`check_groups.py` (`/wikicommit-status` and `/wikicommit-organize`). A missing
file means "no groups" and every reader behaves exactly as before; an invalid
file is reported and treated as missing, so a typo never breaks a build.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

GROUPS_DIR = Path(".wikicommit/groups")

# The key is published as part of the Explorer's virtual folder and as a heading
# anchor, so it is held to the same shape as a slug. Lowercase only: Quartz
# lowercases what it publishes, and two keys differing only in case would merge.
GROUP_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

GROUP_FIELDS = ("label", "criterion", "pages")
TOP_LEVEL_FIELDS = ("groups", "unclassified_label")

# The heading for pages no group claims, when the file does not supply one for
# the index's language. The file can override per language (unclassified_label).
UNCLASSIFIED_LABELS = {"ja": "未分類", "en": "Unclassified"}


@dataclass
class Group:
    key: str
    label: dict[str, str]
    criterion: str
    pages: list[str]

    def label_for(self, lang: str) -> str:
        return self.label.get(lang) or self.key


@dataclass
class GroupFile:
    type_name: str
    path: Path
    groups: list[Group] = field(default_factory=list)
    unclassified_label: dict[str, str] = field(default_factory=dict)

    def group_of(self) -> dict[str, str]:
        """slug -> group key."""
        return {slug: g.key for g in self.groups for slug in g.pages}

    def unclassified_label_for(self, lang: str) -> str:
        return (
            self.unclassified_label.get(lang)
            or UNCLASSIFIED_LABELS.get(lang)
            or UNCLASSIFIED_LABELS["en"]
        )


def group_file_path(type_name: str, groups_dir: Path = GROUPS_DIR) -> Path:
    """`.wikicommit/groups/<Type>.yml`; a custom type keeps its `custom/` segment,
    exactly as `.wikicommit/schema/` does (the path is derived, never searched)."""
    return groups_dir / f"{type_name}.yml"


def discover_group_files(groups_dir: Path = GROUPS_DIR) -> list[tuple[str, Path]]:
    """Every `(type_name, path)` under the groups directory, sorted."""
    if not groups_dir.is_dir():
        return []
    found = []
    for path in sorted(groups_dir.rglob("*.yml")):
        type_name = path.relative_to(groups_dir).with_suffix("").as_posix()
        found.append((type_name, path))
    return found


def _label_map(value, where: str, errors: list[str]) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict) and any(isinstance(k, bool) for k in value):
        # YAML 1.1 reads a bare `no` (Norwegian) — and `yes`/`on`/`off` — as a
        # boolean, so the language code never arrives as a string. Say so,
        # rather than the generic message that does not name the cause.
        errors.append(
            f"{where} has a language code YAML read as true/false — quote it (e.g. \"no\": ...)"
        )
        return {}
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in value.items()
    ):
        errors.append(f"{where} must map language codes to non-empty strings")
        return {}
    return {k: " ".join(v.split()) for k, v in value.items()}


def parse_group_file(type_name: str, path: Path) -> tuple[GroupFile | None, list[str]]:
    """Parse and validate one group file. Returns (file, errors); `file` is None
    whenever `errors` is non-empty, so a reader can never act on half a file."""
    errors: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as e:
        return None, [f"could not be read as YAML: {e}"]
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, ["the file must be a mapping with a `groups:` key"]
    for key in data:
        if key not in TOP_LEVEL_FIELDS:
            errors.append(f"unknown top-level key `{key}` (expected one of: {', '.join(TOP_LEVEL_FIELDS)})")
    raw_groups = data.get("groups") or {}
    if not isinstance(raw_groups, dict):
        return None, errors + ["`groups:` must be a mapping of group key -> group"]

    result = GroupFile(type_name=type_name, path=path)
    result.unclassified_label = _label_map(data.get("unclassified_label"), "`unclassified_label`", errors)
    owner: dict[str, str] = {}
    for key, raw in raw_groups.items():
        key = str(key)
        if not GROUP_KEY_RE.match(key):
            errors.append(f"group key `{key}` must be lowercase letters, digits and hyphens")
        if not isinstance(raw, dict):
            errors.append(f"group `{key}` must be a mapping with label / criterion / pages")
            continue
        for sub in raw:
            if sub not in GROUP_FIELDS:
                errors.append(f"group `{key}` has unknown key `{sub}` (expected one of: {', '.join(GROUP_FIELDS)})")
        label = _label_map(raw.get("label"), f"group `{key}`'s label", errors)
        criterion = raw.get("criterion") or ""
        if not isinstance(criterion, str):
            errors.append(f"group `{key}`'s criterion must be a string")
            criterion = ""
        pages = raw.get("pages") or []
        if not isinstance(pages, list) or not all(isinstance(p, str) and p for p in pages):
            errors.append(f"group `{key}`'s pages must be a list of slugs")
            pages = []
        for slug in pages:
            # One page, one group: a page in two groups would show twice in the
            # Explorer and twice in the index.
            if slug in owner:
                errors.append(
                    f"page `{slug}` is in both `{owner[slug]}` and `{key}` — a page belongs to one group"
                )
            else:
                owner[slug] = key
        result.groups.append(Group(key=key, label=label, criterion=" ".join(criterion.split()), pages=list(pages)))
    if errors:
        return None, errors
    return result, []


def load_group_file(type_name: str, groups_dir: Path = GROUPS_DIR) -> tuple[GroupFile | None, list[str]]:
    """The group file for `type_name`, or (None, []) when there is none."""
    path = group_file_path(type_name, groups_dir)
    if not path.is_file():
        return None, []
    return parse_group_file(type_name, path)
