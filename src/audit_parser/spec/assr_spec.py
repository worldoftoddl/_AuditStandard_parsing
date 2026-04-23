"""ASSR standard specification — Phase 4b-2 c3.

``ASSR_SPEC`` targets the KICPA Korean rendering of IAASB **ISAE 3000
(Revised)** — the single "역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준"
(2022년 개정). Target Qdrant collection: ``audit_standards_기타인증업무기준_2022``
(Phase 4e — out of 4b-2 scope).

Key differences vs ISA:

* Body content sits inside a ``tbl[427x2]`` wrapper table that is *purely
  visual* (2-column, layout only — paragraph_id comes from ``numPr`` as in
  ISA). Recursive descent (Phase 4c wiring in ``docx_reader``) walks the
  wrapper; no specialised body_parser is needed, so
  ``body_parser`` stays ``None``.
* Heading-N style 이 없음. Section 경계는 text-match state machine
  (:func:`_assr_section_detector`) 로 판별 — ``서론`` / ``시행일`` / ``목적`` /
  ``용어의 정의`` / ``요구사항`` / ``적용 및 기타 설명자료`` 전이 추적.
* ``prelude_skip`` is a stateless marker predicate identifying the **end**
  of the 개정개요 prelude — the first ``"서론"`` paragraph inside the
  ``tbl[427x2]`` body table. Caller (Phase 4c ``md_parser``) maintains the
  ``in_prelude`` flag and toggles it off on ``True`` return, skipping the
  marker block itself per Critic v1.1 LOCK interpretation.
* ``appendix_extractor`` reuses :func:`isa_default_appendix_extractor`.
  ASSR profile §6 does not list appendices (body-table focus); IAASB ISAE
  3000 has a single un-numbered "Appendix: Application of the general
  requirements..." whose KICPA translation may or may not be present. Domain
  Reviewer 2026-04-23 Q3: ISA fallback OK for 4b-2; re-examine in Phase 4c
  after MD rendering. Should a title-carrying un-numbered appendix appear,
  switching to a Domain Reviewer-sanctioned override is a MINOR bump.

Marker fragility — Phase 5 에서 regex/structural 추상화 재검토 (ticket: TBD).
현 section text literal set (``ASSR_PRIMARY_SECTIONS``) 는 2026-04-22 freeze
data 기준. KICPA 개정 시 silent miss 가능.

References:
* ``docs/assurance_other_structure_profile.md §2.3`` — section state machine
* ``docs/assurance_other_structure_profile.md §2.4`` — prelude skip 규약
* ``docs/checkpoint_4_prep.md §1.3.4`` — 3-party agreed regex
* Domain Reviewer 2026-04-23 DM Q3 — ISA default fallback 조건부 동의
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from audit_parser.spec.standard_spec import (
    PreludeSkip,
    SectionDetector,
    StandardSpec,
    isa_default_appendix_extractor,
)

if TYPE_CHECKING:
    from audit_parser.ir.types import RawBlock


class ASSRSection(StrEnum):
    """ASSR-3000 section enumeration — 7-entry set aligned with ISAE 3000
    layout. Lowercase literals coincide with ISA's ``Section`` where shared
    (intro, purpose, definitions, requirements, application, appendix).
    """

    INTRO = "intro"
    EFFECTIVE_DATE = "effective_date"
    PURPOSE = "purpose"
    DEFINITIONS = "definitions"
    REQUIREMENTS = "requirements"
    APPLICATION = "application"
    APPENDIX = "appendix"


# ASSR primary section heading texts — used by the section detector state
# machine. Source: ``docs/assurance_other_structure_profile.md §2.3``.
# ``목적`` / ``용어의 정의`` appear **twice** (once in body_primary, once in
# application); disambiguation happens in the state machine, not the set.
ASSR_PRIMARY_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        "서론",
        "시행일",
        "목적",
        "용어의 정의",
        "요구사항",
        "적용 및 기타 설명자료",
    }
)


# ``docs/checkpoint_4_prep.md §1.3.4`` 3-party agreed regex (ASSR alt):
#   pattern: "^ASSR-\d{3,4}$" — 향후 ISAE 3400/3410 통합 여지
_ASSR_STANDARD_ID_RE: Final = re.compile(r"^ASSR-\d{3,4}$")
# ``docs/checkpoint_4_prep.md §1.3.4`` standard_no relax:
#   pattern: "^\d{1,4}$"
_ASSR_STANDARD_NO_RE: Final = re.compile(r"^\d{1,4}$")


def _assr_section_detector(block: RawBlock, current_section: str | None) -> str | None:
    """Text-based section state machine for ASSR — implements the transition
    table from ``docs/assurance_other_structure_profile.md §2.3``.

    Rules:

    * ``"서론"`` → ``"intro"`` (always)
    * ``"시행일"`` → ``"effective_date"``
    * ``"요구사항"`` → ``"requirements"``
    * ``"목적"`` — ``"purpose"`` when current is ``None`` / ``intro`` /
      ``effective_date`` (primary body); ``"application"`` when current is
      already ``"requirements"`` (second occurrence marks application start)
    * ``"용어의 정의"`` — ``"definitions"`` when primary, no transition inside
      application (stays at current)
    * ``"적용 및 기타 설명자료"`` → ``"application"``
    * any other text → ``None`` (no transition; caller keeps current)

    Returns the new section name (str) when a transition fires, or ``None``
    to indicate no change. The caller (Phase 4c md_parser) keeps track of
    current_section and applies the update.
    """
    text = block.text.strip()
    if text == "서론":
        return "intro"
    if text == "시행일":
        return "effective_date"
    if text == "요구사항":
        return "requirements"
    if text == "적용 및 기타 설명자료":
        return "application"
    if text == "목적":
        if current_section == "requirements":
            return "application"
        return "purpose"
    if text == "용어의 정의":
        if current_section == "requirements" or current_section == "application":
            return None
        return "definitions"
    return None


def _assr_prelude_skip(block: RawBlock) -> bool:
    """Marker matcher returning ``True`` when the block is the first ``"서론"``
    inside the body table — the prelude-end marker.

    Per Critic v1.1 LOCK interpretation (i): caller owns the ``in_prelude``
    flag, this predicate only flags the marker block. The caller toggles
    ``in_prelude=False`` on ``True`` AND skips the marker itself (the
    downstream section_detector re-introduces ``"intro"`` once the marker
    block is processed as the state-entry signal).

    Stateless per-block check is sufficient because the first ``"서론"`` is
    structurally equivalent to the marker — any earlier prelude blocks
    contain ``개요 / 개정 배경 / 주요 개정 내용 / 주요 개정 이슈`` text which
    never matches ``"서론"``. The ``RawBlock`` objects emitted by
    ``docx_reader`` do not yet carry container provenance in 4b-2; Phase 4c
    wiring will combine this predicate with container introspection (must
    be inside a ``<w:tbl>``) to disambiguate if necessary.
    """
    return block.text.strip() == "서론"


_ASSR_SECTION_DETECTOR: SectionDetector = _assr_section_detector
_ASSR_PRELUDE_SKIP: PreludeSkip = _assr_prelude_skip


ASSR_SPEC: Final = StandardSpec(
    prefix="ASSR",
    standard_id_regex=_ASSR_STANDARD_ID_RE,
    standard_no_regex=_ASSR_STANDARD_NO_RE,
    section_enum=ASSRSection,
    appendix_extractor=isa_default_appendix_extractor,
    body_parser=None,
    section_detector=_ASSR_SECTION_DETECTOR,
    prelude_skip=_ASSR_PRELUDE_SKIP,
)


__all__ = [
    "ASSR_PRIMARY_SECTIONS",
    "ASSR_SPEC",
    "ASSRSection",
]
