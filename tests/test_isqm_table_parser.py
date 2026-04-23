"""Tests for ``audit_parser.ir.isqm_table_parser`` — Phase 4b-2 c2.

Scope (Plan v1.1 §c Exit gate #4 + Domain Reviewer Q1(d)/Q5 + Critic R1 verbal):

* ``_extract_sub_id`` 4-alt regex coverage ((a)/(가)/(i)/(1))
* ``parse_isqm_body_table`` 10+ fixture row cases:
  - numbered paragraph_id ("1", "57")
  - KICPA 한N-M prefix ("한4-1")
  - 한4-1 trailing ASCII whitespace (Domain Q1(d))
  - 한4-1 nbsp/ideographic-space trailing (Domain Q1(d))
  - empty col[0] + col[1] in ISQM_SECTIONS → HEADING "isqm_section"
  - empty col[0] + col[1] in ISQM_SUBSECTIONS → HEADING "isqm_subsection"
  - empty col[0] + col[1] unregistered → PARAGRAPH_BODY + WARNING
  - empty col[0] + col[1] empty → skip (layout filler)
  - numbered col[0] + multi-<w:p> col[1] with sub-items (a), (b), (1)
  - sub-item (i) lowerRoman + (가) Hangul
"""

from __future__ import annotations

from lxml import etree

from audit_parser.ir.isqm_table_parser import (
    _extract_sub_id,
    parse_isqm_body_table,
)
from audit_parser.ir.types import BlockKind, RawBlock
from audit_parser.spec import ISQM_SECTIONS, ISQM_SUBSECTIONS

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMAP = {"w": _W_NS}


def _build_paragraph(text: str) -> str:
    """Return a minimal ``<w:p>`` XML snippet with one text run."""
    # xml.sax.saxutils.escape-ish: users pass already-escaped content.
    return f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>{text}</w:t></w:r></w:p>'


def _build_cell(*paragraph_texts: str) -> str:
    """Return a ``<w:tc>`` with one ``<w:p>`` per argument."""
    paras = "".join(_build_paragraph(t) for t in paragraph_texts)
    return f'<w:tc xmlns:w="{_W_NS}">{paras}</w:tc>'


def _build_row(col0: str, *col1_paragraphs: str) -> str:
    """Return a ``<w:tr>`` with 2 cells — col[0] single para, col[1] multi-para."""
    return (
        f'<w:tr xmlns:w="{_W_NS}">'
        f"{_build_cell(col0)}"
        f"{_build_cell(*col1_paragraphs)}"
        f"</w:tr>"
    )


def _build_table(*rows: str) -> etree._Element:
    """Wrap rows into a ``<w:tbl>`` and parse to ``lxml.etree._Element``."""
    body = "".join(rows)
    return etree.fromstring(f'<w:tbl xmlns:w="{_W_NS}">{body}</w:tbl>')


# ---------------------------------------------------------------------------
# _extract_sub_id — 4-alt regex coverage (Critic R1 verbal)
# ---------------------------------------------------------------------------


def test_extract_sub_id_lower_letter() -> None:
    assert _extract_sub_id("(a) body text") == "(a)"


def test_extract_sub_id_lower_letter_2char() -> None:
    assert _extract_sub_id("(zz) marginal") == "(zz)"


def test_extract_sub_id_hangul() -> None:
    assert _extract_sub_id("(가) 국내 관례") == "(가)"


def test_extract_sub_id_lower_roman() -> None:
    assert _extract_sub_id("(i) first") == "(i)"
    assert _extract_sub_id("(iv) fourth") == "(iv)"
    assert _extract_sub_id("(xiii) thirteenth") == "(xiii)"


def test_extract_sub_id_digit() -> None:
    """Critic verbal R1 (2026-04-23 LOCK) — digit alt was missing in v1.0 plan."""
    assert _extract_sub_id("(1) decimal") == "(1)"
    assert _extract_sub_id("(99) last") == "(99)"


def test_extract_sub_id_none_for_plain_text() -> None:
    assert _extract_sub_id("plain continuation text") is None


def test_extract_sub_id_none_for_triple_digit() -> None:
    """Regex ``\\d{1,2}`` — 3-digit 거부 (KICPA 실측 없음)."""
    assert _extract_sub_id("(100) too many") is None


def test_extract_sub_id_leading_whitespace_tolerated() -> None:
    assert _extract_sub_id("   (a) indented") == "(a)"


