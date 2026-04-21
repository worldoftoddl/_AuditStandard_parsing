"""`md_renderer.py` + `cli.py` 렌더링 테스트 — Phase 1 Task #5."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from audit_parser.cli import app as cli_app
from audit_parser.convert.md_renderer import (
    SCHEMA_VERSION,
    RenderResult,
    render_markdown,
    write_markdown_files,
)
from audit_parser.ir.docx_reader import iter_body
from audit_parser.ir.numbering import NumberingEngine, parse_numbering_from_docx
from audit_parser.ir.structure import iter_blocks
from audit_parser.ir.types import Block, BlockKind, Section

_REAL_DOCX = Path(__file__).resolve().parents[1] / "raw" / "0. 회계감사기준 전문(2025 개정).docx"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mk_block(
    *,
    idx: int = 0,
    kind: BlockKind = BlockKind.PARAGRAPH_BODY,
    text: str = "",
    style: str = "",
    paragraph_id: str | None = None,
    is_application_guidance: bool = False,
    parent_paragraph_id: str | None = None,
    standard_no: str | None = "200",
    standard_title: str | None = "독립된 감사인의 전반적인 목적과 감사기준에 따른 감사의 수행",
    section: Section | None = None,
    heading_trail: tuple[str, ...] = (),
    immediate_heading: str | None = None,
    is_toc: bool = False,
    is_header_footer: bool = False,
    table_cells: tuple[tuple[str, ...], ...] | None = None,
) -> Block:
    return Block(
        idx=idx,
        kind=kind,
        text=text,
        style=style,
        paragraph_id=paragraph_id,
        is_application_guidance=is_application_guidance,
        parent_paragraph_id=parent_paragraph_id,
        standard_no=standard_no,
        standard_title=standard_title,
        section=section,
        heading_trail=heading_trail,
        immediate_heading=immediate_heading,
        is_toc=is_toc,
        is_header_footer=is_header_footer,
        table_cells=table_cells,
    )


def _by_filename(results: list[RenderResult], name: str) -> RenderResult:
    for r in results:
        if r.filename == name:
            return r
    raise AssertionError(f"filename {name!r} not found in {[r.filename for r in results]}")


# ---------------------------------------------------------------------------
# R1 — prelude 파일 + TOC entry
# ---------------------------------------------------------------------------


def test_r1_prelude_with_toc_entries() -> None:
    blocks = [
        _mk_block(
            idx=0,
            kind=BlockKind.HEADING,
            text="회계감사기준 전문",
            style="heading 1",
            standard_no=None,
            standard_title=None,
        ),
        _mk_block(
            idx=1,
            kind=BlockKind.TOC_ENTRY,
            text="서론 ......... 1",
            style="목차",
            standard_no=None,
            standard_title=None,
            is_toc=True,
        ),
    ]
    results = render_markdown(blocks, source_file="0. 회계감사기준 전문(2025 개정).docx")
    assert len(results) == 1
    r = results[0]
    assert r.filename == "00_전문.md"
    assert r.standard_no is None
    assert f'schema_version: "{SCHEMA_VERSION}"' in r.content
    assert 'content_type: "prelude_and_toc"' in r.content
    assert "# 회계감사기준 전문" in r.content
    assert "- 서론 ......... 1" in r.content
    assert "<!-- kind: toc_entry | idx: 1 -->" in r.content


# ---------------------------------------------------------------------------
# R2 — heading 1 + heading 2 섹션 + REQ 1.
# ---------------------------------------------------------------------------


def test_r2_standard_with_section_and_requirement() -> None:
    blocks = [
        _mk_block(
            idx=5,
            kind=BlockKind.HEADING,
            text="감사기준서 200 독립된 감사인의 전반적인 목적과 감사기준에 따른 감사의 수행",
            style="heading 1",
            heading_trail=("감사기준서 200",),
        ),
        _mk_block(
            idx=6,
            kind=BlockKind.HEADING,
            text="서론",
            style="heading 2",
            section=Section.INTRO,
            heading_trail=("감사기준서 200", "서론"),
        ),
        _mk_block(
            idx=10,
            kind=BlockKind.REQUIREMENT,
            text="본 감사기준서는 ...",
            style="목록A",
            paragraph_id="1.",
            section=Section.REQUIREMENTS,
            heading_trail=("감사기준서 200", "요구사항"),
        ),
    ]
    results = render_markdown(blocks, source_file="src.docx")
    r = _by_filename(results, "ISA-200.md")
    c = r.content
    assert f'schema_version: "{SCHEMA_VERSION}"' in c
    assert 'standard_id: "ISA-200"' in c
    assert 'standard_no: "200"' in c
    assert "# 감사기준서 200" in c
    assert "## 서론\n<!-- section: intro | idx: 6 -->" in c
    assert "1.\t본 감사기준서는 ...\n<!-- para: 1. | kind: requirement | idx: 10 -->" in c


# ---------------------------------------------------------------------------
# R3 — APPLICATION_GUIDANCE parent
# ---------------------------------------------------------------------------


def test_r3_application_guidance_with_parent() -> None:
    blocks = [
        _mk_block(
            idx=100,
            kind=BlockKind.APPLICATION_GUIDANCE,
            text="적용지침 본문",
            style="목록A",
            paragraph_id="A1.",
            is_application_guidance=True,
            parent_paragraph_id="9.",
            section=Section.APPLICATION,
            standard_no="200",
        ),
    ]
    results = render_markdown(blocks, source_file="src.docx")
    c = _by_filename(results, "ISA-200.md").content
    assert "A1.\t적용지침 본문" in c
    assert "<!-- para: A1. | kind: application_guidance | parent: 9. | idx: 100 -->" in c


# ---------------------------------------------------------------------------
# R4~R5 — SUB_ITEM indent 규칙
# ---------------------------------------------------------------------------


def test_r4_sub_item_lowercase_letter_one_tab() -> None:
    block = _mk_block(
        idx=50,
        kind=BlockKind.SUB_ITEM,
        text="부문감사인이 업무를 수행한다.",
        style="목록A",
        paragraph_id="(a)",
        parent_paragraph_id="1.",
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "\t(a)\t부문감사인이 업무를 수행한다." in c
    assert "<!-- para: (a) | kind: sub_item | parent: 1. | idx: 50 -->" in c


def test_r5_sub_item_lowercase_roman_two_tabs() -> None:
    block = _mk_block(
        idx=51,
        kind=BlockKind.SUB_ITEM,
        text="세부 항목",
        style="목록A",
        paragraph_id="(i)",
        parent_paragraph_id="1.",
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "\t\t(i)\t세부 항목" in c


# ---------------------------------------------------------------------------
# R6 — BULLET
# ---------------------------------------------------------------------------


def test_r6_bullet_normalized_to_unicode_bullet() -> None:
    block = _mk_block(idx=77, kind=BlockKind.BULLET, text="불릿 본문", style="불릿목록A")
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "\t•\t불릿 본문" in c
    assert "<!-- kind: bullet | idx: 77 -->" in c


# ---------------------------------------------------------------------------
# R7 — PARAGRAPH_BODY (no label)
# ---------------------------------------------------------------------------


def test_r7_paragraph_body_without_label() -> None:
    block = _mk_block(idx=200, kind=BlockKind.PARAGRAPH_BODY, text="자유 본문 단락.", style="문단")
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "\n자유 본문 단락.\n<!-- kind: paragraph_body | idx: 200 -->" in c


# ---------------------------------------------------------------------------
# R8 — UNKNOWN_NUMBERING
# ---------------------------------------------------------------------------


def test_r8_unknown_numbering_rendered_with_question_marker() -> None:
    block = _mk_block(
        idx=77,
        kind=BlockKind.UNKNOWN_NUMBERING,
        text="미지 번호 본문",
        style="목록A",
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "[?]\t미지 번호 본문" in c
    assert "<!-- kind: unknown_numbering | idx: 77 -->" in c


# ---------------------------------------------------------------------------
# R9~R10 — BLOCK_QUOTE
# ---------------------------------------------------------------------------


def test_r9_block_quote_single_line() -> None:
    block = _mk_block(idx=88, kind=BlockKind.BLOCK_QUOTE, text="경고: 이 기준서는 …", style="")
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "> 경고: 이 기준서는 …" in c
    assert "<!-- kind: block_quote | idx: 88 -->" in c


def test_r10_block_quote_multi_line() -> None:
    block = _mk_block(idx=89, kind=BlockKind.BLOCK_QUOTE, text="1행\n2행\n3행", style="")
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "> 1행\n> 2행\n> 3행" in c


# ---------------------------------------------------------------------------
# R11~R12 — TABLE
# ---------------------------------------------------------------------------


def test_r11_table_three_rows_two_cols() -> None:
    block = _mk_block(
        idx=301,
        kind=BlockKind.TABLE,
        text="",
        style="",
        table_cells=(
            ("위험", "대응"),
            ("부정위험", "추가 절차 수행"),
            ("회계추정", "경영진 바이어스 검토"),
        ),
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "| 위험 | 대응 |" in c
    assert "| --- | --- |" in c
    assert "| 부정위험 | 추가 절차 수행 |" in c
    assert "<!-- kind: table | rows: 3 | cols: 2 | idx: 301 -->" in c


def test_r12_table_escapes_pipe_and_newline() -> None:
    block = _mk_block(
        idx=302,
        kind=BlockKind.TABLE,
        text="",
        style="",
        table_cells=(
            ("헤더|A", "헤더B"),
            ("행1\n줄2", "값"),
        ),
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "| 헤더\\|A | 헤더B |" in c
    assert "| 행1<br>줄2 | 값 |" in c


# ---------------------------------------------------------------------------
# R13 — 보론 제목 APPENDIX 전이
# ---------------------------------------------------------------------------


def test_r13_appendix_heading_emits_section_comment() -> None:
    blocks = [
        _mk_block(
            idx=1000,
            kind=BlockKind.HEADING,
            text="적용 및 기타 설명자료",
            style="heading 2",
            section=Section.APPLICATION,
        ),
        _mk_block(
            idx=1247,
            kind=BlockKind.HEADING,
            text="보론 A",
            style="보론 제목",
            section=Section.APPENDIX,
        ),
    ]
    c = _by_filename(render_markdown(blocks, source_file="s.docx"), "ISA-200.md").content
    assert "### 보론 A\n<!-- section: appendix | idx: 1247 -->" in c


# ---------------------------------------------------------------------------
# R14 — ISA 전환
# ---------------------------------------------------------------------------


def test_r14_standard_transition_produces_two_files() -> None:
    blocks = [
        _mk_block(
            idx=5,
            kind=BlockKind.HEADING,
            text="감사기준서 200",
            style="heading 1",
            standard_no="200",
            standard_title="A",
        ),
        _mk_block(
            idx=900,
            kind=BlockKind.HEADING,
            text="감사기준서 210",
            style="heading 1",
            standard_no="210",
            standard_title="B",
        ),
    ]
    results = render_markdown(blocks, source_file="s.docx")
    names = {r.filename for r in results}
    assert names == {"ISA-200.md", "ISA-210.md"}


# ---------------------------------------------------------------------------
# R15 — is_toc=True 블록이 standard_no 가 있어도 00_전문.md 로 이동
# ---------------------------------------------------------------------------


def test_r15_is_toc_routes_to_prelude_even_with_standard_no() -> None:
    blocks = [
        _mk_block(
            idx=5,
            kind=BlockKind.HEADING,
            text="감사기준서 200",
            style="heading 1",
            standard_no="200",
        ),
        _mk_block(
            idx=6,
            kind=BlockKind.TOC_ENTRY,
            text="요구사항 .... 10",
            style="목차",
            standard_no="200",
            is_toc=True,
        ),
    ]
    results = render_markdown(blocks, source_file="s.docx")
    isa_200 = _by_filename(results, "ISA-200.md")
    prelude = _by_filename(results, "00_전문.md")
    assert "요구사항 .... 10" in prelude.content
    assert "요구사항 .... 10" not in isa_200.content


# ---------------------------------------------------------------------------
# R16 — YAML escape
# ---------------------------------------------------------------------------


def test_r16_yaml_escapes_quotes_in_title() -> None:
    block = _mk_block(
        idx=5,
        kind=BlockKind.HEADING,
        text="감사기준서 200",
        style="heading 1",
        standard_no="200",
        standard_title='제목 "따옴표" 포함',
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert 'standard_title: "제목 \\"따옴표\\" 포함"' in c


# ---------------------------------------------------------------------------
# R17 — standard_title=None 시 키 생략
# ---------------------------------------------------------------------------


def test_r17_missing_standard_title_omits_key() -> None:
    block = _mk_block(
        idx=5,
        kind=BlockKind.HEADING,
        text="감사기준서 200",
        style="heading 1",
        standard_no="200",
        standard_title=None,
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "standard_title" not in c


# ---------------------------------------------------------------------------
# R18 — 매핑되지 않은 heading 2
# ---------------------------------------------------------------------------


def test_r18_unmapped_heading2_has_no_section_comment() -> None:
    block = _mk_block(
        idx=20,
        kind=BlockKind.HEADING,
        text="기타 섹션",
        style="heading 2",
        section=None,
    )
    c = _by_filename(render_markdown([block], source_file="s.docx"), "ISA-200.md").content
    assert "## 기타 섹션" in c
    assert "section:" not in c.split("## 기타 섹션")[1].split("\n", 2)[1]


# ---------------------------------------------------------------------------
# F1~F3 — 파일 I/O
# ---------------------------------------------------------------------------


def test_f1_write_creates_files_in_out_dir(tmp_path: Path) -> None:
    blocks = [
        _mk_block(
            idx=0,
            kind=BlockKind.HEADING,
            text="표지",
            style="heading 1",
            standard_no=None,
            standard_title=None,
        ),
        _mk_block(
            idx=5,
            kind=BlockKind.HEADING,
            text="감사기준서 200",
            style="heading 1",
            standard_no="200",
            standard_title="제목",
        ),
    ]
    paths = write_markdown_files(blocks, source_file="s.docx", out_dir=tmp_path)
    names = {p.name for p in paths}
    assert "00_전문.md" in names
    assert "ISA-200.md" in names
    for p in paths:
        assert p.exists()


def test_f2_rewrite_overwrites_existing(tmp_path: Path) -> None:
    block = _mk_block(
        idx=5,
        kind=BlockKind.HEADING,
        text="감사기준서 200",
        style="heading 1",
        standard_no="200",
        standard_title="A",
    )
    write_markdown_files([block], source_file="s.docx", out_dir=tmp_path)
    new_block = _mk_block(
        idx=5,
        kind=BlockKind.HEADING,
        text="감사기준서 200",
        style="heading 1",
        standard_no="200",
        standard_title="B",
    )
    write_markdown_files([new_block], source_file="s.docx", out_dir=tmp_path)
    content = (tmp_path / "ISA-200.md").read_text(encoding="utf-8")
    assert 'standard_title: "B"' in content
    assert 'standard_title: "A"' not in content


def test_f3_empty_input_writes_no_files(tmp_path: Path) -> None:
    paths = write_markdown_files([], source_file="s.docx", out_dir=tmp_path)
    assert paths == []


# ---------------------------------------------------------------------------
# C1~C2 — CLI 스모크
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="원본 DOCX 필요")
def test_c1_cli_dry_run_reports_block_count(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["convert", str(_REAL_DOCX), "--out", str(tmp_path), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "[dry-run] processed" in result.output
    assert "blocks" in result.output


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="원본 DOCX 필요")
def test_c2_cli_full_run_creates_prelude_and_isa_files(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli_app, ["convert", str(_REAL_DOCX), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "00_전문.md").exists()
    assert (tmp_path / "ISA-200.md").exists()
    assert (tmp_path / "ISA-1200.md").exists()


# ---------------------------------------------------------------------------
# E2E — 실제 DOCX
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="원본 DOCX 필요")
def test_e2e_render_real_docx(tmp_path: Path) -> None:
    import zipfile

    with zipfile.ZipFile(_REAL_DOCX) as zf:
        abstract_nums, num_defs = parse_numbering_from_docx(zf)
    engine = NumberingEngine(abstract_nums, num_defs)
    paths = write_markdown_files(
        iter_blocks(iter_body(_REAL_DOCX), engine),
        source_file=_REAL_DOCX.name,
        out_dir=tmp_path,
    )
    names = sorted(p.name for p in paths)
    # 1. 파일 수 = 37 (00_전문 + ISA-{nnn} 36개)
    assert "00_전문.md" in names
    isa_files = [n for n in names if n.startswith("ISA-")]
    assert len(isa_files) == 36, isa_files

    # 2. ISA-200.md 구조
    isa200 = (tmp_path / "ISA-200.md").read_text(encoding="utf-8")
    lines = isa200.splitlines()
    assert lines[0] == "---"
    assert lines[1] == f'schema_version: "{SCHEMA_VERSION}"'
    assert "# 감사기준서 200" in isa200

    # 3. ISA-1200 은 각 파트(서론/계획/위험평가/...)별 `### 목적` 서브헤드 반복
    isa1200 = (tmp_path / "ISA-1200.md").read_text(encoding="utf-8")
    purpose_heading_count = sum(1 for ln in isa1200.splitlines() if ln.strip() == "### 목적")
    assert purpose_heading_count >= 3, purpose_heading_count

    # 4. ISA-550 첫 REQ = 1. (numbering.reset() 회귀 가드)
    isa550 = (tmp_path / "ISA-550.md").read_text(encoding="utf-8")
    first_req_line = next(ln for ln in isa550.splitlines() if "kind: requirement" in ln)
    # first REQ 주석이 para: 1. 를 포함해야 함
    assert "para: 1." in first_req_line, first_req_line

    # 5. 모든 ISA-*.md 에 toc_entry 주석 없음
    for name in isa_files:
        content = (tmp_path / name).read_text(encoding="utf-8")
        assert "kind: toc_entry" not in content, name

    # 6. 00_전문.md 에 toc_entry 주석 ≥ 700
    prelude = (tmp_path / "00_전문.md").read_text(encoding="utf-8")
    toc_count = prelude.count("kind: toc_entry")
    assert toc_count >= 700, toc_count
