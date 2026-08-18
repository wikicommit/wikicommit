"""Shared Schema.org vocabulary loading/lookup for check_schema_org_type.py
and validate_frontmatter.py (Issue #495), extended with rangeIncludes/
DataType lookups for check_schema_org_type.py's entity-vs-scalar range query
(Issue #496 — deciding whether a property's value should be written as a
`[[Type/slug]]` WikiLink).

Lazily builds .wikicommit/schemaorg-vocab.json the first time it's needed
(same build-on-first-query pattern as search_index.py) by fetching the
official machine-readable dump from
https://schema.org/version/latest/schemaorg-current-https.jsonld. Unlike
search_index.sqlite3, this file is committed to Git (Issue #319) rather than
gitignored: it's semi-static reference data with a real network-fetch cost,
not a disposable cache, so it lives at .wikicommit/schemaorg-vocab.json (not
under .wikicommit/.cache/) and is expected to be added to a commit like any
other WikiCommit output. No TTL/auto-refresh — Schema.org's vocabulary
changes rarely, and the only cost of a stale copy is "a newer type isn't
visible yet". As of Issue #512 this cost is no longer purely soft: a `type:`
absent only because the cache predates that type's addition to Schema.org
now makes validate_frontmatter.py's type-existence check (not just its
`properties:` domainIncludes check) report a hard ERROR, blocking
wikicommit-merge for every page of that type until the cache is rebuilt.
Delete .wikicommit/schemaorg-vocab.json manually to force a rebuild against
the latest vocabulary. A cache written by a pre-Issue-#496
version of this module (missing the per-entry "is_datatype"/"range" keys
_build_index() now writes) does not need manual deletion — load_or_build_index()
detects the outdated shape itself via _is_well_shaped_index() and rebuilds
automatically.

Consolidated out of check_schema_org_type.py (Issue #495) so
validate_frontmatter.py's new `properties:` domainIncludes check (verifying
a page's properties: keys actually belong to its `type:`, per the same
domainIncludes + rdfs:subClassOf ancestry logic) can reuse the identical
vocabulary-loading and ancestry-walking logic instead of a second, divergence-
prone copy — the same "one implementation every script imports" precedent as
_frontmatter.py/_wikilink.py (docs/DesignDoc-skills.md §11.5).
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

VOCAB_PATH = Path(".wikicommit/schemaorg-vocab.json")
VOCAB_URL = "https://schema.org/version/latest/schemaorg-current-https.jsonld"

# Testing-only hook: when set, read the JSON-LD vocabulary dump from this
# local file instead of fetching it over the network, and skip the on-disk
# cache entirely. Never set in normal operation — this exists solely so
# tests can exercise the parsing/verification logic offline and
# deterministically (Issue #285).
TEST_VOCAB_PATH_ENV = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"


def strip_prefix(value: str) -> str:
    """'schema:Game' -> 'Game'; 'Game' -> 'Game' (already bare)."""
    return value.split(":", 1)[1] if ":" in value else value


def _fetch_vocab_jsonld() -> dict:
    override = os.environ.get(TEST_VOCAB_PATH_ENV)
    if override:
        return json.loads(Path(override).read_text(encoding="utf-8"))
    with urllib.request.urlopen(VOCAB_URL, timeout=30) as resp:  # noqa: S310 (fixed https:// constant, no user input)
        return json.loads(resp.read().decode("utf-8"))


def _ids(raw: object) -> list[str]:
    """Normalize a JSON-LD value (single ref, list of refs, or absent) to a
    list of bare (prefix-stripped) schema: ids, dropping any non-schema:
    reference (e.g. external Wikidata/rdf: links)."""
    items = raw if isinstance(raw, list) else ([raw] if raw else [])
    return [
        strip_prefix(item["@id"]) for item in items
        if isinstance(item, dict) and str(item.get("@id", "")).startswith("schema:")
    ]


def _comment_text(raw: object) -> str:
    """rdfs:comment is usually a plain string, but JSON-LD allows a
    language-tagged object ({"@value": "...", "@language": "en"}) — handle
    both so a description isn't silently dropped. Also collapses embedded
    newlines/runs of whitespace to single spaces: roughly 6% of real
    Schema.org type comments (e.g. "3DModel") span multiple lines, which
    would otherwise break --list-types' one-line-per-type tab-separated
    output contract."""
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, dict):
        text = str(raw.get("@value", ""))
    else:
        return ""
    return " ".join(text.split())


def _build_index(jsonld: dict) -> dict:
    """Reduce the raw JSON-LD @graph to a small lookup structure:
    {"types": {name: {"parents": [name, ...], "comment": str, "is_datatype": bool}},
     "properties": {name: {"domain": [name, ...], "range": [name, ...], "comment": str}}}.

    "range"/"is_datatype" (Issue #496) support deciding whether a property's
    value should be written as a WikiLink: `schema:rangeIncludes` lists the
    type(s) a property's value may be (e.g. `affiliation` -> `Organization`,
    `description` -> `Text`/`TextObject`), and a range candidate is a
    DataType (Text/Number/Boolean/Date/... — plain scalar values, never a
    linkable WikiCommit page) if it or any ancestor in its rdfs:subClassOf
    chain is tagged `schema:DataType` in `@type` (e.g. `URL` has no direct
    tag but is `subClassOf: Text`, which does — see is_in_datatype_lineage()
    below, which walks the same ancestors() chain used for domainIncludes).

    A property's own "comment" (Issue #497) supports check_schema_org_type.py's
    `--list-properties` mode — the same one-line-description contract
    `--list-types` already has for types, via the same `_comment_text()`."""
    types: dict[str, dict] = {}
    properties: dict[str, dict] = {}

    for node in jsonld.get("@graph", []):
        if not isinstance(node, dict):
            continue  # malformed dump entry (e.g. a bare string) — skip rather than crash
        node_id = node.get("@id", "")
        if not str(node_id).startswith("schema:"):
            continue
        name = strip_prefix(node_id)

        node_types = node.get("@type")
        node_types = node_types if isinstance(node_types, list) else [node_types]

        if "rdfs:Class" in node_types:
            types[name] = {
                "parents": _ids(node.get("rdfs:subClassOf")),
                "comment": _comment_text(node.get("rdfs:comment")),
                "is_datatype": "schema:DataType" in node_types,
            }
        elif "rdf:Property" in node_types:
            properties[name] = {
                "domain": _ids(node.get("schema:domainIncludes")),
                "range": _ids(node.get("schema:rangeIncludes")),
                "comment": _comment_text(node.get("rdfs:comment")),
            }

    return {"types": types, "properties": properties}


def _is_well_shaped_index(cached: object) -> bool:
    """True if cached matches _build_index()'s current output shape,
    including per-entry "is_datatype"/"range" keys (Issue #496) and
    properties' "comment" key (Issue #497) — not just the outer
    {"types": dict, "properties": dict} envelope. A cache written before one
    of these Issues (or a partial hand-edit/bad-merge that dropped keys from
    only some entries) has the right envelope but missing keys; without this
    per-entry check it would be silently accepted, and
    is_in_datatype_lineage()'s `.get("is_datatype")` would then treat every
    missing key as `None`/falsy — indistinguishable from a confirmed
    "not a DataType" — so a stale cache wouldn't just lose --show-range/
    --list-properties output, it could actively misclassify a DataType
    (e.g. URL) as an entity-linkable type. Rejecting the whole file here
    forces a rebuild instead, which is safe (self-healing) rather than
    silently wrong."""
    if not (isinstance(cached, dict) and isinstance(cached.get("types"), dict) and isinstance(cached.get("properties"), dict)):
        return False
    return all(
        isinstance(t, dict) and "is_datatype" in t for t in cached["types"].values()
    ) and all(
        isinstance(p, dict) and "range" in p and "comment" in p for p in cached["properties"].values()
    )


def load_or_build_index() -> tuple[dict | None, str]:
    """Return (index, "") on success — index is {"types": ..., "properties":
    ...}, see _build_index() — reading the committed
    .wikicommit/schemaorg-vocab.json cache when present, or fetching and
    building it (and writing the cache) otherwise. Returns (None,
    error_message) if the vocabulary could not be obtained at all (network
    failure and no usable cache).

    Deliberately does not print anything itself (unlike the pre-Issue-#495
    version of this logic, which lived directly in check_schema_org_type.py
    and printed its own "ERROR: ..." line): the two callers need different
    presentation. check_schema_org_type.py's CLI treats a failed fetch as a
    hard failure (prints ERROR:, exits 1), while validate_frontmatter.py
    treats it as an expected, non-blocking degradation of `properties:`
    validation (prints WARNING:, exits 0 same as any other run) — a raw
    unconditional "ERROR:" line from inside this shared function would be
    misleading in the latter context, where every "ERROR:" line is expected
    to correspond to a counted error in that script's own summary line.

    Every failure mode below is deliberately folded into the same (None,
    error_message) contract rather than left to propagate as an uncaught
    exception: a hand-edited/badly-merged/stale-checkout schemaorg-vocab.json
    that parses as valid JSON but has the wrong shape, a non-UTF-8 or
    malformed fetch response, or an @graph entry that isn't the expected
    dict shape. validate_frontmatter.py now calls this on every
    wikicommit-merge run that touches a page with type-specific frontmatter
    (previously only the occasionally-invoked check_schema_org_type.py CLI
    exercised this code path), so an uncaught exception here would crash the
    blocking quality gate for the whole repository rather than just degrade
    one script's optional check."""
    using_test_override = bool(os.environ.get(TEST_VOCAB_PATH_ENV))

    if VOCAB_PATH.exists() and not using_test_override:
        try:
            cached = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
            if not _is_well_shaped_index(cached):
                raise ValueError("schemaorg-vocab.json has an unexpected shape")
            return cached, ""
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # file is unreadable/corrupt/malformed — fall through and rebuild

    try:
        jsonld = _fetch_vocab_jsonld()
        index = _build_index(jsonld)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, UnicodeDecodeError, AttributeError, TypeError) as e:
        return None, str(e)

    if not using_test_override:
        VOCAB_PATH.parent.mkdir(parents=True, exist_ok=True)
        VOCAB_PATH.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    return index, ""


