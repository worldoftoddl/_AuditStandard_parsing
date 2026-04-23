"""DOCX body 순회 — `word/document.xml` → `RawBlock` Iterator.

Phase 1 Task #2 구현. numbering.xml 파싱과 kind 확정은 `numbering.py` 에 위임하고,
여기서는 `num_id`/`ilvl` 문자열·정수만 추출한다. 표 cell 텍스트 그리드도 평탄화해
`RawBlock.table_cells` 로 전달한다.

Phase 4c c1 확장 (2026-04-23):
- `iter_body(docx_path, spec=ISA_SPEC)` — StandardSpec 주입 (default ISA_SPEC → Phase
  1 경로 100% backward-compat).
- `spec.body_parser is not None` 시 top-level ``<w:tbl>`` 을 body_parser 에 위임 —
  ISQM ``tbl[236x2]`` 내부 paragraph_id cell-text 추출 경로. β-1 invariant (docs/
  checkpoint_4_prep.md §1.8): body_parser 는 **atomic RawBlock** emit only, split
  책임은 ``chunk_splitter.split_oversized_chunks`` 독점. Phase 4c wiring 은
  body_parser 결과를 pre-split 하지 않는다.
- Wrapper table recursive descent — FRMK ``tbl[3x3]`` / ASSR ``tbl[427x2]`` 같은
  visual wrapper 의 내부 ``<w:p>`` 를 top-level 처럼 순회. ``_MAX_DESCENT_DEPTH``
  (Critic verbal note #X2) 로 infinite loop 방어.

설계 근거:
- PLAN.md §4 Phase 1 (IR 레이어)
- docs/isa_structure_profile.md §3 (num_id='0' 303건 등 실측)
- docs/devils_advocate_checkpoint_0.md (S4: 1×1 박스 — 승격은 structure.py 에서)
- docs/assurance_other_structure_profile.md §6.1 (ASSR wrapper descent)
- docs/framework_structure_profile.md §6.1 (FRMK wrapper descent)
- docs/isqm_structure_profile.md §2.3 (ISQM body_parser 경로)
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Final

from lxml import etree

from audit_parser.ir._xml import safe_parse
from audit_parser.ir.styles import StyleIndex, parse_styles_xml, resolve_paragraph_numPr
from audit_parser.ir.types import BlockKind, RawBlock
from audit_parser.spec import ISA_SPEC, StandardSpec

_W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMAP: Final[dict[str, str]] = {"w": _W_NS}


def _qn(tag: str) -> str:
    """`w:p` 와 같은 prefixed tag 를 Clark notation(`{ns}local`)으로 변환."""
    prefix, _, local = tag.partition(":")
    return f"{{{_NSMAP[prefix]}}}{local}"


_TAG_P: Final = _qn("w:p")
_TAG_TBL: Final = _qn("w:tbl")
_TAG_SDT: Final = _qn("w:sdt")
_TAG_SDT_CONTENT: Final = _qn("w:sdtContent")
_TAG_TR: Final = _qn("w:tr")
_TAG_TC: Final = _qn("w:tc")
_TAG_T: Final = _qn("w:t")
_TAG_TAB: Final = _qn("w:tab")
_TAG_BR: Final = _qn("w:br")
_TAG_CR: Final = _qn("w:cr")
_TAG_R: Final = _qn("w:r")
_TAG_PPR: Final = _qn("w:pPr")
_TAG_PSTYLE: Final = _qn("w:pStyle")
_TAG_NUMPR: Final = _qn("w:numPr")
_TAG_NUMID: Final = _qn("w:numId")
_TAG_ILVL: Final = _qn("w:ilvl")
_TAG_BODY: Final = _qn("w:body")
_ATTR_VAL: Final = _qn("w:val")

# 스타일 → 초기 BlockKind 매핑. numbering.py 가 REQUIREMENT/APPLICATION_GUIDANCE/SUB_ITEM 으로
# 재분류할 수 있으므로 여기서는 "numbering 정보가 없는 경우의 기본값"에 가깝다.
_HEADING_STYLE_PREFIXES: Final = ("heading ",)
_HEADING_KOREAN_STYLES: Final = frozenset({"보론 제목"})
_TOC_STYLES: Final = frozenset({"목차", "ad"})

# Phase 4c c1 — Critic verbal note #X2 (2026-04-23 LOCK).
# ``docs/checkpoint_4_prep.md §2.4`` — infinite loop 방어 + 실제 KICPA DOCX 관찰 depth
# 은 최대 3 (wrapper tbl → 내부 tbl → cell ``<w:p>``) 수준이므로 10 은 여유 있음.
# Phase 1 ISA 경로는 recursive descent 를 사용하지 않으므로 depth=0 유지.
_MAX_DESCENT_DEPTH: Final[int] = 10


def open_docx_zip(docx_path: Path) -> zipfile.ZipFile:
    """DOCX 를 zip 으로 열어 반환. 호출자가 `with` 블록에서 close 책임.

    `numbering.py` 의 `parse_numbering` 에서도 재사용한다.
    """
    return zipfile.ZipFile(docx_path, "r")


def iter_body(
    docx_path: Path,
    *,
    spec: StandardSpec = ISA_SPEC,
) -> Iterator[RawBlock]:
    """DOCX body 를 순회하며 `RawBlock` 을 yield.

    w:sdt (Structured Document Tag) 내부 w:p 도 전개한다. w:sectPr 등 순수 메타 요소는 skip.
    빈 문단 (strip 후 공백) 과 빈 표 (모든 cell 이 공백) 는 skip.

    `w:pStyle w:val` 이 반환하는 내부 styleId ('10', 'ad', 'aff3' 등) 는 `word/styles.xml`
    의 `w:name w:val` 로 display name ('heading 1', '목차', '보론 제목') 로 변환해
    RawBlock.style 에 담는다 — structure.py 의 스타일 기반 분기(heading, 보론 제목, 목차) 가
    display name 을 전제로 하기 때문.

    Phase 4c c1:
        ``spec: StandardSpec`` 주입 (default ISA_SPEC → Phase 1 경로 100% backward-compat).

        * ``spec.body_parser is not None`` (ISQM 전용) — 첫 번째 top-level ``<w:tbl>``
          을 만나면 body_parser 에 위임. 그 이전 ``<w:p>`` 및 이후 ``<w:p>`` 는 기존
          경로 유지. body_parser 가 emit 하는 RawBlock 은 ``paragraph_id`` 를 cell
          text 에서 추출하므로 numbering.xml 경유 없이 최종 IR 로 직접 소비 가능.
        * ``spec.body_parser is None`` 이지만 non-ISA (ISQM/ASSR/FRMK) — wrapper
          table (``tbl[3x3]`` / ``tbl[427x2]``) 가 outer container 인 경우
          ``_iter_block_level`` recursive descent 로 내부 ``<w:p>`` 를 top-level 처럼
          순회. ``_MAX_DESCENT_DEPTH`` 로 infinite loop 방어.
        * ``spec is ISA_SPEC`` — 기존 Phase 1 경로 (top-level ``<w:p>`` + ``<w:tbl>``
          직계 순회, recursive descent 없음). 36 ISA JSON 바이트 동등 보장.

        β-1 invariant (docs/checkpoint_4_prep.md §1.8): body_parser 는 atomic RawBlock
        emit only. split 책임은 ``chunk_splitter.split_oversized_chunks`` 독점. 본
        함수는 body_parser 결과를 pre-split 하지 않음.
    """
    with open_docx_zip(docx_path) as zf:
        style_index = _load_style_index(zf)
        with zf.open("word/document.xml") as stream:
            tree = safe_parse(stream)

    root = tree.getroot()
    body = root.find(_TAG_BODY)
    if body is None:
        return

    counter = _Counter()
    # spec is ISA_SPEC: use recurse=False to preserve exact Phase 1 iteration order.
    # non-ISA: recurse=True descends into wrapper tables (FRMK tbl[3x3] / ASSR
    # tbl[427x2]) — inner <w:p> yielded at top-level.
    recurse = spec is not ISA_SPEC
    body_parser = spec.body_parser
    for child in _iter_block_level(body, recurse=recurse):
        # body_parser dispatch — atomic RawBlock emission, no chunk_of tampering.
        if body_parser is not None and child.tag == _TAG_TBL:
            yield from body_parser(child)
            continue
        raw = _block_to_raw(child, counter, style_index)
        if raw is not None:
            yield raw


def _load_style_index(zf: zipfile.ZipFile) -> StyleIndex:
    """`word/styles.xml` → display name + style-level numPr 인덱스 번들."""
    try:
        with zf.open("word/styles.xml") as stream:
            raw = stream.read()
    except KeyError:
        from types import MappingProxyType

        empty: dict[str, str] = {}
        return StyleIndex(
            display_names=MappingProxyType(empty),
            num_defaults=MappingProxyType({}),
        )
    return parse_styles_xml(raw)


def _flag_repeating_headers(blocks: Iterable[RawBlock]) -> Iterator[RawBlock]:
    """반복 페이지 헤더/푸터 탐지 보험 훅 — 현재 pass-through.

    실측상 `word/document.xml` body 에는 페이지 헤더/푸터가 포함되지 않으므로
    (`word/header*.xml` / `word/footer*.xml` 에 별도 저장) 이 훅은 no-op 이다.
    향후 다른 DOCX 계열(Phase 4) 에서 body 유입 케이스가 확인되면 여기서 필터링한다.
    """
    yield from blocks


class _Counter:
    """idx 증가용 내부 카운터. dataclass 불변성과 무관하게 클로저 대체."""

    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value = 0

    def next(self) -> int:
        v = self._value
        self._value += 1
        return v


def _iter_block_level(
    parent: etree._Element,
    *,
    recurse: bool = False,
    _depth: int = 0,
) -> Iterator[etree._Element]:
    """body 직계 자식을 순회하되 w:sdt 내부 블록 요소는 전개한다.

    Phase 4c c1:
        * ``recurse=False`` (ISA default) — 기존 Phase 1 동작: top-level ``<w:p>`` +
          ``<w:tbl>`` 직계 yield, ``<w:sdt>`` 만 전개.
        * ``recurse=True`` (non-ISA) — wrapper table 내부 ``<w:p>`` 를 top-level
          처럼 descent iteration. ``<w:tbl>`` 은 여전히 yield (body_parser dispatch
          대상일 수 있음) + 내부 ``<w:p>`` 병행 descent. ``_MAX_DESCENT_DEPTH``
          (default 10) 초과 시 ``AssertionError`` 로 infinite loop 방어 (Critic
          verbal note #X2 / ``docs/checkpoint_4_prep.md §2.4``).

    Args:
        parent: XML element to iterate (w:body 또는 w:tbl/w:sdt descendants).
        recurse: non-ISA wrapper table descent mode.
        _depth: internal recursion depth counter (caller 불호출).

    Raises:
        AssertionError: descent depth 가 ``_MAX_DESCENT_DEPTH`` 초과 시.
    """
    if _depth > _MAX_DESCENT_DEPTH:
        raise AssertionError(
            f"docx_reader descent depth exceeded {_MAX_DESCENT_DEPTH} at depth "
            f"{_depth} — infinite loop guard (Critic #X2 / "
            f"docs/checkpoint_4_prep.md §2.4)."
        )
    for child in parent:
        tag = child.tag
        if not isinstance(tag, str):
            continue
        if tag == _TAG_SDT:
            content = child.find(_TAG_SDT_CONTENT)
            if content is not None:
                yield from _iter_block_level(
                    content, recurse=recurse, _depth=_depth + 1
                )
        elif tag == _TAG_P:
            yield child
        elif tag == _TAG_TBL:
            yield child
            if recurse:
                # Descend into wrapper tables — FRMK tbl[3x3] / ASSR tbl[427x2]
                # body content is inside cells. Inner <w:p> yielded at top-level.
                # body_parser dispatch (for ISQM) already consumed the <w:tbl> above;
                # for non-ISA specs without body_parser, this is how wrapper content
                # flows out.
                yield from _iter_block_level(
                    child, recurse=recurse, _depth=_depth + 1
                )
        elif recurse and tag in (_TAG_TR, _TAG_TC):
            # Transparent descent: <w:tr> / <w:tc> 자체는 yield 하지 않고 내부
            # <w:p> / <w:tbl> 만 top-level 로 노출. recurse=False 에서는 이 분기
            # 도달 불가 (기존 Phase 1 동작은 <w:tbl> 내부 descent 자체가 없음).
            yield from _iter_block_level(child, recurse=recurse, _depth=_depth + 1)


def _block_to_raw(
    elem: etree._Element, counter: _Counter, style_index: StyleIndex
) -> RawBlock | None:
    """단일 body 자식 요소를 RawBlock 으로 변환. skip 대상이면 None."""
    tag = elem.tag
    if tag == _TAG_P:
        return _paragraph_to_raw(elem, counter, style_index)
    if tag == _TAG_TBL:
        return _table_to_raw(elem, counter)
    return None


def _paragraph_to_raw(
    p_elem: etree._Element, counter: _Counter, style_index: StyleIndex
) -> RawBlock | None:
    text = _xml_para_text(p_elem)
    stripped = text.strip()
    if not stripped:
        return None

    style_id = _xml_para_style(p_elem) or ""
    style = style_index.display_names.get(style_id, style_id)
    p_num_id, p_ilvl = _xml_para_numpr(p_elem)
    # F1: 문단 직속 numPr 이 없으면 styles.xml chain 에서 상속 해결.
    num_id, ilvl = resolve_paragraph_numPr(
        p_num_id, p_ilvl, style_id or None, style_index.num_defaults
    )
    kind = _initial_kind_for_paragraph(style, num_id)

    return RawBlock(
        idx=counter.next(),
        kind=kind,
        text=stripped,
        style=style,
        num_id=num_id,
        ilvl=ilvl,
        table_cells=None,
    )


def _table_to_raw(tbl_elem: etree._Element, counter: _Counter) -> RawBlock | None:
    cells = _xml_table_cells(tbl_elem)
    if not cells or all(not cell.strip() for row in cells for cell in row):
        return None
    return RawBlock(
        idx=counter.next(),
        kind=BlockKind.TABLE,
        text="",
        style="",
        num_id=None,
        ilvl=None,
        table_cells=cells,
    )


def _xml_para_text(p_elem: etree._Element) -> str:
    """w:p 의 모든 텍스트 run 을 concat (w:tab → '\\t', w:br/w:cr → '\\n')."""
    parts: list[str] = []
    for r_elem in p_elem.findall(_TAG_R):
        for child in r_elem:
            if child.tag == _TAG_T:
                parts.append(child.text or "")
            elif child.tag == _TAG_TAB:
                parts.append("\t")
            elif child.tag in (_TAG_BR, _TAG_CR):
                parts.append("\n")
    return "".join(parts)


def _xml_para_style(p_elem: etree._Element) -> str | None:
    """w:p/w:pPr/w:pStyle@w:val 반환."""
    pPr = p_elem.find(_TAG_PPR)
    if pPr is None:
        return None
    pStyle = pPr.find(_TAG_PSTYLE)
    if pStyle is None:
        return None
    val = pStyle.get(_ATTR_VAL)
    return val


def _xml_para_numpr(p_elem: etree._Element) -> tuple[str | None, int | None]:
    """(num_id, ilvl) 반환. numPr 없으면 (None, None).

    num_id 문자열 '0' (명시적 번호 제거 마커) 은 '0' 그대로 보존한다 — None 과 구별 필수.
    ilvl 이 정수 변환 불가 시 None.
    """
    pPr = p_elem.find(_TAG_PPR)
    if pPr is None:
        return None, None
    numPr = pPr.find(_TAG_NUMPR)
    if numPr is None:
        return None, None

    num_id: str | None = None
    numId_elem = numPr.find(_TAG_NUMID)
    if numId_elem is not None:
        num_id = numId_elem.get(_ATTR_VAL)

    ilvl: int | None = None
    ilvl_elem = numPr.find(_TAG_ILVL)
    if ilvl_elem is not None:
        raw_val = ilvl_elem.get(_ATTR_VAL)
        if raw_val is not None:
            try:
                ilvl = int(raw_val)
            except ValueError:
                ilvl = None

    return num_id, ilvl


def _xml_table_cells(tbl_elem: etree._Element) -> tuple[tuple[str, ...], ...]:
    """w:tbl → 행×열 텍스트 그리드. 셀 내부 w:p 의 텍스트는 '\\n' 으로 join."""
    rows: list[tuple[str, ...]] = []
    for tr in tbl_elem.findall(_TAG_TR):
        row_cells: list[str] = []
        for tc in tr.findall(_TAG_TC):
            cell_parts: list[str] = []
            for p in tc.findall(_TAG_P):
                cell_text = _xml_para_text(p).strip()
                if cell_text:
                    cell_parts.append(cell_text)
            row_cells.append("\n".join(cell_parts))
        if row_cells:
            rows.append(tuple(row_cells))
    return tuple(rows)


def _initial_kind_for_paragraph(style: str, num_id: str | None) -> BlockKind:
    """style·num_id 기반 초기 kind 추정. REQUIREMENT/APPLICATION_GUIDANCE/SUB_ITEM 은
    numbering.py 가 lvlText 패턴으로 확정하므로 여기서는 부여하지 않는다.
    """
    if style in _TOC_STYLES:
        return BlockKind.TOC_ENTRY
    if style in _HEADING_KOREAN_STYLES or _is_heading_style(style):
        return BlockKind.HEADING
    return BlockKind.PARAGRAPH_BODY


def _is_heading_style(style: str) -> bool:
    return any(style.startswith(prefix) for prefix in _HEADING_STYLE_PREFIXES)


__all__ = [
    "iter_body",
    "open_docx_zip",
    "_flag_repeating_headers",
]
