"""The pathspecs of the pages `wikicommit-merge` checks, for the guards that need them.

Three guards (`test_guides_tree.py`, `test_review_record_tree.py`,
`test_run_record_tree.py`) assert that a tree they own — the guides, the review
records, the run records — is not swept into merge's page checks (its
`changed_md`). Each used to carry its own byte-identical copy of the loader, and
each copy put `.wikicommit/scripts` on `sys.path` again, so one session could hold
the same entry three times (Issue #1238).

Loaded under its own name: generate's checks are also a module called
`workflow_checks`. The load is cached, so the module is executed and the path is
added once per session however many guards ask.
"""

import functools
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

_SCRIPTS = REPO_ROOT / ".wikicommit" / "scripts"
_MERGE_CHECKS = REPO_ROOT / ".claude" / "skills" / "wikicommit-merge" / "scripts" / "workflow_checks.py"


@functools.cache
def merge_page_pathspecs() -> tuple[str, ...]:
    """The pathspecs of the pages `wikicommit-merge` checks (its `changed_md`)."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location("merge_workflow_checks", _MERGE_CHECKS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PAGE_PATHSPECS
