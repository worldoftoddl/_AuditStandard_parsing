"""Phase 4d MD -> JSON tests for non-ISA standards."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from audit_parser.ingest.md_parser import parse_md, to_json_dict

REPO_ROOT = Path(__file__).resolve().parents[1]
MD_DIR = REPO_ROOT / "output" / "md"
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "json_schema_v1_2.schema.json"
THREE_LEVEL_NUMERIC_SUFFIX_RE = re.compile(r"#\d+#\d+#\d+")


NON_ISA_MD_CASES = (
    (
        "ISQM-1",
        "1",
        "품질관리기준서 1",
        "requirements",
        "1",
        "품질관리시스템은 기준서 요구사항에 따라 설계되어야 한다.",
    ),
    (
        "ASSR-3000",
        "3000",
        "인증업무기준 3000",
        "requirements",
        "12.",
        "업무수행자는 인증업무의 목적을 달성하기 위한 절차를 수행한다.",
    ),
    (
        "FRMK-1",
        "1",
        "인증업무개념체계",
        "appendix",
        "26.",
        "역할과 책임은 인증업무 상황에 따라 명확히 식별되어야 한다.",
    ),
)

REAL_NON_ISA_MD_FILES = ("ISQM-1.md", "ASSR-3000.md", "FRMK-1.md")


@pytest.fixture(scope="session")
def schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _write_non_isa_md(
    tmp_path: Path,
    *,
    standard_id: str,
    standard_no: str,
    standard_title: str,
    section: str,
    paragraph_id: str,
    body: str,
) -> Path:
    md_path = tmp_path / f"{standard_id}.md"
    md_path.write_text(
        "\n".join(
            [
                "---",
                'schema_version: "1.0"',
                f'standard_id: "{standard_id}"',
                f'standard_no: "{standard_no}"',
                f'standard_title: "{standard_title}"',
                f'source_file: "{standard_id}.docx"',
                "---",
                "",
                f"# {standard_title}",
                "<!-- idx: 1 -->",
                "",
                "## 요구사항",
                f"<!-- section: {section} | idx: 2 -->",
                "",
                f"{paragraph_id}\t{body}",
                f"<!-- para: {paragraph_id} | kind: requirement | idx: 3 -->",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return md_path


def _parse_case(tmp_path: Path, case: tuple[str, str, str, str, str, str]):
    standard_id, standard_no, standard_title, section, paragraph_id, body = case
    md_path = _write_non_isa_md(
        tmp_path,
        standard_id=standard_id,
        standard_no=standard_no,
        standard_title=standard_title,
        section=section,
        paragraph_id=paragraph_id,
        body=body,
    )
    parsed = parse_md(md_path)
    assert parsed is not None
    return parsed


@pytest.mark.parametrize(
    "case",
    NON_ISA_MD_CASES,
    ids=[case[0] for case in NON_ISA_MD_CASES],
)
def test_parse_md_succeeds_for_non_isa_phase4d(
    tmp_path: Path,
    case: tuple[str, str, str, str, str, str],
) -> None:
    standard_id, standard_no, _title, section, paragraph_id, _body = case

    parsed = _parse_case(tmp_path, case)

    assert parsed.standard.standard_id == standard_id
    assert parsed.standard.standard_no == standard_no
    assert len(parsed.chunks) == 1
    chunk = parsed.chunks[0]
    assert chunk.chunk_id.startswith(f"{standard_id}:{section}:")
    assert chunk.paragraph_id == paragraph_id
    assert chunk.section == section


@pytest.mark.parametrize(
    "case",
    NON_ISA_MD_CASES,
    ids=[case[0] for case in NON_ISA_MD_CASES],
)
def test_non_isa_json_serialization_validates_schema_v1_2(
    tmp_path: Path,
    schema_validator: Draft202012Validator,
    case: tuple[str, str, str, str, str, str],
) -> None:
    parsed = _parse_case(tmp_path, case)
    data = to_json_dict(parsed)

    errors = sorted(schema_validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    assert not errors, [e.message for e in errors[:3]]
    assert data["schema_version"] == "1.2.0"
    assert data["standard"]["standard_id"] == parsed.standard.standard_id


@pytest.mark.parametrize(
    "case",
    NON_ISA_MD_CASES,
    ids=[case[0] for case in NON_ISA_MD_CASES],
)
def test_non_isa_chunk_ids_are_unique_without_3level_numeric_suffix(
    tmp_path: Path,
    case: tuple[str, str, str, str, str, str],
) -> None:
    parsed = _parse_case(tmp_path, case)
    chunk_ids = [chunk.chunk_id for chunk in parsed.chunks]

    assert len(chunk_ids) == len(set(chunk_ids))
    assert not [
        chunk_id
        for chunk_id in chunk_ids
        if THREE_LEVEL_NUMERIC_SUFFIX_RE.search(chunk_id)
    ]


@pytest.mark.parametrize(
    "case",
    NON_ISA_MD_CASES,
    ids=[case[0] for case in NON_ISA_MD_CASES],
)
def test_write_json_uses_standard_id_filename_for_non_isa(
    tmp_path: Path,
    case: tuple[str, str, str, str, str, str],
) -> None:
    from audit_parser.cli import _write_json

    parsed = _parse_case(tmp_path, case)
    out_dir = tmp_path / "json"
    out_dir.mkdir()

    written = _write_json(parsed, out_dir)

    assert written == out_dir / f"{parsed.standard.standard_id}.json"
    assert written.exists()


@pytest.mark.parametrize("filename", REAL_NON_ISA_MD_FILES)
def test_real_phase4d_non_isa_md_parse_and_validate_if_present(
    filename: str,
    schema_validator: Draft202012Validator,
) -> None:
    md_path = MD_DIR / filename
    if not md_path.exists():
        pytest.skip(f"{md_path} missing — run Phase 4c convert first")

    parsed = parse_md(md_path)
    assert parsed is not None
    data = to_json_dict(parsed)
    errors = sorted(schema_validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    assert not errors, [e.message for e in errors[:3]]

    chunk_ids = [chunk.chunk_id for chunk in parsed.chunks]
    assert len(chunk_ids) == len(set(chunk_ids))
    assert not any(THREE_LEVEL_NUMERIC_SUFFIX_RE.search(chunk_id) for chunk_id in chunk_ids)


def test_real_frmk_restores_table_heading_sections_and_special_appendix() -> None:
    """FRMK heading list is separate from body tables; parser must restore row scope."""
    md_path = MD_DIR / "FRMK-1.md"
    if not md_path.exists():
        pytest.skip(f"{md_path} missing — run Phase 4c convert first")

    parsed = parse_md(md_path)
    assert parsed is not None

    assert any(chunk.section == "intro" for chunk in parsed.chunks)
    assert any(chunk.section == "evidence" for chunk in parsed.chunks)
    assert any(chunk.section == "appendix" for chunk in parsed.chunks)
    assert not all(chunk.section == "appendix" for chunk in parsed.chunks)

    special_chunks = [
        chunk
        for chunk in parsed.chunks
        if chunk.special_appendix_name == "역할과 책임"
    ]
    assert special_chunks
    assert all(chunk.appendix_index is None for chunk in special_chunks)


def test_real_isqm_iter_body_global_idx_unique_if_raw_present() -> None:
    """ISQM body_parser output must be globally reindexed before MD rendering."""
    from audit_parser.ir import iter_body
    from audit_parser.spec import ISQM_SPEC

    raw_path = REPO_ROOT / "raw" / "3. 품질관리기준서1(2018년 제정)_국어전문.docx"
    if not raw_path.exists():
        pytest.skip(f"{raw_path} missing")

    blocks = list(iter_body(raw_path, spec=ISQM_SPEC))
    indices = [block.idx for block in blocks]
    assert len(indices) == len(set(indices))
    assert indices == list(range(len(indices)))
