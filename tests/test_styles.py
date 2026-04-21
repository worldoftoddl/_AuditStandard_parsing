"""`styles.py` 단위 테스트 — Phase 1 F1 rework.

CHECKPOINT 1 검수 §1.5 의 5 개 case (style numPr 상속 + basedOn 체인) 을 커버.
"""

from __future__ import annotations

from types import MappingProxyType

from audit_parser.ir.styles import (
    StyleIndex,
    StyleNumDefault,
    parse_styles_xml,
    resolve_paragraph_numPr,
)

# ---------------------------------------------------------------------------
# parse_styles_xml — 실제 DOCX 에서 확정된 스타일 6 개 파싱
# ---------------------------------------------------------------------------


def _make_styles_xml() -> bytes:
    """실제 DOCX 의 a1/A/A0/A2/B0/B 스타일 6 개 축약 버전."""
    return b"""<?xml version='1.0' encoding='UTF-8'?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="a1">
    <w:name w:val="\xeb\xac\xb8\xeb\x8b\xa8"/>
    <w:basedOn w:val="a9"/>
    <w:pPr><w:numPr><w:numId w:val="119"/></w:numPr></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="A">
    <w:name w:val="\xeb\xac\xb8\xeb\x8b\xa8A"/>
    <w:basedOn w:val="a9"/>
    <w:pPr><w:numPr><w:numId w:val="105"/></w:numPr></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="A0">
    <w:name w:val="\xeb\xb6\x88\xeb\xa6\xbf\xeb\xaa\xa9\xeb\xa1\x9dA"/>
    <w:basedOn w:val="a9"/>
    <w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="105"/></w:numPr></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="A2">
    <w:name w:val="\xeb\xaa\xa9\xeb\xa1\x9dA"/>
    <w:basedOn w:val="a9"/>
    <w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="119"/></w:numPr></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="B0">
    <w:name w:val="\xeb\xaa\xa9\xeb\xa1\x9dB"/>
    <w:basedOn w:val="A2"/>
    <w:pPr><w:numPr><w:ilvl w:val="2"/></w:numPr></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="B">
    <w:name w:val="\xeb\xb6\x88\xeb\xa6\xbf\xeb\xaa\xa9\xeb\xa1\x9dB"/>
    <w:basedOn w:val="A0"/>
    <w:pPr><w:numPr><w:ilvl w:val="2"/></w:numPr></w:pPr>
  </w:style>
</w:styles>"""


def test_parse_styles_xml_extracts_numpr_and_based_on() -> None:
    index = parse_styles_xml(_make_styles_xml())
    nd = index.num_defaults
    assert nd["a1"] == StyleNumDefault(style_id="a1", based_on="a9", num_id="119", ilvl=None)
    assert nd["A"] == StyleNumDefault(style_id="A", based_on="a9", num_id="105", ilvl=None)
    assert nd["A0"] == StyleNumDefault(style_id="A0", based_on="a9", num_id="105", ilvl=1)
    assert nd["A2"] == StyleNumDefault(style_id="A2", based_on="a9", num_id="119", ilvl=1)
    assert nd["B0"] == StyleNumDefault(style_id="B0", based_on="A2", num_id=None, ilvl=2)
    assert nd["B"] == StyleNumDefault(style_id="B", based_on="A0", num_id=None, ilvl=2)


def test_parse_styles_xml_display_names_present() -> None:
    index = parse_styles_xml(_make_styles_xml())
    assert index.display_names["a1"] == "문단"
    assert index.display_names["A"] == "문단A"
    assert index.display_names["A0"] == "불릿목록A"


# ---------------------------------------------------------------------------
# resolve_paragraph_numPr — 검수 리포트 §1.5 의 5 case
# ---------------------------------------------------------------------------


def _fixture_index() -> StyleIndex:
    return parse_styles_xml(_make_styles_xml())


