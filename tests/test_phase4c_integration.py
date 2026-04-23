"""Phase 4c integration tests — built up across c1/c2/c3 commits.

Scope (c1):
    * `docx_reader` recursive descent toggle (ISA vs non-ISA path)
    * `_MAX_DESCENT_DEPTH` infinite-loop guard (Critic verbal note #X2)
    * `spec.body_parser` dispatch path (ISQM tbl[236x2])
    * ISA 36 JSON byte-equivalence regression check

Scope (c2 — placeholder markers, populated in c2 commit):
    * PreludeSkip Option (i) caller state toggle (3 variant)
    * Referential transparency invariant (Critic Q1 — (ii) drift detector)
    * FRMK normalize heading 2 한정 (Critic #X3)

Scope (c3 — placeholder markers, populated in c3 commit):
    * 3 DOCX → 3 MD 산출 smoke
    * 3-level suffix chunk_id 부재 invariant (Critic Q2 — β-1 결정적)
    * CLI --prefix heuristic 10건
    * FRMK special_appendix_name JSON payload smoke (1 chunk)
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from lxml import etree

from audit_parser.ir.docx_reader import _MAX_DESCENT_DEPTH, _iter_block_level
from audit_parser.ir.types import BlockKind, RawBlock
from audit_parser.spec import ISA_SPEC, ISQM_SPEC

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_body_fragment(xml: str) -> etree._Element:
    """Wrap arbitrary ``<w:p>`` / ``<w:tbl>`` XML into a ``<w:body>`` element."""
    return etree.fromstring(
        f'<w:body xmlns:w="{_W_NS}">{xml}</w:body>'
    )


# ---------------------------------------------------------------------------
# c1 — recursive descent toggle
# ---------------------------------------------------------------------------


def test_iter_block_level_default_no_recurse_preserves_phase1_behavior() -> None:
    """ISA path (`recurse=False`) — top-level `<w:p>` + `<w:tbl>` 만 yield, 내부
    wrapper table cell 내부 `<w:p>` 는 unvisited."""
    body = _make_body_fragment(
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>outer_p</w:t></w:r></w:p>'
        f'<w:tbl xmlns:w="{_W_NS}">'
        f"<w:tr><w:tc>"
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>inner_p</w:t></w:r></w:p>'
        f"</w:tc></w:tr>"
        f"</w:tbl>"
    )
    children = list(_iter_block_level(body, recurse=False))
    # 기존 Phase 1 동작: outer <w:p> + <w:tbl> 각 1개 yield, 내부 <w:p> 는 skip
    tags = [_local_tag(c) for c in children]
    assert tags == ["p", "tbl"]


def test_iter_block_level_recurse_descends_into_wrapper_tables() -> None:
    """non-ISA path (`recurse=True`) — wrapper table 내부 `<w:p>` 를 descent yield.

    ASSR ``tbl[427x2]`` / FRMK ``tbl[3x3]`` 처럼 body content 가 wrapper table
    내부에 있는 경우 내부 `<w:p>` 가 top-level 처럼 visible 해야 함.
    """
    body = _make_body_fragment(
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>outer_p</w:t></w:r></w:p>'
        f'<w:tbl xmlns:w="{_W_NS}">'
        f"<w:tr><w:tc>"
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>inner_p</w:t></w:r></w:p>'
        f"</w:tc></w:tr>"
        f"</w:tbl>"
    )
    children = list(_iter_block_level(body, recurse=True))
    # outer <w:p> + <w:tbl> + inner <w:p> (descent 결과) = 3개
    tags = [_local_tag(c) for c in children]
    assert tags == ["p", "tbl", "p"]
    # 마지막 <w:p> 의 text 가 "inner_p" (descent 결과 정확)
    inner_p = children[-1]
    texts = [t.text for t in inner_p.iter(f"{{{_W_NS}}}t") if t.text]
    assert texts == ["inner_p"]


def test_iter_block_level_recurse_handles_sdt_container() -> None:
    """recurse mode 에서도 `<w:sdt>` container 내부 `<w:p>` 는 기존 방식 유지."""
    body = etree.fromstring(
        f'<w:body xmlns:w="{_W_NS}">'
        f"<w:sdt><w:sdtContent>"
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>sdt_inner</w:t></w:r></w:p>'
        f"</w:sdtContent></w:sdt>"
        f"</w:body>"
    )
    children = list(_iter_block_level(body, recurse=True))
    assert [_local_tag(c) for c in children] == ["p"]


# ---------------------------------------------------------------------------
# c1 — _MAX_DESCENT_DEPTH guard (Critic verbal note #X2)
# ---------------------------------------------------------------------------


def test_max_descent_depth_constant_is_10() -> None:
    """Critic #X2 — 실제 KICPA DOCX 관찰 depth ~3, 여유 10 책정."""
    assert _MAX_DESCENT_DEPTH == 10


