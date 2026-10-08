#!/usr/bin/env python3
"""Estimate, per step, how much instruction text each Skill workflow hands the agent.

Issue #1267. The workflow engine (`skill_workflow.py`) hands an agent step its
`instructions` file — and `also_read`, when the step has one — every time the
step comes up, including once per item inside a `for_each`. This reads every
`.claude/skills/*/workflow.yaml` and prints one line per step:

    step id · type · loop (the `for_each` list it repeats over, or -) ·
    conditional (`when:`) · the files the step hands over and their bytes

and, per Skill, three totals:

    always        SKILL.md + every unconditional top-level step
    conditional   top-level steps with `when:` (and the conditional parts of
                  a loop body are still counted in `per item` below)
    per item      the body of each `for_each`, once per item — what the agent
                  is told to read again for every source / pair

## What counts as "a file the step hands over"

1. The step's `instructions` and `also_read` (the engine names them itself).
2. A human step's `ask` text and `choices` (the engine hands them inline, and
   nothing else: a human step's `instructions` are not handed over).
3. Files the instructions file tells the agent to **read** — a backticked
   `.md` path that a read / follow / load verb points at in the same clause
   ("read `.wikicommit/schema-authoring.md` and follow it"). A path that is
   only named in passing ("used by Pass 2b (`references/pass2b-type.md`)") is
   a cross-reference, not a read. A path is
   resolved as `references/…` (inside the Skill), `../<skill>/…` (a sibling
   Skill) or `.wikicommit/<name>.md` (a distributed template, measured at
   `wikicommit-init/scripts/templates/<name>.md`). Naming is not followed past
   one level.

What this cannot pick up is listed under each Skill rather than guessed at:
**unresolved** (a placeholder path such as `.wikicommit/schema/<Type>.md`, or
a file that does not exist here — the read happens, its size is unknown) and
**mentioned** (a resolvable path no read verb points at — a cross-reference,
not counted). A file that is a step's own `instructions` / `also_read` is not
listed as mentioned, even where another file only names it. A file the agent
hands to a *subagent* (Pass 4 hands `review-rules.md` to the reviewer) is counted
only when a read verb points at it; when it is, it is counted as if it were read
in the main context, which it is not.

## Tokens

Bytes divided by `--bytes-per-token` (default 4, the rough figure for English
prose that `check_skill_md_lines.py` also uses). The output states the
assumption. Nothing is sent anywhere — counting tokens exactly would mean
sending the instructions to an API, which this tool does not do.

What this measures is the **instruction text the engine points at**, not the
context a run uses: extracted source text, generated pages, tool output and
whether the agent actually re-reads a file it has already read are invisible
here. `tools/measure_workflow_context.py` measures those from a real run.

Usage:
    python tools/report_workflow_context_cost.py [--skills-dir .claude/skills]
        [--skill wikicommit-generate] [--bytes-per-token 4] [--json]

Exit code: 0, or 2 on a usage error / unreadable workflow file.
Dev-only (not distributed).
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".wikicommit" / "scripts"))

import skill_workflow  # noqa: E402

DEFAULT_SKILLS_DIR = Path(".claude/skills")
DEFAULT_BYTES_PER_TOKEN = 4.0

# The distributed templates that land at `.wikicommit/<name>` in a wiki.
TEMPLATES_REL = Path("wikicommit-init") / "scripts" / "templates"

BACKTICK_MD = re.compile(r"`([^`\s]+\.md)`")
# A read instruction: the verb, then the path within the same clause.
READ_BEFORE = re.compile(
    r"\b(?:read|reads|re-read|follow|follows|load|loads)\b[^`.;:()]{0,40}`([^`\s]+\.md)`",
    re.IGNORECASE,
)


class ReportError(Exception):
    pass


def resolve_reference(ref: str, skill_dir: Path, skills_dir: Path) -> Path | None:
    """The file a backticked reference names, or None when it cannot be pinned down."""
    if any(c in ref for c in "<>*{}"):
        return None
    if ref.startswith("../"):
        candidate = (skill_dir / ref).resolve()
    elif ref.startswith("references/"):
        candidate = skill_dir / ref
    elif ref.startswith(".wikicommit/") and ref.count("/") == 1:
        candidate = skills_dir / TEMPLATES_REL / ref.split("/", 1)[1]
    else:
        return None
    return candidate if candidate.is_file() else None


def scan_references(path: Path, skill_dir: Path, skills_dir: Path) -> dict:
    """The files `path` tells the agent to read, plus what could not be counted."""
    read: dict[str, Path] = {}
    unresolved: set[str] = set()
    mentioned: set[str] = set()
    own = {path.resolve(), (skill_dir / "SKILL.md").resolve()}
    for line in path.read_text(encoding="utf-8").splitlines():
        refs = BACKTICK_MD.findall(line)
        if not refs:
            continue
        told = set(READ_BEFORE.findall(line))
        for ref in refs:
            verb = ref in told
            if "/" not in ref:
                continue  # a bare file name (`Person.md`) is an example, not a pointer
            target = resolve_reference(ref, skill_dir, skills_dir)
            if target is not None and target.resolve() in own:
                continue
            if target is None:
                if verb:
                    unresolved.add(ref)
            elif verb:
                read[ref] = target
            else:
                mentioned.add(ref)
    mentioned -= set(read)
    return {"read": read, "unresolved": unresolved, "mentioned": mentioned}


def _size(path: Path) -> int:
    return len(path.read_bytes())


def step_files(step: dict, skill_dir: Path, skills_dir: Path, notes: dict) -> list[dict]:
    """Every file (or inline text) the engine hands over with this step, with bytes."""
    files: list[dict] = []
    seen: set[str] = set()

    def add(label: str, size: int, via: str, key: str | None = None) -> None:
        key = key or label
        if key in seen:
            return
        seen.add(key)
        files.append({"file": label, "bytes": size, "via": via, "key": key})

    if step.get("type") == "human":
        # the engine hands a human step its question and choices, nothing more
        inline = str(step.get("ask") or "") + json.dumps(step.get("choices") or {},
                                                        ensure_ascii=False)
        add("(ask text)", len(inline.encode("utf-8")), "inline", f"ask|{step.get('id')}")
        return files
    for key in ("instructions", "also_read"):
        rel = step.get(key)
        if not rel:
            continue
        for one in rel if isinstance(rel, list) else [rel]:
            path = skill_dir / str(one)
            if not path.is_file():
                notes["unresolved"].add(f"{one} (named by {step.get('id')}, missing)")
                continue
            add(str(one), _size(path), key, str(path.resolve()))
            refs = scan_references(path, skill_dir, skills_dir)
            for ref, target in sorted(refs["read"].items()):
                add(ref, _size(target), f"read by {one}", str(target.resolve()))
            notes["unresolved"].update(refs["unresolved"])
            notes["mentioned"].update(refs["mentioned"])
    return files


def walk_steps(steps: list, loop: str | None, skill_dir: Path, skills_dir: Path,
               notes: dict) -> list[dict]:
    rows: list[dict] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get("for_each"):
            rows.extend(walk_steps(step.get("steps") or [], str(step["for_each"]),
                                   skill_dir, skills_dir, notes))
            continue
        files = step_files(step, skill_dir, skills_dir, notes)
        rows.append({
            "id": str(step.get("id")),
            "type": str(step.get("type")),
            "loop": loop,
            "conditional": "when" in step,
            "files": files,
            "bytes": sum(f["bytes"] for f in files),
        })
    return rows


def report_skill(workflow_path: Path, skills_dir: Path) -> dict:
    skill_dir = workflow_path.parent
    try:
        workflow = skill_workflow.load_workflow(workflow_path)
    except skill_workflow.WorkflowError as e:
        raise ReportError(str(e)) from e
    notes = {"unresolved": set(), "mentioned": set()}
    rows = walk_steps(workflow["steps"], None, skill_dir, skills_dir, notes)
    skill_md = skill_dir / "SKILL.md"
    skill_md_bytes = _size(skill_md) if skill_md.is_file() else 0

    # A file handed over by several steps is counted once in a total that
    # covers all of them — the same text does not grow on a second mention
    # unless it is actually read again, which is what the per-item total and
    # the measuring tool are about.
    def total(selected: list[dict], start: dict[str, int] | None = None) -> int:
        files = dict(start or {})
        for row in selected:
            for f in row["files"]:
                files.setdefault(f["key"], f["bytes"])
        return sum(files.values())

    always_rows = [r for r in rows if r["loop"] is None and not r["conditional"]]
    conditional_rows = [r for r in rows if r["loop"] is None and r["conditional"]]
    loops: dict[str, list[dict]] = {}
    for r in rows:
        if r["loop"] is not None:
            loops.setdefault(r["loop"], []).append(r)
    return {
        "skill": str(workflow.get("skill") or skill_dir.name),
        "workflow": workflow_path.as_posix(),
        "skill_md_bytes": skill_md_bytes,
        "steps": rows,
        "always_bytes": total(always_rows, {str(skill_md.resolve()): skill_md_bytes}),
        "conditional_bytes": total(conditional_rows),
        "per_item_bytes": {name: total(body) for name, body in loops.items()},
        "unresolved": sorted(notes["unresolved"]),
        # a file some step hands over is counted there, whatever else names it
        "mentioned": sorted(notes["mentioned"] - {f["file"] for r in rows for f in r["files"]}),
    }


def tokens(size: int, bytes_per_token: float) -> int:
    return round(size / bytes_per_token)


def format_text(reports: list[dict], bytes_per_token: float) -> str:
    def k(size: int) -> str:
        return f"{size:,} B (~{tokens(size, bytes_per_token) / 1000:.1f}K tok)"

    out = [f"# assumption: 1 token ~ {bytes_per_token:g} bytes (estimate, not a tokenizer count)"]
    for rep in reports:
        out.append("")
        out.append(f"== {rep['skill']} ({rep['workflow']})")
        out.append(f"   SKILL.md: {k(rep['skill_md_bytes'])}")
        for row in rep["steps"]:
            flags = []
            if row["loop"]:
                flags.append(f"for_each {row['loop']}")
            if row["conditional"]:
                flags.append("when")
            flag = f" [{', '.join(flags)}]" if flags else ""
            out.append(f"   {row['id']:<28} {row['type']:<6}{flag}  {k(row['bytes'])}")
            for f in row["files"]:
                out.append(f"       {f['file']}  {f['bytes']:,} B  ({f['via']})")
        out.append(f"   TOTAL always (SKILL.md + unconditional top-level steps): {k(rep['always_bytes'])}")
        out.append(f"   TOTAL conditional top-level steps: {k(rep['conditional_bytes'])}")
        for name, size in rep["per_item_bytes"].items():
            out.append(f"   TOTAL per item of `{name}` (if every file is re-read): {k(size)}")
        for ref in rep["unresolved"]:
            out.append(f"   UNRESOLVED (read, size unknown): {ref}")
        for ref in rep["mentioned"]:
            out.append(f"   MENTIONED (no read verb, not counted): {ref}")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--skills-dir", default=str(DEFAULT_SKILLS_DIR))
    p.add_argument("--skill", action="append", default=[],
                   help="only this Skill (repeatable); default: every Skill with a workflow.yaml")
    p.add_argument("--bytes-per-token", type=float, default=DEFAULT_BYTES_PER_TOKEN)
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    if args.bytes_per_token <= 0:
        print("ERROR: --bytes-per-token must be positive", file=sys.stderr)
        return 2
    skills_dir = Path(args.skills_dir)
    paths = sorted(skills_dir.glob("*/workflow.yaml"))
    if args.skill:
        wanted = set(args.skill)
        paths = [p for p in paths if p.parent.name in wanted]
        missing = wanted - {p.parent.name for p in paths}
        if missing:
            print(f"ERROR: no workflow.yaml for: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    try:
        reports = [report_skill(p, skills_dir) for p in paths]
    except ReportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"bytes_per_token": args.bytes_per_token, "skills": reports},
                         ensure_ascii=False, indent=2))
    else:
        print(format_text(reports, args.bytes_per_token))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
