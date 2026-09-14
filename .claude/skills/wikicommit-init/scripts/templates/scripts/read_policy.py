#!/usr/bin/env python3
"""Return the prose policy a policy file actually states (Issue #844).

`.wikicommit/source-policy.md` and `.wikicommit/entity-policy.md` ship with their
whole body written as a commented-out worked example. The design says a body that
is empty, or still that example, states no policy — but until now the deciding was
done by a sentence repeated in four places across two SKILL.md files, each telling
an LLM to judge whether the body it had just read was "still the shipped comment".

That is the shape Issue #474 named: an operation that is entirely deterministic,
expressed as an instruction. The shipped text is right here on disk, so nothing
has to be judged. And the failure it invites is one-sided — every line of both
examples argues for *excluding* something, so a misread only ever suppresses pages
that should have been written, which is the direction one pilot already went in
far enough to end up with no `Person` pages at all.

The rule this applies is simpler than "is this the shipped example", and does not
depend on which version shipped it:

    An HTML comment is never policy.

Both templates put their example inside one, and both tell the reader to delete it
once they have written their own; a policy someone writes is ordinary prose. So the
comments come out, and what is left is the policy. A repository initialized before
this script existed needs no migration: its body is a comment too.

`<!-- wikicommit:example ... -->` marks the shipped block explicitly. Stripping
comments would handle it anyway, but the marker makes "this is ours, not yours"
greppable, and it separates the two ways a body can be all comment: the marked
block, and a comment someone opened themselves. What no marker can tell is
whether the marked block is untouched or was edited *in place*, since both leave
the same shape on disk — so neither reason claims that. Both say, in their own
words, that a policy written inside a comment is not read, because a policy
silently ignored is the failure this script exists to remove rather than to
relocate.

Reads only. Nothing here writes, and the frontmatter is left to its own readers:
`exclude_domains` is unioned by check_extraction_quality.py, and the entity policy's
switch is read where it is applied.

Usage:

    python .wikicommit/scripts/read_policy.py .wikicommit/source-policy.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_and_body_text

# Non-greedy, DOTALL: each comment is closed by its own first `-->`. HTML comments
# do not nest, so this matches what a Markdown renderer would drop.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# The shipped worked example, tagged so it can be told from a comment a user wrote.
_EXAMPLE_COMMENT_RE = re.compile(r"<!--\s*wikicommit:example\b.*?-->", re.DOTALL)


def strip_frontmatter(text: str) -> str:
    r"""Drop a leading YAML frontmatter block, if there is one.

    Delegated to _frontmatter.py rather than done with a `\A---\n.*?\n---` regex
    here, for the reason that module's docstring gives (Issue #212): that regex
    never matches a block with zero content lines (`---\n---\n`), because there is
    no newline between the two delimiters for `.*?` to sit on. A policy file whose
    keys have all been deleted would then keep its `---` lines in the body, and a
    file whose body is only the shipped example would be reported as stating
    `---` as its policy. The line scan there handles that case, and it also
    returns the body for a frontmatter block whose YAML does not parse, which is
    what this script wants: the frontmatter's own readers report that failure.
    """
    _fm, _err, body = parse_frontmatter_and_body_text(text)
    return body


def prose_policy(text: str) -> tuple[str, str]:
    """Split a policy file into (prose, reason-it-is-empty).

    Exactly one of the two is non-empty. The reason distinguishes the three ways a
    file can state nothing, because they call for different things from the reader:
    an empty body is a file waiting to be filled in, a body that is entirely the
    marked example is either untouched or edited in place inside the comment (the
    marker cannot tell those apart, so the reason names both), and a body that is
    commented out some other way is most likely a policy someone wrote inside a
    comment they did not open.
    """
    body = strip_frontmatter(text)
    if not body.strip():
        return "", "the body is empty"

    without_example = _EXAMPLE_COMMENT_RE.sub("", body)
    was_only_the_example = not without_example.strip()

    prose = _HTML_COMMENT_RE.sub("", without_example).strip()
    if prose:
        return prose, ""
    if was_only_the_example:
        # The marker cannot tell an untouched example from one edited in place:
        # both leave the whole body inside `<!-- wikicommit:example ... -->`, and
        # telling them apart would mean comparing against whichever version
        # shipped it, which is the version dependence this rule exists to avoid.
        # So this says both, rather than asserting the one it cannot verify.
        return "", (
            "the body is still the worked example this file ships with — if you "
            "wrote your policy inside that comment, move it outside the "
            "<!-- --> so it is read"
        )
    return "", "every line of the body is inside an HTML comment"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Print the prose policy a policy file states, with the shipped "
        "worked example and any other HTML comment removed."
    )
    parser.add_argument("path", metavar="<policy-file>")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.is_file():
        print(f"NONE: {args.path} is not present, so there is no prose policy")
        return 0
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        # UnicodeDecodeError is a ValueError, not an OSError, so it needs naming:
        # a policy file saved in a legacy encoding would otherwise traceback out of
        # a script whose whole contract is that it always exits 0 with one line.
        # Not an error exit: a policy that cannot be read is reported the same way
        # an absent one is, so a caller has one line to read either way. It still
        # says which of the two happened, because wikicommit-generate must warn on
        # an unreadable entity policy and stay silent on an absent one. The
        # frontmatter's own readers report their own failures.
        print(f"NONE: {args.path} could not be read ({e}), so there is no prose policy")
        return 0

    prose, reason = prose_policy(text)
    if not prose:
        print(f"NONE: {args.path} states no prose policy — {reason}")
        return 0
    print(f"POLICY: {args.path}")
    print(prose)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
