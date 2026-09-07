"""Tests for .wikicommit/scripts/check_extraction_quality.py (Issue #425)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_extraction_quality.py"

# A synthetic reproduction of a JS/SPA "content shell": embedded router/hydration
# state and script tags, with no readable prose. Modeled after the general
# failure mode Issue #425 describes (client-rendered pages where a static
# fetch tool returns a non-empty but useless result) rather than a byte-exact
# capture of any one real page, since real captures go stale as sites change.
JS_SHELL_FIXTURE = """window.__reactRouterContext = {"state":{"loaderData":{"root":null},"actionData":null,"errors":null},"future":{"v7_fetcherPersist":true}};
window.__reactRouterRouteModules = {"root":{"clientLoader":undefined,"clientAction":undefined,"hydrateFallback":undefined}};
{"props":{"pageProps":{"initialState":{"user":null,"theme":"dark","locale":"en-US","features":{"flag1":true,"flag2":false}}}},"page":"/status/[id]","query":{"id":"1886192184808149383"},"buildId":"a1b2c3d4e5f6g7h8i9j0"}
<div id="react-root" data-reactroot=""></div><script src="/static/js/main.a1b2c3d4.chunk.js"></script><script src="/static/js/vendor.e5f6g7h8.chunk.js"></script>
"""

# A nav/login-only shell (markdown-converted boilerplate with no article
# content) — the shape markitdown tends to produce for a page whose real
# content never rendered without JS.
NAV_SHELL_FIXTURE = """## Post

[Log in](/i/jf/onboarding/web?mode=login)[Sign up](/i/jf/onboarding/web?mode=signup)

## Post

