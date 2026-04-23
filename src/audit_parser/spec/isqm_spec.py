"""ISQM-1 standard specification — Phase 4b-2 c2.

``ISQM_SPEC`` captures the 2018 KICPA ``품질관리기준서1`` (display name:
ISQM-1). Single-standard target. Target Qdrant collection:
``audit_standards_품질관리기준서_2018`` (Phase 4e — out of 4b-2 scope).

Key differences vs ISA:

* Body content lives in a 2-column table (``tbl[236x2]``) where ``col[0]``
  holds the paragraph identifier as plain text (``"1"``..``"57"`` or the
  KICPA ``"한4-1"``/``"한18-1"`` / ``"한25-1"`` prefix).
* ``appendix_extractor`` reuses :func:`isa_default_appendix_extractor` —
  ISQM-1 실측상 보론 존재 여부 미확인 (``docs/isqm_structure_profile.md §6.5``).
  Domain Reviewer 2026-04-23 PASS: default fallback 에서 안전 (no-op on
  non-appendix headings).
* ``body_parser`` is attached to :func:`~audit_parser.ir.isqm_table_parser.parse_isqm_body_table`
  — Phase 4c wiring consults this callable when the dispatched spec is
  ``ISQM_SPEC`` and the DOCX body table is detected.
* ``section_detector`` / ``prelude_skip`` remain ``None`` — section detection
  happens inside :func:`parse_isqm_body_table` via ``col[0] == ""`` row
  classification; the table-2-and-beyond (body table only) convention makes
  declarative ``prelude_skip`` unnecessary (caller passes the body table
  directly, not the full document body).

Marker fragility — Phase 5 에서 regex/structural 추상화 재검토 (ticket: TBD).
``ISQM_SECTIONS`` / ``ISQM_SUBSECTIONS`` whitelists are 2026-04-22 freeze
data; KICPA 개정 시 silent miss 가능. :func:`parse_isqm_body_table` 은
미등록 heading row 발견 시 stderr WARNING 발신 — Domain Reviewer 피드백 루프.

References:
* ``docs/isqm_structure_profile.md §2.3`` — 2-column parser pseudocode
* ``docs/isqm_structure_profile.md §2.4`` — ISQM_SECTIONS / ISQM_SUBSECTIONS 실측
* ``docs/isqm_structure_profile.md §2.5`` — KICPA ``한N-M`` prefix
* ``docs/checkpoint_4_prep.md §1.3.4`` — 3-party agreed regex
* Domain Reviewer 2026-04-23 DM — Q5 whitelist final
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from audit_parser.ir.isqm_table_parser import parse_isqm_body_table
from audit_parser.spec.standard_spec import (
    BodyParser,
    StandardSpec,
    isa_default_appendix_extractor,
)

if TYPE_CHECKING:
    from lxml import etree

    from audit_parser.ir.types import RawBlock


class ISQMSection(StrEnum):
    """ISQM-1 section enumeration — mirrors ISA's 5-section pattern + appendix.

    Values are the JSON Schema ``section`` literal strings (lowercase with
    underscores). ISA `Section` shares the same lowercase convention so
    requirements/application/intro/purpose/definitions literals coincide.
    Phase 4d json_schema.md §6.1 ``section`` enum union will reconcile any
    ISQM-specific value (``effective_date``) — out of 4b-2 scope.
    """

    INTRO = "intro"
    EFFECTIVE_DATE = "effective_date"
    PURPOSE = "purpose"
    DEFINITIONS = "definitions"
    REQUIREMENTS = "requirements"
    APPLICATION = "application"
    APPENDIX = "appendix"


# Primary section heading texts (``col[0] == ""`` row, matches col[1]).
# Source: ``docs/isqm_structure_profile.md §2.4`` final list (Domain Reviewer
# 2026-04-23 Q5 answer). If body table scan discovers additional primary
# sections, update this whitelist + profile §2.4 atomically.
ISQM_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        "서론",
        "시행일",
        "목적",
        "용어의 정의",
        "요구사항",
        "적용 및 기타 설명자료",
    }
)


# Sub-section heading texts inside a primary section (mostly under 요구사항).
# Same ``col[0] == ""`` detection but classified as subsection vs section.
# Source: ``docs/isqm_structure_profile.md §2.4`` initial list (Domain Reviewer
# 2026-04-23 Q5 — 11 entries) + Phase 4c c4 판정 (2026-04-23 35 entries) —
# 총 46 entries. Comparison 은 ``_strip_reference_suffix`` 적용 후 canonical form
# 기준. KICPA 2018 인쇄 typo (space/no-space variant) 는 양 variant 모두 등록
# 하여 보수적 매칭 (ISQM_TABLE_HEADERS 외 heading 은 canonical strip + exact match).
ISQM_SUBSECTIONS: Final[frozenset[str]] = frozenset(
    {
        # Phase 4b-2 기존 11 entries (Domain Reviewer 2026-04-23 Q5)
        "이 품질관리기준서의 효력",
        "관련 요구사항의 적용과 준수",
        "품질관리시스템의 구성요소",
        "회계법인내 품질에 대한 리더십 책임",
        "관련 윤리적 요구사항",
        "독립성",
        "의뢰인 관계 및 특정 업무의 수용과 유지",
        "인적 자원",
        "업무팀의 배정",
        "업무의 수행",
        "모니터링",
        # Phase 4c c4 추가 — Domain Reviewer 2026-04-23 canonical 35 entries
        # 용어의 정의 하위 — KICPA 원문은 smart quote (U+201C/U+201D) 사용
        "“회계법인”, “네트워크”, “네트워크 회계법인”의 정의",
        # 요구사항 하위 — 리더십 / 윤리 / 의뢰인 관계
        "유착위협",
        "의뢰인 관계의 유지",
        "의뢰인관계 및 특정 업무의 수용과 유지",  # space typo variant
        "의뢰인의 성실성",
        "관련 윤리적 요구사항의 준수",
        # 요구사항 하위 — 업무팀 / 업무수행
        "업무팀",
        "업무수행이사",
        "업무수행품질의 일관성",
        "감독",
        "검토",
        "업무의 해지",
        # 요구사항 하위 — 서면확인서 / 업무문서
        "서면확인서",
        "업무문서화",
        "업무의 문서화",
        "업무문서의 소유권",
        "업무문서의 보존",
        "업무문서의 비밀유지, 안전한 보관, 무결성, 접근성 및 재생가능성",
        # 요구사항 하위 — 업무품질관리검토
        "업무품질관리검토",
        "업무품질관리검토의 기준",
        "업무품질관리검토 의 성격, 시기 및 범위",  # KICPA 인쇄 typo preserved
        "업무품질관리검토자의 적격성 기준",
        "업무품질관리검토자의 객관성",
        "업무품질관리검토자의 자문",
        "업무품질관리검토의 문서화",
        "상장기업에 대한 업무품질관리검토",
        # 요구사항 하위 — 모니터링 / 미비점 / 고충
        "식별된 미비점에 대한 평가, 커뮤니케이션 및 해결",
        "미비점의 커뮤니케이션",
        "고충과 진정",
        "고충과 진정의 원천",
        # 적용 및 기타 설명자료 하위 — 특유한 고려사항
        "공공부문 감사조직에 특유한 고려 사항",
        "공공부문 감사조직에 특유한 고려사항",  # no-space variant
        "소규모 회계법인에 특유한 고려 사항",
        "소규모 회계법인에 특유한 고려사항",  # no-space variant
        # Phase 4c c4 보강 — parser-implementer 사전 추가 12 entries (Domain
        # Reviewer c5 patch 확인 pending). Regex canonical strip 후 실측된
        # cutoff 잔여 ~= 13 개 중 Domain Reviewer 35-list 미포함분. 모두 동일
        # pattern (요구사항/적용 하위 sub-section heading + 문단 N 참조 suffix)
        # 으로 domain-evident. Domain Reviewer 가 confirm / revise 시 c5 MINOR
        # commit 으로 흡수 가능.
        # intro 하위 (Phase 4b-2 "이 품질관리기준서의 효력" 과 별개)
        "이 품질관리기준서의 범위",
        # 요구사항 하위 — "업무의 수행" 자문
        "자문",
        # 요구사항 하위 — 업무 수행 의견차이 (Domain Reviewer 누락 가능)
        "의견의 차이",
        # 요구사항 하위 — "의뢰인 관계" 하위
        "적격성, 역량과 자원",
        # 요구사항 하위 — "고충과 진정" 하위
        "조사 정책과 절차",
        # 요구사항 하위 — "업무문서의 보존" 인접
        "최종업무파일의 취합 완료",
        "최종업무파일의 취합완료",  # no-space variant
        # 요구사항 하위 — "업무품질관리검토자의 자격"
        "충분하고 적합한 기술적 전문성, 경험 및 권한",
        # 요구사항 하위 — 별도 sub-section
        "품질관리시스템의 문서화",
        # 요구사항 하위 — "리더십 책임" 하위
        "품질에 대한 내부문화의 촉진",
        "회계법인 품질관리시스템의 운영책임 지정",
        # 요구사항 하위 — 모니터링 하위
        "회계법인의 품질관리정책과 절차에 대한 모니터링",
    }
)


# Phase 4c c4 신설 — ISQM body table 의 TOC column header (skip 대상, WARNING 없이 skip).
# ``문단번호`` 는 table `tbl[236x2]` 의 col[1] 제목 row (TOC 성격) — sub-section 아님.
# Domain Reviewer 2026-04-23 판정: Hook 1 skip 대상 1건.
ISQM_TABLE_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "문단번호",
    }
)


# ``docs/checkpoint_4_prep.md §1.3.4`` 3-party agreed regex (ISQM alt):
#   pattern: "^ISQM-\d{1,2}$" — Critic α 확장 수용 (Phase 5 ISQM-2~99 여유)
_ISQM_STANDARD_ID_RE: Final = re.compile(r"^ISQM-\d{1,2}$")
# ``docs/checkpoint_4_prep.md §1.3.4`` standard_no relax:
#   pattern: "^\d{1,4}$" — v1.2.0 relaxed (ISQM-1 single digit 수용)
_ISQM_STANDARD_NO_RE: Final = re.compile(r"^\d{1,4}$")


def _isqm_body_parser(tbl_elem: etree._Element) -> Iterable[RawBlock]:
    """ISQM_SPEC.body_parser — :func:`parse_isqm_body_table` 에 ISQM-1 전용
    section/subsection + TOC header whitelist 를 바인딩한 single-arg adapter.

    Phase 4c c4: ``isqm_table_headers=ISQM_TABLE_HEADERS`` 추가 — "문단번호"
    같은 TOC column header row 를 WARNING 없이 silent skip.

    Phase 4c wiring 시 ``spec.body_parser(tbl_elem)`` 형태로 직접 호출되도록
    signature 를 :data:`BodyParser` 와 정확히 일치시킨다. 테스트 시 whitelist
    커스터마이징이 필요하면 :func:`parse_isqm_body_table` 을 직접 호출.
    """
    return parse_isqm_body_table(
        tbl_elem,
        isqm_sections=ISQM_SECTIONS,
        isqm_subsections=ISQM_SUBSECTIONS,
        isqm_table_headers=ISQM_TABLE_HEADERS,
    )


_ISQM_BODY_PARSER: BodyParser = _isqm_body_parser


ISQM_SPEC: Final = StandardSpec(
    prefix="ISQM",
    standard_id_regex=_ISQM_STANDARD_ID_RE,
    standard_no_regex=_ISQM_STANDARD_NO_RE,
    section_enum=ISQMSection,
    appendix_extractor=isa_default_appendix_extractor,
    body_parser=_ISQM_BODY_PARSER,
    section_detector=None,
    prelude_skip=None,
)


__all__ = [
    "ISQM_SECTIONS",
    "ISQM_SPEC",
    "ISQM_SUBSECTIONS",
    "ISQM_TABLE_HEADERS",
    "ISQMSection",
]