def test_iter_block_level_rejects_descent_depth_overflow() -> None:
    """infinite loop 방어 — depth > MAX 시 AssertionError.

    실제로는 KICPA DOCX 에 depth=11 nested table 이 존재하지 않으나, code-level
    guard 가 trigger 되는지 synthetic depth=11 body 로 검증.
    """
    # Build a synthetic body with 11 nested <w:tbl>/cell wrapping a single <w:p>.
    inner = f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>deep</w:t></w:r></w:p>'
    for _ in range(11):
        inner = (
            f'<w:tbl xmlns:w="{_W_NS}">'
            f"<w:tr><w:tc>{inner}</w:tc></w:tr>"
            f"</w:tbl>"
        )
    body = _make_body_fragment(inner)
    with pytest.raises(AssertionError, match="descent depth exceeded"):
        list(_iter_block_level(body, recurse=True))


def test_iter_block_level_depth_within_limit_ok() -> None:
    """MAX 이하 depth 는 정상 동작 (경계 3 에서 확인 — 실 KICPA depth 수준)."""
    inner = f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>ok</w:t></w:r></w:p>'
    for _ in range(3):
        inner = (
            f'<w:tbl xmlns:w="{_W_NS}">'
            f"<w:tr><w:tc>{inner}</w:tc></w:tr>"
            f"</w:tbl>"
        )
    body = _make_body_fragment(inner)
    # depth=3 → AssertionError 없음. inner <w:p> 가 descent 결과로 yield 되는지.
    children = list(_iter_block_level(body, recurse=True))
    # 3 tbl + 1 p (최내부) = 4 (각 descent 단계마다 tbl 1개 yield)
    assert len(children) >= 1
    # 마지막 yield 된 <w:p> 의 text 는 "ok"
    last_p = children[-1]
    assert _local_tag(last_p) == "p"
    texts = [t.text for t in last_p.iter(f"{{{_W_NS}}}t") if t.text]
    assert texts == ["ok"]


# ---------------------------------------------------------------------------
# c1 — spec.body_parser dispatch (ISQM path)
# ---------------------------------------------------------------------------


def test_isqm_spec_body_parser_is_attached_and_callable() -> None:
    """4b-2 c2 에서 attach 된 ISQM_SPEC.body_parser 가 c1 에서 여전히 호출 가능한지."""
    assert ISQM_SPEC.body_parser is not None
    assert callable(ISQM_SPEC.body_parser)


def test_isqm_body_parser_emits_atomic_rawblocks_without_chunk_of_leak() -> None:
    """β-1 invariant (docs/checkpoint_4_prep.md §1.8) — ISQM body_parser 가 atomic
    RawBlock emit only. RawBlock dataclass 에 ``chunk_of`` 필드 부재 — state leak
    경로 자체 없음. Critic Q2 가 c3 에서 후방 3-level suffix grep test 로 결정적
    검증을 수행하며, c1 에서는 여기서 dataclass 구조 확인.
    """
    # Build a minimal ISQM 2-column table fragment.
    tbl_xml = (
        f'<w:tbl xmlns:w="{_W_NS}">'
        f"<w:tr>"
        f'<w:tc><w:p xmlns:w="{_W_NS}"><w:r><w:t>1</w:t></w:r></w:p></w:tc>'
        f'<w:tc><w:p xmlns:w="{_W_NS}"><w:r><w:t>본문</w:t></w:r></w:p></w:tc>'
        f"</w:tr>"
        f"</w:tbl>"
    )
    tbl = etree.fromstring(tbl_xml)
    body_parser = ISQM_SPEC.body_parser
    assert body_parser is not None
    emitted: Iterable[RawBlock] = body_parser(tbl)
    blocks = list(emitted)
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, RawBlock)
    assert block.kind is BlockKind.REQUIREMENT
    assert block.paragraph_id == "1"
    # RawBlock dataclass 에 chunk_of 필드 부재 — β-1 invariant 구조적 보증
    assert not hasattr(block, "chunk_of")


