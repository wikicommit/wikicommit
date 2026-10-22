"""`deploy.yml` の共有カード画像の差し替え段を実際に走らせて検証する（Issue #1371）。

この段は GitHub Pages への deploy でしか走らず、壊れても公開サイトのカード画像が
Quartz のロゴに戻るだけで誰も気づかない。段の `run:` を取り出して一時ディレクトリで
実行し、(1) PNG があれば `quartz/public/static/og-image.png` を置き換える、
(2) 無ければ何もしない、(3) PNG でない（Git LFS のポインタ等）なら置き換えない、
の 3 つを固定する。あわせて、段が「Build Quartz site」の後・アップロードの前に
あることを固定する（前に置くと Quartz の Static emitter が上書きし直す）。
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

DEPLOY_YML = (
    Path(__file__).parent.parent
    / ".claude"
    / "skills"
    / "wikicommit-init"
    / "scripts"
    / "templates"
    / "workflows"
    / "deploy.yml"
)
STEP_NAME = "Use the wiki's social-card image"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
QUARTZ_LOGO = PNG_SIGNATURE + b"quartz-logo"


def _steps() -> list[dict]:
    return yaml.safe_load(DEPLOY_YML.read_text(encoding="utf-8"))["jobs"]["build"]["steps"]


def _index(steps: list[dict], name: str) -> int:
    return next(i for i, step in enumerate(steps) if step.get("name") == name)


def test_step_runs_after_build_and_before_upload():
    steps = _steps()
    og = _index(steps, STEP_NAME)
    assert _index(steps, "Build Quartz site") < og < _index(steps, "Upload artifact")


def _run(tmp_path: Path) -> subprocess.CompletedProcess:
    if shutil.which("bash") is None:
        pytest.skip("bash is not available")
    static = tmp_path / "quartz" / "public" / "static"
    static.mkdir(parents=True)
    (static / "og-image.png").write_bytes(QUARTZ_LOGO)
    script = _steps()[_index(_steps(), STEP_NAME)]["run"]
    return subprocess.run(
        ["bash", "-e", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=True
    )


def _published(tmp_path: Path) -> bytes:
    return (tmp_path / "quartz" / "public" / "static" / "og-image.png").read_bytes()


def test_png_replaces_the_quartz_logo(tmp_path: Path):
    image = PNG_SIGNATURE + b"wiki-card"
    (tmp_path / ".wikicommit" / "assets").mkdir(parents=True)
    (tmp_path / ".wikicommit" / "assets" / "og-image.png").write_bytes(image)
    _run(tmp_path)
    assert _published(tmp_path) == image


def test_no_image_leaves_the_quartz_logo(tmp_path: Path):
    _run(tmp_path)
    assert _published(tmp_path) == QUARTZ_LOGO


def test_lfs_pointer_is_not_published(tmp_path: Path):
    (tmp_path / ".wikicommit" / "assets").mkdir(parents=True)
    (tmp_path / ".wikicommit" / "assets" / "og-image.png").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 12345\n"
    )
    result = _run(tmp_path)
    assert _published(tmp_path) == QUARTZ_LOGO
    assert "::warning" in result.stdout
