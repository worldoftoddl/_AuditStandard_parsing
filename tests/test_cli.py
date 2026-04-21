"""`audit_parser.cli` 테스트 — Task #4 (C7 임계 fail + ingest 실구현).

`convert` C7 (3 cases) + `ingest` 일괄/단건/skipped/prelude (5 cases) +
JSON 내용 검증 (1 case) = 9 tests.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from audit_parser.cli import app as cli_app

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_DOCX = _REPO_ROOT / "raw" / "0. 회계감사기준 전문(2025 개정).docx"
_EXISTING_MD_DIR = _REPO_ROOT / "output" / "md"

_ISA_SAMPLES = ("ISA-200.md", "ISA-300.md", "ISA-1200.md")
_PRELUDE_FILE = "00_전문.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _copy_samples(dst: Path, names: tuple[str, ...]) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = _EXISTING_MD_DIR / name
        if not src.exists():
            pytest.skip(f"fixture MD 미존재: {src}")
        shutil.copyfile(src, dst / name)


# ---------------------------------------------------------------------------
# convert C7 (3 cases)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="원본 DOCX 필요")
def test_convert_c7_default_threshold_passes(tmp_path: Path) -> None:
    """기본 threshold 0.05 기준 PHASE_1_REPORT 실측 0.053% < 0.05% fail? 아니 0.053% < 5% → pass."""
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["convert", str(_REAL_DOCX), "--out", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    # 메시지 포맷 검증: "(unknown_numbering=N/M=0.xxxx%)"
    match = re.search(
        r"unknown_numbering=(\d+)/(\d+)=(\d+\.\d+)%",
        result.output,
    )
    assert match is not None, result.output
    unknown = int(match.group(1))
    total = int(match.group(2))
    assert total > 0
    assert unknown / total <= 0.05


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="원본 DOCX 필요")
def test_convert_c7_tight_threshold_fails_with_sample_idx(tmp_path: Path) -> None:
    """--unknown-threshold 0.0001 로 강제 fail — 출력에 sample idx + ERROR 포함."""
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "convert",
            str(_REAL_DOCX),
            "--out",
            str(tmp_path),
            "--unknown-threshold",
            "0.0001",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "ERROR" in result.output
    assert "unknown_numbering" in result.output
    # sample idx 는 리스트 형태 "[idx1, idx2, idx3]" — 정수 1~3 개 추출
    idx_match = re.search(r"sample block idx: \[(.*?)\]", result.output)
    assert idx_match is not None, result.output
    idxs = [s.strip() for s in idx_match.group(1).split(",") if s.strip()]
    assert 1 <= len(idxs) <= 3
    # 파일은 정상적으로 생성됨 (exit 1 은 품질 가드일 뿐)
    assert (tmp_path / _PRELUDE_FILE).exists()


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="원본 DOCX 필요")
def test_convert_c7_max_threshold_always_passes(tmp_path: Path) -> None:
    """--unknown-threshold 1.0 경계 max → 어떤 비율에서도 pass."""
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "convert",
            str(_REAL_DOCX),
            "--out",
            str(tmp_path),
            "--unknown-threshold",
            "1.0",
        ],
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# ingest — dir / single / skip (5 cases)
# ---------------------------------------------------------------------------


def test_ingest_dir_batch_writes_json_per_standard(tmp_path: Path) -> None:
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, _ISA_SAMPLES)
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["ingest", str(md_dir), "--out", str(json_dir)],
    )
    assert result.exit_code == 0, result.output
    assert f"Wrote {len(_ISA_SAMPLES)} files" in result.output
    assert (json_dir / "ISA-200.json").exists()
    assert (json_dir / "ISA-300.json").exists()
    assert (json_dir / "ISA-1200.json").exists()


def test_ingest_dir_logs_skipped_non_isa_md(tmp_path: Path) -> None:
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, ("ISA-200.md",))
    # 00_전문.md 추가 — parse_md_dir glob 에서 자동 제외 대상
    prelude_src = _EXISTING_MD_DIR / _PRELUDE_FILE
    if not prelude_src.exists():
        pytest.skip(f"fixture prelude 미존재: {prelude_src}")
    shutil.copyfile(prelude_src, md_dir / _PRELUDE_FILE)
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["ingest", str(md_dir), "--out", str(json_dir)],
    )
    assert result.exit_code == 0, result.output
    assert f"skipped: {_PRELUDE_FILE}" in result.output
    assert "Wrote 1 files" in result.output
    assert (json_dir / "ISA-200.json").exists()
    assert not (json_dir / "00_전문.json").exists()


def test_ingest_single_file_writes_one_json(tmp_path: Path) -> None:
    src = _EXISTING_MD_DIR / "ISA-200.md"
    if not src.exists():
        pytest.skip(f"fixture MD 미존재: {src}")
    json_dir = tmp_path / "json"
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["ingest", "--single", str(src), "--out", str(json_dir)],
    )
    assert result.exit_code == 0, result.output
    assert (json_dir / "ISA-200.json").exists()
    assert "Wrote 1 file" in result.output
    assert "ISA-200.json" in result.output


def test_ingest_single_prelude_md_is_skipped(tmp_path: Path) -> None:
    src = _EXISTING_MD_DIR / _PRELUDE_FILE
    if not src.exists():
        pytest.skip(f"fixture prelude 미존재: {src}")
    json_dir = tmp_path / "json"
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["ingest", "--single", str(src), "--out", str(json_dir)],
    )
    assert result.exit_code == 0, result.output
    assert "skipped (prelude)" in result.output
    assert list(json_dir.iterdir()) == []  # 파일 미생성


def test_ingest_file_without_single_flag_raises_bad_parameter(tmp_path: Path) -> None:
    src = _EXISTING_MD_DIR / "ISA-200.md"
    if not src.exists():
        pytest.skip(f"fixture MD 미존재: {src}")
    json_dir = tmp_path / "json"
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["ingest", str(src), "--out", str(json_dir)],
    )
    assert result.exit_code != 0
    # typer.BadParameter → Usage error 출력
    assert "expected directory" in result.output or "Usage" in result.output


# ---------------------------------------------------------------------------
# ingest — JSON 내용 검증 (1 case)
# ---------------------------------------------------------------------------


def test_ingest_dir_produces_valid_json_with_v1_1_schema(tmp_path: Path) -> None:
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, ("ISA-200.md",))
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["ingest", str(md_dir), "--out", str(json_dir)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads((json_dir / "ISA-200.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.1.1"
    assert data["standard"]["standard_no"] == "200"
    assert data["standard"]["standard_id"] == "ISA-200"
    assert isinstance(data["chunks"], list)
    assert len(data["chunks"]) > 0
    # paragraph_links 는 리스트 (비어도 존재해야 함 — schema required)
    assert isinstance(data["paragraph_links"], list)