def ancestors(type_name: str, types: dict) -> set[str]:
    """type_name itself plus every ancestor reachable via rdfs:subClassOf."""
    seen: set[str] = set()
    queue = [type_name]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(types.get(current, {}).get("parents", []))
    return seen


def property_in_domain(prop_name: str, ancestry: set[str], properties: dict) -> bool | None:
    """Return True if prop_name exists in the vocabulary and belongs to (a
    type in) ancestry's domainIncludes, False if it exists but belongs to a
    different domain, or None if prop_name isn't in the vocabulary at all.

    Shared by check_schema_org_type.py's --property verification and
    validate_frontmatter.py's `properties:` checks (Issue #495) so the single
    domain-membership rule lives in one place rather than two independently
    maintained copies."""
    info = properties.get(prop_name)
    if info is None:
        return None
    return bool(ancestry & set(info["domain"]))


def is_in_datatype_lineage(type_name: str, types: dict) -> bool:
    """True if type_name or any ancestor (via rdfs:subClassOf) is tagged
    `schema:DataType` — i.e. a plain scalar value (Text/Number/Boolean/
    Date/...), never a linkable WikiCommit page. `URL` is the motivating
    case (Issue #496): it carries no `schema:DataType` tag of its own but is
    `subClassOf: Text`, which does — so DataType-ness has to be checked
    across the whole ancestor chain, not just the type itself."""
    return any(types.get(t, {}).get("is_datatype") for t in ancestors(type_name, types))


