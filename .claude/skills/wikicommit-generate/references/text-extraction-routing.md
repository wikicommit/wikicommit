# Text extraction routing (`wikicommit-generate` Pass 1)

Which tool extracts which file type, and what to install when one is missing. Pass 1
is the only reader — nothing else in this Skill dispatches on a file extension — which
is why this is not in `SKILL.md`: it was 4,949 bytes loaded on every invocation of a
Skill that, under `--regenerate` or on a run that finds nothing to process, may never
reach Pass 1 at all (Issue #894).

**Read this when Pass 1 is about to extract its first source**, not before. The rule at
the top of the table applies whatever brought you here: a missing skill stops the run
with an install command, except where a documented fallback exists.

If a required skill is not installed, **stop processing and display the install command** before proceeding. Exception: `.pdf` (text-based), `.docx`, `.pptx`, and `.xlsx` do not stop when their respective official skill is unavailable — Pass 1 automatically falls back to running the `markitdown` CLI directly instead (see Pass 1 in `SKILL.md`); each only stops if `markitdown` itself turns out not to be installed. `.epub` and image files have no such fallback (see rows below) — `markitdown` cannot equivalently cover EPUB or OCR extraction, so these two file types still stop when their skill is unavailable (Issue #268).

| File type | Required skill | Install command |
|---|---|---|
| `.pdf` (text-based) | Anthropic official `pdf` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill pdf` — if this fails to create a `.claude/skills/pdf/` symlink (known upstream bug: [vercel-labs/skills#744](https://github.com/vercel-labs/skills/issues/744), [#851](https://github.com/vercel-labs/skills/issues/851)), no action is needed: Pass 1 detects this and automatically runs the `markitdown` CLI instead. If `markitdown` itself isn't installed, Pass 1 stops and displays `pip install 'markitdown[pdf]'` for you to run |
| `.pdf` (scanned) | `ocr-and-documents` | `npx skills add https://github.com/NousResearch/skills --skill ocr-and-documents` |
| `.docx` | Anthropic official `docx` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill docx` — if this fails to create a `.claude/skills/docx/` symlink (same upstream bug as `.pdf`, see above), no action is needed: Pass 1 detects this and automatically runs the `markitdown` CLI instead (`.docx` needs no extra beyond the base `markitdown` package, unlike `.pdf`'s `[pdf]` extra). If `markitdown` itself isn't installed, Pass 1 stops and displays `pip install markitdown` for you to run |
| `.pptx` | Anthropic official `pptx` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill pptx` — same fallback pattern as `.docx` above (`pip install markitdown` if not yet installed) |
| `.xlsx` | Anthropic official `xlsx` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill xlsx` — same fallback pattern as `.docx` above (`pip install markitdown` if not yet installed) |
| `.epub` | `ebook-extractor` (no `markitdown` fallback — see note above; Issue #268) | `npx skills add https://github.com/anthropics/skills --skill ebook-extractor` |
| Image files | `ocr-and-documents` (no `markitdown` fallback — see note above; Issue #268) | `npx skills add https://github.com/NousResearch/skills --skill ocr-and-documents` |
| URL (web page or direct file link, e.g. PDF) | `markitdown` (Python package, not a Claude Skill), invoked via `add_source.py --fetch-url` rather than the CLI directly — see the Issue #527 note under Pass 1 in `SKILL.md` | `pip install 'markitdown[pdf]'` — run via `python .claude/skills/wikicommit-generate/scripts/add_source.py --fetch-url <url> --output <path>` (see Pass 1 in `SKILL.md`) |
| URL (YouTube video) | `markitdown` **plus** `youtube-transcript-api` — without the second package `markitdown` extracts only the title, keywords, runtime and description and drops the transcript, with no error or warning, so the video's actual content never reaches Pass 2 (Issue #574). Only `https://www.youtube.com/watch?v=<id>` links (and the `youtu.be/<id>` / `m.youtube.com` forms that redirect to them) are recognized as videos at all — a `/shorts/<id>`, `/playlist`, channel, or `music.youtube.com` URL is not, and extracts to navigation boilerplate; register the `watch?v=<id>` equivalent instead | `pip install youtube-transcript-api` (in addition to `markitdown` above). Pass 1 checks for this before fetching and stops with this command if it is missing |
| Other (unmatched file extensions) | `markitdown` (fallback; same package as above) | `pip install 'markitdown[pdf]'` — run via CLI: `PYTHONIOENCODING=utf-8 markitdown <path>` |

Every `markitdown` invocation in this skill is prefixed with `PYTHONIOENCODING=utf-8`: on Windows, a Japanese-locale console codepage (`cp932`) can make the `markitdown` subprocess's stdout encoding disagree with the UTF-8 the rest of the pipeline (redirect target, `Read` tool, hash computation) assumes, corrupting extracted text into mojibake before it ever reaches Pass 2 (Issue #272). This `VAR=value command` prefix syntax is POSIX shell — it works unmodified under both Git Bash and WSL, the two execution paths Claude Code's Bash tool uses on Windows; it would need different syntax under raw PowerShell/cmd.exe, but Skills never run there.