# ---------------------------------------------------------------------------
# parse_isqm_body_table — 10+ fixture row cases
# ---------------------------------------------------------------------------


def _collect_blocks(*rows: str) -> list[RawBlock]:
    tbl = _build_table(*rows)
    return list(
        parse_isqm_body_table(
            tbl,
            isqm_sections=ISQM_SECTIONS,
            isqm_subsections=ISQM_SUBSECTIONS,
            warn_unknown_headings=False,
        )
    )


def test_case_01_numbered_paragraph_id() -> None:
    """숫자 paragraph_id "1" → REQUIREMENT."""
    blocks = _collect_blocks(_build_row("1", "품질관리기준서1 본문"))
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.REQUIREMENT
    assert blocks[0].paragraph_id == "1"
    assert blocks[0].text == "품질관리기준서1 본문"


def test_case_02_numbered_paragraph_id_large() -> None:
    """숫자 paragraph_id "57" → REQUIREMENT."""
    blocks = _collect_blocks(_build_row("57", "최종 문단 본문"))
    assert len(blocks) == 1
    assert blocks[0].paragraph_id == "57"


def test_case_03_kicpa_hangul_prefix() -> None:
    """KICPA 국내 추가 paragraph_id "한4-1" → REQUIREMENT."""
    blocks = _collect_blocks(_build_row("한4-1", "KICPA 국내 추가 요구사항"))
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.REQUIREMENT
    assert blocks[0].paragraph_id == "한4-1"


def test_case_04_trailing_ascii_whitespace_stripped() -> None:
    """Domain Reviewer Q1(d) — "한4-1 " trailing ASCII space 는 ``.strip()`` 적용."""
    blocks = _collect_blocks(_build_row("한4-1 ", "trailing space 포함 col[0]"))
    assert len(blocks) == 1
    assert blocks[0].paragraph_id == "한4-1"


def test_case_05_trailing_ideographic_space_stripped() -> None:
    """Domain Reviewer Q1(d) — U+3000 IDEOGRAPHIC SPACE trailing 도 strip.

    Python ``str.strip()`` 기본동작은 Unicode category Zs 포함.
    """
    blocks = _collect_blocks(_build_row("한4-1　", "ideographic trailing"))
    assert len(blocks) == 1
    assert blocks[0].paragraph_id == "한4-1"


def test_case_06_empty_col0_section_heading() -> None:
    """col[0]="" + col[1] ∈ ISQM_SECTIONS → HEADING "isqm_section"."""
    blocks = _collect_blocks(_build_row("", "요구사항"))
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.HEADING
    assert blocks[0].style == "isqm_section"
    assert blocks[0].text == "요구사항"
    assert blocks[0].paragraph_id is None


def test_case_07_empty_col0_subsection_heading() -> None:
    """col[0]="" + col[1] ∈ ISQM_SUBSECTIONS → HEADING "isqm_subsection"."""
    blocks = _collect_blocks(_build_row("", "독립성"))
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.HEADING
    assert blocks[0].style == "isqm_subsection"
    assert blocks[0].text == "독립성"


def test_case_08_empty_col0_unregistered_fallback() -> None:
    """Domain Reviewer Q5 — 미등록 heading row → PARAGRAPH_BODY fallback.

    WARNING 로그 발신은 별도 (warn_unknown_headings=False 로 여기서는 silence).
    """
    blocks = _collect_blocks(_build_row("", "미등록 섹션 후보"))
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.PARAGRAPH_BODY
    assert blocks[0].text == "미등록 섹션 후보"
    assert blocks[0].paragraph_id is None


def test_case_09_empty_row_layout_filler_skipped() -> None:
    """col[0]="" + col[1]="" = layout filler row → emit 0."""
    blocks = _collect_blocks(_build_row("", ""))
    assert blocks == []


def test_case_10_multi_paragraph_cell_with_sub_items() -> None:
    """col[1] 이 multi-<w:p>: 첫 body + (a)/(b)/(1) sub-items 3건.

    Critic R1 verbal — digit alt (1) 포함 4-alt 전수 커버.
    """
    blocks = _collect_blocks(
        _build_row(
            "11",
            "요구사항 본문",
            "(a) 첫 번째 서브아이템",
            "(b) 두 번째 서브아이템",
            "(1) decimal 서브아이템",
        )
    )
    assert len(blocks) == 4
    assert blocks[0].kind is BlockKind.REQUIREMENT
    assert blocks[0].paragraph_id == "11"
    assert blocks[1].kind is BlockKind.SUB_ITEM
    assert blocks[1].paragraph_id == "(a)"
    assert blocks[2].paragraph_id == "(b)"
    assert blocks[3].paragraph_id == "(1)"


