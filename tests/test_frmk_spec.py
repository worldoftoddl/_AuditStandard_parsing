"""Tests for ``audit_parser.spec.frmk_spec`` — Phase 4b-2 c3.

Scope:

* ``FRMK_SPEC`` invariants — prefix / regex / section_enum
* ``format_standard_id`` / ``validate_standard_id`` 1 digit 수용
* ``FRMKSection`` StrEnum values (17-entry)
* ``_frmk_appendix_extractor`` B-v2 4-case + period variant
  (``docs/framework_structure_profile.md §6.2`` + Critic Q3 verbal)
* ``_frmk_prelude_skip`` marker predicate (heading 2 == "문단번호")
* ``normalize_framework_heading`` heading_range_strip contract
* heading_trail reversed 순회 시 numbered vs un-numbered precedence
"""

from __future__ import annotations

import pytest

from audit_parser.ir.types import BlockKind, RawBlock
from audit_parser.spec import (
    FRMK_SPEC,
    FRMKSection,
    isa_default_appendix_extractor,
    normalize_framework_heading,
)
from audit_parser.spec.frmk_spec import _frmk_appendix_extractor


def _make_block(text: str, *, style: str = "") -> RawBlock:
    return RawBlock(
        idx=0,
        kind=BlockKind.PARAGRAPH_BODY,
        text=text,
        style=style,
        num_id=None,
        ilvl=None,
    )


# ---------------------------------------------------------------------------
# FRMK_SPEC invariants
# ---------------------------------------------------------------------------


def test_frmk_spec_prefix() -> None:
    assert FRMK_SPEC.prefix == "FRMK"


def test_frmk_spec_standard_id_regex_pattern() -> None:
    """docs/checkpoint_4_prep.md §1.3.4 — A3 harmonisation ``FRMK-\\d``."""
    assert FRMK_SPEC.standard_id_regex.pattern == r"^FRMK-\d$"


def test_frmk_spec_standard_no_regex_pattern() -> None:
    assert FRMK_SPEC.standard_no_regex.pattern == r"^\d{1,4}$"


def test_frmk_spec_section_enum_is_frmk_section() -> None:
    assert FRMK_SPEC.section_enum is FRMKSection


def test_frmk_spec_appendix_extractor_is_dedicated_not_isa_default() -> None:
    """Critic P3 2026-04-23 LOCK — FRMK 는 반드시 전용 extractor.
    ISA default 재사용 절대 금지 (B-v2 un-numbered 보론 title 보존)."""
    assert FRMK_SPEC.appendix_extractor is _frmk_appendix_extractor
    assert FRMK_SPEC.appendix_extractor is not isa_default_appendix_extractor


def test_frmk_spec_body_parser_is_none() -> None:
    """FRMK outer tbl[3x3] wrapper 는 recursive descent 로 처리, body_parser 불필요."""
    assert FRMK_SPEC.body_parser is None


def test_frmk_spec_section_detector_is_none() -> None:
    """FRMK 는 heading 2 style 명시 (21건) — default detector 충분."""
    assert FRMK_SPEC.section_detector is None


def test_frmk_spec_prelude_skip_attached() -> None:
    """FRMK prelude-end marker = heading 2 == "문단번호"."""
    assert FRMK_SPEC.prelude_skip is not None


# ---------------------------------------------------------------------------
# format_standard_id / validate_standard_id
# ---------------------------------------------------------------------------


def test_frmk_format_standard_id_single_digit() -> None:
    assert FRMK_SPEC.format_standard_id("1") == "FRMK-1"


def test_frmk_format_standard_id_future_version() -> None:
    """향후 2030+ FRMK-2/3 개정 시 regex 수용 여지."""
    assert FRMK_SPEC.format_standard_id("2") == "FRMK-2"
    assert FRMK_SPEC.format_standard_id("9") == "FRMK-9"


@pytest.mark.parametrize(
    "bad_standard_no",
    ["", "abc", "10"],
)
def test_frmk_format_standard_id_rejects_bad_standard_no(bad_standard_no: str) -> None:
    with pytest.raises(ValueError):
        FRMK_SPEC.format_standard_id(bad_standard_no)


def test_frmk_validate_accepts_frmk_1() -> None:
    FRMK_SPEC.validate_standard_id("FRMK-1")


