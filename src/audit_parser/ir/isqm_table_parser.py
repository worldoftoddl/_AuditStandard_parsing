"""ISQM-1 body-table parser — Phase 4b-2 c2.

The ISQM-1 (``raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx``) body content
is stored entirely inside a single 2-column table (``tbl[236x2]``). The left
column holds the paragraph identifier as **plain cell text** (not ``numPr``),
and the right column holds the body content (potentially across multiple
``<w:p>`` elements — the first is the requirement body, subsequent are
``(a)/(b)/(i)/(1)`` sub-items). Empty left columns mark section / sub-section
heading rows. See ``docs/isqm_structure_profile.md §2.3`` for the structural
profile and ``§2.5`` for the KICPA-specific ``한{N}-{M}`` prefix semantics.

Phase 4b-2 scope: this module emits ``RawBlock`` instances that a Phase 4c
wiring step (``docx_reader.iter_blocks`` + ``structure.py``) will consume to
build the final ``Block`` stream. The emitted ``RawBlock`` instances carry
``paragraph_id`` directly (cell-text extraction) instead of relying on the
``NumberingEngine`` replay used for ISA. β-1 invariant (Critic
``docs/checkpoint_4_prep.md §1.8``): this parser emits **atomic** ``RawBlock``
only — chunk splitting remains ``chunk_splitter.split_oversized_chunks``'s
sole responsibility. Future 2-column parsers (e.g. ISQM-2) should live in
sibling ``ir/`` modules; do NOT generalize this file.

Marker fragility — Phase 5 에서 regex/structural 추상화 재검토 (ticket: TBD).
현 heuristics (``col[0]==""`` 가 section/subsection heading, ``_SUB_ID_RE`` 로
sub-item 감지) 는 2026-04-22 freeze data 기준. KICPA 차후 개정 시 silent miss
가능 — WARNING 로그를 stderr 로 발신해 Domain Reviewer 피드백 루프 확보.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from typing import Final

from lxml import etree

from audit_parser.ir.types import BlockKind, RawBlock

_W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMAP: Final[dict[str, str]] = {"w": _W_NS}


def _qn(tag: str) -> str:
    prefix, _, local = tag.partition(":")
    return f"{{{_NSMAP[prefix]}}}{local}"


_TAG_TR: Final = _qn("w:tr")
_TAG_TC: Final = _qn("w:tc")
_TAG_P: Final = _qn("w:p")
_TAG_T: Final = _qn("w:t")
_TAG_TAB: Final = _qn("w:tab")
_TAG_BR: Final = _qn("w:br")
_TAG_CR: Final = _qn("w:cr")
_TAG_R: Final = _qn("w:r")


# Sub-item prefix regex. Covers four alternatives per
# ``docs/isqm_structure_profile.md §3.2`` + ``§2.3`` pseudocode:
#   * ``(a)``..``(zz)``  — latin lowercase (1-2 chars)
#   * ``(가)``..          — single Hangul syllable
#   * ``(i)``..``(ivx)``  — lowercase roman numeral (1-4 chars)
#   * ``(1)``..``(99)``   — decimal (Critic verbal R1 — 2026-04-23 LOCK)
# Must be **prefix**-anchored: sub-items start with the marker followed by
# whitespace (or end-of-string for single-paren rows).
_SUB_ID_RE: Final = re.compile(
    r"^\s*\(([a-z]{1,2}|[가-힣]|[ivx]{1,4}|\d{1,2})\)\s*"
)


# Phase 4c c4 추가 — reference suffix canonical strip (Domain Reviewer 2026-04-23
# 판정 (c)). KICPA 2018 ISQM-1 body table sub-section headings 이 종종
# ``(문단 N 참조)`` / ``(문단 N-M 관련)`` parenthetical reference 를 동반. 비교
# 전 strip 하여 canonical form 으로 ISQM_SUBSECTIONS 매칭.
# 예: "감독(문단 32(b) 참조)" → "감독"
# 예: "업무의 해지 (문단 28 참조)" → "업무의 해지"
# 예: "공공부문 감사조직에 특유한 고려 사항 (문단 26-28 관련)"
#     → "공공부문 감사조직에 특유한 고려 사항"
_REFERENCE_SUFFIX_RE: Final = re.compile(
    r"\s*\(문단.*(?:참조|관련)\s*\)\s*$"
)


def _strip_reference_suffix(text: str) -> str:
    """Strip trailing ``(문단 N 참조)`` / ``(문단 N-M 관련)`` suffix.

    Returns canonical form for ISQM_SUBSECTIONS comparison. Idempotent —
    calling twice on same text returns same result.

    Supports KICPA body-table heading patterns including nested parentheses
    for sub-item references: ``"감독(문단 32(b) 참조)"`` → ``"감독"``,
    ``"업무품질관리검토의 기준 (문단 35(b) 참조)"`` → ``"업무품질관리검토의 기준"``.
    """
    return _REFERENCE_SUFFIX_RE.sub("", text).strip()


def _extract_sub_id(text: str) -> str | None:
    """Return the sub-item prefix like ``"(a)"`` / ``"(가)"`` / ``"(i)"`` / ``"(1)"``.

    The KICPA body cells occasionally embed sub-item text as plain body without
    the parenthesis form (continuation lines). ``None`` means "not a sub-item
    row — treat as paragraph continuation".

    Examples:
        >>> _extract_sub_id("(a) 독립성의 위협")
        '(a)'
        >>> _extract_sub_id("(가) 국내 관례")
        '(가)'
        >>> _extract_sub_id("(iii) minor")
        '(iii)'
        >>> _extract_sub_id("(1) enumerated")
        '(1)'
        >>> _extract_sub_id("plain continuation text") is None
        True
    """
    match = _SUB_ID_RE.match(text)
    if match is None:
        return None
    return f"({match.group(1)})"


def _cell_text(tc_elem: etree._Element) -> str:
    """Concatenate all ``<w:t>`` runs in a single cell paragraph (first ``<w:p>``).

    Used for the col[0] paragraph_id extraction which should be a single line.
    Multi-paragraph col[1] iteration lives in :func:`_cell_paragraphs`.
    """
    parts: list[str] = []
    for p_elem in tc_elem.iter(_TAG_P):
        parts.append(_paragraph_text(p_elem))
        # col[0] is expected to be a single <w:p>; iterate in case of layout
        # quirks but break on first non-empty content.
        if parts[-1].strip():
            break
    return "".join(parts)


def _cell_paragraphs(tc_elem: etree._Element) -> list[etree._Element]:
    """Return list of ``<w:p>`` elements inside the cell, preserving order."""
    return list(tc_elem.iter(_TAG_P))


def _paragraph_text(p_elem: etree._Element) -> str:
    """Concatenate ``<w:t>`` runs inside a single ``<w:p>``.

    Same convention as ``docx_reader._xml_para_text`` — tabs become ``\\t``
    and ``<w:br>``/``<w:cr>`` become ``\\n``.
    """
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


def parse_isqm_body_table(
    tbl_elem: etree._Element,
    *,
    isqm_sections: frozenset[str] | None = None,
    isqm_subsections: frozenset[str] | None = None,
    isqm_table_headers: frozenset[str] | None = None,
    warn_unknown_headings: bool = True,
) -> Iterable[RawBlock]:
    """Parse an ISQM-1 2-column body table into a stream of ``RawBlock`` instances.

    Args:
        tbl_elem: The ``<w:tbl>`` element of the body table (``tbl[236x2]`` in
            the 2018 KICPA DOCX). Meta (``tbl[3x3]``) and TOC (``tbl[244x1]``)
            tables must be handled by the caller — this function assumes the
            input is the body table.
        isqm_sections: Optional whitelist of primary section heading texts.
            When provided, rows with ``col[0]`` empty and ``col[1]`` matching
            a member emit ``BlockKind.HEADING`` with ``style="isqm_section"``.
        isqm_subsections: Optional whitelist of sub-section heading texts.
            Same semantics as ``isqm_sections`` but ``style="isqm_subsection"``.
        warn_unknown_headings: When ``True`` (default), rows with empty
            ``col[0]`` whose ``col[1]`` matches neither whitelist emit a
            ``stderr`` WARNING + fall through to ``PARAGRAPH_BODY``. Domain
            Reviewer feedback loop per ``docs/isqm_structure_profile.md §2.4``.

    Yields:
        ``RawBlock`` with ``paragraph_id`` populated from ``col[0]`` (for
        REQUIREMENT / SUB_ITEM) or ``None`` (for HEADING / PARAGRAPH_BODY
        continuations). ``idx`` counts emitted blocks zero-based.

    Notes:
        * β-1 invariant: atomic emission only. Cell text > 4000 tokens is
          passed through unchanged; ``chunk_splitter`` handles re-splitting
          downstream.
        * ``paragraph_id`` is ``.strip()``-normalized (ASCII + Unicode Zs
          including IDEOGRAPHIC SPACE U+3000 + nbsp U+00A0).
    """
    sections = isqm_sections or frozenset()
    subsections = isqm_subsections or frozenset()
    table_headers = isqm_table_headers or frozenset()
    emit_counter = 0

    for tr_elem in tbl_elem.iter(_TAG_TR):
        cells = tr_elem.findall(_TAG_TC)
        if len(cells) != 2:
            _warn_non_2_col(len(cells), warn_unknown_headings)
            continue

        col0_text = _cell_text(cells[0]).strip()
        col1_paragraphs = _cell_paragraphs(cells[1])
        col1_first_text = (
            _paragraph_text(col1_paragraphs[0]).strip() if col1_paragraphs else ""
        )

        if not col0_text:
            # Case 1: heading row / layout filler
            emitted = list(
                _emit_heading_or_fallback(
                    col1_first_text,
                    emit_counter,
                    sections,
                    subsections,
                    table_headers,
                    warn_unknown_headings,
                )
            )
            yield from emitted
            emit_counter += len(emitted)
            continue

        # Case 2: Non-empty col[0] = paragraph_id row with body content.
        paragraph_id = col0_text
        yield RawBlock(
            idx=emit_counter,
            kind=BlockKind.REQUIREMENT,
            text=col1_first_text,
            style="",
            num_id=None,
            ilvl=None,
            paragraph_id=paragraph_id,
        )
        emit_counter += 1

        # Subsequent paragraphs = sub-items or paragraph-body continuations.
        for sub_block in _iter_sub_item_blocks(
            col1_paragraphs[1:], counter_start=emit_counter
        ):
            yield sub_block
            emit_counter += 1


def _warn_non_2_col(cell_count: int, warn: bool) -> None:
    """Warn on a row whose cell count is not 2 (layout anomaly)."""
    if warn and cell_count != 0:
        print(
            f"[isqm_table_parser] non-2-col row (cells={cell_count}) "
            f"— skipping. Inspect DOCX for schema drift.",
            file=sys.stderr,
        )


def _emit_heading_or_fallback(
    col1_first_text: str,
    idx: int,
    sections: frozenset[str],
    subsections: frozenset[str],
    table_headers: frozenset[str],
    warn_unknown: bool,
) -> Iterable[RawBlock]:
    """Classify an empty-col[0] row — TOC header (silent skip), HEADING
    (section/subsection), or PARAGRAPH_BODY fallback with WARNING.

    Phase 4c c4 (Domain Reviewer 2026-04-23):

    * ``table_headers`` match (``"문단번호"`` etc.) — silent skip, no WARNING.
    * ``sections`` / ``subsections`` match — HEADING emit with
      ``style="isqm_section"`` / ``"isqm_subsection"``.
    * Comparison uses canonical form after ``_strip_reference_suffix`` —
      e.g. ``"감독(문단 32(b) 참조)"`` matches canonical ``"감독"`` in
      ISQM_SUBSECTIONS.
    * Empty col[1] — layout filler, silent skip.
    * No match — PARAGRAPH_BODY fallback + WARNING.
    """
    if not col1_first_text:
        return
    canonical = _strip_reference_suffix(col1_first_text)
    # TOC column header — silent skip (e.g. "문단번호").
    if canonical in table_headers:
        return
    if canonical in sections:
        yield RawBlock(
            idx=idx,
            kind=BlockKind.HEADING,
            text=canonical,
            style="isqm_section",
            num_id=None,
            ilvl=None,
            paragraph_id=None,
        )
        return
    if canonical in subsections:
        yield RawBlock(
            idx=idx,
            kind=BlockKind.HEADING,
            text=canonical,
            style="isqm_subsection",
            num_id=None,
            ilvl=None,
            paragraph_id=None,
        )
        return
    if warn_unknown:
        print(
            f"[isqm_table_parser] unregistered heading row "
            f"(col[0]='', col[1]={col1_first_text!r}, canonical={canonical!r}) — "
            f"fallback to PARAGRAPH_BODY. Domain Reviewer: update "
            f"`docs/isqm_structure_profile.md §2.4` "
            f"ISQM_SECTIONS / ISQM_SUBSECTIONS whitelist if intended.",
            file=sys.stderr,
        )
    yield RawBlock(
        idx=idx,
        kind=BlockKind.PARAGRAPH_BODY,
        text=col1_first_text,
        style="",
        num_id=None,
        ilvl=None,
        paragraph_id=None,
    )


def _iter_sub_item_blocks(
    paragraphs: list[etree._Element],
    *,
    counter_start: int,
) -> Iterable[RawBlock]:
    """Yield SUB_ITEM or PARAGRAPH_BODY rows for col[1] continuations."""
    idx = counter_start
    for p_elem in paragraphs:
        text = _paragraph_text(p_elem).strip()
        if not text:
            continue
        sub_id = _extract_sub_id(text)
        if sub_id is not None:
            yield RawBlock(
                idx=idx,
                kind=BlockKind.SUB_ITEM,
                text=text,
                style="",
                num_id=None,
                ilvl=None,
                paragraph_id=sub_id,
            )
        else:
            yield RawBlock(
                idx=idx,
                kind=BlockKind.PARAGRAPH_BODY,
                text=text,
                style="",
                num_id=None,
                ilvl=None,
                paragraph_id=None,
            )
        idx += 1


__all__ = [
    "parse_isqm_body_table",
]
