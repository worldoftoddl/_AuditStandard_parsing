"""Tests for ``audit_parser.spec.isqm_spec`` — Phase 4b-2 c2.

Scope:

* ``ISQM_SPEC`` invariants — prefix / regex / section_enum / appendix_extractor
* ``format_standard_id`` / ``validate_standard_id`` single-digit 수용
* ``ISQMSection`` StrEnum values
* ``ISQM_SECTIONS`` / ``ISQM_SUBSECTIONS`` whitelist content (Domain Reviewer
  2026-04-23 Q5 final list)
* **Check 4** (Domain Reviewer 2026-04-23) — ``한4-1`` chunk_id sanity regex
  PASS (``docs/checkpoint_4_prep.md §1.3.4`` chunk_id regex + KICPA 국내 prefix
  unicode 호환)
"""

from __future__ import annotations

import re

import pytest

from audit_parser.spec import (
    ISA_SPEC,
    ISQM_SECTIONS,
    ISQM_SPEC,
    ISQM_SUBSECTIONS,
    ISQMSection,
    isa_default_appendix_extractor,
)

# ---------------------------------------------------------------------------
# ISQM_SPEC invariants
# ---------------------------------------------------------------------------


def test_isqm_spec_prefix() -> None:
    assert ISQM_SPEC.prefix == "ISQM"


def test_isqm_spec_standard_id_regex_pattern() -> None:
    """docs/checkpoint_4_prep.md §1.3.4 — Critic α 확장 ``ISQM-\\d{1,2}``."""
    assert ISQM_SPEC.standard_id_regex.pattern == r"^ISQM-\d{1,2}$"


def test_isqm_spec_standard_no_regex_pattern() -> None:
    """v1.2.0 relaxed — ISQM-1 single-digit standard_no 수용."""
    assert ISQM_SPEC.standard_no_regex.pattern == r"^\d{1,4}$"


def test_isqm_spec_section_enum_is_isqm_section() -> None:
    assert ISQM_SPEC.section_enum is ISQMSection


def test_isqm_spec_appendix_extractor_reuses_isa_default() -> None:
    """Domain Reviewer 2026-04-23 Q2 — ISQM-1 보론 존재 여부 실측 미완료.
    ISA default fallback 채택 (non-match → ``(None, None)`` 안전)."""
    assert ISQM_SPEC.appendix_extractor is isa_default_appendix_extractor


def test_isqm_spec_body_parser_is_attached() -> None:
    """c2 핵심 — body_parser attach 확인. ISA_SPEC 는 None 유지."""
    assert ISQM_SPEC.body_parser is not None
    assert ISA_SPEC.body_parser is None


def test_isqm_spec_section_detector_and_prelude_skip_none() -> None:
    """ISQM-1 은 body table 내부 row 분류로 section 결정 — declarative detector
    불필요. prelude 도 body table 자체가 skip marker 역할."""
    assert ISQM_SPEC.section_detector is None
    assert ISQM_SPEC.prelude_skip is None


# ---------------------------------------------------------------------------
# ISQM_SPEC.format_standard_id / validate_standard_id
# ---------------------------------------------------------------------------


def test_isqm_format_standard_id_single_digit() -> None:
    assert ISQM_SPEC.format_standard_id("1") == "ISQM-1"


def test_isqm_format_standard_id_two_digit() -> None:
    """Critic α 확장 — Phase 5 ISQM-10~99 수용."""
    assert ISQM_SPEC.format_standard_id("99") == "ISQM-99"


@pytest.mark.parametrize(
    "bad_standard_no",
    ["", "abc", "100a", "12345"],
)
def test_isqm_format_standard_id_rejects_bad_standard_no(bad_standard_no: str) -> None:
    with pytest.raises(ValueError):
        ISQM_SPEC.format_standard_id(bad_standard_no)


def test_isqm_format_standard_id_rejects_3digit_out_of_range() -> None:
    """ISQM-100 은 3-digit — regex ``\\d{1,2}`` 가 거부. v1.3 bump 시 확장 여지."""
    with pytest.raises(ValueError):
        ISQM_SPEC.format_standard_id("100")


def test_isqm_validate_accepts_target_id() -> None:
    ISQM_SPEC.validate_standard_id("ISQM-1")


