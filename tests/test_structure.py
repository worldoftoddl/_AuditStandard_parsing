"""`structure.py` 상태머신·heading_trail 테스트 — Phase 1 Task #4."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest

from audit_parser.ir.docx_reader import iter_body, open_docx_zip
from audit_parser.ir.numbering import (
    AbstractNumDef,
    LevelDef,
    NumberingEngine,
    NumDef,
    parse_numbering_from_docx,
)
from audit_parser.ir.structure import StructureMachine, iter_blocks
from audit_parser.ir.types import Block, BlockKind, RawBlock, Section

_REAL_DOCX = Path(__file__).resolve().parents[1] / "raw" / "0. 회계감사기준 전문(2025 개정).docx"


# ---------------------------------------------------------------------------
# Fixture helpers — 합성 RawBlock / NumberingEngine
# ---------------------------------------------------------------------------


class _Idx:
    __slots__ = ("_n",)

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        v = self._n
        self._n += 1
        return v


def _raw_para(
    idx: _Idx,
    text: str,
    style: str = "문단",
    *,
    kind: BlockKind = BlockKind.PARAGRAPH_BODY,
    num_id: str | None = None,
    ilvl: int | None = None,
    table_cells: tuple[tuple[str, ...], ...] | None = None,
) -> RawBlock:
    return RawBlock(
        idx=idx.next(),
        kind=kind,
        text=text,
        style=style,
        num_id=num_id,
        ilvl=ilvl,
        table_cells=table_cells,
    )


def _heading(idx: _Idx, text: str, level: int) -> RawBlock:
    return _raw_para(idx, text, style=f"heading {level}", kind=BlockKind.HEADING)


def _toc_entry(idx: _Idx, text: str) -> RawBlock:
    return _raw_para(idx, text, style="목차", kind=BlockKind.TOC_ENTRY)


def _table(idx: _Idx, rows: tuple[tuple[str, ...], ...]) -> RawBlock:
    return _raw_para(idx, "", style="", kind=BlockKind.TABLE, table_cells=rows)


def _make_engine() -> NumberingEngine:
    abstract_req = AbstractNumDef(
        abstract_num_id="140",
        levels=MappingProxyType(
            {
                0: LevelDef(ilvl=0, lvl_text="%1.", num_fmt="decimal", start=1, suff=None),
                1: LevelDef(ilvl=1, lvl_text="(%2)", num_fmt="lowerLetter", start=1, suff=None),
                2: LevelDef(ilvl=2, lvl_text="(%3)", num_fmt="lowerRoman", start=1, suff=None),
            }
        ),
    )
    abstract_app = AbstractNumDef(
        abstract_num_id="51",
        levels=MappingProxyType(
            {
                0: LevelDef(ilvl=0, lvl_text="A%1.", num_fmt="decimal", start=1, suff=None),
                1: LevelDef(ilvl=1, lvl_text="", num_fmt="bullet", start=1, suff=None),
            }
        ),
    )
    num_defs = {
        "86": NumDef(num_id="86", abstract_num_id="140", level_overrides=MappingProxyType({})),
        "118": NumDef(num_id="118", abstract_num_id="51", level_overrides=MappingProxyType({})),
    }
    abstract_nums = {"140": abstract_req, "51": abstract_app}
    return NumberingEngine(MappingProxyType(abstract_nums), MappingProxyType(num_defs))


def _feed_all(machine: StructureMachine, raws: list[RawBlock]) -> list[Block]:
    return [machine.feed(r) for r in raws]


# ---------------------------------------------------------------------------
# T1~T14 — 상태머신 단위 테스트
# ---------------------------------------------------------------------------


def test_t1_state_transitions_pretoc_toc_body() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    cover = _raw_para(idx, "회계감사기준 전문", style="")
    toc = _toc_entry(idx, "서론 ......... 1")
    heading = _heading(idx, "감사기준서 200 독립된 감사인의 전반적인 목적", level=1)
    blocks = _feed_all(machine, [cover, toc, heading])

    assert blocks[0].standard_no is None
    assert blocks[1].is_toc is True
    assert blocks[1].standard_no is None
    assert machine.state == "STANDARD_BODY"
    assert blocks[2].standard_no == "200"
    assert blocks[2].standard_title == "독립된 감사인의 전반적인 목적"
    assert blocks[2].heading_trail == ("감사기준서 200",)


def test_t2_section_and_heading_trail() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200 제목", 1),
        _heading(idx, "서론", 2),
        _heading(idx, "이 감사기준서의 범위", 3),
    ]
    blocks = _feed_all(machine, raws)
    assert blocks[1].section == Section.INTRO
    assert blocks[2].section == Section.INTRO
    assert blocks[2].heading_trail == ("감사기준서 200", "서론", "이 감사기준서의 범위")
    assert blocks[2].immediate_heading == "이 감사기준서의 범위"


def test_t3_overall_objective_isa_200() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _heading(idx, "감사인의 전반적인 목적", 2),
    ]
    blocks = _feed_all(machine, raws)
    assert blocks[1].section == Section.OVERALL_OBJECTIVE


def test_t4_requirement_and_sub_item_parent() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _heading(idx, "요구사항", 2),
        _raw_para(idx, "요구사항 1", num_id="86", ilvl=0),
        _raw_para(idx, "하위 a", num_id="86", ilvl=1),
    ]
    blocks = _feed_all(machine, raws)
    assert blocks[2].kind == BlockKind.REQUIREMENT
    assert blocks[2].paragraph_id == "1."
    assert blocks[2].parent_paragraph_id is None
    assert blocks[3].kind == BlockKind.SUB_ITEM
    assert blocks[3].paragraph_id == "(a)"
    assert blocks[3].parent_paragraph_id == "1."


def test_t5_application_guidance_links_to_requirement() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _heading(idx, "요구사항", 2),
    ]
    # 9 개 요구사항을 만들어 마지막이 '9.' 이 되도록 한다.
    for n in range(9):
        raws.append(_raw_para(idx, f"요구사항 {n + 1}", num_id="86", ilvl=0))
    raws += [
        _heading(idx, "적용 및 기타 설명자료", 2),
        _raw_para(idx, "적용지침 A1", num_id="118", ilvl=0),
    ]
    blocks = _feed_all(machine, raws)
    app_block = blocks[-1]
    assert app_block.kind == BlockKind.APPLICATION_GUIDANCE
    assert app_block.paragraph_id == "A1."
    assert app_block.parent_paragraph_id == "9."
    assert app_block.is_application_guidance is True


def test_t6_engine_reset_on_standard_boundary() -> None:
    """numId=86 이 두 기준서에 걸쳐 등장해도 두 번째 기준서에서 1. 부터 시작해야 한다."""
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _heading(idx, "요구사항", 2),
        _raw_para(idx, "req1", num_id="86", ilvl=0),
        _raw_para(idx, "req2", num_id="86", ilvl=0),
        _heading(idx, "감사기준서 210", 1),
        _heading(idx, "요구사항", 2),
        _raw_para(idx, "req1-210", num_id="86", ilvl=0),
        _raw_para(idx, "req2-210", num_id="86", ilvl=0),
    ]
    blocks = _feed_all(machine, raws)
    assert blocks[2].paragraph_id == "1."
    assert blocks[3].paragraph_id == "2."
    assert blocks[6].paragraph_id == "1."
    assert blocks[6].standard_no == "210"
    assert blocks[7].paragraph_id == "2."
    assert machine.enter_standard_count == 2


def test_t7_single_cell_table_promoted_to_block_quote() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _heading(idx, "적용 및 기타 설명자료", 2),
        _table(idx, (("경고 박스 본문",),)),
    ]
    blocks = _feed_all(machine, raws)
    quoted = blocks[-1]
    assert quoted.kind == BlockKind.BLOCK_QUOTE
    assert quoted.text == "경고 박스 본문"
    assert quoted.table_cells is None
    assert quoted.heading_trail == ("감사기준서 200", "적용 및 기타 설명자료")
    assert quoted.section == Section.APPLICATION


def test_t8_multi_cell_table_retains_cells() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 315", 1),
        _table(idx, (("col A", "col B"), ("val 1", "val 2"))),
    ]
    blocks = _feed_all(machine, raws)
    table_block = blocks[-1]
    assert table_block.kind == BlockKind.TABLE
    assert table_block.table_cells == (("col A", "col B"), ("val 1", "val 2"))
    assert table_block.text == ""


def test_t9_appendix_heading_stacks_at_level_three() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 230", 1),
        _heading(idx, "적용 및 기타 설명자료", 2),
        _heading(idx, "이전 heading 3", 3),
        _raw_para(idx, "보론 제목1", style="보론 제목", kind=BlockKind.HEADING),
        _raw_para(idx, "보론 본문", num_id=None, ilvl=None),
    ]
    blocks = _feed_all(machine, raws)
    appendix_heading = blocks[3]
    # heading 3 이 pop 되고 보론 제목이 level=3 으로 push 된다
    assert appendix_heading.heading_trail == (
        "감사기준서 230",
        "적용 및 기타 설명자료",
        "보론 제목1",
    )
    assert appendix_heading.section == Section.APPENDIX
    body = blocks[4]
    assert body.section == Section.APPENDIX
    assert body.heading_trail[-1] == "보론 제목1"


def test_t9b_appendix_heading2_dynamic_match() -> None:
    """F5: heading 2 텍스트가 `^보론\\s*\\d+\\b` 패턴이면 Section.APPENDIX 동적 할당.

    ISA-1200 의 `보론 1 용어의 정의`, `보론 2 감사보고서` 처럼 `보론 제목` 전용
    스타일이 아닌 heading 2 로 보론 섹션이 열리는 케이스. 정적 `_SECTION_BY_HEADING2`
    매핑 실패 시 정규식 fallback.
    """
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 1200", 1),
        _heading(idx, "요구사항", 2),
        _raw_para(idx, "본문 1", num_id="140", ilvl=0),
        _heading(idx, "보론 1 용어의 정의", 2),
        _raw_para(idx, "보론 본문", num_id=None, ilvl=None),
        _heading(idx, "보론 2 감사보고서", 2),
        _raw_para(idx, "보론 본문 2", num_id=None, ilvl=None),
    ]
    blocks = _feed_all(machine, raws)
    assert blocks[1].section == Section.REQUIREMENTS
    assert blocks[2].section == Section.REQUIREMENTS
    assert blocks[3].section == Section.APPENDIX
    assert blocks[4].section == Section.APPENDIX
    assert blocks[5].section == Section.APPENDIX
    assert blocks[6].section == Section.APPENDIX


def test_t9c_heading2_similar_to_보론_but_not_appendix_rejected() -> None:
    """F5 regression: `보론적인 고려사항` 같은 오검출 방지 (word boundary `\\b`).

    team-lead 3차 rework 스펙 C1~C4 — `보론적`, `보론자`, `보론의`, `보론인` 등
    유사어가 숫자와 결합되지 않으면 APPENDIX 로 매핑되지 않아야 한다.
    """
    false_positives = [
        "보론적인 고려사항",
        "보론자 등의 역할",
        "보론의 의미",
        "보론인에 대한 설명",
    ]
    for text in false_positives:
        idx = _Idx()
        machine = StructureMachine(_make_engine())
        raws = [
            _heading(idx, "감사기준서 999", 1),
            _heading(idx, "요구사항", 2),
            _heading(idx, text, 2),
            _raw_para(idx, "본문", num_id=None, ilvl=None),
        ]
        blocks = _feed_all(machine, raws)
        # 매핑 실패 → 이전 section (REQUIREMENTS) 유지
        assert blocks[3].section == Section.REQUIREMENTS, (
            f"오검출: '{text}' 가 APPENDIX 로 매핑됨"
        )


def test_t9d_appendix_heading2_whitespace_variants() -> None:
    """F5 regression: `보론1` / `보론 1` / `보론  2` whitespace 변형 모두 매칭."""
    for text in ["보론1 용어", "보론 1 용어", "보론  2 용어", "보론\t3 용어"]:
        idx = _Idx()
        machine = StructureMachine(_make_engine())
        raws = [
            _heading(idx, "감사기준서 999", 1),
            _heading(idx, "요구사항", 2),
            _heading(idx, text, 2),
            _raw_para(idx, "본문", num_id=None, ilvl=None),
        ]
        blocks = _feed_all(machine, raws)
        assert blocks[2].section == Section.APPENDIX, f"매칭 실패: '{text}'"
        assert blocks[3].section == Section.APPENDIX


def test_t10_toc_style_marks_is_toc_globally() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _heading(idx, "요구사항", 2),
        _toc_entry(idx, "요구사항 ....... 12"),
    ]
    blocks = _feed_all(machine, raws)
    toc = blocks[-1]
    assert toc.is_toc is True
    assert toc.kind == BlockKind.TOC_ENTRY
    # heading_stack 영향 없음 (section 유지)
    assert toc.section == Section.REQUIREMENTS


def test_t11_isa_1200_triple_purpose_no_error() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 1200", 1),
        _heading(idx, "목적", 2),
        _heading(idx, "목적", 2),
        _heading(idx, "목적", 2),
    ]
    blocks = _feed_all(machine, raws)
    assert all(b.section == Section.PURPOSE for b in blocks[1:])


def test_t12_unknown_numbering_preserved() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 200", 1),
        _raw_para(idx, "이상한 문단", num_id="9999", ilvl=0),
    ]
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("ignore")
        blocks = _feed_all(machine, raws)
    unknown = blocks[-1]
    assert unknown.kind == BlockKind.UNKNOWN_NUMBERING
    assert unknown.paragraph_id is None


def test_t13_pretoc_blocks_have_no_standard() -> None:
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [_raw_para(idx, "표지 텍스트", style="")]
    blocks = _feed_all(machine, raws)
    assert blocks[0].standard_no is None
    assert blocks[0].section is None
    assert machine.state == "PRE_TOC"


def test_t14_heading_3_ambiguous_text_does_not_switch_standard() -> None:
    """EC-4: 'heading 3' 로 '감사기준서 315와 ... 간의 관계' 가 와도 경계 아님."""
    idx = _Idx()
    machine = StructureMachine(_make_engine())
    raws = [
        _heading(idx, "감사기준서 315", 1),
        _heading(idx, "감사기준서 315와 감사기준서 610 간의 관계", 3),
    ]
    blocks = _feed_all(machine, raws)
    assert blocks[1].standard_no == "315"
    # heading 3 은 스택에 push 되지만 state 전환은 아님
    assert machine.state == "STANDARD_BODY"
    assert "감사기준서 315" in blocks[1].heading_trail


# ---------------------------------------------------------------------------
# E2E — 실제 DOCX
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="실제 DOCX 없음")
def test_iter_blocks_e2e_real_docx() -> None:
    with open_docx_zip(_REAL_DOCX) as zf:
        abstract_nums, num_defs = parse_numbering_from_docx(zf)
    engine = NumberingEngine(abstract_nums, num_defs)

    blocks = list(iter_blocks(iter_body(_REAL_DOCX), engine))

    assert len(blocks) > 5000

    # 1. ISA 기준서 수
    standards = {b.standard_no for b in blocks if b.standard_no is not None}
    assert len(standards) >= 35, f"기준서 수 부족: {len(standards)}"

    # 2. 첫 REQ, 첫 APP paragraph_id
    req_blocks = [b for b in blocks if b.kind == BlockKind.REQUIREMENT]
    app_blocks = [b for b in blocks if b.kind == BlockKind.APPLICATION_GUIDANCE]
    assert req_blocks, "REQUIREMENT 블록 없음"
    assert app_blocks, "APPLICATION_GUIDANCE 블록 없음"
    assert req_blocks[0].paragraph_id == "1."
    assert app_blocks[0].paragraph_id == "A1."

    # 3. 기준서 550 의 첫 REQ paragraph_id == '1.' (numId=86 리셋 회귀 가드)
    std_550_reqs = [b for b in blocks if b.kind == BlockKind.REQUIREMENT and b.standard_no == "550"]
    if std_550_reqs:
        assert std_550_reqs[0].paragraph_id == "1.", (
            f"ISA-550 첫 REQ: {std_550_reqs[0].paragraph_id}"
        )

    # 4. unknown_numbering 비율 < 5%
    metrics = engine.metrics()
    total_numbered = sum(metrics.values())
    unknown = metrics.get("unknown_numbering", 0)
    assert total_numbered > 0
    ratio = unknown / total_numbered
    assert ratio < 0.05, f"unknown_numbering 비율 {ratio:.2%} >= 5%"

    # 5. is_toc 블록 존재
    toc_count = sum(1 for b in blocks if b.is_toc)
    assert toc_count > 500

    # 6. BLOCK_QUOTE 승격 수
    block_quote_count = sum(1 for b in blocks if b.kind == BlockKind.BLOCK_QUOTE)
    assert block_quote_count >= 20

    # 7. 모든 APP 블록의 parent 가 동일 기준서 REQ 거나 None
    for app in app_blocks:
        if app.parent_paragraph_id is None or app.standard_no is None:
            continue
        same_std_reqs = {
            b.paragraph_id
            for b in blocks
            if b.kind == BlockKind.REQUIREMENT and b.standard_no == app.standard_no
        }
        assert app.parent_paragraph_id in same_std_reqs, (
            f"APP {app.paragraph_id} (std={app.standard_no}) parent 누수"
        )