def properties_available_to(type_name: str, types: dict, properties: dict) -> dict[str, list[str]]:
    """Return {property_name: [declaring_type, ...]} for every property in
    the vocabulary whose `schema:domainIncludes` intersects type_name's
    ancestry (type_name itself or any rdfs:subClassOf ancestor) — i.e. every
    property a page of this type could plausibly declare under
    `properties:` (docs/DesignDoc-data.md §4.1). declaring_type(s) are the
    specific ancestry members that appear in that property's own
    domainIncludes, sorted — usually exactly one, but a property's
    domainIncludes can name more than one ancestor of type_name at once
    (e.g. a property declared on both `Thing` and a nearer ancestor
    redundantly), so this returns all matches rather than picking one
    arbitrarily. Used by check_schema_org_type.py's `--list-properties`
    (Issue #497 — browsing "what can this type's `properties:` hold" when
    writing a new schema file, now that Issue #495 removed the old
    `recommended` field's role as a starting point)."""
    ancestry = ancestors(type_name, types)
    result: dict[str, list[str]] = {}
    for prop_name, info in properties.items():
        declaring = sorted(ancestry & set(info.get("domain", [])))
        if declaring:
            result[prop_name] = declaring
    return result


def entity_range_candidates(prop_name: str, properties: dict, types: dict) -> tuple[list[str], list[str]] | None:
    """Split prop_name's `schema:rangeIncludes` candidates into (entity_types,
    datatype_types), or return None if prop_name isn't in the vocabulary at
    all. entity_types are candidates a property's value could reasonably be
    written as a `[[Type/slug]]` WikiLink to (docs/DesignDoc-data.md §4.1);
    datatype_types are plain scalar values that never should be. Either list
    may be empty — some properties have exactly one kind or the other
    (`affiliation` -> `Organization` only, entity; `sameAs` -> `URL` only,
    DataType via lineage), while others mix both (`jobTitle` -> `DefinedTerm`
    and `Text`; `description` -> `TextObject`, an entity type — despite the
    name, `TextObject` is `subClassOf: MediaObject`, not a DataType — and
    `Text`)."""
    info = properties.get(prop_name)
    if info is None:
        return None
    entity_types = [t for t in info.get("range", []) if not is_in_datatype_lineage(t, types)]
    datatype_types = [t for t in info.get("range", []) if is_in_datatype_lineage(t, types)]
    return entity_types, datatype_types
