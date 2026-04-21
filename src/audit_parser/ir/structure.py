"""`RawBlock` → `Block` 상태머신 — Phase 1 Task #4.

`docx_reader.iter_body` 의 원시 블록을 소비해 다음을 결정한다.

- `standard_no` / `standard_title` (감사기준서 경계)
- `section` (서론/목적/용어의 정의/요구사항/적용 및 기타 설명자료/보론)
- `heading_trail` (heading 1~9 + `보론 제목` 기반 상위→하위 제목 경로)
- `paragraph_id` / `kind` (NumberingEngine.advance() replay 결과)
- `parent_paragraph_id` (SUB_ITEM 은 직전 ilvl=0, APPLICATION_GUIDANCE 는 직전 REQUIREMENT)
- 1×1 단일 셀 표의 `BLOCK_QUOTE` 승격
- 전역 `is_toc` 마킹 (`목차`/`ad` 스타일)

설계 근거: `docs/isa_structure_profile.md` §2 / §5 / §6 / §8, `docs/numbering_strategy.md §4.4`.
후자의 옵션 A 가정이 실측과 어긋나(동일 numId 가 기준서 간 공유되고 lvlOverride 부재)
기준서 전환 시 `NumberingEngine.reset()` 을 호출해 카운터 누수를 차단한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Final, Literal

from audit_parser.ir.numbering import NumberingEngine
from audit_parser.ir.types import Block, BlockKind, RawBlock, Section

ISA_BOUNDARY: Final = re.compile(r"^감사기준서\s+(\d{3,4})(?:\s+(.+))?$")
_HEADING_STYLE_RE: Final = re.compile(r"^heading ([1-9])$")
_APPENDIX_STYLE: Final = "보론 제목"
_APPENDIX_HEADING2_RE: Final = re.compile(r"^보론\s*\d+\b")
_TOC_STYLES: Final = frozenset({"목차", "ad"})
_APP_GUIDANCE_RE: Final = re.compile(r"^A(\d+)\.$")

_SECTION_BY_HEADING2: Final[dict[str, Section]] = {
    "서론": Section.INTRO,
    "감사인의 전반적인 목적": Section.OVERALL_OBJECTIVE,
    "목적": Section.PURPOSE,
    "용어의 정의": Section.DEFINITIONS,
    "요구사항": Section.REQUIREMENTS,
    "적용 및 기타 설명자료": Section.APPLICATION,
    # ISA-1200 전용 서브섹션 (CHECKPOINT 1 F2). 실측 DOCX 텍스트와 domain-reviewer DM
    # 에 나온 alias 를 모두 수록한다.
    "일반원칙과 책임": Section.GENERAL_PRINCIPLES,
    "회계법인의 윤리적 요구사항 준수": Section.ETHICAL_REQUIREMENTS,
    "감사업무의 수임 또는 유지": Section.ENGAGEMENT_ACCEPTANCE,
    "감사계약의 수임 및 유지": Section.ENGAGEMENT_ACCEPTANCE,
    "감사 계획": Section.PLANNING,
    "중요성": Section.MATERIALITY,
    "위험평가": Section.RISK_ASSESSMENT,
    "평가된 위험에 대한 감사인의 대응": Section.RISK_RESPONSE,
    "평가된 위험에 대한 대응": Section.RISK_RESPONSE,
    "결론 및 보고": Section.CONCLUSION_REPORTING,
    "결론형성과 보고": Section.CONCLUSION_REPORTING,
    "기타 고려사항": Section.OTHER_CONSIDERATIONS,
}

_APPENDIX_LEVEL: Final = 3

_State = Literal["PRE_TOC", "TOC", "STANDARD_BODY"]


def iter_blocks(
    raw_blocks: Iterable[RawBlock],
    engine: NumberingEngine,
) -> Iterator[Block]:
    """`RawBlock` Iterator → `Block` Iterator.

    `engine` 은 호출자가 준비한 `NumberingEngine` 인스턴스. 기준서 경계에서
    `engine.reset()` 이 호출된다.
    """
    machine = StructureMachine(engine)
    for raw in raw_blocks:
        yield machine.feed(raw)


class StructureMachine:
    """RawBlock 1 개를 받아 Block 1 개를 내보내는 상태머신.

    내부 상태(기준서·섹션·heading 스택·parent 트래킹)를 유지하므로 순서대로 feed
    해야 한다. `iter_blocks` 는 이 클래스를 생성 후 얇게 감싼다.
    """

    __slots__ = (
        "_engine",
        "_state",
        "_standard_no",
        "_standard_title",
        "_heading_stack",
        "_current_section",
        "_last_requirement_id_by_standard",
        "_last_level0_paragraph_id",
        "_enter_standard_count",
    )

    def __init__(self, engine: NumberingEngine) -> None:
        self._engine = engine
        self._state: _State = "PRE_TOC"
        self._standard_no: str | None = None
        self._standard_title: str | None = None
        self._heading_stack: list[tuple[int, str]] = []
        self._current_section: Section | None = None
        self._last_requirement_id_by_standard: dict[str, str] = {}
        self._last_level0_paragraph_id: str | None = None
        self._enter_standard_count = 0

    # -- public ------------------------------------------------------------

    @property
    def state(self) -> _State:
        return self._state

    @property
    def standard_no(self) -> str | None:
        return self._standard_no

    @property
    def enter_standard_count(self) -> int:
        """기준서 경계에서 `engine.reset()` 이 호출된 횟수 — 검증용."""
        return self._enter_standard_count

    def feed(self, raw: RawBlock) -> Block:
        is_toc = raw.style in _TOC_STYLES
        standard_boundary = False

        # 1. 상태 전이
        if raw.style == "heading 1":
            match = ISA_BOUNDARY.match(raw.text)
            if match is not None:
                self._enter_standard(match.group(1), match.group(2))
                standard_boundary = True
        elif is_toc and self._state == "PRE_TOC":
            self._state = "TOC"

        # 2. heading stack / section 갱신
        # 기준서 boundary 일 때는 _enter_standard() 가 이미 level=1 항목을 정규화된
        # ("감사기준서 NNN") 형태로 push 했으므로 raw.text 재-push 를 skip.
        if not is_toc and not standard_boundary:
            if raw.kind == BlockKind.HEADING and raw.style != _APPENDIX_STYLE:
                self._update_heading_stack(raw)
            elif raw.style == _APPENDIX_STYLE:
                self._push_heading(_APPENDIX_LEVEL, raw.text)
                self._current_section = Section.APPENDIX

        # 3. 1×1 단일 셀 표 → BLOCK_QUOTE 승격
        kind: BlockKind = raw.kind
        text: str = raw.text
        table_cells = raw.table_cells
        table_promoted = False
        if raw.kind == BlockKind.TABLE and _is_single_cell(table_cells):
            assert table_cells is not None  # _is_single_cell 가 보장
            promoted_text = table_cells[0][0].strip()
            if promoted_text:
                kind = BlockKind.BLOCK_QUOTE
                text = promoted_text
                table_cells = None
                table_promoted = True

        # 4. numbering replay (HEADING / TABLE / TOC_ENTRY 는 skip)
        paragraph_id: str | None = None
        parent_id: str | None = None
        is_app = False
        if (
            not table_promoted
            and raw.kind not in (BlockKind.HEADING, BlockKind.TABLE, BlockKind.TOC_ENTRY)
            and raw.style != _APPENDIX_STYLE
        ):
            numbered = self._engine.advance(raw.num_id, raw.ilvl)
            kind = numbered.kind
            paragraph_id = self._finalize_paragraph_id(numbered.paragraph_id)
            is_app = kind == BlockKind.APPLICATION_GUIDANCE
            parent_id = self._resolve_parent(kind)
            self._update_parent_tracking(kind, paragraph_id)

        # 5. Block 생성
        trail = tuple(t for _, t in self._heading_stack)
        return Block(
            idx=raw.idx,
            kind=kind,
            text=text,
            style=raw.style,
            paragraph_id=paragraph_id,
            is_application_guidance=is_app,
            parent_paragraph_id=parent_id,
            standard_no=self._standard_no,
            standard_title=self._standard_title,
            section=self._current_section,
            heading_trail=trail,
            immediate_heading=trail[-1] if trail else None,
            is_toc=is_toc,
            is_header_footer=False,
            table_cells=table_cells,
        )

    # -- internals ---------------------------------------------------------

    def _enter_standard(self, no: str, title_group: str | None) -> None:
        """새 기준서 진입 — 스택·섹션·parent 트래킹 전부 초기화 후 engine.reset()."""
        self._standard_no = no
        self._standard_title = title_group.strip() if title_group else None
        self._state = "STANDARD_BODY"
        self._heading_stack = [(1, f"감사기준서 {no}")]
        self._current_section = None
        self._last_level0_paragraph_id = None
        self._engine.reset()
        self._enter_standard_count += 1

    def _update_heading_stack(self, raw: RawBlock) -> None:
        """heading N 스타일 → stack 갱신 + section 매핑."""
        match = _HEADING_STYLE_RE.match(raw.style)
        if match is None:
            return
        level = int(match.group(1))
        self._push_heading(level, raw.text)
        if level == 2 and self._state == "STANDARD_BODY":
            mapped = _classify_heading2(raw.text.strip())
            if mapped is not None:
                self._current_section = mapped
            # 매핑 실패 시 이전 section 유지 (EC: 서브섹션이 heading 2 로 잘못 승격된 경우)

    def _push_heading(self, level: int, text: str) -> None:
        while self._heading_stack and self._heading_stack[-1][0] >= level:
            self._heading_stack.pop()
        self._heading_stack.append((level, text))

    def _finalize_paragraph_id(self, raw_id: str) -> str | None:
        """번호 라벨을 block 에 담기 전 최종 형태로 가공.

        - 빈 문자열 → None
        - 보론(APPENDIX) 영역의 번호는 본문과 별도 scheme 이라 `1.`~`n.` 이 본문
          requirement 와 충돌. 원본 DOCX 의미는 유지하되 paragraph_id 의 전역 고유성을
          확보하기 위해 `부록-` prefix 를 붙인다.
        """
        if not raw_id:
            return None
        if self._current_section == Section.APPENDIX:
            return f"부록-{raw_id}"
        return raw_id

    def _resolve_parent(self, kind: BlockKind) -> str | None:
        if kind == BlockKind.SUB_ITEM:
            return self._last_level0_paragraph_id
        if kind == BlockKind.APPLICATION_GUIDANCE:
            if self._standard_no is None:
                return None
            return self._last_requirement_id_by_standard.get(self._standard_no)
        return None

    def _update_parent_tracking(self, kind: BlockKind, paragraph_id: str | None) -> None:
        if paragraph_id is None:
            return
        if kind == BlockKind.REQUIREMENT and self._standard_no is not None:
            self._last_requirement_id_by_standard[self._standard_no] = paragraph_id
        if kind in (BlockKind.REQUIREMENT, BlockKind.APPLICATION_GUIDANCE):
            self._last_level0_paragraph_id = paragraph_id


def _classify_heading2(text: str) -> Section | None:
    """heading 2 텍스트 → Section enum.

    정적 매핑 (_SECTION_BY_HEADING2) 우선. 실패 시 `보론 N ...` 패턴에 한해
    Section.APPENDIX 동적 할당 — ISA-1200 의 `보론 1 용어의 정의` 처럼 `보론 제목`
    전용 스타일이 아닌 heading 2 로 보론 섹션이 열리는 케이스 대응.
    """
    mapped = _SECTION_BY_HEADING2.get(text)
    if mapped is not None:
        return mapped
    if _APPENDIX_HEADING2_RE.match(text):
        return Section.APPENDIX
    return None


def _is_single_cell(
    cells: tuple[tuple[str, ...], ...] | None,
) -> bool:
    return cells is not None and len(cells) == 1 and len(cells[0]) == 1


__all__ = [
    "ISA_BOUNDARY",
    "StructureMachine",
    "iter_blocks",
]