def test_case_11_multi_paragraph_cell_with_hangul_and_roman_sub_items() -> None:
    """col[1] sub-item (가) Hangul + (i) lowerRoman 믹스."""
    blocks = _collect_blocks(
        _build_row(
            "18",
            "리더십 요구사항",
            "(가) 국내 사례",
            "(i) 첫 번째 조건",
        )
    )
    assert len(blocks) == 3
    assert blocks[0].kind is BlockKind.REQUIREMENT
    assert blocks[1].paragraph_id == "(가)"
    assert blocks[2].paragraph_id == "(i)"


def test_case_12_plain_continuation_in_multi_paragraph_cell() -> None:
    """Sub-item regex 미매칭 continuation 은 PARAGRAPH_BODY (parent_paragraph_id
    링크는 Phase 4c structure.py 단에서 처리)."""
    blocks = _collect_blocks(
        _build_row(
            "5",
            "본문 첫 줄",
            "본문 이어지는 둘째 줄 — sub-item 아님",
        )
    )
    assert len(blocks) == 2
    assert blocks[0].kind is BlockKind.REQUIREMENT
    assert blocks[1].kind is BlockKind.PARAGRAPH_BODY
    assert blocks[1].paragraph_id is None


# ---------------------------------------------------------------------------
# Integration — multiple rows sequence sanity (counter monotone)
# ---------------------------------------------------------------------------


def test_multirow_idx_counter_monotone() -> None:
    """Emitted ``RawBlock.idx`` 는 연속 증가 (0, 1, 2, ...) — Phase 4c 의
    source_idx / chunk_id hash 계산 시 sequence integrity 전제."""
    blocks = _collect_blocks(
        _build_row("", "요구사항"),
        _build_row("1", "본문 하나"),
        _build_row("2", "본문 둘"),
        _build_row("", "독립성"),
        _build_row("3", "본문 셋", "(a) 서브"),
    )
    indices = [b.idx for b in blocks]
    assert indices == list(range(len(blocks)))


def test_multirow_mixed_sections_and_body() -> None:
    """Section heading + body + subsection heading + body 5-row 혼합 → 6 blocks."""
    blocks = _collect_blocks(
        _build_row("", "요구사항"),  # HEADING section
        _build_row("1", "본문 1"),  # REQUIREMENT
        _build_row("", "독립성"),  # HEADING subsection
        _build_row("한4-1", "KICPA 추가"),  # REQUIREMENT (Hangul prefix)
        _build_row(
            "5",
            "본문 5",
            "(a) sub a",
        ),  # REQUIREMENT + SUB_ITEM
    )
    assert len(blocks) == 6
    kinds = [b.kind for b in blocks]
    assert kinds == [
        BlockKind.HEADING,
        BlockKind.REQUIREMENT,
        BlockKind.HEADING,
        BlockKind.REQUIREMENT,
        BlockKind.REQUIREMENT,
        BlockKind.SUB_ITEM,
    ]
    styles = [b.style for b in blocks]
    assert styles == [
        "isqm_section",
        "",
        "isqm_subsection",
        "",
        "",
        "",
    ]
    paragraph_ids = [b.paragraph_id for b in blocks]
    assert paragraph_ids == [None, "1", None, "한4-1", "5", "(a)"]


# ---------------------------------------------------------------------------
# Non-2-col row robustness
# ---------------------------------------------------------------------------


def test_non_2_col_row_skipped() -> None:
    """Layout anomaly — 1-cell row 는 skip + WARNING (silent in test)."""
    tbl = etree.fromstring(
        f'<w:tbl xmlns:w="{_W_NS}">'
        f'<w:tr><w:tc>{_build_paragraph("anomaly")}</w:tc></w:tr>'
        f"</w:tbl>"
    )
    blocks = list(
        parse_isqm_body_table(
            tbl,
            isqm_sections=ISQM_SECTIONS,
            isqm_subsections=ISQM_SUBSECTIONS,
            warn_unknown_headings=False,
        )
    )
    assert blocks == []