# ---------------------------------------------------------------------------
# c1 — ISA baseline backward-compat (iter_body 36 ISA 재파싱 default path)
# ---------------------------------------------------------------------------


def test_iter_body_default_spec_resolves_to_isa() -> None:
    """iter_body(docx_path) default spec 이 None → lazy resolve 시 ISA_SPEC.

    Circular import 회피를 위해 signature default 는 ``None``, 함수 진입 시점
    ``from audit_parser.spec import ISA_SPEC`` 로 lazy resolve. ISA path backward-
    compat 는 c1 regression test (`test_iter_block_level_default_no_recurse_*`)
    + ISA 36 JSON byte-equiv test 로 보증.
    """
    import inspect

    from audit_parser.ir.docx_reader import iter_body

    sig = inspect.signature(iter_body)
    spec_param = sig.parameters["spec"]
    assert spec_param.default is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _local_tag(elem: etree._Element) -> str:
    """``{ns}p`` → ``"p"``."""
    tag = elem.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


# ---------------------------------------------------------------------------
# c2 — PreludeSkip Option (i) 3축 drift detection
# ---------------------------------------------------------------------------


def test_prelude_skip_caller_state_toggle_variant_isqm() -> None:
    """PreludeSkip Option (i) — ISQM variant.

    ISQM_SPEC 는 body_parser 를 통해 table-level dispatch 를 하므로 prelude_skip
    은 None. StructureMachine 초기화 시 `_in_prelude=False` 예상.
    """
    from audit_parser.ir.numbering import NumberingEngine
    from audit_parser.ir.structure import StructureMachine

    machine = StructureMachine(NumberingEngine({}, {}), spec=ISQM_SPEC)
    # ISQM_SPEC.prelude_skip is None → caller state 는 False 로 초기화
    assert machine._in_prelude is False


def test_prelude_skip_caller_state_toggle_variant_assr_frmk() -> None:
    """PreludeSkip Option (i) — ASSR + FRMK variants.

    ASSR_SPEC / FRMK_SPEC 은 prelude_skip 을 제공 → caller `_in_prelude=True`
    초기값 + marker block 통해 toggle 정상 동작 검증.

    Critic rework #2 trigger guard — (ii) stateful filter / (iii) declarative
    tuple 해석 drift 시 이 test fail.
    """
    from audit_parser.ir.numbering import NumberingEngine
    from audit_parser.ir.structure import StructureMachine
    from audit_parser.ir.types import BlockKind
    from audit_parser.spec import ASSR_SPEC, FRMK_SPEC

    # ASSR — marker = "서론" text
    assr_machine = StructureMachine(NumberingEngine({}, {}), spec=ASSR_SPEC)
    assert assr_machine._in_prelude is True
    # Pre-marker block (random content): predicate False → skip via caller state
    pre_block = RawBlock(
        idx=0, kind=BlockKind.PARAGRAPH_BODY, text="개정 배경",
        style="", num_id=None, ilvl=None,
    )
    assert assr_machine.feed(pre_block) is None
    assert assr_machine._in_prelude is True  # state preserved
    # Marker block: predicate True → toggle + skip marker
    marker = RawBlock(
        idx=1, kind=BlockKind.PARAGRAPH_BODY, text="서론",
        style="", num_id=None, ilvl=None,
    )
    assert assr_machine.feed(marker) is None
    assert assr_machine._in_prelude is False  # toggled

    # FRMK — marker = heading 2 + text startswith "문단번호"
    frmk_machine = StructureMachine(NumberingEngine({}, {}), spec=FRMK_SPEC)
    assert frmk_machine._in_prelude is True
    pre_frmk = RawBlock(
        idx=0, kind=BlockKind.PARAGRAPH_BODY, text="개정 배경",
        style="", num_id=None, ilvl=None,
    )
    assert frmk_machine.feed(pre_frmk) is None
    assert frmk_machine._in_prelude is True
    marker_frmk = RawBlock(
        idx=1, kind=BlockKind.HEADING, text="문단번호",
        style="heading 2", num_id=None, ilvl=None,
    )
    assert frmk_machine.feed(marker_frmk) is None
    assert frmk_machine._in_prelude is False


