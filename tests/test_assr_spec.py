"""Tests for ``audit_parser.spec.assr_spec`` — Phase 4b-2 c3.

Scope:

* ``ASSR_SPEC`` invariants — prefix / regex / section_enum / extractor
* ``format_standard_id`` / ``validate_standard_id`` 3-4 digit 수용
* ``ASSRSection`` StrEnum values
* ``_assr_section_detector`` state machine transitions
  (``docs/assurance_other_structure_profile.md §2.3``)
* ``_assr_prelude_skip`` marker predicate (``"서론"`` match)
"""

from __future__ import annotations

import pytest

from audit_parser.ir.types import BlockKind, RawBlock
from audit_parser.spec import (
    ASSR_PRIMARY_SECTIONS,
    ASSR_SPEC,
    ASSRSection,
    isa_default_appendix_extractor,
)


def _make_block(
    text: str,
    *,
    style: str = "",
    kind: BlockKind = BlockKind.PARAGRAPH_BODY,
) -> RawBlock:
    return RawBlock(
        idx=0,
        kind=kind,
        text=text,
        style=style,
        num_id=None,
        ilvl=None,
    )


# ---------------------------------------------------------------------------
# ASSR_SPEC invariants
# ---------------------------------------------------------------------------


def test_assr_spec_prefix() -> None:
    assert ASSR_SPEC.prefix == "ASSR"


def test_assr_spec_standard_id_regex_pattern() -> None:
    """docs/checkpoint_4_prep.md §1.3.4 — 3-4 digit ISAE alt."""
    assert ASSR_SPEC.standard_id_regex.pattern == r"^ASSR-\d{3,4}$"


def test_assr_spec_standard_no_regex_pattern() -> None:
    assert ASSR_SPEC.standard_no_regex.pattern == r"^\d{1,4}$"


def test_assr_spec_section_enum_is_assr_section() -> None:
    assert ASSR_SPEC.section_enum is ASSRSection


def test_assr_spec_appendix_extractor_reuses_isa_default() -> None:
    """Domain Reviewer 2026-04-23 Q3 — ISA default fallback 조건부 OK.
    ASSR 보론 구조 실측 미완료, Phase 5 재검토 가능."""
    assert ASSR_SPEC.appendix_extractor is isa_default_appendix_extractor


def test_assr_spec_body_parser_is_none() -> None:
    """ASSR body 는 tbl[427x2] wrapper 내부지만 paragraph_id 가 numPr 에서 나옴.
    Phase 4c recursive descent 로 충분, body_parser 불필요."""
    assert ASSR_SPEC.body_parser is None


def test_assr_spec_section_detector_and_prelude_skip_attached() -> None:
    """ASSR 는 heading-N style 부재 → text-based detector + prelude marker 필수."""
    assert ASSR_SPEC.section_detector is not None
    assert ASSR_SPEC.prelude_skip is not None


# ---------------------------------------------------------------------------
# format_standard_id / validate_standard_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "standard_no,expected_id",
    [
        ("3000", "ASSR-3000"),
        ("3410", "ASSR-3410"),
        ("999", "ASSR-999"),
    ],
)
def test_assr_format_standard_id_valid(standard_no: str, expected_id: str) -> None:
    assert ASSR_SPEC.format_standard_id(standard_no) == expected_id


@pytest.mark.parametrize(
    "bad_standard_no",
    ["", "abc", "12345", "30"],
)
def test_assr_format_standard_id_rejects_bad_standard_no(bad_standard_no: str) -> None:
    with pytest.raises(ValueError):
        ASSR_SPEC.format_standard_id(bad_standard_no)


def test_assr_validate_accepts_scope_ids() -> None:
    ASSR_SPEC.validate_standard_id("ASSR-3000")
    ASSR_SPEC.validate_standard_id("ASSR-3410")


@pytest.mark.parametrize(
    "bad_id",
    ["ASSR-30", "ASSR-99999", "ASSR", "ASSR-", "ISA-200", "ASSR-3000a"],
)
def test_assr_validate_rejects_out_of_scope(bad_id: str) -> None:
    with pytest.raises(ValueError):
        ASSR_SPEC.validate_standard_id(bad_id)


# ---------------------------------------------------------------------------
# ASSRSection StrEnum
# ---------------------------------------------------------------------------