def test_case1_paragraph_without_numpr_inherits_style_a1() -> None:
    """문단 pPr 無 + style=a1 → (119, 0) 상속."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=None, style_id="a1", num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == ("119", 0)


def test_case2_paragraph_with_suppress_numid_preserved() -> None:
    """문단 pPr numId=0 (suppress) + style=a1 → ('0', ilvl) 그대로 (스타일 fall-through 없음).

    리뷰 리포트는 "None 반환" 을 단축 표기했으나, downstream numbering engine 은
    numId='0' 일 때 별도 suppressed path 를 타야 하므로 구체적으로는 '0' 을 그대로
    전달한다 (기존 suppressed-marker 보존 — 본 검수에서도 ✓ 로 판정된 동작).
    """
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id="0", p_ilvl=None, style_id="a1", num_defaults=index.num_defaults
    )
    assert num_id == "0"
    assert ilvl is None


def test_case3_paragraph_ilvl_override_with_style_A() -> None:
    """문단 pPr ilvl=1 override + style=A → (105, 1) — 문단 ilvl 이 스타일 ilvl 을 덮음."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=1, style_id="A", num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == ("105", 1)


def test_case4_based_on_chain_B0_resolves_to_A2() -> None:
    """style=B0 → basedOn=A2 → (119, 2) 체인 해결. B0 own ilvl=2 가 A2 ilvl=1 을 덮음."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=None, style_id="B0", num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == ("119", 2)


def test_case4b_based_on_chain_B_resolves_to_A0() -> None:
    """style=B → basedOn=A0 → (105, 2) 체인 해결."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=None, style_id="B", num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == ("105", 2)


def test_case5_unknown_style_returns_none() -> None:
    """style 미존재 → (None, p_ilvl)."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=3, style_id="does_not_exist", num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == (None, 3)


def test_case6_no_style_id_returns_none() -> None:
    """style_id=None → (None, p_ilvl)."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=None, style_id=None, num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == (None, None)


def test_case7_style_without_numpr_and_no_basedon_returns_none() -> None:
    """C7 fixture: style=NormalText (numPr None, basedOn None) → (None, p_ilvl).

    Domain-reviewer fixture `style_numpr_cases.json` C7 — 번호 정보가 전혀 없는 본문 스타일.
    """
    normal: dict[str, StyleNumDefault] = {
        "NormalText": StyleNumDefault(
            style_id="NormalText", based_on=None, num_id=None, ilvl=None
        ),
    }
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None,
        p_ilvl=None,
        style_id="NormalText",
        num_defaults=MappingProxyType(normal),
    )
    assert (num_id, ilvl) == (None, None)


def test_case8_paragraph_direct_numid_takes_precedence() -> None:
    """문단 직속 numId=86 + style=a1 → (86, p_ilvl) — style 상속 없음."""
    index = _fixture_index()
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id="86", p_ilvl=0, style_id="a1", num_defaults=index.num_defaults
    )
    assert (num_id, ilvl) == ("86", 0)


# ---------------------------------------------------------------------------
# Cycle guard / depth limit
# ---------------------------------------------------------------------------


def test_cycle_in_based_on_chain_returns_none_without_infinite_loop() -> None:
    cyclic: dict[str, StyleNumDefault] = {
        "X": StyleNumDefault(style_id="X", based_on="Y", num_id=None, ilvl=None),
        "Y": StyleNumDefault(style_id="Y", based_on="X", num_id=None, ilvl=None),
    }
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None,
        p_ilvl=None,
        style_id="X",
        num_defaults=MappingProxyType(cyclic),
    )
    assert (num_id, ilvl) == (None, None)


def test_very_deep_chain_stops_at_depth_limit() -> None:
    deep: dict[str, StyleNumDefault] = {}
    for i in range(20):
        deep[f"s{i}"] = StyleNumDefault(
            style_id=f"s{i}",
            based_on=f"s{i + 1}",
            num_id=None,
            ilvl=None,
        )
    # s19 → s20 없음. 12 단계 따라가면 depth 10 초과.
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id=None, p_ilvl=None, style_id="s0", num_defaults=MappingProxyType(deep)
    )
    assert (num_id, ilvl) == (None, None)


# ---------------------------------------------------------------------------
# 빈/결측 styles.xml
# ---------------------------------------------------------------------------


def test_parse_styles_xml_empty() -> None:
    empty = b"<?xml version='1.0'?><w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"/>"
    index = parse_styles_xml(empty)
    assert len(index.display_names) == 0
    assert len(index.num_defaults) == 0