def test_isqm_validate_rejects_isa_id() -> None:
    with pytest.raises(ValueError):
        ISQM_SPEC.validate_standard_id("ISA-200")


@pytest.mark.parametrize(
    "bad_id",
    ["ISQM-100", "ISQM", "ISQM-", "ISQM-1A"],
)
def test_isqm_validate_rejects_out_of_scope(bad_id: str) -> None:
    with pytest.raises(ValueError):
        ISQM_SPEC.validate_standard_id(bad_id)


# ---------------------------------------------------------------------------
# ISQMSection StrEnum
# ---------------------------------------------------------------------------


def test_isqm_section_values_match_profile_2_4() -> None:
    """docs/isqm_structure_profile.md §4 — 7-entry enum."""
    expected = {
        "intro",
        "effective_date",
        "purpose",
        "definitions",
        "requirements",
        "application",
        "appendix",
    }
    assert {member.value for member in ISQMSection} == expected


def test_isqm_section_shares_lowercase_literal_with_isa() -> None:
    """JSON Schema section literal 공유 — ISQMSection.REQUIREMENTS 의 value 가
    ISA Section.REQUIREMENTS value 와 동일 string ``"requirements"``. Phase 4d
    schema union merge 시 중복 제거 가능."""
    from audit_parser.ir.types import Section

    assert ISQMSection.REQUIREMENTS.value == Section.REQUIREMENTS.value
    assert ISQMSection.INTRO.value == Section.INTRO.value


# ---------------------------------------------------------------------------
# ISQM_SECTIONS / ISQM_SUBSECTIONS whitelists (Domain Reviewer Q5)
# ---------------------------------------------------------------------------


def test_isqm_sections_whitelist() -> None:
    """Domain Reviewer 2026-04-23 Q5 — 6-entry primary section list."""
    expected = {
        "서론",
        "시행일",
        "목적",
        "용어의 정의",
        "요구사항",
        "적용 및 기타 설명자료",
    }
    assert ISQM_SECTIONS == expected


def test_isqm_subsections_whitelist_includes_phase4b2_baseline() -> None:
    """Phase 4b-2 Q5 기존 11 entries + Phase 4c c4 확장분 포함 확인.

    4b-2 초기 11 entries 는 ISQM_SUBSECTIONS 에 반드시 포함되어야 함
    (backward-compat). c4 확장분은 Domain Reviewer 2026-04-23 판정 35 +
    parser-implementer 사전 추가 12 → 총 46+ entries (set equality 는
    향후 c5 patch 로 변동 가능하므로 subset 확인만).
    """
    phase4b2_baseline = {
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
    }
    assert phase4b2_baseline <= ISQM_SUBSECTIONS, (
        f"Phase 4b-2 baseline 11 entries must stay in ISQM_SUBSECTIONS. "
        f"Missing: {phase4b2_baseline - ISQM_SUBSECTIONS}"
    )
    # c4 minimum: Domain Reviewer 35 + parser-implementer 12 = 47 추가 (smart quote
    # entry 포함) = 최소 46 이상 (기존 11 + 신규 35 = 46).
    assert len(ISQM_SUBSECTIONS) >= 46


def test_isqm_sections_and_subsections_are_disjoint() -> None:
    """section 과 subsection 은 겹쳐서는 안 됨 — col[0]=="" row 분류 시 모호성
    방지. 교집합 발생 시 row classifier 우선순위 의존 증가."""
    assert ISQM_SECTIONS.isdisjoint(ISQM_SUBSECTIONS)


# ---------------------------------------------------------------------------
# Check 4 — Domain Reviewer 2026-04-23 sanity regex PASS for KICPA 한N-M prefix
# ---------------------------------------------------------------------------


# docs/checkpoint_4_prep.md §1.3.2 chunk_id sanity regex (full v1.2.0 form).
_CHUNK_ID_SANITY_REGEX = re.compile(
    r"^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)"
    r":[a-z_]+:[0-9a-f]{8}:[^#\s:]+(#\d+(#\d+)?)?$"
)


