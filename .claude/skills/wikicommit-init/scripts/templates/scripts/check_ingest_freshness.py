#!/usr/bin/env python3
"""Detect ingest management files whose source has changed (hash mismatch).

For each management file with source.type=path and status in {generated, partial,
outdated}, computes the SHA-256 of the source file and compares it with source.hash.
If they differ, updates the management file's status to 'outdated'.

Usage:
    python .wikicommit/scripts/check_ingest_freshness.py [<ingest-file>...]

Exit code: always 0 (warning-only, non-blocking).

Side effect: writes 'status: outdated' back to management files (status: generated or
partial) when a hash mismatch is detected.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_text

SOURCE_DIR = Path(".wikicommit/source")

# Only used to locate the frontmatter block for the status: rewrite below —
# out of scope for the _frontmatter.py consolidation (Issue #231), which
# covers read-side parsing only; this write-side logic is a separate concern.
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)

CHECKABLE_STATUSES = {"generated", "partial", "outdated"}


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, raw_content) for a management file."""
    content = path.read_text(encoding="utf-8-sig")
    fm, err = parse_frontmatter_text(content)
    if err:
        print(f"WARNING: {path}: {err} — cannot check freshness", file=sys.stderr)
        print(f"WARNING: {path}: {err} — cannot check freshness")
        return {}, content
    return fm, content


def _write_status(path: Path, content: str, new_status: str) -> None:
    """Update only the status field in the frontmatter, preserving all other formatting."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return
    yaml_block = m.group(1)
    status_re = re.compile(r"^(status:\s*).*$", re.MULTILINE)
    if status_re.search(yaml_block):
        updated = status_re.sub(rf"\g<1>{new_status}", yaml_block)
    else:
        updated = yaml_block + f"\nstatus: {new_status}"
    path.write_text(content[:m.start(1)] + updated + content[m.end(1):], encoding="utf-8")


def _sha256_of_file(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_ingest_files(args: list[str]) -> list[Path]:
    if args:
        return [Path(p) for p in args]
    if not SOURCE_DIR.exists():
        return []
    return sorted(SOURCE_DIR.rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect outdated ingest sources.")
    parser.add_argument("ingest_files", nargs="*", metavar="<ingest-file>")
    parsed = parser.parse_args()

    targets = collect_ingest_files(parsed.ingest_files)

    outdated_count = 0
    ok_count = 0

    for mgmt_file in targets:
        fm, content = _parse_frontmatter(mgmt_file)

        source = fm.get("source") or {}
        if source.get("type") != "path":
            continue

        status = fm.get("status")
        if status not in CHECKABLE_STATUSES:
            continue

        source_path_raw = source.get("path")
        if not source_path_raw:
            print(f"WARNING: {mgmt_file}: source.path is missing", file=sys.stderr)
            continue

        # Normalize Windows-style backslashes for cross-platform compatibility
        source_path = Path(str(source_path_raw).replace("\\", "/"))
        if not source_path.exists():
            print(
                f"WARNING: {mgmt_file}: source file not found: {source_path}",
                file=sys.stderr,
            )
            continue

        raw_hash = source.get("hash")
        if not raw_hash:
            print(f"WARNING: {mgmt_file}: source.hash is missing — skipping", file=sys.stderr)
            continue
        expected_hex = str(raw_hash).removeprefix("sha256:")
        actual_hex = _sha256_of_file(source_path)

        if actual_hex != expected_hex:
            print(f"OUTDATED: {mgmt_file} (source: {source_path_raw})")
            print(f"page: {mgmt_file}")
            if status != "outdated":
                _write_status(mgmt_file, content, "outdated")
            outdated_count += 1
        else:
            ok_count += 1

    print(f"SUMMARY: outdated={outdated_count}, ok={ok_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
