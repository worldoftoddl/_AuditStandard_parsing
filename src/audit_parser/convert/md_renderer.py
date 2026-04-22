"""`Block` Iterator → Structured Markdown 렌더러 — Phase 1 Task #5.

`structure.py` 가 생산한 `Block` 스트림을 받아 기준서별 MD 파일 후보를 만든다.
산출물은 `_IFRS_parsing/converter/md_renderer.py` 와 동형 구조
(YAML frontmatter + HTML 주석 메타 + 탭 구분 번호 문단) 을 따르지만,
ISA 는 `FormattedRun` 서식 정보를 수집하지 않으므로 bold/italic 인라인 서식은
렌더하지 않는다. 번호(`1.`, `A1.`, `(a)`, `(i)`)는 `Block.paragraph_id` 로
이미 확정돼 있으므로 renderer 는 단순히 탭 구분으로 붙이기만 한다.

파일 분할 규칙 (PLAN §4 Phase 1):
- ``00_전문.md`` — standard_no 가 할당되지 않은 PRE_TOC/TOC prelude 구간 + 모든 is_toc=True 블록
  (기준서 내부 목차 항목도 여기로 이동).
- ``ISA-{nnn}.md`` — 36 개 기준서 본문.

설계 근거: plan 파일 `/home/shin/.claude/plans/compressed-zooming-muffin.md`
(Task #5 승인 판).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final, NamedTuple

from audit_parser.ir.types import Block, BlockKind, Section
from audit_parser.spec import ISA_SPEC, StandardSpec

SCHEMA_VERSION: Final = "1.0"

_PRELUDE_FILENAME: Final = "00_전문.md"

_HEADING_STYLE_RE: Final = re.compile(r"^heading ([1-9])$")
_APPENDIX_STYLE: Final = "보론 제목"

_LOWER_LETTER_RE: Final = re.compile(r"^\([a-z]+\)$")
_LOWER_ROMAN_RE: Final = re.compile(r"^\([ivxlcdm]+\)$")
_DECIMAL_PAREN_RE: Final = re.compile(r"^\(\d+\)$")


class RenderResult(NamedTuple):
    """render_markdown 출력 — 기준서별 1 파일 단위."""

    standard_no: str | None
    filename: str
    content: str
    block_count: int


def render_markdown(
    blocks: Iterable[Block],
    *,
    source_file: str,
    spec: StandardSpec = ISA_SPEC,
) -> list[RenderResult]:
    """Block Iterator → 기준서별 MD 파일 후보 리스트 (파일 I/O 없음).

    v1.2 (Phase 4b-1): ``spec`` 주입으로 prefix-specific filename + frontmatter
    ``standard_id`` 생성. ``ISA_SPEC`` default 로 기존 호출 경로 backward-compat.
    """
    renderer = _Renderer(source_file=source_file, spec=spec)
    for block in blocks:
        renderer.feed(block)
    return renderer.finalize()


def write_markdown_files(
    blocks: Iterable[Block],
    *,
    source_file: str,
    out_dir: Path,
    spec: StandardSpec = ISA_SPEC,
) -> list[Path]:
    """render_markdown 결과를 ``out_dir`` 에 기록 후 경로 리스트 반환."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = render_markdown(blocks, source_file=source_file, spec=spec)
    written: list[Path] = []
    for result in results:
        target = out_dir / result.filename
        target.write_text(result.content, encoding="utf-8")
        written.append(target)
    return written


# ---------------------------------------------------------------------------
# 내부 구현
# ---------------------------------------------------------------------------


class _FileBuffer:
    """기준서 또는 prelude 파일 단위 누적 버퍼."""

    __slots__ = (
        "standard_no",
        "filename",
        "_header_lines",
        "_body_lines",
        "_last_section",
        "_block_count",
    )

    def __init__(self, standard_no: str | None, filename: str) -> None:
        self.standard_no = standard_no
        self.filename = filename
        self._header_lines: list[str] = []
        self._body_lines: list[str] = []
        self._last_section: Section | None = None
        self._block_count = 0

    def set_header(self, lines: list[str]) -> None:
        self._header_lines = lines

    def append(self, lines: list[str]) -> None:
        if not lines:
            return
        self._body_lines.extend(lines)
        self._body_lines.append("")

    def observe_section(self, section: Section | None) -> Section | None:
        prev = self._last_section
        self._last_section = section
        return prev

    def bump_count(self) -> None:
        self._block_count += 1

    def finalize(self) -> RenderResult:
        body = "\n".join(self._header_lines + self._body_lines).rstrip() + "\n"
        return RenderResult(
            standard_no=self.standard_no,
            filename=self.filename,
            content=body,
            block_count=self._block_count,
        )