@pytest.mark.parametrize(
    "bad_id",
    ["FRMK", "FRMK-", "FRMK-10", "ISA-200", "ISQM-1", "ASSR-3000"],
)
def test_frmk_validate_rejects_out_of_scope(bad_id: str) -> None:
    with pytest.raises(ValueError):
        FRMK_SPEC.validate_standard_id(bad_id)


# ---------------------------------------------------------------------------
# FRMKSection StrEnum — 17 entries per profile §4
# ---------------------------------------------------------------------------


def test_frmk_section_has_17_entries() -> None:
    assert len(list(FRMKSection)) == 17


def test_frmk_section_values_match_profile_4() -> None:
    expected = {
        "intro",
        "ethical_requirements_and_quality",
        "assurance_definition",
        "attestation_vs_direct",
        "reasonable_vs_limited_assurance",
        "framework_scope",
        "non_assurance_reports",
        "assurance_preconditions",
        "assurance_components",
        "three_party_relationship",
        "underlying_subject_matter",
        "criteria",
        "evidence",
        "assurance_report",
        "other_matters",
        "inappropriate_use_of_name",
        "appendix",
    }
    assert {member.value for member in FRMKSection} == expected


# ---------------------------------------------------------------------------
# _frmk_appendix_extractor — B-v2 4 case + period variant (Critic Q3)
# ---------------------------------------------------------------------------


def test_frmk_extractor_b_v2_numbered_1() -> None:
    """docs/framework_structure_profile.md §6.2 B-v2 idx=150."""
    heading = "보론 1: 회계감사기준위원회가 제정한 기준 등의 상호 관계…"
    assert _frmk_appendix_extractor(heading) == (1, None)


def test_frmk_extractor_b_v2_numbered_2() -> None:
    assert _frmk_appendix_extractor("보론 2: 입증업무와 직접업무") == (2, None)


def test_frmk_extractor_b_v2_numbered_3() -> None:
    assert _frmk_appendix_extractor("보론 3: 인증업무의 당사자") == (3, None)


def test_frmk_extractor_b_v2_unnumbered_colon() -> None:
    """docs/framework_structure_profile.md §6.2 B-v2 idx=149 — un-numbered."""
    assert _frmk_appendix_extractor("보론: 역할과 책임") == (None, "역할과 책임")


def test_frmk_extractor_period_variant() -> None:
    """Critic Q3 2026-04-23 verbal — period `.` variant future-proof."""
    assert _frmk_appendix_extractor("보론. 역할과 책임") == (None, "역할과 책임")


def test_frmk_extractor_non_appendix_returns_none() -> None:
    for text in ["서론", "삼자관계", "개념체계의 범위", "준거기준", "인증보고서"]:
        assert _frmk_appendix_extractor(text) == (None, None)


def test_frmk_extractor_numbered_precedence_over_unnumbered() -> None:
    """``보론 1: ...`` 은 numbered regex 가 먼저 매칭 — un-numbered regex 는
    number 가 있는 경우 skip. Critic 요청 precedence 확인."""
    # 이 입력은 un-numbered regex ``^보론\s*[:.]`` 와도 매칭될 가능성 있는 형태 아님
    # (보론 뒤에 space+digit 이 있어야 numbered). 확실한 경계 케이스 — `보론 1`
    # 은 numbered; `보론:` 은 un-numbered. coexistence 는 heading 내 없음.
    assert _frmk_appendix_extractor("보론 1: 역할") == (1, None)
    assert _frmk_appendix_extractor("보론: 역할과 책임") == (None, "역할과 책임")


def test_frmk_extractor_whitespace_tolerated() -> None:
    assert _frmk_appendix_extractor("  보론 1: 내용  ") == (1, None)
    assert _frmk_appendix_extractor("  보론: 책임  ") == (None, "책임")


# ---------------------------------------------------------------------------
# heading_trail reversed 순회 시 inner-most match 우선
# ---------------------------------------------------------------------------


def test_frmk_extractor_heading_trail_reversed_inner_unnumbered() -> None:
    """caller (md_parser) 는 reversed(trail) 순회 — 첫 non-(None, None) 에서 중단.

    가상의 trail ``["보론: 역할과 책임", "하위"]`` — reversed 에서 "하위"
    (None, None) → "보론: 역할과 책임" match. 실제 FRMK 에서 이런 coexistence
    는 없으나 방어 규칙 test.
    """
    trail = ["보론: 역할과 책임", "하위"]
    for heading in reversed(trail):
        result = _frmk_appendix_extractor(heading)
        if result != (None, None):
            assert result == (None, "역할과 책임")
            return
    pytest.fail("expected a match")


