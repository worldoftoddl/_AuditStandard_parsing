"""FRMK standard specification — Phase 4b-2 c3.

``FRMK_SPEC`` captures the 2022 KICPA ``인증업무개념체계`` (display name:
International Framework for Assurance Engagements). Single-document spec
identified internally as ``FRMK-1`` for naming harmonisation with ISA /
ISQM / ASSR. Target Qdrant collection: ``audit_standards_인증업무개념체계_2022``
(Phase 4e — out of 4b-2 scope).

Key differences vs ISA:

* Body content lives inside an outer ``tbl[3x3]`` wrapper. Recursive descent
  (Phase 4c wiring in ``docx_reader``) handles the descent; no body_parser
  override — ``body_parser`` stays ``None``.
* Heading 2 style IS present (21 entries, ``docs/framework_structure_profile.md
  §2.2``), so the default heading-based section detector is adequate;
  ``section_detector`` stays ``None``.
* ``prelude_skip`` is a marker predicate identifying the
  ``heading 2 == "문단번호"`` marker that terminates the 개정개요 prelude.
  Caller (Phase 4c md_parser) maintains ``in_prelude`` state and toggles
  off on ``True`` return, skipping the marker heading itself per Critic v1.1
  LOCK interpretation.
* ``appendix_extractor`` is :func:`_frmk_appendix_extractor` — a brand new
  FRMK-specific implementation. **Reusing ``isa_default_appendix_extractor``
  is explicitly forbidden** because FRMK ships both numbered appendices
  (``보론 1/2/3``) AND a single un-numbered ``보론: 역할과 책임`` that must
  be emitted as ``(None, "역할과 책임")`` (B-v2 ``special_appendix_name``
  channel, ``docs/framework_structure_profile.md §6.2`` + Critic P3 LOCK).
* Additional module-level helper :func:`normalize_framework_heading` strips
  the ``"서론1-4"``-style paragraph-range suffix from FRMK heading 2 text,
  preserving the range for provenance without contaminating the clean
  section name. Phase 4c md_parser will invoke this when
  ``spec is FRMK_SPEC``.

Period variant (``보론.`` instead of ``보론:``) is accepted pre-emptively on
Critic 2026-04-23 verbal Q3 recommendation (cost 0, future-proofs against
KICPA style drift).

Marker fragility — Phase 5 에서 regex/structural 추상화 재검토 (ticket: TBD).
현 marker (heading_2=='문단번호', prefix startswith check) 는 2026-04-22
freeze data 기준. KICPA 개정 시 silent miss 가능.

References:
* ``docs/framework_structure_profile.md §2.3`` — heading_range_strip 규칙
* ``docs/framework_structure_profile.md §2.4`` — prelude_end_marker ``문단번호``
* ``docs/framework_structure_profile.md §6.2`` (B-v2) — un-numbered 보론
* ``docs/json_schema.md §7.2.1a`` — special_appendix_name 채널
* ``docs/checkpoint_4_prep.md §1.3.4`` — 3-party agreed regex
* Critic 2026-04-23 DM — P3 independent extractor + Q3 period variant
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from audit_parser.spec.standard_spec import PreludeSkip, StandardSpec

if TYPE_CHECKING:
    from audit_parser.ir.types import RawBlock


class FRMKSection(StrEnum):
    """FRMK-1 section enumeration — 17 entries per ``docs/framework_structure_profile.md §4``.

    Covers all heading 2 entries in the 2022 KICPA 인증업무개념체계 body
    (문단번호 / 서론1-4 / 윤리 원칙과 품질관리기준5-9 / 인증업무의 의의10-11 /
    ...), after ``normalize_framework_heading`` strips the paragraph-range
    suffix. Lowercase English underscore form for JSON Schema section literal
    (Phase 4d union reconciliation).
    """

    INTRO = "intro"
    ETHICAL_REQUIREMENTS_AND_QUALITY = "ethical_requirements_and_quality"
    ASSURANCE_DEFINITION = "assurance_definition"
    ATTESTATION_VS_DIRECT = "attestation_vs_direct"
    REASONABLE_VS_LIMITED_ASSURANCE = "reasonable_vs_limited_assurance"
    FRAMEWORK_SCOPE = "framework_scope"
    NON_ASSURANCE_REPORTS = "non_assurance_reports"
    ASSURANCE_PRECONDITIONS = "assurance_preconditions"
    ASSURANCE_COMPONENTS = "assurance_components"
    THREE_PARTY_RELATIONSHIP = "three_party_relationship"
    UNDERLYING_SUBJECT_MATTER = "underlying_subject_matter"
    CRITERIA = "criteria"
    EVIDENCE = "evidence"
    ASSURANCE_REPORT = "assurance_report"
    OTHER_MATTERS = "other_matters"
    INAPPROPRIATE_USE_OF_NAME = "inappropriate_use_of_name"
    APPENDIX = "appendix"


# ``docs/checkpoint_4_prep.md §1.3.4`` 3-party agreed regex (FRMK alt):
#   pattern: "^FRMK-\d$" — A3 harmonisation (prefix-N 균일화)
_FRMK_STANDARD_ID_RE: Final = re.compile(r"^FRMK-\d$")
# ``docs/checkpoint_4_prep.md §1.3.4`` standard_no relax:
#   pattern: "^\d{1,4}$" — FRMK-1 single digit
_FRMK_STANDARD_NO_RE: Final = re.compile(r"^\d{1,4}$")


# ``보론 1: ...`` / ``보론1: ...`` / ``보론  1 : ...`` — numbered 보론 prefix.
_FRMK_APPENDIX_NUMBERED_RE: Final = re.compile(r"^보론\s*(\d+)\s*[:.]?\s*(.*)")

# ``보론: 역할과 책임`` / ``보론 : 역할과 책임`` / Critic Q3 verbal period variant
# ``보론. 역할과 책임`` — un-numbered 보론 prefix with ``:`` or ``.`` separator.
# Must NOT match ``보론 1: ...`` (numbered) — numbered regex takes precedence.
_FRMK_APPENDIX_UNNUMBERED_RE: Final = re.compile(r"^보론\s*[:.]\s*(.*)")


def _frmk_appendix_extractor(heading: str) -> tuple[int | None, str | None]:
    """FRMK-specific appendix extractor — ``docs/json_schema.md §7.2.1a`` B-v2.

    Contract:

    * ``"보론 1: ..."`` → ``(1, None)`` (numbered takes precedence)
    * ``"보론 2: 입증업무와 직접업무"`` → ``(2, None)``
    * ``"보론: 역할과 책임"`` → ``(None, "역할과 책임")`` (un-numbered, special
      name in payload ``special_appendix_name`` field)
    * ``"보론. 역할과 책임"`` → ``(None, "역할과 책임")`` (period variant —
      Critic 2026-04-23 Q3 verbal, future-proofing)
    * Non-appendix heading → ``(None, None)``

    The caller (md_parser) iterates ``reversed(heading_trail)`` and stops on
    the first non-``(None, None)`` tuple. If both a numbered ``보론 1``
    parent heading and a ``보론: 역할과 책임`` inner heading coexist in the
    trail (not observed in ``framework_structure_profile.md §2.2`` but
    defensive), the inner-most match wins per reversed iteration.

    Examples:
        >>> _frmk_appendix_extractor("보론 1: 회계감사기준위원회가 제정한 기준")
        (1, None)
        >>> _frmk_appendix_extractor("보론: 역할과 책임")
        (None, '역할과 책임')
        >>> _frmk_appendix_extractor("보론. 역할과 책임")
        (None, '역할과 책임')
        >>> _frmk_appendix_extractor("서론")
        (None, None)
    """
    stripped = heading.strip()
    numbered = _FRMK_APPENDIX_NUMBERED_RE.match(stripped)
    if numbered:
        return int(numbered.group(1)), None
    unnumbered = _FRMK_APPENDIX_UNNUMBERED_RE.match(stripped)
    if unnumbered:
        name = unnumbered.group(1).strip()
        return None, name
    return None, None


# ``서론1-4`` / ``삼자관계27-38`` / ``인증인 명칭의 부적절한 사용96`` — heading
# text 에 embedded paragraph-range suffix. Regex captures optional range.
_FRMK_HEADING_RANGE_RE: Final = re.compile(r"(\d+(?:-\d+)?)\s*$")


def normalize_framework_heading(text: str) -> tuple[str, str | None]:
    """Strip the ``"...NN-MM"`` paragraph-range suffix from an FRMK heading 2 text.

    Returns ``(clean_heading, range_suffix)``. The suffix (e.g. ``"1-4"`` or
    ``"26"``) is preserved for provenance — Phase 4c md_parser/ md_renderer
    will expose it via heading_trail metadata (TBD). The clean heading is
    used for section enum mapping and heading_trail display.

    ``보론`` headings retain their original text (no suffix to strip) — the
    appendix_extractor consumes the raw heading.

    Examples:
        >>> normalize_framework_heading("서론1-4")
        ('서론', '1-4')
        >>> normalize_framework_heading("삼자관계27-38")
        ('삼자관계', '27-38')
        >>> normalize_framework_heading("인증업무의 구성 요소26")
        ('인증업무의 구성 요소', '26')
        >>> normalize_framework_heading("보론 1: 회계감사기준위원회가 제정한 기준")
        ('보론 1: 회계감사기준위원회가 제정한 기준', None)
        >>> normalize_framework_heading("보론: 역할과 책임")
        ('보론: 역할과 책임', None)
        >>> normalize_framework_heading("  문단번호  ")
        ('문단번호', None)
    """
    stripped = text.strip()
    if stripped.startswith("보론"):
        return stripped, None
    match = _FRMK_HEADING_RANGE_RE.search(stripped)
    if match is None:
        return stripped, None
    clean = stripped[: match.start()].rstrip()
    return clean, match.group(1)


def _frmk_prelude_skip(block: RawBlock) -> bool:
    """Marker matcher — ``True`` when the block is the ``"문단번호"`` heading 2
    that ends the 개정개요 prelude (``docs/framework_structure_profile.md §2.4``).

    Per Critic v1.1 LOCK interpretation (i): caller owns ``in_prelude`` flag
    and toggles off on ``True`` return, skipping the marker block itself.

    Implementation:
        * block.style must be ``"heading 2"`` (Word style id)
        * block.text stripped must start with ``"문단번호"`` (Critic verbal
          marker-fragility note — prefix match for whitespace tolerance)
    """
    return block.style == "heading 2" and block.text.strip().startswith("문단번호")


_FRMK_PRELUDE_SKIP: PreludeSkip = _frmk_prelude_skip


FRMK_SPEC: Final = StandardSpec(
    prefix="FRMK",
    standard_id_regex=_FRMK_STANDARD_ID_RE,
    standard_no_regex=_FRMK_STANDARD_NO_RE,
    section_enum=FRMKSection,
    appendix_extractor=_frmk_appendix_extractor,
    body_parser=None,
    section_detector=None,
    prelude_skip=_FRMK_PRELUDE_SKIP,
)


__all__ = [
    "FRMK_SPEC",
    "FRMKSection",
    "normalize_framework_heading",
]
