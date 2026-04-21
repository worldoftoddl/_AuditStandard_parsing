"""Stage 2a 데이터클래스 — MD → JSON 중간형식.

`docs/json_schema.md` v1.1 의 ParsedStandard 구조를 파이썬 frozen dataclass 로
반영한다. 모든 dataclass 는 `slots=True, frozen=True` — 해시 가능 + 메모리 컴팩트.

필드 순서는 json_schema.md §3/§4/§5/§11 필드 표 순서를 정확히 따르며,
`to_json_dict` 직렬화 시 그 순서로 dict 가 emit 된다 (가독성 + 외부 연계 공식
스펙 일관성).

JSON 스키마 버전 (`JSON_SCHEMA_VERSION`) 은 MD frontmatter 의 `SCHEMA_VERSION`
(src/audit_parser/convert/md_renderer.py) 과 **독립 카운터** — json_schema.md
§2.3 참조.

v1.1 MINOR bump 변경점 (2026-04-21 team-lead 확정):
- ``heading_trail_hash`` canonical form 에 원소별 ``.strip()`` 선행 적용.
- ``chunk_id`` 2-Pass 알고리즘 (Pass 1 candidate → Pass 2 collision suffix).
- ``assert_chunk_id_uniqueness`` 최종 emit 전 호출 (md_parser.parse_md 말미).
- 번호 없는 보론 매핑 ISA 목록 9 개 확장 (ISA-230/300/510/570/620/700/705/710/1100).

v1.1.1 PATCH bump 변경점 (2026-04-21 Domain Reviewer Task #7 파생):
- docs/json_schema.md §2.2 PATCH row 신설 파생 — `JSON_SCHEMA_VERSION` 문자열만
  "1.1" → "1.1.1". chunk_id / embedding / heading_trail_hash / paragraph_links
  등 payload 바이트 동등성 유지, 재임베딩 불필요.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

JSON_SCHEMA_VERSION: Final = "1.1.1"


@dataclass(slots=True, frozen=True)
class StandardRecord:
    """기준서 전역 메타 1 건. MD frontmatter 에서 파생.

    Attributes:
        standard_id: ``ISA-<standard_no>`` 포맷. 전역 고유.
        standard_no: 숫자 문자열 ``"200"``~``"1200"``.
        standard_title: 기준서 제목. 없는 경우 빈 문자열.
        source_file: 원본 DOCX 파일명. Collection 네이밍 역추적용.
        authority_base: 기준서 자체 권위 레벨. 현 4 DOCX 모두 1.
    """

    standard_id: str
    standard_no: str
    standard_title: str
    source_file: str
    authority_base: int


@dataclass(slots=True, frozen=True)
class StandardSummary:
    """기준서별 검색 필터·UI 요약용. 범위·정의 텍스트 + summary embedding slot.

    json_schema.md §4 필드 순서 고정.
    """

    scope_text: str | None
    scope_markdown: str | None
    definitions_text: str | None
    definitions_markdown: str | None
    embedding: tuple[float, ...] | None = None
    embedded_at: str | None = None
    embedding_model: str | None = None


@dataclass(slots=True, frozen=True)
class ChunkRecord:
    """Qdrant 업서트 단위. json_schema.md §5.1 21 필드 전수 보존.

    ``embedding`` / ``table_cells`` 는 frozen 요구 충족 위해 tuple. to_json_dict
    에서 list 변환.

    ``part_of`` 는 chunk_splitter (Phase 2 Task #3) 가 분할 발생 시 후속 조각에만
    부여. md_parser 단계에서는 항상 ``None``.
    """

    chunk_id: str
    paragraph_id: str | None
    kind: str
    section: str | None
    appendix_index: int | None
    heading_trail: tuple[str, ...]
    heading_trail_hash: str
    content_text: str
    content_markdown: str
    authority: int
    parent_paragraph_id: str | None
    is_application_guidance: bool
    token_estimate: int
    chunk_index: int
    chunk_of: int
    source_idx: int
    part_of: str | None = None
    table_cells: tuple[tuple[str, ...], ...] | None = None
    embedding: tuple[float, ...] | None = None
    embedded_at: str | None = None
    embedding_model: str | None = None


@dataclass(slots=True, frozen=True)
class ParagraphLink:
    """문단 간 명시적 관계. Phase 2 는 ``guidance_of`` 만 (An → n)."""

    source: str
    target: str
    link_type: str


@dataclass(slots=True, frozen=True)
class ParsedStandard:
    """단일 MD 파일(=ISA-NNN.md) 파싱 결과의 최상위 컨테이너."""

    schema_version: str
    standard: StandardRecord
    summary: StandardSummary
    chunks: tuple[ChunkRecord, ...]
    paragraph_links: tuple[ParagraphLink, ...]


__all__ = [
    "JSON_SCHEMA_VERSION",
    "ChunkRecord",
    "ParagraphLink",
    "ParsedStandard",
    "StandardRecord",
    "StandardSummary",
]