def test_prelude_skip_predicate_is_referentially_transparent() -> None:
    """Critic Q1 2026-04-23 LOCK — (ii) hidden state drift 결정적 invariant.

    동일 RawBlock 2회 호출 시 동일 결과. 변동 = hidden state = (ii) drift.
    closure / dict / class-state 전 변형을 단일 assertion 으로 포착.
    """
    from audit_parser.ir.types import BlockKind
    from audit_parser.spec import ASSR_SPEC, FRMK_SPEC

    # ASSR — "서론" marker
    if ASSR_SPEC.prelude_skip is not None:
        marker = RawBlock(
            idx=0, kind=BlockKind.PARAGRAPH_BODY, text="서론",
            style="", num_id=None, ilvl=None,
        )
        first = ASSR_SPEC.prelude_skip(marker)
        second = ASSR_SPEC.prelude_skip(marker)
        assert first == second, (
            f"ASSR prelude_skip 가 동일 block 에 대해 {first} → {second} 변동 — "
            f"hidden predicate state = (ii) drift (Critic rework #2 trigger)"
        )

    # FRMK — heading 2 "문단번호" marker
    if FRMK_SPEC.prelude_skip is not None:
        marker_frmk = RawBlock(
            idx=0, kind=BlockKind.HEADING, text="문단번호",
            style="heading 2", num_id=None, ilvl=None,
        )
        first_frmk = FRMK_SPEC.prelude_skip(marker_frmk)
        second_frmk = FRMK_SPEC.prelude_skip(marker_frmk)
        assert first_frmk == second_frmk


def test_structure_machine_exposes_in_prelude_attribute() -> None:
    """Critic Q3 2026-04-23 LOCK — 3축 중 axis 2 (caller state) 감지.

    `hasattr(machine, "_in_prelude")` attribute 부재 시 (ii) drift. 본 test 는
    StructureMachine 이 `_in_prelude` slot 을 유지하고 있음을 보증. Slot rename
    시 (예: `_prelude_state` 로 변경) 이 test fail → Critic rework #2 trigger.
    """
    from audit_parser.ir.numbering import NumberingEngine
    from audit_parser.ir.structure import StructureMachine
    from audit_parser.spec import ASSR_SPEC, FRMK_SPEC

    for spec in (ASSR_SPEC, FRMK_SPEC, ISQM_SPEC, ISA_SPEC):
        machine = StructureMachine(NumberingEngine({}, {}), spec=spec)
        assert hasattr(machine, "_in_prelude"), (
            f"{spec.prefix} StructureMachine missing _in_prelude — (ii) drift "
            f"(Critic rework #2 trigger)"
        )


def test_spec_prelude_skip_is_callable_when_provided() -> None:
    """Critic Q3 axis 1 (iii) declarative tuple drift 감지.

    `spec.prelude_skip` 이 callable (non-tuple) 여야 함. tuple 로 declarative
    marker 를 선언하면 `callable(...)` False → rework #2 trigger.
    """
    from audit_parser.spec import ASSR_SPEC, FRMK_SPEC

    for spec in (ASSR_SPEC, FRMK_SPEC):
        if spec.prelude_skip is not None:
            assert callable(spec.prelude_skip), (
                f"{spec.prefix} prelude_skip is not callable — (iii) drift "
                f"(Critic rework #2 trigger)"
            )


# ---------------------------------------------------------------------------
# c2 — FRMK normalize_framework_heading wiring (heading 2 한정)
# ---------------------------------------------------------------------------