class _Renderer:
    """파일별 버퍼 + standard 전환 추적."""

    __slots__ = ("_source_file", "_spec", "_prelude", "_standards", "_current_standard_no")

    def __init__(self, *, source_file: str, spec: StandardSpec = ISA_SPEC) -> None:
        self._source_file = source_file
        self._spec = spec
        self._prelude = _FileBuffer(standard_no=None, filename=_PRELUDE_FILENAME)
        self._prelude.set_header(_format_prelude_frontmatter(source_file))
        self._standards: dict[str, _FileBuffer] = {}
        self._current_standard_no: str | None = None

    def feed(self, block: Block) -> None:
        buffer = self._route(block)
        buffer.bump_count()
        prev_section = buffer.observe_section(block.section)

        if block.kind == BlockKind.HEADING:
            lines = _render_heading(block, prev_section)
        elif block.kind == BlockKind.TOC_ENTRY:
            lines = _render_toc_entry(block)
        elif block.kind == BlockKind.TABLE:
            lines = _render_table(block)
        elif block.kind == BlockKind.BLOCK_QUOTE:
            lines = _render_block_quote(block)
        else:
            lines = _render_numbered(block)
        buffer.append(lines)

    def finalize(self) -> list[RenderResult]:
        results: list[RenderResult] = []
        if self._prelude._block_count > 0:
            results.append(self._prelude.finalize())
        # 기준서 번호 숫자 오름차순 — 200, 210, …, 1200
        for key in sorted(self._standards.keys(), key=lambda s: int(s)):
            results.append(self._standards[key].finalize())
        return results

    # -- internals ---------------------------------------------------------

    def _route(self, block: Block) -> _FileBuffer:
        if block.is_toc or block.standard_no is None:
            return self._prelude
        return self._get_or_create_standard_buffer(block)

    def _get_or_create_standard_buffer(self, block: Block) -> _FileBuffer:
        no = block.standard_no
        assert no is not None
        buf = self._standards.get(no)
        if buf is None:
            standard_id = self._spec.format_standard_id(no)
            filename = f"{standard_id}.md"
            buf = _FileBuffer(standard_no=no, filename=filename)
            buf.set_header(
                _format_standard_frontmatter(
                    standard_id=standard_id,
                    standard_no=no,
                    standard_title=block.standard_title,
                    source_file=self._source_file,
                )
            )
            self._standards[no] = buf
        return buf


# ---------------------------------------------------------------------------
# frontmatter
# ---------------------------------------------------------------------------


def _format_standard_frontmatter(
    *,
    standard_id: str,
    standard_no: str,
    standard_title: str | None,
    source_file: str,
) -> list[str]:
    """Phase 4b-1 v1.2: ``standard_id`` 는 ``spec.format_standard_id(standard_no)``
    결과 그대로 주입받아 렌더. 기존 ``f'ISA-{standard_no}'`` 하드코딩 제거.
    """
    lines = [
        "---",
        f'schema_version: "{SCHEMA_VERSION}"',
        f'standard_id: "{standard_id}"',
        f'standard_no: "{standard_no}"',
    ]
    if standard_title:
        lines.append(f'standard_title: "{_escape_yaml_string(standard_title)}"')
    lines.append(f'source_file: "{_escape_yaml_string(source_file)}"')
    lines.append("---")
    lines.append("")
    return lines


def _format_prelude_frontmatter(source_file: str) -> list[str]:
    return [
        "---",
        f'schema_version: "{SCHEMA_VERSION}"',
        "standard_id: null",
        f'source_file: "{_escape_yaml_string(source_file)}"',
        'content_type: "prelude_and_toc"',
        "---",
        "",
    ]


def _escape_yaml_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# block renderers
# ---------------------------------------------------------------------------


