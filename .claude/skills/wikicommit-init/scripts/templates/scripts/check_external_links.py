#!/usr/bin/env python3
"""check_external_links.py — 全ページの外部リンク切れを lychee で調べる（Issue #1182）。

`/wikicommit-merge` の lychee はそのバッチで変わったページだけを見る（Issue #1196）。
書かれた後で切れたリンク（既存ページ）はこのスクリプトが見つけ、`/wikicommit-status`
が報告する。

1 回の呼び出しはシェルの時間制限（Claude Code の Bash は既定 120 秒）の内側で返る。
数ページずつ lychee を `--cache` 付きで呼び、新しいバッチは `--budget` 秒までしか始めず、
lychee は呼び出し開始から `--limit` 秒で打ち切る。続きは
`.wikicommit/.cache/lychee/all-pages-progress.json` に残るので、呼び出し側は
`CONTINUE:` が出なくなるまで同じコマンドを呼び直す。完走した結果は
`all-pages-result.json` に残り、`--last` がネットワークに触れずに読み直す。

バッチを回す部分（`check_link_batches()`）は `wikicommit-merge` の
`workflow_checks.py links` と共有する。所見は `{"kind": "broken"|"not_checked",
"pages": [...], "text": "..."}` の形で持ち、リンク切れか調べられなかったかは `kind`
で、消えたページの所見を落とすかは `pages` で決める（文言の書き出しには頼らない。
Issue #1243）。

Usage:
    python .wikicommit/scripts/check_external_links.py [--restart]
        [--batch N] [--budget SEC] [--limit SEC]
    python .wikicommit/scripts/check_external_links.py --last

Output (stdout):
    CONTINUE: <checked>/<total> page(s) checked     — 未完了。同じコマンドをもう一度呼ぶ
    BROKEN_LINK: <page>: <url> (<status>)           — 完走時（--last も同じ）
    NOT_CHECKED: <reason>                           — lychee が無い・時間切れ・起動失敗
    IN_PROGRESS: <checked>/<total> page(s) checked  — --last のみ。途中の実行がある
    SUMMARY: checked_at=<ISO 8601|never> pages=<N> broken_links=<N> not_checked=<N>

Exit code: always 0 (warning-only, non-blocking). 2 = usage error.
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CACHE_DIR = Path(".wikicommit/.cache")
LYCHEE_DIR = CACHE_DIR / "lychee"
PROGRESS_FILE = LYCHEE_DIR / "all-pages-progress.json"
RESULT_FILE = LYCHEE_DIR / "all-pages-result.json"
BROKEN = "broken"
NOT_CHECKED = "not_checked"


def finding(kind: str, pages: list[str], text: str) -> dict:
    """One finding: a broken link (`kind` BROKEN) or links that could not be checked
    (`kind` NOT_CHECKED). `pages` are the pages it is about; a finding whose pages
    are all gone is dropped. `pages` is empty only when it is about no page in
    particular, and such a finding is never dropped that way."""
    return {"kind": kind, "pages": list(pages), "text": text}


def parse_findings(values) -> list[dict] | None:
    """`values` as findings, or None when any entry is not one.

    Files written before the findings had a structure hold plain strings (Issue
    #1243). A progress file holding them is discarded, so the check starts over;
    a result file holding them is read by `read_legacy_findings()`."""
    if not isinstance(values, list):
        return None
    out: list[dict] = []
    for v in values:
        if not (isinstance(v, dict) and v.get("kind") in (BROKEN, NOT_CHECKED)
                and isinstance(v.get("text"), str) and isinstance(v.get("pages"), list)
                and all(isinstance(p, str) for p in v["pages"])):
            return None
        out.append(finding(v["kind"], v["pages"], v["text"]))
    return out


def read_legacy_findings(values: list) -> list[dict]:
    """A result file written before Issue #1243: plain strings, where every line
    that could not be checked began with `lychee ` and every broken link with its
    page. That set of lines is closed — no new file is written this way — so the
    prefix reads them exactly. The pages are not recovered: the result is only
    printed, never pruned. An entry that is a finding is kept as one, and one that
    is neither a string nor a finding is skipped rather than printed as its repr."""
    out: list[dict] = []
    for v in values:
        if isinstance(v, str):
            out.append(finding(NOT_CHECKED if v.startswith("lychee ") else BROKEN, [], v))
        else:
            parsed = parse_findings([v])
            if parsed:
                out.extend(parsed)
    return out


def lychee_findings(result: subprocess.CompletedProcess, batch: list[str]) -> list[dict]:
    """One finding per failed link (text `<page>: <url> (<status>)`) from lychee's
    JSON, or one NOT_CHECKED finding for the batch when there is no JSON."""
    try:
        data = json.loads(result.stdout)
    except ValueError:
        if result.returncode == 0:
            return []
        lines = [line for line in (result.stdout + "\n" + result.stderr).splitlines()
                 if line.strip()]
        first = lines[0].strip() if lines else f"exit {result.returncode}"
        return [finding(NOT_CHECKED, batch,
                        f"lychee could not check {', '.join(batch)}: {first}")]
    out: list[dict] = []
    # `fail_map` in older lychee, `error_map` in newer; read both, once each.
    for key in ("fail_map", "error_map"):
        mapping = data.get(key) if isinstance(data, dict) else None
        if not isinstance(mapping, dict):
            continue
        for source, entries in mapping.items():
            try:
                page = os.path.relpath(str(source))
            except ValueError:
                page = str(source)
            for entry in entries if isinstance(entries, list) else []:
                url = entry.get("url", "?") if isinstance(entry, dict) else str(entry)
                status = entry.get("status") if isinstance(entry, dict) else None
                if isinstance(status, dict):
                    status = status.get("text") or status.get("code")
                page = Path(page).as_posix()
                f = finding(BROKEN, [page], f"{page}: {url} ({status or 'failed'})")
                if f not in out:
                    out.append(f)
    return out


def check_link_batches(pages: list[str], progress_file: Path, *, batch: int,
                       budget: float, limit: float, what: str = "pages",
                       started: float | None = None) -> tuple[list[str], list[dict], list[str]]:
    """Check `pages` a few per lychee call, continuing from `progress_file`.

    Returns `(checked, findings, remaining)`. Starts no new batch after `budget`
    seconds and stops lychee `limit` seconds after the call began, but always runs
    at least one batch, so every call makes progress. lychee runs inside
    `.wikicommit/.cache/lychee/`, so its `.lycheecache` lands there (ignored by
    Git) and is shared by every caller. `what` names the pages in the message
    written when lychee is not installed. `started` is the `time.monotonic()` the
    caller's own clock began at (default: now), so work done before this call,
    such as collecting the pages, counts against `budget` and `limit` too.

    The findings are `finding()` dicts. A finding whose pages are none of `pages`
    any more (deleted or removed between calls) is dropped, as the page's checked
    mark is; one naming several pages stays while any of them is still wanted. A
    progress file whose findings are not all such dicts (one written before Issue
    #1243) is discarded and the check starts over.
    """
    try:
        progress = json.loads(progress_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        progress = {}
    if not isinstance(progress, dict):
        progress = {}
    stored = parse_findings(progress.get("findings", []))
    stored_checked = progress.get("checked", [])
    if stored is None or not (isinstance(stored_checked, list)
                              and all(isinstance(p, str) for p in stored_checked)):
        progress = {k: v for k, v in progress.items() if k not in ("checked", "findings")}
        stored = []
    wanted = set(pages)
    checked = [p for p in progress.get("checked", []) if p in wanted]
    done = set(checked)
    findings = [f for f in stored if not f["pages"] or any(p in wanted for p in f["pages"])]
    seen = {(f["kind"], f["text"]) for f in findings}
    remaining = [p for p in pages if p not in done]

    def save() -> None:
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        data = dict(progress)
        data.update({"checked": checked, "findings": findings})
        progress_file.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                 encoding="utf-8")

    lychee = shutil.which("lychee")
    if remaining and lychee is None:
        findings.append(finding(NOT_CHECKED, remaining,
                                f"lychee is not installed; the external links of the {what} "
                                "were not checked"))
        checked.extend(remaining)
        remaining = []
    workdir = LYCHEE_DIR.resolve()
    config = Path(".lychee.toml").resolve()
    # lychee reads `.lycheeignore` from its working directory, which is not the
    # repository root here: carry the repository's copy (or its absence) over.
    ignore = Path(".lycheeignore")
    if remaining and lychee is not None:
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            if ignore.is_file():
                shutil.copyfile(ignore, workdir / ".lycheeignore")
            else:
                (workdir / ".lycheeignore").unlink(missing_ok=True)
        except OSError:
            pass
    if started is None:
        started = time.monotonic()
    first = True
    while remaining and (first or time.monotonic() - started < budget):
        first = False
        group = remaining[:max(1, batch)]
        timeout = max(10.0, limit - (time.monotonic() - started))
        argv = [lychee, "--cache", "--no-progress", "--format", "json"]
        if config.is_file():
            argv += ["--config", str(config)]
        argv += [str(Path(p).resolve()) for p in group]
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            # lychee's JSON is UTF-8 and carries URLs and paths that need not be ASCII.
            result = subprocess.run(argv, cwd=workdir, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace",
                                    check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            findings.append(finding(NOT_CHECKED, group,
                                    f"lychee did not finish within {int(timeout)} s on "
                                    f"{', '.join(group)}; their links were not checked"))
        except OSError as e:
            findings.append(finding(NOT_CHECKED, group,
                                    f"lychee could not run on {', '.join(group)}: {e}"))
        else:
            for f in lychee_findings(result, group):
                if (f["kind"], f["text"]) not in seen:
                    seen.add((f["kind"], f["text"]))
                    findings.append(f)
        checked.extend(group)
        remaining = remaining[len(group):]
        save()
    save()
    return checked, findings, remaining


def all_pages() -> list[str]:
    """Every published page of both trees, minus `index.md` and removed pages."""
    from _wikilink import ENTITY_DIR, VIEW_DIR, collect_entity_pages, collect_view_pages, is_removed

    pages = collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)
    return [p.as_posix() for p in pages if not is_removed(p)]


def print_result(result: dict) -> None:
    values = result.get("findings", [])
    findings = parse_findings(values)
    if findings is None:
        findings = read_legacy_findings(values if isinstance(values, list) else [])
    broken = [f["text"] for f in findings if f["kind"] == BROKEN]
    not_checked = [f["text"] for f in findings if f["kind"] == NOT_CHECKED]
    for line in broken:
        print(f"BROKEN_LINK: {line}")
    for line in not_checked:
        print(f"NOT_CHECKED: {line}")
    print(f"SUMMARY: checked_at={result.get('checked_at') or 'never'} "
          f"pages={result.get('pages', 0)} broken_links={len(broken)} "
          f"not_checked={len(not_checked)}")


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def cmd_last() -> int:
    progress = read_json(PROGRESS_FILE)
    if progress is not None:
        total = progress.get("total")
        # A progress file the next call discards (findings not structured, Issue
        # #1243) continues nothing, so it reports no page as checked.
        checked = progress.get("checked", [])
        done = (len(checked) if isinstance(checked, list)
                and parse_findings(progress.get("findings", [])) is not None else 0)
        print(f"IN_PROGRESS: {done}/{total if total is not None else '?'} "
              "page(s) checked")
    print_result(read_json(RESULT_FILE) or {})
    return 0


def cmd_check(args) -> int:
    started = time.monotonic()
    if args.restart:
        PROGRESS_FILE.unlink(missing_ok=True)
    pages = all_pages()
    # `total` is what `--last` shows in `IN_PROGRESS:`; refresh it on every call, so
    # it follows pages added or removed since the check began.
    progress = read_json(PROGRESS_FILE) or {"checked": [], "findings": []}
    progress["total"] = len(pages)
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    checked, findings, remaining = check_link_batches(
        pages, PROGRESS_FILE, batch=args.batch, budget=args.budget, limit=args.limit,
        started=started)
    if remaining:
        print(f"CONTINUE: {len(checked)}/{len(pages)} page(s) checked")
        return 0
    result = {
        "checked_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "pages": len(pages),
        "findings": findings,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    PROGRESS_FILE.unlink(missing_ok=True)
    print_result(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check every page's external links with lychee, a few pages per call.")
    parser.add_argument("--last", action="store_true",
                        help="Print the last completed check without touching the network.")
    parser.add_argument("--restart", action="store_true",
                        help="Discard an unfinished check and start over.")
    parser.add_argument("--batch", type=int, default=5, help="Pages per lychee call.")
    parser.add_argument("--budget", type=float, default=45.0,
                        help="Seconds after which no new batch starts.")
    parser.add_argument("--limit", type=float, default=100.0,
                        help="Seconds after which a running lychee is stopped.")
    args = parser.parse_args()
    if args.last and args.restart:
        parser.error("--last and --restart cannot be combined")
    return cmd_last() if args.last else cmd_check(args)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
