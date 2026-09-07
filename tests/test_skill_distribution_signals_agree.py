"""Skill の配布可否を判定する 3 つのシグナルが互いに整合することを検証する (Issue #660)。

`.claude/skills/` には配布対象の Skill と、WikiCommit 本体の開発専用で配布しない
内部 Skill（`implement-issue` / `review-and-merge`）が同居している。Claude Code が
Skill の配置場所を `.claude/skills/<name>/` に固定するため、この 2 種類を物理的に
別ディレクトリへ分けることはできない。

代わりに、区別は 3 通りの方法で機械的に付く:

1. ディレクトリ名の接頭辞 — 配布対象は全件 `wikicommit-` で始まり、内部 Skill は持たない
2. SKILL.md の `metadata.internal: true` — 内部 Skill のみが持つ
   （`npx skills add` の一括インストールから除外するための仕組み。Issue #132）
3. `install.sh` の `SKILLS=(...)` 配列 — 配布対象のみを列挙する

このテストは 3 者が食い違わないことを両方向で固定する。これにより
「公開スナップショットの対象は `.claude/skills/wikicommit-*/` である」という
glob 1 行の規則が成り立ち続ける（Issue #660。公開可否をディレクトリ単位で
判断できる形への整理）。内部 Skill を `wikicommit-` 接頭辞で追加する・
配布 Skill に `internal: true` を付けるといった取り違えは、その場で落ちる。

`tests/test_skill_distribution_list_sync.py`（`SKILLS` 配列と `plugin.json` の
同期）の対にあたる。あちらが 2 つの配布経路の**間**の一致を見るのに対し、
こちらは配布対象の**集合そのもの**を 3 つの独立したシグナルから突き合わせる。
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
INSTALL_SH = REPO_ROOT / "install.sh"

sys.path.insert(0, str(REPO_ROOT / ".wikicommit" / "scripts"))
from _frontmatter import parse_frontmatter  # noqa: E402

DISTRIBUTED_PREFIX = "wikicommit-"
SKILLS_ARRAY_RE = re.compile(r"^SKILLS=\((.*)\)$", re.MULTILINE)


def _skill_dirs() -> list[Path]:
    return sorted(d for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file())


def _install_sh_skills() -> set[str]:
    match = SKILLS_ARRAY_RE.search(INSTALL_SH.read_text(encoding="utf-8"))
    assert match, (
        f"{INSTALL_SH} に `SKILLS=(...)` 配列が見つかりません。"
        " install.sh の配列定義が変更された場合は本テストの SKILLS_ARRAY_RE も"
        " 更新してください。"
    )
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _is_internal(skill_dir: Path) -> bool:
    frontmatter, error = parse_frontmatter(skill_dir / "SKILL.md")
    assert not error, f"{skill_dir.name}/SKILL.md の frontmatter を読めません: {error}"
    assert frontmatter is not None, f"{skill_dir.name}/SKILL.md に frontmatter がありません"
    metadata = frontmatter.get("metadata") or {}
    assert isinstance(metadata, dict), (
        f"{skill_dir.name}/SKILL.md の metadata がマッピングではありません: {metadata!r}"
    )
    return metadata.get("internal") is True


def test_skill_dirs_are_discovered():
    """走査自体が空振りしていないことを確かめる（他のテストの前提）。"""
    assert _skill_dirs(), f"{SKILLS_DIR} に SKILL.md を持つディレクトリがありません"


def test_prefixed_skills_are_distributed_and_not_internal():
    """`wikicommit-` 接頭辞を持つ Skill は配布対象である。"""
    install_sh_skills = _install_sh_skills()
    for skill_dir in _skill_dirs():
        if not skill_dir.name.startswith(DISTRIBUTED_PREFIX):
            continue
        assert not _is_internal(skill_dir), (
            f"{skill_dir.name} は `{DISTRIBUTED_PREFIX}` 接頭辞を持つ配布対象ですが"
            " SKILL.md に metadata.internal: true があります。"
            " 内部 Skill であれば接頭辞を外してください（Issue #660）。"
        )
        assert skill_dir.name in install_sh_skills, (
            f"{skill_dir.name} は `{DISTRIBUTED_PREFIX}` 接頭辞を持ちますが"
            " install.sh の SKILLS 配列に含まれていません（Issue #660）。"
        )


def test_unprefixed_skills_are_internal_and_not_distributed():
    """接頭辞を持たない Skill は内部専用であり、配布されない。"""
    install_sh_skills = _install_sh_skills()
    for skill_dir in _skill_dirs():
        if skill_dir.name.startswith(DISTRIBUTED_PREFIX):
            continue
        assert _is_internal(skill_dir), (
            f"{skill_dir.name} は `{DISTRIBUTED_PREFIX}` 接頭辞を持たないため"
            " 内部 Skill とみなされますが、SKILL.md に metadata.internal: true が"
            " ありません。配布対象であれば接頭辞を付けてください（Issue #660）。"
        )
        assert skill_dir.name not in install_sh_skills, (
            f"{skill_dir.name} は内部 Skill ですが install.sh の SKILLS 配列に"
            " 含まれています（Issue #660）。"
        )


def test_install_sh_skills_all_exist_and_are_prefixed():
    """SKILLS 配列側から見た逆方向 — 存在しない Skill を配っていないこと。"""
    skill_names = {d.name for d in _skill_dirs()}
    for name in sorted(_install_sh_skills()):
        assert name in skill_names, (
            f"install.sh の SKILLS 配列が存在しない Skill を指しています: {name}"
        )
        assert name.startswith(DISTRIBUTED_PREFIX), (
            f"install.sh の SKILLS 配列に `{DISTRIBUTED_PREFIX}` 接頭辞を持たない"
            f" Skill があります: {name}（Issue #660）"
        )