* [![user avatar](https://example.com/profile_images/1.jpg)](/someuser)

  [Someone](https://x.com/someuser)

  [@someuser](https://x.com/someuser)

  1.5K
  3.6K
  34K
  18K
"""

NORMAL_PROSE_EN = (
    "WikiCommit is a Git-based knowledge management platform. It runs a "
    "CI/CD-style pipeline over knowledge instead of code, generating wiki "
    "pages from source documents with an LLM and publishing them as a "
    "static site after automated and human review."
)

NORMAL_PROSE_JA = (
    "WikiCommitはGitベースの知識管理プラットフォームであり、コードではなく"
    "知識に対してCI/CDスタイルのパイプラインを実行する。ソースドキュメントから"
    "LLMを使ってWikiページを生成し、自動・人間によるレビューを経て静的サイト"
    "として公開する。"
)

# Issue #562: the Japanese half of the equivalence pair. Percent-encoded link
# targets are what made this shape score near zero before — `text.split()` fused
# the running prose into the same token as the URL that followed it, and the URL
# rule then discarded both. Same content and same link density as
# PROSE_WITH_LINKS_EN below, so the two ratios are expected to land close.
PROSE_WITH_LINKS_JA = (
    "さいたま市は、[埼玉県](https://ja.wikipedia.org/wiki/%E5%9F%BC%E7%8E%89%E7%9C%8C)"
    "南東部に位置する市であり、同県の県庁所在地である。"
    "[政令指定都市](https://ja.wikipedia.org/wiki/%E6%94%BF%E4%BB%A4%E6%8C%87%E5%AE%9A%E9%83%BD%E5%B8%82)"
    "に指定されており、[人口](https://ja.wikipedia.org/wiki/%E4%BA%BA%E5%8F%A3)は約133万人である。"
    "2001年に[浦和市](https://ja.wikipedia.org/wiki/%E6%B5%A6%E5%92%8C%E5%B8%82)・"
    "[大宮市](https://ja.wikipedia.org/wiki/%E5%A4%A7%E5%AE%AE%E5%B8%82)・"
    "[与野市](https://ja.wikipedia.org/wiki/%E4%B8%8E%E9%87%8E%E5%B8%82)が合併して発足した。"
)

PROSE_WITH_LINKS_EN = (
    "Saitama is a city in the southeastern part of "
    "[Saitama Prefecture](https://en.wikipedia.org/wiki/Saitama_Prefecture) and is "
    "the capital of that prefecture. It is designated as a "
    "[government ordinance city](https://en.wikipedia.org/wiki/Cities_designated_by_government_ordinance_of_Japan), "
    "and its [population](https://en.wikipedia.org/wiki/Population) is about 1.33 "
    "million. It was founded in 2001 by merging "
    "[Urawa](https://en.wikipedia.org/wiki/Urawa), "
    "[Omiya](https://en.wikipedia.org/wiki/Omiya) and "
    "[Yono](https://en.wikipedia.org/wiki/Yono)."
)

PROSE_WITH_LINKS = (
    "Andrej Karpathy is a researcher known for work on deep learning. See "
    "his [blog](https://karpathy.github.io) and "
    "[Twitter profile](https://x.com/karpathy) for more. He previously "
    "worked at [Tesla](https://www.tesla.com) and [OpenAI](https://openai.com)."
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ── check-domain ─────────────────────────────────────────────────────────

def test_check_domain_blocks_known_js_shell_domain():
    result = run("check-domain", "https://x.com/karpathy/status/1886192184808149383")
    assert result.returncode == 1
    assert "BLOCKED: x.com" in result.stdout


def test_check_domain_blocks_twitter_com():
    result = run("check-domain", "https://twitter.com/someuser/status/123")
    assert result.returncode == 1
    assert "BLOCKED: twitter.com" in result.stdout


def test_check_domain_normalizes_www_prefix():
    result = run("check-domain", "https://www.x.com/someuser/status/123")
    assert result.returncode == 1
    assert "BLOCKED: x.com" in result.stdout


def test_check_domain_allows_unknown_domain():
    result = run("check-domain", "https://example.com/article")
    assert result.returncode == 0
    assert "OK: example.com" in result.stdout


# ── check-density ────────────────────────────────────────────────────────

def test_check_density_flags_js_shell(tmp_path):
    f = tmp_path / "extracted.md"
    f.write_text(JS_SHELL_FIXTURE, encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 1
    assert "LOW_DENSITY:" in result.stdout


def test_check_density_flags_nav_only_shell(tmp_path):
    f = tmp_path / "extracted.md"
    f.write_text(NAV_SHELL_FIXTURE, encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 1
    assert "LOW_DENSITY:" in result.stdout


def test_check_density_allows_normal_english_prose(tmp_path):
    f = tmp_path / "extracted.md"
    f.write_text(NORMAL_PROSE_EN, encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 0
    assert "OK:" in result.stdout


def test_check_density_allows_normal_japanese_prose(tmp_path):
    f = tmp_path / "extracted.md"
    f.write_text(NORMAL_PROSE_JA, encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 0
    assert "OK:" in result.stdout


def test_check_density_allows_prose_with_markdown_links(tmp_path):
    f = tmp_path / "extracted.md"
    f.write_text(PROSE_WITH_LINKS, encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 0
    assert "OK:" in result.stdout


def test_check_density_missing_file_is_error(tmp_path):
    result = run("check-density", str(tmp_path / "does-not-exist.md"))
    assert result.returncode == 1
    assert "ERROR:" in result.stderr


def test_check_density_empty_file_is_low_density(tmp_path):
    f = tmp_path / "extracted.md"
    f.write_text("", encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 1


def test_check_density_reads_stdin_when_file_omitted():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check-density"],
        input=NORMAL_PROSE_EN,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "OK: <stdin>" in result.stdout


def test_check_density_stdin_flags_js_shell():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check-density"],
        input=JS_SHELL_FIXTURE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "LOW_DENSITY: <stdin>" in result.stdout


# ── check-density: CJK / link-density regressions (Issue #562) ────────────

def _ratio_of(stdout: str) -> float:
    """Pull the ratio back out of either the OK: or LOW_DENSITY: line."""
    marker = "natural-language character ratio: "
    tail = stdout.split(marker, 1)[1]
    return float(tail.split(",")[0].split(")")[0].strip())


def test_check_density_allows_japanese_prose_with_percent_encoded_links(tmp_path):
    """(a) Link-dense Japanese prose must clear the threshold.

    Before Issue #562 this scored near zero: whitespace tokenization fused the
    prose with the following URL, and _is_natural_token discarded the whole
    fused token as a URL — taking the prose's characters with it.
    """
    f = tmp_path / "extracted.md"
    f.write_text(PROSE_WITH_LINKS_JA, encoding="utf-8")
    result = run("check-density", str(f))
    assert result.returncode == 0, result.stdout
    assert "OK:" in result.stdout


def test_check_density_scores_equivalent_japanese_and_english_prose_alike(tmp_path):
    """(c) The same content at the same link density should score alike.

    The docstring on _density_report has always claimed CJK isn't penalized;
    this pins that claim to an actual measurement.
    """
    ja = tmp_path / "ja.md"
    ja.write_text(PROSE_WITH_LINKS_JA, encoding="utf-8")
    en = tmp_path / "en.md"
    en.write_text(PROSE_WITH_LINKS_EN, encoding="utf-8")

    ja_ratio = _ratio_of(run("check-density", str(ja)).stdout)
    en_ratio = _ratio_of(run("check-density", str(en)).stdout)
    assert abs(ja_ratio - en_ratio) < 0.15, f"ja={ja_ratio} en={en_ratio}"


def test_check_density_still_flags_shells_after_cjk_fix(tmp_path):
    """(b) The Issue #425 originating cases must keep failing.

    Loosening the measurement to un-penalize CJK must not loosen it for the
    ASCII shells guard A exists to catch — these two fixtures are the reason
    the ratio is measured with URLs still in the denominator rather than
    stripped out entirely (stripping link targets lifts NAV_SHELL_FIXTURE well
    above the threshold, because a nav shell is made almost entirely of links).
    """
    for name, fixture in (("js", JS_SHELL_FIXTURE), ("nav", NAV_SHELL_FIXTURE)):
        f = tmp_path / f"{name}.md"
        f.write_text(fixture, encoding="utf-8")
        result = run("check-density", str(f))
        assert result.returncode == 1, f"{name}: {result.stdout}"
        assert "LOW_DENSITY:" in result.stdout


def test_check_density_reports_non_prose_breakdown(tmp_path):
    """The LOW_DENSITY line carries the breakdown a human needs to override it."""
    f = tmp_path / "extracted.md"
    f.write_text(NAV_SHELL_FIXTURE, encoding="utf-8")
    result = run("check-density", str(f))
    assert "non-prose breakdown: links " in result.stdout
    assert "numbers/tables " in result.stdout
    assert "other markup " in result.stdout


def test_check_density_breakdown_identifies_link_heavy_text(tmp_path):
    """A link-dense page below the threshold is labelled as link-dominated,
    which is how the operator tells it apart from a script/JSON shell."""
    f = tmp_path / "extracted.md"
    # Japanese prose diluted with far more link markup than the fixture above.
    f.write_text(
        PROSE_WITH_LINKS_JA
        + "".join(
            f"[![](//upload.wikimedia.org/wikipedia/commons/thumb/a/a1/"
            f"%E3%81%95%E3%81%84%E3%81%9F%E3%81%BE%E5%B8%82_{i}.jpg/250px-x.jpg)]"
            f"(//upload.wikimedia.org/wikipedia/commons/a/a1/x_{i}.jpg)\n"
            for i in range(40)
        ),
        encoding="utf-8",
    )
    result = run("check-density", str(f))
    assert result.returncode == 1, result.stdout
    links_pct = int(result.stdout.split("links ", 1)[1].split("%", 1)[0])
    assert links_pct >= 50, result.stdout


def test_check_density_numeric_table_text_is_reported_as_such(tmp_path):
    """A statistics table is a known limitation (docs/DesignDoc-ScriptSpec.md):
    it scores low, and the breakdown says why so the operator can override."""
    f = tmp_path / "extracted.md"
    f.write_text(
        "\n".join(
            f"| {i} | {i * 1234:,} | {i * 5678:,} | {i * 91:,} | {i / 7:.3f} |"
            for i in range(1, 60)
        ),
        encoding="utf-8",
    )
    result = run("check-density", str(f))
    assert result.returncode == 1, result.stdout
    numeric_pct = int(result.stdout.split("numbers/tables ", 1)[1].split("%", 1)[0])
    assert numeric_pct >= 50, result.stdout


def test_check_density_allows_japanese_prose_with_bare_urls(tmp_path):
    """A *bare* URL must not swallow the Japanese prose that follows it.

    The Markdown-link case is terminated by `)`, but a bare URL in running
    Japanese text has no whitespace after it, so the URL pattern ran straight
    on into the prose and counted the whole thing as a link target — the same
    fusion _tokenize() was introduced to undo, one layer further in.
    """
    f = tmp_path / "extracted.md"
    f.write_text(
        "出典: https://www.city.saitama.lg.jp/001/index.html（2026年8月28日閲覧）。"
        "さいたま市は埼玉県南東部に位置する市であり、同県の県庁所在地である。"
        "政令指定都市に指定されており、人口は約133万人である。",
        encoding="utf-8",
    )
    result = run("check-density", str(f))
    assert result.returncode == 0, result.stdout
    assert "OK:" in result.stdout


# ── check-fetch-capability (#574) ────────────────────────────────────────

@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://youtube.com/watch?v=jNQXAC9IVRw",
        "https://youtu.be/jNQXAC9IVRw",
        "https://m.youtube.com/watch?v=jNQXAC9IVRw",
    ],
)
def test_check_fetch_capability_recognizes_every_youtube_host(url):
    """markitdown resolves redirects before choosing a converter, so all of
    these reach the transcript-dependent path and every alias must be listed."""
    result = run("check-fetch-capability", url)
    assert "youtube_transcript_api" in result.stdout or "youtube-transcript-api" in result.stdout


def test_music_youtube_is_a_js_shell_domain_not_a_capability_requirement():
    """music.youtube.com never redirects to www.youtube.com/watch, so
    markitdown's YouTubeConverter refuses it and the transcript package is
    irrelevant — it returns a "not optimized for your browser" shell instead,
    which guard A scores as prose. Guard B has to stop it (Issue #574)."""
    blocked = run("check-domain", "https://music.youtube.com/watch?v=jNQXAC9IVRw")
    assert blocked.returncode == 1
    assert "BLOCKED:" in blocked.stdout

    capability = run("check-fetch-capability", "https://music.youtube.com/watch?v=jNQXAC9IVRw")
    assert capability.returncode == 0
    assert "needs no extra extraction package" in capability.stdout


def test_check_fetch_capability_passes_through_unaffected_hosts():
    result = run("check-fetch-capability", "https://example.com/article")
    assert result.returncode == 0
    assert "needs no extra extraction package" in result.stdout


def test_check_fetch_capability_normalizes_www_and_port():
    """`www.` and the port have to be stripped before the host lookup, otherwise
    the requirement is missed entirely and the check reports the unaffected-host
    verdict — so assert on which branch was taken, not just on the host name."""
    result = run("check-fetch-capability", "https://www.youtube.com:443/watch?v=abc")
    assert "youtube.com" in result.stdout
    assert "needs no extra extraction package" not in result.stdout


def test_check_fetch_capability_ok_when_package_installed():
    """The sandbox has youtube-transcript-api installed, so this is the happy path."""
    pytest.importorskip("youtube_transcript_api")
    result = run("check-fetch-capability", "https://www.youtube.com/watch?v=abc")
    assert result.returncode == 0
    assert result.stdout.startswith("OK:")


def test_check_fetch_capability_blocks_when_package_missing(tmp_path):
    """Simulate the package being absent by running the script with a sitecustomize
    that hides it, rather than uninstalling it from the environment."""
    blocker = tmp_path / "sitecustomize.py"
    blocker.write_text(
        "import importlib.util\n"
        "_real = importlib.util.find_spec\n"
        "def find_spec(name, *a, **k):\n"
        "    if name == 'youtube_transcript_api':\n"
        "        return None\n"
        "    return _real(name, *a, **k)\n"
        "importlib.util.find_spec = find_spec\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check-fetch-capability", "https://www.youtube.com/watch?v=abc"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "MISSING_PACKAGE:" in result.stdout
    assert "pip install youtube-transcript-api" in result.stdout


def test_check_fetch_capability_is_independent_of_the_other_two_guards():
    """A YouTube URL is not a known JS-shell domain, and a transcript-less
    extraction is not low-density — this is why #574 needed a third check."""
    assert run("check-domain", "https://www.youtube.com/watch?v=abc").returncode == 0

    metadata_only = (
        "# YouTube\n\n"
        "## Me at the zoo\n\n"
        "### Video Metadata\n\n"
        "**Description:** The first video uploaded to YouTube, recorded at the San Diego Zoo. "
        "It shows one of the site's founders standing in front of the elephant enclosure and "
        "remarking on how long their trunks are. The clip runs for less than twenty seconds "
        "and has since become widely referenced as a landmark in the history of online video.\n\n"
        "**Keywords:** zoo, elephants, first video, history\n\n"
        "**Runtime:** 00:00:19\n"
    )
    density = subprocess.run(
        [sys.executable, str(SCRIPT), "check-density"],
        input=metadata_only,
        capture_output=True,
        text=True,
        check=False,
    )
    assert density.returncode == 0, density.stdout


# ── source-policy.md exclude_domains (Issue #564) ────────────────────────────

def run_in(*args: str, cwd) -> subprocess.CompletedProcess:
    """`run()` with a working directory — the policy file is resolved from cwd."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd, check=False,
    )


def _write_policy(root, body: str):
    path = root / ".wikicommit" / "source-policy.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_policy_exclude_domain_blocks(tmp_path):
    _write_policy(tmp_path, "---\nwikicommit:\n  exclude_domains: [example.com]\n---\n\nprose\n")
    result = run_in("check-domain", "https://www.example.com/a", cwd=tmp_path)
    assert result.returncode == 1
    assert "BLOCKED: example.com is listed under wikicommit.exclude_domains" in result.stdout


def test_policy_cannot_re_enable_a_builtin_domain(tmp_path):
    """The built-in list is a fact about fetchability, not a preference to override."""
    _write_policy(tmp_path, "---\nwikicommit:\n  exclude_domains: []\n---\n\nprose\n")
    result = run_in("check-domain", "https://x.com/a", cwd=tmp_path)
    assert result.returncode == 1
    assert "known JS-rendering-required domain" in result.stdout


def test_missing_policy_file_changes_nothing(tmp_path):
    result = run_in("check-domain", "https://example.com/a", cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: example.com is not a known JS-shell domain" in result.stdout


def test_malformed_policy_file_does_not_break_the_guard(tmp_path):
    """A source-selection policy must never take the pre-fetch guard down with it."""
    for body in (
        "no frontmatter at all\n",
        "---\nwikicommit: not-a-mapping\n---\n",
        "---\nwikicommit:\n  exclude_domains: example.com\n---\n",
        "---\n  : [\n---\n",
    ):
        _write_policy(tmp_path, body)
        result = run_in("check-domain", "https://example.com/a", cwd=tmp_path)
        assert result.returncode == 0, body
        result = run_in("check-domain", "https://x.com/a", cwd=tmp_path)
        assert result.returncode == 1, body


def test_policy_domains_are_normalized(tmp_path):
    _write_policy(tmp_path, "---\nwikicommit:\n  exclude_domains: [\"  Example.COM \", \"\", 42]\n---\n")
    result = run_in("check-domain", "https://example.com/a", cwd=tmp_path)
    assert result.returncode == 1


def test_policy_entries_may_carry_a_scheme_or_www(tmp_path):
    """An entry written the way `rejected:` writes URLs must still match.

    _domain_of() strips scheme/port/www from the *candidate*, so an unnormalized
    "https://example.com/" or "www.example.com" entry could never match anything —
    the file would say the domain is excluded while it kept being fetched.
    """
    _write_policy(
        tmp_path,
        '---\nwikicommit:\n  exclude_domains: ["https://Example.com/x", "www.foo.org", "bar.net/path"]\n---\n',
    )
    for url in ("https://www.example.com/a", "https://foo.org/b", "https://bar.net:8443/c"):
        result = run_in("check-domain", url, cwd=tmp_path)
        assert result.returncode == 1, url
        assert "wikicommit.exclude_domains" in result.stdout, url

    unrelated = run_in("check-domain", "https://other.example.org/a", cwd=tmp_path)
    assert unrelated.returncode == 0, unrelated.stdout


def test_unparseable_policy_warns_on_stderr_but_keeps_stdout_contract(tmp_path):
    """Failing open is right; failing open *silently* is not.

    wikicommit-collect appends to this file's `rejected:` list, so one malformed
    append would switch every exclude_domains entry off with nothing to show for
    it. The warning goes to stderr so the BLOCKED:/OK: stdout contract that
    callers parse is untouched.
    """
    _write_policy(tmp_path, "---\n  : [\n---\n")
    result = run_in("check-domain", "https://example.com/a", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "OK: example.com is not a known JS-shell domain"
    assert "WARNING:" in result.stderr and "exclude_domains" in result.stderr


def test_missing_policy_file_does_not_warn(tmp_path):
    result = run_in("check-domain", "https://example.com/a", cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING:" not in result.stderr