def test_assr_section_values() -> None:
    expected = {
        "intro",
        "effective_date",
        "purpose",
        "definitions",
        "requirements",
        "application",
        "appendix",
    }
    assert {member.value for member in ASSRSection} == expected


def test_assr_primary_sections_whitelist() -> None:
    expected = {
        "서론",
        "시행일",
        "목적",
        "용어의 정의",
        "요구사항",
        "적용 및 기타 설명자료",
    }
    assert ASSR_PRIMARY_SECTIONS == expected


# ---------------------------------------------------------------------------
# _assr_section_detector — state machine transitions (profile §2.3)
# ---------------------------------------------------------------------------


def test_section_detector_intro_from_none() -> None:
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("서론"), None)
    assert result == "intro"


def test_section_detector_effective_date() -> None:
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("시행일"), "intro")
    assert result == "effective_date"


def test_section_detector_purpose_from_primary() -> None:
    """첫 번째 `목적` — primary body 에서 definitions 로 전이."""
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("목적"), "effective_date")
    assert result == "purpose"


def test_section_detector_definitions_from_primary() -> None:
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("용어의 정의"), "purpose")
    assert result == "definitions"


def test_section_detector_requirements() -> None:
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("요구사항"), "definitions")
    assert result == "requirements"


def test_section_detector_second_purpose_transitions_to_application() -> None:
    """두 번째 `목적` — requirements 이후 등장이므로 application 전환 marker.
    docs/assurance_other_structure_profile.md §2.3."""
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("목적"), "requirements")
    assert result == "application"


def test_section_detector_explicit_application_heading() -> None:
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("적용 및 기타 설명자료"), "requirements")
    assert result == "application"


def test_section_detector_second_definitions_no_transition() -> None:
    """`용어의 정의` 가 application 내부 재등장 시 전이 없음 (current 유지)."""
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("용어의 정의"), "application")
    assert result is None


def test_section_detector_non_heading_text_returns_none() -> None:
    assert ASSR_SPEC.section_detector is not None
    assert ASSR_SPEC.section_detector(_make_block("일반 문단 본문"), "requirements") is None


def test_section_detector_whitespace_tolerated() -> None:
    assert ASSR_SPEC.section_detector is not None
    result = ASSR_SPEC.section_detector(_make_block("  서론  "), None)
    assert result == "intro"


# ---------------------------------------------------------------------------
# _assr_prelude_skip — marker matcher
# ---------------------------------------------------------------------------


def test_prelude_skip_matches_seoron() -> None:
    assert ASSR_SPEC.prelude_skip is not None
    assert ASSR_SPEC.prelude_skip(_make_block("서론")) is True


def test_prelude_skip_matches_whitespace_padded_seoron() -> None:
    assert ASSR_SPEC.prelude_skip is not None
    assert ASSR_SPEC.prelude_skip(_make_block("  서론  ")) is True


def test_prelude_skip_does_not_match_prelude_headings() -> None:
    """개정개요 prelude 내부 heading 들은 매칭되어서는 안 됨."""
    assert ASSR_SPEC.prelude_skip is not None
    for prelude_text in ["개요", "개정 배경", "개정 기준서의 주요 내용", "주요 개정 이슈"]:
        assert ASSR_SPEC.prelude_skip(_make_block(prelude_text)) is False


def test_prelude_skip_does_not_match_other_headings() -> None:
    assert ASSR_SPEC.prelude_skip is not None
    for text in ["시행일", "목적", "요구사항", "용어의 정의", "적용 및 기타 설명자료"]:
        assert ASSR_SPEC.prelude_skip(_make_block(text)) is False


# ---------------------------------------------------------------------------
# Per-spec regex alt integrity (c4 drift guard)
# ---------------------------------------------------------------------------


def test_assr_regex_accepts_isae_3000_and_3410() -> None:
    for candidate in ["ASSR-3000", "ASSR-3410", "ASSR-999"]:
        assert ASSR_SPEC.standard_id_regex.fullmatch(candidate) is not None


def test_assr_regex_rejects_isqm_frmk_isa() -> None:
    for candidate in ["ISA-200", "ISQM-1", "FRMK-1"]:
        assert ASSR_SPEC.standard_id_regex.fullmatch(candidate) is None