def test_frmk_render_heading_2_normalizes_range_suffix() -> None:
    """Critic #X3 — heading 2 에서 range suffix strip + HTML 주석 보존.

    Phase 4d forward-contract (Domain Reviewer Check 2):
    - cleaned text ``"서론"`` 이 display 에 나옴
    - range ``"1-4"`` 는 HTML 주석 ``<!-- range: 1-4 -->`` 로 보존
    """
    from audit_parser.convert.md_renderer import _render_heading
    from audit_parser.ir.types import Block, BlockKind
    from audit_parser.spec import FRMK_SPEC

    block = Block(
        idx=10, kind=BlockKind.HEADING, text="서론1-4",
        style="heading 2",
        paragraph_id=None, is_application_guidance=False,
        parent_paragraph_id=None, standard_no="1", standard_title="인증업무개념체계",
        section=None, heading_trail=(), immediate_heading=None,
    )
    lines = _render_heading(block, prev_section=None, spec=FRMK_SPEC)
    # line 0 = heading display. cleaned "서론" — range 제거.
    assert lines[0] == "## 서론"
    # line 1 = HTML comment. "range: 1-4" 포함.
    assert "range: 1-4" in lines[1]
    # range suffix 가 display line 에 leak 되지 않음.
    assert "1-4" not in lines[0]


def test_frmk_render_heading_1_does_not_normalize_year_suffix() -> None:
    """Critic #X3 핵심 — heading 1 의 연도 suffix silent strip 방지.

    ``"인증업무개념체계 2022"`` (heading 1 title) 는 연도가 strip 되면 안 됨.
    heading 2 한정 normalize 가 엄격 작동하는지 검증.
    """
    from audit_parser.convert.md_renderer import _render_heading
    from audit_parser.ir.types import Block, BlockKind
    from audit_parser.spec import FRMK_SPEC

    block = Block(
        idx=0, kind=BlockKind.HEADING, text="인증업무개념체계 2022",
        style="heading 1",
        paragraph_id=None, is_application_guidance=False,
        parent_paragraph_id=None, standard_no=None, standard_title=None,
        section=None, heading_trail=(), immediate_heading=None,
    )
    lines = _render_heading(block, prev_section=None, spec=FRMK_SPEC)
    # heading 1 이므로 normalize 미적용 — 연도 2022 유지
    assert lines[0] == "# 인증업무개념체계 2022"
    assert "2022" in lines[0]
    # HTML comment 에 range 필드 없음 (range_suffix is None)
    assert "range:" not in lines[1]


def test_non_frmk_render_heading_skips_normalization() -> None:
    """ISA/ISQM/ASSR spec 에서는 normalize 미적용 — 기존 heading 동작 유지."""
    from audit_parser.convert.md_renderer import _render_heading
    from audit_parser.ir.types import Block, BlockKind
    from audit_parser.spec import ASSR_SPEC

    block = Block(
        idx=5, kind=BlockKind.HEADING, text="서론1-4",
        style="heading 2",
        paragraph_id=None, is_application_guidance=False,
        parent_paragraph_id=None, standard_no="3000", standard_title=None,
        section=None, heading_trail=(), immediate_heading=None,
    )
    lines = _render_heading(block, prev_section=None, spec=ASSR_SPEC)
    # ASSR spec 에서는 normalize 미적용 — raw text 그대로
    assert lines[0] == "## 서론1-4"
    assert "range:" not in lines[1]


# ---------------------------------------------------------------------------
# c2 — md_parser auto-dispatch
# ---------------------------------------------------------------------------


def test_parse_md_default_spec_is_none_for_auto_dispatch() -> None:
    """parse_md(path) default spec=None → frontmatter 기반 auto-dispatch."""
    import inspect

    from audit_parser.ingest.md_parser import parse_md

    sig = inspect.signature(parse_md)
    spec_param = sig.parameters["spec"]
    assert spec_param.default is None


# ---------------------------------------------------------------------------
# c3 — CLI --prefix + heuristic 10건 (Critic #X1 Option A + Domain Check 4)
# ---------------------------------------------------------------------------


def test_infer_prefix_heuristic_4_real_filenames() -> None:
    """4 실제 KICPA DOCX 파일명 heuristic 매핑."""
    from pathlib import Path

    from audit_parser.cli import _infer_prefix_from_filename

    assert (
        _infer_prefix_from_filename(
            Path("raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx")
        )
        == "ISQM"
    )
    assr_name = (
        "raw/역사적 재무정보에 대한 감사 및 검토 이외의 "
        "인증업무기준(2022년 개정)_전문(개정개요 포함).docx"
    )
    assert _infer_prefix_from_filename(Path(assr_name)) == "ASSR"
    assert (
        _infer_prefix_from_filename(Path("raw/인증업무개념체계(2022년 개정)_전문.docx"))
        == "FRMK"
    )
    assert (
        _infer_prefix_from_filename(Path("raw/0. 회계감사기준 전문(2025 개정).docx"))
        == "ISA"
    )


