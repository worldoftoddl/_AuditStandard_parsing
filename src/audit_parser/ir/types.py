"""IR 데이터클래스 — Phase 1 Stage 1 (docx → Structured Markdown).

`RawBlock` 은 `docx_reader.iter_body` 의 출력으로 DOCX body 의 순회 결과를 최소 가공한
원시 블록이다. `Block` 은 `structure.py` 상태머신을 통과해 standard/section/heading_trail
이 부여된 최종 IR 이며 `md_renderer.py` 로 입력된다.

상수·Enum 값의 근거: PLAN.md §4 Phase 1, docs/isa_structure_profile.md §2·§3·§8,
docs/devils_advocate_checkpoint_0.md (S3, S4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BlockKind(StrEnum):
    """블록 종류. `docx_reader` 에서는 style 기반 초기 값, `numbering`/`structure` 에서 최종화."""

    HEADING = "heading"
    REQUIREMENT = "requirement"
    APPLICATION_GUIDANCE = "application_guidance"
    SUB_ITEM = "sub_item"
    BULLET = "bullet"
    PARAGRAPH_BODY = "paragraph_body"
    TOC_ENTRY = "toc_entry"
    TABLE = "table"
    BLOCK_QUOTE = "block_quote"
    UNKNOWN_NUMBERING = "unknown_numbering"


class Section(StrEnum):
    """ISA 섹션. ISA-200 전용 OVERALL_OBJECTIVE, 섹션 매핑 실패 시 UNKNOWN.

    ISA-1200 (소규모기업) 은 요구사항/적용 구조 대신 감사 절차 단계별 heading 2 로
    구성되므로 ``GENERAL_PRINCIPLES``~``OTHER_CONSIDERATIONS`` 서브섹션을 별도로 둔다
    (domain-reviewer CHECKPOINT 1 F2 요청).
    """

    INTRO = "intro"
    OVERALL_OBJECTIVE = "overall_objective"
    PURPOSE = "purpose"
    DEFINITIONS = "definitions"
    REQUIREMENTS = "requirements"
    APPLICATION = "application"
    APPENDIX = "appendix"
    # ISA-1200 전용 서브섹션
    GENERAL_PRINCIPLES = "general_principles"
    ETHICAL_REQUIREMENTS = "ethical_requirements"
    ENGAGEMENT_ACCEPTANCE = "engagement_acceptance"
    PLANNING = "planning"
    MATERIALITY = "materiality"
    RISK_ASSESSMENT = "risk_assessment"
    RISK_RESPONSE = "risk_response"
    CONCLUSION_REPORTING = "conclusion_reporting"
    OTHER_CONSIDERATIONS = "other_considerations"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class RawBlock:
    """DOCX body 순회 결과의 최소 가공 블록.

    Attributes:
        idx: body 순회 0-based index (w:sectPr 등 skip 된 요소 제외한 순번은 아님 — 원본 순번).
        kind: style 기반 초기 추정 BlockKind. 번호 관련 kind 는 `numbering.py` 에서 확정.
        text: 정규화 (strip) 된 본문. 빈 문자열이면 yield 되지 않음 (docx_reader 가 skip).
        style: Word 스타일 ID (`w:pStyle w:val`). 스타일 없으면 "".
        num_id: `w:numPr/w:numId w:val`. 문자열 "0" 은 "번호 명시 제거" 마커 (EC-1).
            numPr 자체가 없으면 None — "0" 과 반드시 구별.
        ilvl: `w:numPr/w:ilvl w:val` 의 정수. numPr 없으면 None.
        table_cells: kind=TABLE 일 때 행×열 텍스트 그리드. 그 외 None.
        paragraph_id: Phase 4b-2 — non-ISA specs (ISQM-1) 에서 cell text 로부터 직접
            추출된 paragraph_id 를 전달하기 위한 선택적 override. ISA 경로는 항상
            ``None`` — ``NumberingEngine.replay`` 결과가 ``structure.py`` 에서
            ``Block.paragraph_id`` 로 주입됨. ISQM 처럼 numPr 이 아닌 table cell text
            에 번호가 저장된 경우 이 필드에 pre-populated 되어 ``structure.py`` 가
            NumberingEngine 을 건너뛰고 이 값을 채택. 기본값 ``None`` 유지로 ISA
            바이트 동등성 보장.
    """

    idx: int
    kind: BlockKind
    text: str
    style: str
    num_id: str | None
    ilvl: int | None
    table_cells: tuple[tuple[str, ...], ...] | None = None
    paragraph_id: str | None = None


@dataclass(slots=True, frozen=True)
class Block:
    """structure.py 가 RawBlock 에 standard/section/heading_trail 을 부여한 최종 IR.

    Attributes:
        idx: RawBlock.idx 유지 (원본 body 순번, CHECKPOINT 1 검수용).
        kind: 최종 BlockKind (BLOCK_QUOTE 승격, SUB_ITEM 분류 등 포함).
        text: 본문. BLOCK_QUOTE 승격된 1×1 표의 경우 단일 셀 텍스트.
        style: Word 스타일 ID 유지.
        paragraph_id: 카운터 replay 결과 라벨 ("1", "A1", "(a)", ...). 미해당 시 None.
        is_application_guidance: `A%1.` 계열 여부 (section=APPLICATION 인지와는 별개).
        parent_paragraph_id: `An` 블록이 가리키는 직전 요구사항 문단 번호 ("12" 등). None=미연결.
        standard_no: "200"/"1200" 등. PRE_TOC/TOC 구간은 None.
        standard_title: `감사기준서 NNN` 뒤 제목. None 허용.
        section: 소속 Section. 섹션 미진입 구간은 None.
        heading_trail: ["감사기준서 200", "서론", "이 감사기준서의 범위"] 의 상위→하위 스택.
        immediate_heading: `heading_trail[-1]` 단축 접근. heading_trail 빈 tuple 시 None.
        is_toc: `ad`/`목차` 전역 2차 규칙으로 True 마킹 (상태 무관, EC-2).
        is_header_footer: 반복 페이지 헤더/푸터 보험 플래그. 실측상 body 자동 제외로 대부분 False.
        table_cells: TABLE kind 유지 시만 보존. BLOCK_QUOTE 승격 후에는 None (text 로 이관).
    """

    idx: int
    kind: BlockKind
    text: str
    style: str
    paragraph_id: str | None
    is_application_guidance: bool
    parent_paragraph_id: str | None
    standard_no: str | None
    standard_title: str | None
    section: Section | None
    heading_trail: tuple[str, ...] = field(default_factory=tuple)
    immediate_heading: str | None = None
    is_toc: bool = False
    is_header_footer: bool = False
    table_cells: tuple[tuple[str, ...], ...] | None = None


__all__ = [
    "Block",
    "BlockKind",
    "RawBlock",
    "Section",
]
