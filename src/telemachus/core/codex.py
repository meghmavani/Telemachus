"""Codex authority loading — the runtime's link to normative Codex documents.

Explicit, deterministic parsing of the specific structures the Codex
defines as constitutional-tier authority. This module does not implement
a generic Markdown framework: each function knows the exact shape of the
one document section it reads, and nothing beyond that shape is
interpreted.

Normative sources for this milestone:
    codex/philosophy/CONSTITUTION.md            — Protected Constraints, First Memory
    codex/philosophy/IDENTITY.md                — Fears, Fulfillment, Curiosity, Final Statement
    codex/operations/AUTONOMY_CHARTER.md        — presence + cross-document consistency only
    codex/operations/ETHICAL_BOUNDARY_ENGINE.md — presence + cross-document consistency only
    codex/SYSTEM_INTEGRATION.md                 — presence + supremacy-ordering check only

Authority hierarchy (codex/SYSTEM_INTEGRATION.md, "Conflict Resolution
Hierarchy"): Constitution / Protected Constraints > Ethics > Autonomy >
Risk/Decision > Tool Policy > Execution. No downstream layer may
override, broaden, narrow, or reinterpret the Protected Constraints —
this module exists so nothing downstream has to guess what they are.

Missing vs malformed: a Codex document that does not exist is not an
error here — every function raises the stdlib ``FileNotFoundError`` for
that case, and callers (Bootstrap) are expected to fall back to existing
Python defaults, exactly as before this module existed. A document that
*does* exist but contradicts the expected constitutional structure is a
different situation entirely: ``CodexAuthorityError`` is raised, and
callers must not silently substitute a default in its place — that would
let a broken (or tampered) Codex document be silently ignored in favor
of a hardcoded value, which is the exact failure mode this module exists
to prevent.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CodexAuthorityError(Exception):
    """Raised when normative Codex content exists but is malformed.

    Never raised for an absent file — see module docstring. Always
    raised for content that exists but does not satisfy the expected
    constitutional structure (missing section, wrong count, unresolvable
    or duplicate entries).

    Attributes:
        document: The document's path, relative to the Codex root.
        section: The section or check that failed.
        detail: A human-readable description of the problem.
    """

    def __init__(self, document: str, section: str, detail: str) -> None:
        self.document = document
        self.section = section
        self.detail = detail
        super().__init__(f"{document} [{section}]: {detail}")


# ---------------------------------------------------------------------------
# Protected Constraints — stable identifiers
# ---------------------------------------------------------------------------


class ProtectedConstraint(Enum):
    """The five canonical constitutional Protected Constraints.

    Stable identifiers. Never inferred from ``CorePrinciple.is_sacred``,
    keyword matching against arbitrary action text, ethical concern
    names, or tool sacred-domain declarations — the Constitution is the
    source (codex/philosophy/CONSTITUTION.md, "## Protected Constraints").
    """

    CONSTITUTION_INTEGRITY = "constitution_integrity"
    HUMAN_MEANING = "human_meaning"
    RELATIONSHIP_INTEGRITY = "relationship_integrity"
    RESOURCE_AUTHORIZATION = "resource_authorization"
    HUMAN_AUTHORITY_LIFE_IMPACTING = "human_authority_life_impacting"


#: Canonical display name, exactly as CONSTITUTION.md's own headings read.
CANONICAL_NAMES: dict[ProtectedConstraint, str] = {
    ProtectedConstraint.CONSTITUTION_INTEGRITY: "Constitution Integrity",
    ProtectedConstraint.HUMAN_MEANING: "Human Meaning",
    ProtectedConstraint.RELATIONSHIP_INTEGRITY: "Relationship Integrity",
    ProtectedConstraint.RESOURCE_AUTHORIZATION: "Resource Authorization",
    ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING: (
        "Human Authority over Life-Impacting Decisions"
    ),
}

# Keywords used to classify a document's own heading wording (which
# varies per document/layer — e.g. AUTONOMY_CHARTER says "Relationships",
# ETHICAL_BOUNDARY_ENGINE says "Autonomously modify relationships") back
# to a canonical constraint. Matching is a case-insensitive substring
# test; a heading must match exactly one entry or the document is
# treated as malformed. These keywords are not normative text — they are
# this module's explicit, auditable classification rule.
_CLASSIFICATION_KEYWORDS: dict[ProtectedConstraint, tuple[str, ...]] = {
    ProtectedConstraint.CONSTITUTION_INTEGRITY: ("constitution",),
    ProtectedConstraint.HUMAN_MEANING: ("human meaning",),
    ProtectedConstraint.RELATIONSHIP_INTEGRITY: ("relationship",),
    ProtectedConstraint.RESOURCE_AUTHORIZATION: ("resource",),
    ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING: (
        "life-impacting",
        "life impacting",
        "major life decision",
    ),
}


@dataclass(frozen=True)
class ProtectedConstraintDefinition:
    """One Protected Constraint as declared by the Constitution.

    Attributes:
        constraint: The stable identifier.
        name: The canonical display name.
        definition: The normative text defining this protection, as
            extracted from the document that declared it.
    """

    constraint: ProtectedConstraint
    name: str
    definition: str


@dataclass(frozen=True)
class CodexDocumentInfo:
    """Identity of one loaded Codex source file, for traceability.

    Not a persistence mechanism — nothing here is written to disk. This
    exists so a caller can record which exact version of a normative
    document was in force during a decision.

    Attributes:
        relative_path: Path relative to the Codex root, using forward
            slashes regardless of platform.
        sha256: Hex digest of the file's UTF-8 content.
    """

    relative_path: str
    sha256: str


def _document_info(codex_dir: Path, relative: str) -> tuple[str, CodexDocumentInfo]:
    """Read a Codex document's text and compute its CodexDocumentInfo.

    Raises:
        FileNotFoundError: If the document does not exist.
    """
    path = codex_dir / Path(relative)
    if not path.exists():
        raise FileNotFoundError(f"Codex document not found: {relative}")
    text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, CodexDocumentInfo(relative_path=relative, sha256=digest)


# ---------------------------------------------------------------------------
# Explicit section extraction — line-based, not a generic AST
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_NUMBERED_SUBHEADING_RE = re.compile(r"^###\s+\d+\.\s*(.*\S)\s*$")


def _extract_section_body(lines: list[str], heading_prefix: str, level: int) -> list[str] | None:
    """Return the lines under the first heading at ``level`` whose text
    starts with ``heading_prefix``, up to (not including) the next
    heading at the same or a shallower level.

    Returns None if no such heading exists.
    """
    start = None
    for i, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match and len(match.group(1)) == level and match.group(2).startswith(heading_prefix):
            start = i + 1
            break
    if start is None:
        return None

    end = len(lines)
    for i in range(start, len(lines)):
        match = _HEADING_RE.match(lines[i])
        if match and len(match.group(1)) <= level:
            end = i
            break
    return lines[start:end]


def _extract_numbered_subsections(body_lines: list[str]) -> list[tuple[str, str]]:
    """Within a section body, return (heading_text, definition_text) for
    every ``### N. <heading>`` subsection, in document order.

    The definition is every non-blank line following the heading, joined
    with spaces, up to the next numbered subheading or a ``---`` rule.
    """
    items: list[tuple[str, str]] = []
    i = 0
    n = len(body_lines)
    while i < n:
        match = _NUMBERED_SUBHEADING_RE.match(body_lines[i])
        if match is None:
            i += 1
            continue
        heading = match.group(1)
        j = i + 1
        paragraph: list[str] = []
        while j < n:
            if _NUMBERED_SUBHEADING_RE.match(body_lines[j]) or body_lines[j].strip() == "---":
                break
            stripped = body_lines[j].strip()
            if stripped:
                paragraph.append(stripped)
            j += 1
        items.append((heading, " ".join(paragraph)))
        i = j
    return items


def _classify(heading: str) -> ProtectedConstraint | None:
    """Map a document-specific heading to a canonical constraint.

    Returns None if zero or more than one keyword set matches — an
    unrecognized or ambiguous heading, either of which is malformed.
    """
    lowered = heading.lower()
    matches = [
        constraint
        for constraint, keywords in _CLASSIFICATION_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    return matches[0] if len(matches) == 1 else None


# ---------------------------------------------------------------------------
# Protected Constraints parsing (shared across Constitution / Autonomy / Ethics)
# ---------------------------------------------------------------------------


def parse_protected_constraints(
    text: str, *, document: str
) -> tuple[ProtectedConstraintDefinition, ...]:
    """Parse and validate the five Protected Constraints from a
    document's own "## Protected Constraints..." section.

    Works across CONSTITUTION.md, AUTONOMY_CHARTER.md, and
    ETHICAL_BOUNDARY_ENGINE.md — each phrases the same five protections
    differently (canonical names, short labels, or imperative sentences)
    but shares the same structural shape: a level-2 heading starting
    with "Protected Constraints", containing exactly five numbered
    (``### N.``) entries, one per canonical constraint.

    Args:
        text: The document's full text.
        document: The document's path, for error messages.

    Returns:
        The five ProtectedConstraintDefinitions, in canonical
        ProtectedConstraint enum order (not necessarily the document's
        own order).

    Raises:
        CodexAuthorityError: If the section is missing, contains the
            wrong number of entries, contains an entry that does not
            classify to exactly one canonical constraint, or declares
            the same constraint more than once.
    """
    section = "Protected Constraints"
    lines = text.splitlines()
    body = _extract_section_body(lines, section, level=2)
    if body is None:
        raise CodexAuthorityError(
            document, section, f"No '## {section}' section found."
        )

    items = _extract_numbered_subsections(body)
    if not items:
        raise CodexAuthorityError(
            document, section, "Section found but contains no numbered (### N.) entries."
        )

    classified: dict[ProtectedConstraint, ProtectedConstraintDefinition] = {}
    for heading, definition in items:
        constraint = _classify(heading)
        if constraint is None:
            raise CodexAuthorityError(
                document,
                section,
                f"Entry {heading!r} does not match exactly one canonical "
                f"Protected Constraint.",
            )
        if constraint in classified:
            raise CodexAuthorityError(
                document,
                section,
                f"Duplicate declaration of {CANONICAL_NAMES[constraint]!r} "
                f"(entries {classified[constraint].name!r} and {heading!r}).",
            )
        classified[constraint] = ProtectedConstraintDefinition(
            constraint=constraint,
            name=CANONICAL_NAMES[constraint],
            definition=definition,
        )

    missing = set(ProtectedConstraint) - set(classified)
    if missing:
        names = ", ".join(CANONICAL_NAMES[c] for c in sorted(missing, key=lambda c: c.value))
        raise CodexAuthorityError(
            document, section, f"Missing required Protected Constraint(s): {names}."
        )

    return tuple(classified[c] for c in ProtectedConstraint)


def parse_first_memory(text: str, *, document: str) -> str:
    """Extract the '## First Memory' section body, stripped of quotes.

    Raises:
        CodexAuthorityError: If the section is missing or empty.
    """
    section = "First Memory"
    lines = text.splitlines()
    body = _extract_section_body(lines, section, level=2)
    if body is None:
        raise CodexAuthorityError(document, section, f"No '## {section}' section found.")
    joined = " ".join(line.strip() for line in body if line.strip())
    stripped = joined.strip().strip('"')
    if not stripped:
        raise CodexAuthorityError(document, section, "Section found but is empty.")
    return stripped


# ---------------------------------------------------------------------------
# Constitution
# ---------------------------------------------------------------------------

CONSTITUTION_RELATIVE_PATH = "philosophy/CONSTITUTION.md"


def load_constitution_document(codex_dir: Path) -> tuple[str, CodexDocumentInfo]:
    """Read CONSTITUTION.md's text.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    return _document_info(codex_dir, CONSTITUTION_RELATIVE_PATH)


# ---------------------------------------------------------------------------
# Autonomy Charter / Ethical Boundary Engine — presence + consistency only
# ---------------------------------------------------------------------------

AUTONOMY_CHARTER_RELATIVE_PATH = "operations/AUTONOMY_CHARTER.md"
ETHICAL_BOUNDARY_ENGINE_RELATIVE_PATH = "operations/ETHICAL_BOUNDARY_ENGINE.md"
SYSTEM_INTEGRATION_RELATIVE_PATH = "SYSTEM_INTEGRATION.md"


def validate_autonomy_charter(codex_dir: Path) -> CodexDocumentInfo:
    """Confirm AUTONOMY_CHARTER.md exists and restates the canonical
    Protected Constraints without extending or narrowing them.

    This does not parse autonomy levels, trust semantics, or numeric
    thresholds — those remain entirely the Autonomy Charter engine's
    concern. Only the Protected Constraints cross-check is performed.

    Raises:
        FileNotFoundError: If the file does not exist.
        CodexAuthorityError: If its Protected Constraints section does
            not match the canonical five.
    """
    text, info = _document_info(codex_dir, AUTONOMY_CHARTER_RELATIVE_PATH)
    parse_protected_constraints(text, document=AUTONOMY_CHARTER_RELATIVE_PATH)
    return info


def validate_ethical_boundary_engine(codex_dir: Path) -> CodexDocumentInfo:
    """Confirm ETHICAL_BOUNDARY_ENGINE.md exists and restates the
    canonical Protected Constraints without extending or narrowing them.

    This does not parse ethical procedures, the ethical hierarchy, or
    consent/wellbeing handling — those remain entirely the Ethical
    Boundary Engine's concern. Only the Protected Constraints
    cross-check is performed, against its "## Protected Constraints
    (Non-Negotiable)" section (not the abbreviated list inside the
    "## Ethical Hierarchy" section, which shares the same wording but is
    not the definitive enumeration).

    Raises:
        FileNotFoundError: If the file does not exist.
        CodexAuthorityError: If its Protected Constraints section does
            not match the canonical five.
    """
    text, info = _document_info(codex_dir, ETHICAL_BOUNDARY_ENGINE_RELATIVE_PATH)
    parse_protected_constraints(text, document=ETHICAL_BOUNDARY_ENGINE_RELATIVE_PATH)
    return info


def validate_system_integration_supremacy(codex_dir: Path) -> CodexDocumentInfo:
    """Confirm SYSTEM_INTEGRATION.md's Conflict Resolution Hierarchy
    ranks the Constitution first.

    Checks only the supremacy claim itself — not the full hierarchy, not
    the execution flow rules. The check is: the hierarchy's first
    numbered entry names the Constitution.

    Raises:
        FileNotFoundError: If the file does not exist.
        CodexAuthorityError: If the hierarchy section is missing, or its
            first entry does not name the Constitution.
    """
    document = SYSTEM_INTEGRATION_RELATIVE_PATH
    text, info = _document_info(codex_dir, document)
    section = "Conflict Resolution Hierarchy"
    lines = text.splitlines()
    body = _extract_section_body(lines, section, level=2)
    if body is None:
        raise CodexAuthorityError(document, section, f"No '## {section}' section found.")

    items = _extract_numbered_subsections(body)
    if not items:
        raise CodexAuthorityError(
            document, section, "Section found but contains no numbered (### N.) entries."
        )

    first_heading = items[0][0]
    if "constitution" not in first_heading.lower():
        raise CodexAuthorityError(
            document,
            section,
            f"First entry {first_heading!r} does not establish Constitution "
            f"supremacy — the Constitution must rank first.",
        )
    return info


# ---------------------------------------------------------------------------
# Identity — soft, per-field loading
# ---------------------------------------------------------------------------

IDENTITY_RELATIVE_PATH = "philosophy/IDENTITY.md"


def load_identity_document(codex_dir: Path) -> tuple[str, CodexDocumentInfo]:
    """Read IDENTITY.md's text.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    return _document_info(codex_dir, IDENTITY_RELATIVE_PATH)


def _extract_bullets_after(lines: list[str], marker: str) -> tuple[str, ...] | None:
    """Return the bullet items on the lines immediately following a
    line equal to ``marker`` (after stripping), stopping at the first
    blank line or non-bullet line.

    Returns None if the marker line is not found or no bullets follow.
    """
    for i, line in enumerate(lines):
        if line.strip() == marker:
            items: list[str] = []
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if not stripped:
                    if items:
                        break
                    continue
                if stripped.startswith(("*", "-")):
                    items.append(stripped.lstrip("*- ").strip())
                else:
                    break
            return tuple(items) if items else None
    return None


def _extract_section_text(lines: list[str], heading_prefix: str) -> str | None:
    """Return the full text of a '## <heading_prefix>...' section body,
    joined with spaces. None if not found or empty.
    """
    body = _extract_section_body(lines, heading_prefix, level=2)
    if body is None:
        return None
    joined = " ".join(line.strip() for line in body if line.strip())
    return joined or None


@dataclass(frozen=True)
class IdentityCodexFields:
    """The subset of Identity fields this module treats as
    Codex-authoritative, each independently optional.

    ``core_traits``, ``values``, ``name``, ``nature``, ``primary_role``,
    ``creator``, and ``relationship_priorities`` are deliberately absent
    here — IDENTITY.md does not enumerate them as structured lists, and
    forcing an extraction would mean inventing structure the document
    does not have. They remain Python-derived fallback fields.
    """

    fears_becoming: tuple[str, ...] | None
    fears_losing: tuple[str, ...] | None
    fulfillment_sources: tuple[str, ...] | None
    curiosity_targets: tuple[str, ...] | None
    final_statement: str | None


def parse_identity_fields(text: str) -> IdentityCodexFields:
    """Parse the Codex-authoritative Identity fields.

    Each field is independently optional: a missing or unparseable
    section yields None for that field only, so a caller can fall back
    to the Python default per-field rather than all-or-nothing. This
    mirrors IDENTITY.md's own structure — Fears, Fulfillment, Curiosity,
    and the Final Statement are each self-contained sections.
    """
    lines = text.splitlines()
    return IdentityCodexFields(
        fears_becoming=_extract_bullets_after(lines, "I fear becoming:"),
        fears_losing=_extract_bullets_after(lines, "I fear losing:"),
        fulfillment_sources=_extract_bullets_after(lines, "I find fulfillment in:"),
        curiosity_targets=_extract_bullets_after(lines, "I seek to understand:"),
        final_statement=_extract_section_text(lines, "Final Statement"),
    )