def test_infer_prefix_ambiguous_raises_valueerror() -> None:
    """Multiple prefix substrings → ambiguous, silent mis-dispatch 차단."""
    from pathlib import Path

    import pytest

    from audit_parser.cli import _infer_prefix_from_filename

    with pytest.raises(ValueError, match="Ambiguous prefix"):
        _infer_prefix_from_filename(
            Path("raw/품질관리기준서_인증업무개념체계_합본.docx")
        )


def test_infer_prefix_no_match_returns_none() -> None:
    """heuristic 실패 시 None — caller 가 help message 표시."""
    from pathlib import Path

    from audit_parser.cli import _infer_prefix_from_filename

    assert _infer_prefix_from_filename(Path("raw/unknown_standard.docx")) is None


def test_resolve_spec_prefix_override_takes_precedence() -> None:
    """--prefix 명시 시 파일명 heuristic 무시."""
    from pathlib import Path

    from audit_parser.cli import _resolve_spec
    from audit_parser.spec import ISQM_SPEC

    # 파일명으로는 FRMK 가 추론되지만 --prefix ISQM 명시.
    resolved = _resolve_spec(
        Path("raw/인증업무개념체계(2022년 개정)_전문.docx"),
        prefix_override="ISQM",
    )
    assert resolved is ISQM_SPEC


def test_resolve_spec_unknown_prefix_raises() -> None:
    """--prefix 미등록 값 rejection."""
    from pathlib import Path

    import pytest

    from audit_parser.cli import _resolve_spec

    with pytest.raises(ValueError, match="Unknown --prefix"):
        _resolve_spec(Path("raw/dummy.docx"), prefix_override="XXXX")


def test_resolve_spec_no_heuristic_match_raises_with_help() -> None:
    """파일명 heuristic 실패 + --prefix 미지정 → ValueError with help."""
    from pathlib import Path

    import pytest

    from audit_parser.cli import _resolve_spec

    with pytest.raises(ValueError, match="Specify --prefix explicitly"):
        _resolve_spec(Path("raw/unknown_standard.docx"), prefix_override=None)


@pytest.mark.parametrize(
    "prefix,expected_spec_prefix",
    [("ISA", "ISA"), ("ISQM", "ISQM"), ("ASSR", "ASSR"), ("FRMK", "FRMK")],
)
def test_resolve_spec_explicit_prefix_all_4(
    prefix: str, expected_spec_prefix: str
) -> None:
    """4 prefix 명시 positive — silent fallback 없음."""
    from pathlib import Path

    from audit_parser.cli import _resolve_spec

    # 파일명이 aware 없어도 명시 prefix 로 spec 선택.
    spec = _resolve_spec(Path("raw/unknown.docx"), prefix_override=prefix)
    assert spec.prefix == expected_spec_prefix


# ---------------------------------------------------------------------------
# c3 — Critic Q2 3-level suffix chunk_id 결정적 invariant
# ---------------------------------------------------------------------------


def test_no_3level_suffix_in_existing_isa_chunks() -> None:
    """Critic Q2 결정적 β-1 invariant (baseline check).

    36 ISA JSON 의 기존 chunk_id set 에 3-level ``#\\d+#\\d+#\\d+`` 존재 부재
    확인. Phase 4c c2 body_parser wiring 이 3-level 유발하지 않아야 함.

    Phase 4d 에서 실제 ISQM/ASSR/FRMK JSON 생성 후 동일 invariant 를 전 collection
    에 적용 (그 때는 `full_pipeline_from_docx` helper 작성 후 통합 test 확장).
    """
    import json
    import re
    from pathlib import Path

    SUFFIX_3LEVEL_RE = re.compile(r"#\d+#\d+#\d+")

    isa_json_dir = Path(__file__).parent.parent / "output" / "json"
    isa_jsons = list(isa_json_dir.glob("ISA-*.json"))
    if not isa_jsons:
        pytest.skip("output/json/ISA-*.json not present — skip β-1 ISA invariant")

    violations: list[str] = []
    for json_path in isa_jsons:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        for chunk in data.get("chunks", []):
            chunk_id = chunk.get("chunk_id", "")
            if SUFFIX_3LEVEL_RE.search(chunk_id):
                violations.append(chunk_id)

    assert not violations, (
        f"ISA baseline: 3-level suffix detected {violations[:3]}... "
        f"β-1 violated (docs/checkpoint_4_prep.md §1.8, Critic β-1 guard)"
    )


