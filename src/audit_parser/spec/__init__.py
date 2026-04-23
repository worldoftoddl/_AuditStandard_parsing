"""Standard specification registry — Phase 4b abstraction over prefix-specific parsing.

Phase 4b-1 provides the :class:`StandardSpec` dataclass and ``ISA_SPEC`` default
that preserves Phase 1-3 ISA behavior. Phase 4b-2 adds three optional
dispatch-callable types (:data:`BodyParser` / :data:`SectionDetector` /
:data:`PreludeSkip`) and the non-ISA specs ``ISQM_SPEC`` / ``ASSR_SPEC`` /
``FRMK_SPEC``. The prefix dispatcher :func:`get_spec_for_standard_id` resolves
a ``standard_id`` string to its owning :class:`StandardSpec` via an O(1) dict
lookup — Critic 2026-04-23 P2 (a) choice.

See :mod:`audit_parser.spec.standard_spec` for the dataclass contract and
each ``*_spec`` module for spec-specific behaviour.
"""

from __future__ import annotations

from audit_parser.spec.assr_spec import ASSR_PRIMARY_SECTIONS, ASSR_SPEC, ASSRSection
from audit_parser.spec.frmk_spec import FRMK_SPEC, FRMKSection, normalize_framework_heading
from audit_parser.spec.isa_spec import ISA_SPEC
from audit_parser.spec.isqm_spec import (
    ISQM_SECTIONS,
    ISQM_SPEC,
    ISQM_SUBSECTIONS,
    ISQM_TABLE_HEADERS,
    ISQMSection,
)
from audit_parser.spec.standard_spec import (
    AppendixExtractor,
    BodyParser,
    PreludeSkip,
    SectionDetector,
    StandardSpec,
    isa_default_appendix_extractor,
)

# Prefix dispatcher registry — Critic 2026-04-23 P2 (a) LOCK.
# Phase 5 ISAE / ISRE 확장 시 dict entry 1줄 등록:
#     _SPEC_REGISTRY["ISAE"] = ISAE_SPEC  # ISAE-3400/3410 통합
#     _SPEC_REGISTRY["ISRE"] = ISRE_SPEC  # ISRE-2400/2410 통합
# Alt-order 의존 없음 — substring greedy 함정 회피 (prefix 간 substring 관계 없음
# + Phase 5 확장 시 `docs/checkpoint_4_prep.md §1.7.2` longer-prefix-first 규약).
_SPEC_REGISTRY: dict[str, StandardSpec] = {
    "ISA": ISA_SPEC,
    "ISQM": ISQM_SPEC,
    "ASSR": ASSR_SPEC,
    "FRMK": FRMK_SPEC,
}


def get_spec_for_standard_id(standard_id: str) -> StandardSpec:
    """Resolve ``standard_id`` to the owning :class:`StandardSpec`.

    Two-step fail-fast (Critic 2026-04-23 LOCK):

    1. Split on first ``-`` to extract the prefix. Missing separator
       (``"FRMK"``, ``"ISA"``, prefix-only inputs) → ``ValueError``.
    2. ``_SPEC_REGISTRY`` dict lookup. Unknown prefix (``"XXXX"``, typos,
       out-of-scope prefixes like ``"ISAE"``) → ``ValueError`` listing the
       known prefix set.
    3. Spec's own ``validate_standard_id`` regex fullmatch — catches
       intra-prefix violations (``"ISA-1"`` below the 3-digit minimum,
       ``"ISQM-100"`` above the 2-digit maximum, ``"ISA-220R"`` with
       unsupported Revised suffix).

    Args:
        standard_id: Frontmatter ``standard_id`` string as read from MD.

    Returns:
        The owning ``StandardSpec`` instance.

    Raises:
        ValueError: on any of the three failure modes above. Caller (Phase
            4c md_parser / md_renderer dispatch wiring) may surface as fatal
            since any well-formed MD passes all three checks.

    Examples:
        >>> get_spec_for_standard_id("ISA-200").prefix
        'ISA'
        >>> get_spec_for_standard_id("ISQM-1").prefix
        'ISQM'
        >>> get_spec_for_standard_id("ASSR-3000").prefix
        'ASSR'
        >>> get_spec_for_standard_id("FRMK-1").prefix
        'FRMK'
    """
    prefix, sep, _tail = standard_id.partition("-")
    if sep != "-":
        raise ValueError(
            f"standard_id {standard_id!r} missing '-' separator; "
            f"prefix-only identifiers are not supported"
        )
    spec = _SPEC_REGISTRY.get(prefix)
    if spec is None:
        known = sorted(_SPEC_REGISTRY)
        raise ValueError(
            f"unknown prefix {prefix!r} for standard_id {standard_id!r} — "
            f"known prefixes: {known}"
        )
    spec.validate_standard_id(standard_id)
    return spec


__all__ = [
    "ASSR_PRIMARY_SECTIONS",
    "ASSR_SPEC",
    "ASSRSection",
    "AppendixExtractor",
    "BodyParser",
    "FRMK_SPEC",
    "FRMKSection",
    "ISA_SPEC",
    "ISQM_SECTIONS",
    "ISQM_SPEC",
    "ISQM_SUBSECTIONS",
    "ISQM_TABLE_HEADERS",
    "ISQMSection",
    "PreludeSkip",
    "SectionDetector",
    "StandardSpec",
    "get_spec_for_standard_id",
    "isa_default_appendix_extractor",
    "normalize_framework_heading",
]