def _render_heading(block: Block, prev_section: Section | None) -> list[str]:
    level = _heading_level(block.style)
    hashes = "#" * level
    line = f"{hashes} {block.text}"
    comment_parts: list[str] = []
    # 섹션 전이 or 보론 heading (APPENDIX 영역의 heading 은 매번 재표기). 후자는
    # F5 대응: 동일 기준서 내 `보론 1`, `보론 2` 가 연속 등장해도 각 heading 마다
    # `section: appendix` 주석을 발행해 파일 스캔 시 누락 의심을 줄인다.
    emit_section = block.section is not None and (
        block.section != prev_section or block.section == Section.APPENDIX
    ) and (level == 2 or block.style == _APPENDIX_STYLE)
    if emit_section:
        assert block.section is not None
        comment_parts.append(f"section: {block.section.value}")
    comment_parts.append(f"idx: {block.idx}")
    comment = "<!-- " + " | ".join(comment_parts) + " -->"
    return [line, comment]


def _heading_level(style: str) -> int:
    if style == _APPENDIX_STYLE:
        return 3
    match = _HEADING_STYLE_RE.match(style)
    if match is not None:
        return int(match.group(1))
    # 상태머신이 HEADING kind 를 부여하는 경로는 heading N 또는 보론 제목뿐이지만
    # 방어적으로 2 레벨 fallback.
    return 2


def _render_numbered(block: Block) -> list[str]:
    text = block.text
    paragraph_id = block.paragraph_id

    if block.kind == BlockKind.UNKNOWN_NUMBERING:
        body_line = f"[?]\t{text}"
    elif block.kind == BlockKind.BULLET:
        body_line = f"\t•\t{text}"
    elif block.kind == BlockKind.SUB_ITEM:
        indent = _indent_for_paragraph_id(paragraph_id)
        label = paragraph_id if paragraph_id else ""
        body_line = f"{indent}{label}\t{text}" if label else f"{indent}{text}"
    elif paragraph_id:
        body_line = f"{paragraph_id}\t{text}"
    else:
        body_line = text

    comment = _build_paragraph_comment(block)
    return [body_line, comment]


def _indent_for_paragraph_id(paragraph_id: str | None) -> str:
    if paragraph_id is None:
        return "\t"
    if _LOWER_ROMAN_RE.match(paragraph_id):
        return "\t\t"
    if _LOWER_LETTER_RE.match(paragraph_id):
        return "\t"
    if _DECIMAL_PAREN_RE.match(paragraph_id):
        return "\t"
    return "\t"


def _build_paragraph_comment(block: Block) -> str:
    parts: list[str] = []
    if block.paragraph_id:
        parts.append(f"para: {block.paragraph_id}")
    parts.append(f"kind: {block.kind.value}")
    if block.parent_paragraph_id:
        parts.append(f"parent: {block.parent_paragraph_id}")
    parts.append(f"idx: {block.idx}")
    return "<!-- " + " | ".join(parts) + " -->"


def _render_block_quote(block: Block) -> list[str]:
    lines = [f"> {segment}" for segment in block.text.splitlines() or [""]]
    comment = f"<!-- kind: {block.kind.value} | idx: {block.idx} -->"
    lines.append(comment)
    return lines


def _render_table(block: Block) -> list[str]:
    cells = block.table_cells
    if cells is None or not cells:
        return [f"<!-- kind: table | rows: 0 | cols: 0 | idx: {block.idx} -->"]
    rows = len(cells)
    cols = max(len(r) for r in cells)

    def _prep(cell: str) -> str:
        out = cell.replace("\\", "\\\\").replace("|", "\\|")
        out = out.replace("\t", "    ").replace("\n", "<br>")
        return out

    normalized: list[tuple[str, ...]] = []
    for row in cells:
        padded = list(row) + [""] * (cols - len(row))
        normalized.append(tuple(_prep(c) for c in padded))

    lines: list[str] = []
    header = normalized[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * cols) + " |")
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    lines.append(f"<!-- kind: table | rows: {rows} | cols: {cols} | idx: {block.idx} -->")
    return lines


def _render_toc_entry(block: Block) -> list[str]:
    line = f"- {block.text}"
    comment = f"<!-- kind: toc_entry | idx: {block.idx} -->"
    return [line, comment]


__all__ = [
    "SCHEMA_VERSION",
    "RenderResult",
    "render_markdown",
    "write_markdown_files",
]
