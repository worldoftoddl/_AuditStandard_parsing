"""IR(Intermediate Representation) 레이어 — Phase 1.

`types.py` 의 데이터클래스, `docx_reader` 의 body 순회, `numbering` 의 카운터 replay
엔진을 re-export.
"""

from audit_parser.ir.docx_reader import iter_body, open_docx_zip
from audit_parser.ir.numbering import (
    AbstractNumDef,
    LevelDef,
    NumberedParagraph,
    NumberingEngine,
    NumberingRaw,
    NumDef,
    classify_kind,
    format_counter,
    parse_numbering_from_docx,
    parse_numbering_xml,
    render_lvl_text,
)
from audit_parser.ir.structure import ISA_BOUNDARY, StructureMachine, iter_blocks
from audit_parser.ir.styles import (
    StyleIndex,
    StyleNumDefault,
    parse_styles_xml,
    resolve_paragraph_numPr,
)
from audit_parser.ir.types import Block, BlockKind, RawBlock, Section

__all__ = [
    "ISA_BOUNDARY",
    "AbstractNumDef",
    "Block",
    "BlockKind",
    "LevelDef",
    "NumDef",
    "NumberedParagraph",
    "NumberingEngine",
    "NumberingRaw",
    "RawBlock",
    "Section",
    "StructureMachine",
    "StyleIndex",
    "StyleNumDefault",
    "classify_kind",
    "format_counter",
    "iter_blocks",
    "iter_body",
    "open_docx_zip",
    "parse_numbering_from_docx",
    "parse_numbering_xml",
    "parse_styles_xml",
    "render_lvl_text",
    "resolve_paragraph_numPr",
]