def test_frmk_extractor_heading_trail_reversed_inner_numbered() -> None:
    """``["보론 1: ...", "하위 설명"]`` reversed — "하위 설명" (None,None) →
    "보론 1: ..." match → (1, None)."""
    trail = ["보론 1: 제1 보론", "하위 설명"]
    for heading in reversed(trail):
        result = _frmk_appendix_extractor(heading)
        if result != (None, None):
            assert result == (1, None)
            return
    pytest.fail("expected a match")


# ---------------------------------------------------------------------------
# _frmk_prelude_skip — marker matcher
# ---------------------------------------------------------------------------


def test_prelude_skip_matches_heading_2_mundan_beonho() -> None:
    assert FRMK_SPEC.prelude_skip is not None
    block = _make_block("문단번호", style="heading 2")
    assert FRMK_SPEC.prelude_skip(block) is True


def test_prelude_skip_prefix_match_tolerates_whitespace() -> None:
    """Critic verbal — prefix match for whitespace/suffix tolerance."""
    assert FRMK_SPEC.prelude_skip is not None
    block = _make_block("문단번호  ", style="heading 2")
    assert FRMK_SPEC.prelude_skip(block) is True


def test_prelude_skip_requires_heading_2_style() -> None:
    """style 이 heading 2 가 아니면 False — 본문에서 '문단번호' 단어가 나와도 marker 아님."""
    assert FRMK_SPEC.prelude_skip is not None
    block = _make_block("문단번호", style="")
    assert FRMK_SPEC.prelude_skip(block) is False


def test_prelude_skip_does_not_match_other_headings() -> None:
    assert FRMK_SPEC.prelude_skip is not None
    for text in ["서론", "개요", "보론 1: 제1 보론"]:
        assert FRMK_SPEC.prelude_skip(_make_block(text, style="heading 2")) is False


# ---------------------------------------------------------------------------
# normalize_framework_heading — profile §2.3 heading_range_strip
# ---------------------------------------------------------------------------


def test_normalize_seoron_range() -> None:
    assert normalize_framework_heading("서론1-4") == ("서론", "1-4")


def test_normalize_three_party_range() -> None:
    assert normalize_framework_heading("삼자관계27-38") == ("삼자관계", "27-38")


def test_normalize_single_paragraph_number() -> None:
    """96 과 같은 single paragraph number 도 -(hyphen-less) 로 strip."""
    assert normalize_framework_heading("인증인 명칭의 부적절한 사용96") == (
        "인증인 명칭의 부적절한 사용",
        "96",
    )


def test_normalize_preserves_appendix_heading() -> None:
    """보론 heading 은 range suffix 없으므로 원본 그대로."""
    assert normalize_framework_heading("보론 1: 회계감사기준위원회") == (
        "보론 1: 회계감사기준위원회",
        None,
    )
    assert normalize_framework_heading("보론: 역할과 책임") == (
        "보론: 역할과 책임",
        None,
    )


def test_normalize_preserves_mundan_beonho() -> None:
    """문단번호 marker 는 range suffix 없음."""
    assert normalize_framework_heading("문단번호") == ("문단번호", None)
    assert normalize_framework_heading("  문단번호  ") == ("문단번호", None)


def test_normalize_no_range_preserves_text() -> None:
    assert normalize_framework_heading("일반 제목") == ("일반 제목", None)


# ---------------------------------------------------------------------------
# Per-spec regex alt integrity (c4 drift guard)
# ---------------------------------------------------------------------------


def test_frmk_regex_accepts_frmk_single_digit() -> None:
    for candidate in ["FRMK-1", "FRMK-2", "FRMK-9"]:
        assert FRMK_SPEC.standard_id_regex.fullmatch(candidate) is not None


def test_frmk_regex_rejects_cross_prefix() -> None:
    for candidate in ["ISA-200", "ISQM-1", "ASSR-3000", "FRMK", "FRMK-10"]:
        assert FRMK_SPEC.standard_id_regex.fullmatch(candidate) is None