@pytest.mark.parametrize(
    "chunk_id",
    [
        # KICPA 국내 추가 paragraph_id — 한4-1 / 한18-1 / 한25-1.
        "ISQM-1:requirements:deadbeef:한4-1",
        "ISQM-1:requirements:0123abcd:한18-1",
        "ISQM-1:application:12ab34cd:한25-1",
        # 일반 숫자 paragraph_id 도 동시 검증 (backward-compat).
        "ISQM-1:requirements:cafebabe:18",
        "ISQM-1:requirements:feedface:57",
        # Sub-item paragraph_id
        "ISQM-1:requirements:abcd1234:(a)",
        "ISQM-1:requirements:abcd1235:(가)",
        # chunk_id suffix chain 2-level (Critic β-1 depth<=2 freeze)
        "ISQM-1:requirements:deadbeef:한4-1#100",
        "ISQM-1:requirements:deadbeef:한4-1#100#2",
    ],
)
def test_chunk_id_sanity_regex_accepts_kicpa_paragraph_ids(chunk_id: str) -> None:
    """Check 4 — ``한N-M`` KICPA prefix + sub-item + suffix chain 전수 PASS.

    한글 char class 가 sanity regex ``[^#\\s:]+`` 의 negation 에 걸리지 않음을
    실증. ``\\s`` 는 Python ``re.UNICODE`` default 하에 U+3000 (ideographic
    space) 포함하나 한글 syllable ``한/4/1`` 은 모두 non-whitespace 이므로
    PASS. 4b-1 baseline 8,590 chunks 전수 PASS 실증과 정합.
    """
    match = _CHUNK_ID_SANITY_REGEX.fullmatch(chunk_id)
    assert match is not None, f"chunk_id {chunk_id!r} failed sanity regex"


@pytest.mark.parametrize(
    "bad_chunk_id",
    [
        # whitespace 포함 paragraph_id — sanity regex 거부 확인
        "ISQM-1:requirements:deadbeef:한4 1",
        # `:` 포함 paragraph_id — 5-segment 로 해석되어 suffix regex 와 충돌
        # (paragraph_id ``[^#\\s:]+`` 가 첫 `:` 전까지 매칭, 잔여 ``:1`` 는 suffix
        # regex ``(#\\d+(#\\d+)?)?`` 과 불일치)
        "ISQM-1:requirements:deadbeef:한4:1",
        # 3-level suffix chain — β-1 2-level freeze 위반 (Critic)
        "ISQM-1:requirements:deadbeef:한4-1#1#2#3",
        # prefix 불일치 — ISQM-100 (Critic α 확장 규약상 거부)
        "ISQM-100:requirements:deadbeef:한4-1",
    ],
)
def test_chunk_id_sanity_regex_rejects_malformed(bad_chunk_id: str) -> None:
    """Sanity regex 가 whitespace / 분리자 오염 / scope-out prefix 케이스를 거부.

    주의: ``한4#1`` 형태 (``#`` 포함) 는 실제로는 **valid** — paragraph_id
    ``한4`` + suffix ``#1`` 로 해석. 본 테스트는 명백히 위반되는 케이스만 수집.
    """
    assert _CHUNK_ID_SANITY_REGEX.fullmatch(bad_chunk_id) is None


# ---------------------------------------------------------------------------
# Per-spec regex union equals §1.3.4 full regex (dispatch integrity)
# ---------------------------------------------------------------------------


def test_isqm_regex_is_alt_of_full_v1_2_regex() -> None:
    """ISQM_SPEC.standard_id_regex 가 §1.3.4 full regex 의 ISQM alt 와 동일 alt.

    c4 dispatcher 에서 4 spec regex `|`-union 이 full regex 와 equal 해야 하므로
    c2 단계부터 per-spec subset 정합성 smoke check (drift 방지).
    """
    full_v1_2_regex = re.compile(
        r"^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)$"
    )
    # ISQM_SPEC.standard_id_regex 가 매칭하면 full_v1_2_regex 도 매칭해야.
    for candidate in ["ISQM-1", "ISQM-99"]:
        assert ISQM_SPEC.standard_id_regex.fullmatch(candidate) is not None
        assert full_v1_2_regex.fullmatch(candidate) is not None
    # 거부 대상도 양쪽 모두 거부.
    for bad in ["ISQM-100", "ISQM", "ISQM-1A"]:
        assert ISQM_SPEC.standard_id_regex.fullmatch(bad) is None