# ---------------------------------------------------------------------------
# c3 — FRMK special_appendix_name JSON payload smoke (Domain Check 5)
# ---------------------------------------------------------------------------


def test_frmk_special_appendix_name_extraction_smoke() -> None:
    """Domain Reviewer Check 5 (c3 smoke) — FRMK 보론 extraction 계약 검증.

    ``_extract_appendix_data`` 를 FRMK_SPEC.appendix_extractor 로 직접 호출 →
    ``("FRMK-1", "보론: 역할과 책임")`` heading_trail 에서 ``(None, "역할과 책임")``
    튜플 반환 확인. ``section="appendix"`` gate 통과 필수 (ISA/ISQM/ASSR 은 heading
    2 style 로 section=appendix 분류, FRMK 는 section_detector + state machine 에서
    결정).

    Phase 4d 전수 검증 시 전체 pipeline (DOCX → MD → JSON) 에서 실 chunk 의
    ``special_appendix_name="역할과 책임"`` payload JSON 직렬화 확인 예정.
    """
    from audit_parser.ingest.md_parser import _extract_appendix_data
    from audit_parser.spec import FRMK_SPEC

    # FRMK un-numbered 보론 heading_trail
    heading_trail = ("인증업무개념체계", "보론: 역할과 책임")
    idx, name = _extract_appendix_data(
        "appendix", heading_trail, FRMK_SPEC.appendix_extractor
    )
    assert idx is None
    assert name == "역할과 책임"

    # Numbered case: 보론 1 → (1, None)
    numbered_trail = ("인증업무개념체계", "보론 1: 회계감사기준위원회가 제정한 기준")
    idx2, name2 = _extract_appendix_data(
        "appendix", numbered_trail, FRMK_SPEC.appendix_extractor
    )
    assert idx2 == 1
    assert name2 is None


def test_frmk_special_appendix_name_json_serialization_smoke() -> None:
    """Domain Reviewer Check 5 (bonus) — ChunkRecord(special_appendix_name="역할과 책임")
    가 ``to_json_dict`` 경로에서 JSON ``"special_appendix_name": "역할과 책임"`` 키-값
    으로 직렬화되는지 실측. 4b-2 schema v1.2.0 infrastructure (``types.py:122`` 필드 +
    ``md_parser:941`` serialization) 의 end-to-end 계약 조기 검증.

    ISA 기존 36 JSON 은 전부 ``special_appendix_name: null`` 유지 (4b-2 exit gate
    `test_special_appendix_name_isa_default_null`). 본 test 는 FRMK 가 non-null
    value 를 emit 하는 경로가 깨지지 않음을 smoke level 로 확인.
    """
    from audit_parser.ingest.md_parser import _chunk_to_json
    from audit_parser.ingest.types import ChunkRecord

    # FRMK 보론: 역할과 책임 chunk — Phase 4d 에서 실 DOCX parse 후 자연 발생할
    # 수 있는 record 형태를 smoke level 로 모의.
    frmk_appendix_chunk = ChunkRecord(
        chunk_id="FRMK-1:appendix:deadbeef:1.",
        paragraph_id="1.",
        kind="requirement",
        section="appendix",
        appendix_index=None,
        heading_trail=("인증업무개념체계", "보론: 역할과 책임"),
        heading_trail_hash="deadbeef",
        content_text="어떤 인증업무에서든 역할과 책임의 정의는 필수다.",
        content_markdown="어떤 인증업무에서든 역할과 책임의 정의는 필수다.",
        authority=1,
        parent_paragraph_id=None,
        is_application_guidance=False,
        token_estimate=20,
        chunk_index=1,
        chunk_of=1,
        source_idx=100,
        special_appendix_name="역할과 책임",
    )
    serialized = _chunk_to_json(frmk_appendix_chunk)
    assert serialized["special_appendix_name"] == "역할과 책임"
    assert serialized["appendix_index"] is None
    assert serialized["chunk_id"] == "FRMK-1:appendix:deadbeef:1."
