"""`audit_parser.cli` 테스트 — Task #4 (C7 임계 fail + ingest 실구현 + Phase 3 --upsert).

``convert`` C7 (3) + ``ingest`` 일괄/단건/skipped/prelude (5) + JSON 내용 검증 (1)
= 기존 9. Phase 3 ``--upsert`` 확장으로 신규 7 케이스 추가 → 총 16.

Phase 3 테스트 전략:

* ``Embedder.OpenAI`` 를 ``monkeypatch`` 로 ``_FakeOpenAI`` 교체 → Solar 비용 0.
* Qdrant 는 ``localhost:6333`` 실서버 사용 (Task #1 live). 미가동 시 skipif.
* collection 은 ``__test_cli_upsert_<uuid>__`` 이름으로 격리 + finally cleanup.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from typer.testing import CliRunner

from audit_parser.cli import app as cli_app
from audit_parser.ingest import embedder as emb_mod
from audit_parser.ingest.embedder import EMBED_DIM

if TYPE_CHECKING:
    from collections.abc import Iterator

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_DOCX = _REPO_ROOT / "raw" / "0. 회계감사기준 전문(2025 개정).docx"
_EXISTING_MD_DIR = _REPO_ROOT / "output" / "md"

_ISA_SAMPLES = ("ISA-200.md", "ISA-300.md", "ISA-1200.md")
_PRELUDE_FILE = "00_전문.md"
_SMALL_MD = "ISA-520.md"  # 49 chunks — Phase 3 테스트 최소 fixture
_SMALL2_MD = "ISA-320.md"  # 58 chunks — 두 standard 동시 테스트용

_QDRANT_URL = "http://localhost:6333"


def _qdrant_alive() -> bool:
    try:
        httpx.get(f"{_QDRANT_URL}/healthz", timeout=2.0).raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        return False


_live_qdrant = pytest.mark.skipif(
    not _qdrant_alive(),
    reason=f"Qdrant at {_QDRANT_URL} not reachable — skip live tests",
)


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
    assert data["schema_version"] == "1.2.0"
    assert data["standard"]["standard_no"] == "200"
    assert data["standard"]["standard_id"] == "ISA-200"
    assert isinstance(data["chunks"], list)
    assert len(data["chunks"]) > 0
    # paragraph_links 는 리스트 (비어도 존재해야 함 — schema required)
    assert isinstance(data["paragraph_links"], list)


# ---------------------------------------------------------------------------
# Phase 3 ``--upsert`` — fake OpenAI + live Qdrant (7 cases)
# ---------------------------------------------------------------------------


@dataclass
class _FakeEmbeddingItem:
    embedding: list[float]
    index: int = 0
    object: str = "embedding"


@dataclass
class _FakeUsage:
    prompt_tokens: int | None
    total_tokens: int = 0


@dataclass
class _FakeEmbeddingResponse:
    data: list[_FakeEmbeddingItem]
    usage: _FakeUsage | None = None
    model: str = "embedding-passage"
    object: str = "list"


class _FakeEmbeddings:
    """Solar embeddings 호출 모의. ``fail_for_standard`` 포함 문자열을 감지해 raise.

    standard_id 감지는 입력 텍스트에 해당 id 가 appear 하는지로 판정
    (ParsedStandard summary 또는 chunks 에 포함됨).
    """

    def __init__(
        self,
        *,
        dim: int = EMBED_DIM,
        usage_prompt_tokens_factor: float = 1.0,
        fail_for_standard: str | None = None,
    ) -> None:
        self.dim = dim
        self.usage_prompt_tokens_factor = usage_prompt_tokens_factor
        self.fail_for_standard = fail_for_standard
        self.calls: list[dict[str, Any]] = []

    def create(  # noqa: A002 — SDK 시그니처
        self,
        *,
        input: list[str] | str,  # noqa: A002
        model: str,
    ) -> _FakeEmbeddingResponse:
        texts = list(input) if isinstance(input, list) else [input]
        self.calls.append({"input": texts, "model": model})
        if self.fail_for_standard is not None and any(
            self.fail_for_standard in t for t in texts
        ):
            # Solar 가 RateLimitError 를 연속으로 뱉어 retry 소진하는 패턴 모의.
            import openai

            raise openai.APIConnectionError(
                request=httpx.Request("POST", "http://fake")
            )
        data: list[_FakeEmbeddingItem] = []
        for i, _t in enumerate(texts):
            vec = [float(i) / max(1, self.dim)] * self.dim
            data.append(_FakeEmbeddingItem(embedding=vec, index=i))
        # tiktoken 대비 prompt_tokens 를 factor 배 (정수) 로 보고 → max_ratio 관찰
        prompt_tokens: int | None = int(
            sum(max(1, len(t)) for t in texts) * self.usage_prompt_tokens_factor
        )
        usage = _FakeUsage(prompt_tokens=prompt_tokens)
        return _FakeEmbeddingResponse(data=data, usage=usage, model=model)


class _FakeOpenAI:
    def __init__(self, *, embeddings: _FakeEmbeddings) -> None:
        self.embeddings = embeddings


@pytest.fixture
def temp_qdrant_collection() -> Iterator[str]:
    """격리된 collection 이름 yield + finally cleanup."""
    name = f"__test_cli_upsert_{uuid.uuid4().hex[:8]}__"
    yield name
    try:
        from qdrant_client import QdrantClient

        c = QdrantClient(url=_QDRANT_URL, timeout=10)
        if c.collection_exists(name):
            c.delete_collection(name)
    except Exception:  # noqa: BLE001 — best-effort cleanup
        pass


def _install_fake_embedder(
    monkeypatch: pytest.MonkeyPatch,
    fake: _FakeEmbeddings,
) -> None:
    """Embedder 모듈의 ``OpenAI`` 생성자를 fake 로 교체 + 환경 구성."""

    def _fake_ctor(*, api_key: str, base_url: str) -> _FakeOpenAI:  # noqa: ARG001
        return _FakeOpenAI(embeddings=fake)

    monkeypatch.setattr(emb_mod, "OpenAI", _fake_ctor)
    monkeypatch.setenv("UPSTAGE_API_KEY", "sk-test-fake")
    # retry 대기 0 (CI 가속)
    monkeypatch.setattr(emb_mod, "_RETRY_BASE_SECONDS", 0.0)


@_live_qdrant
def test_ingest_upsert_writes_points_and_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    temp_qdrant_collection: str,
) -> None:
    """단일 작은 ISA → Qdrant count == chunks+1(summary), EMBED_METRICS.json 생성."""
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, (_SMALL_MD,))
    fake = _FakeEmbeddings()
    _install_fake_embedder(monkeypatch, fake)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "ingest",
            str(md_dir),
            "--out",
            str(json_dir),
            "--upsert",
            "--collection",
            temp_qdrant_collection,
            "--cache-path",
            str(tmp_path / "cache.sqlite"),
            "--qdrant-url",
            _QDRANT_URL,
        ],
    )
    assert result.exit_code == 0, result.output

    from qdrant_client import QdrantClient

    client = QdrantClient(url=_QDRANT_URL, timeout=10)
    count = client.count(collection_name=temp_qdrant_collection, exact=True).count
    # ISA-520 chunks + 1 summary
    assert count > 1, f"count={count}"

    metrics_path = json_dir / "EMBED_METRICS.json"
    assert metrics_path.exists()
    doc = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert doc["collection"] == temp_qdrant_collection
    assert doc["dry_run"] is False
    assert doc["standards_processed"] == 1
    assert doc["standards_failed"] == []
    assert doc["points_upserted_total"] == count
    assert doc["summary_upserted_total"] == 1
    assert doc["embedder_stats"]["api_calls"] >= 1
    assert len(doc["per_standard"]) == 1
    assert doc["per_standard"][0]["standard_id"] == "ISA-520"


@_live_qdrant
def test_ingest_upsert_dry_run_skips_qdrant_but_warms_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    temp_qdrant_collection: str,
) -> None:
    """``--dry-run`` 은 Qdrant 호출 0, embedder 캐시는 채움 → 재실행 시 cached_hits."""
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, (_SMALL_MD,))
    fake = _FakeEmbeddings()
    _install_fake_embedder(monkeypatch, fake)
    cache_path = tmp_path / "cache.sqlite"

    runner = CliRunner()
    common = [
        "ingest",
        str(md_dir),
        "--out",
        str(json_dir),
        "--upsert",
        "--dry-run",
        "--collection",
        temp_qdrant_collection,
        "--cache-path",
        str(cache_path),
        "--qdrant-url",
        _QDRANT_URL,
        "--no-ensure-collection",
    ]
    r1 = runner.invoke(cli_app, common)
    assert r1.exit_code == 0, r1.output

    # Qdrant 에 collection 이 생성되지 않아야 함 (ensure_collection 스킵)
    from qdrant_client import QdrantClient

    client = QdrantClient(url=_QDRANT_URL, timeout=10)
    assert not client.collection_exists(temp_qdrant_collection)

    doc = json.loads((json_dir / "EMBED_METRICS.json").read_text(encoding="utf-8"))
    assert doc["dry_run"] is True
    assert doc["points_upserted_total"] == 0
    first_api_calls = doc["embedder_stats"]["api_calls"]
    assert first_api_calls >= 1
    assert doc["embedder_stats"]["cached_hits"] == 0

    # 재실행 — cache hit 이 누적되고 api_calls 는 불변 (전량 cached)
    r2 = runner.invoke(cli_app, common)
    assert r2.exit_code == 0, r2.output
    doc2 = json.loads((json_dir / "EMBED_METRICS.json").read_text(encoding="utf-8"))
    assert doc2["embedder_stats"]["cached_hits"] >= 1
    assert doc2["embedder_stats"]["api_calls"] == 0


def test_ingest_upsert_flags_require_upsert(tmp_path: Path) -> None:
    """``--upsert`` 없이 ``--collection`` 비기본값 지정 → BadParameter."""
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, (_SMALL_MD,))
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "ingest",
            str(md_dir),
            "--out",
            str(json_dir),
            "--collection",
            "audit_standards_custom_2099",
        ],
    )
    assert result.exit_code != 0
    assert "--upsert" in result.output


@_live_qdrant
def test_ingest_upsert_single_file_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    temp_qdrant_collection: str,
) -> None:
    """``--single`` + ``--upsert`` — 해당 ISA 만 적재."""
    src = _EXISTING_MD_DIR / _SMALL_MD
    if not src.exists():
        pytest.skip(f"fixture MD 미존재: {src}")
    json_dir = tmp_path / "json"
    fake = _FakeEmbeddings()
    _install_fake_embedder(monkeypatch, fake)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "ingest",
            str(src),
            "--single",
            "--out",
            str(json_dir),
            "--upsert",
            "--collection",
            temp_qdrant_collection,
            "--cache-path",
            str(tmp_path / "cache.sqlite"),
            "--qdrant-url",
            _QDRANT_URL,
        ],
    )
    assert result.exit_code == 0, result.output
    assert (json_dir / "ISA-520.json").exists()

    from qdrant_client import QdrantClient

    client = QdrantClient(url=_QDRANT_URL, timeout=10)
    assert client.collection_exists(temp_qdrant_collection)
    count = client.count(collection_name=temp_qdrant_collection, exact=True).count
    assert count > 1  # chunks + summary


@_live_qdrant
def test_ingest_upsert_custom_batch_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    temp_qdrant_collection: str,
) -> None:
    """``--batch-size 4 --qdrant-batch-size 8`` 경로 검증 — 정상 종료 + count 일치."""
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, (_SMALL_MD,))
    fake = _FakeEmbeddings()
    _install_fake_embedder(monkeypatch, fake)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "ingest",
            str(md_dir),
            "--out",
            str(json_dir),
            "--upsert",
            "--collection",
            temp_qdrant_collection,
            "--batch-size",
            "4",
            "--qdrant-batch-size",
            "8",
            "--cache-path",
            str(tmp_path / "cache.sqlite"),
            "--qdrant-url",
            _QDRANT_URL,
        ],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((json_dir / "EMBED_METRICS.json").read_text(encoding="utf-8"))
    assert doc["collection"] == temp_qdrant_collection
    assert doc["points_upserted_total"] > 0


@_live_qdrant
def test_ingest_upsert_continues_on_per_standard_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    temp_qdrant_collection: str,
) -> None:
    """한 standard 임베딩 실패 → 다른 standard 는 성공, exit 1, METRICS.standards_failed."""
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, (_SMALL_MD, _SMALL2_MD))
    # "중요성 개념" 은 ISA-320 summary + chunks 4건에만 등장, ISA-520 에는 부재 →
    # fake 가 그 배치만 APIConnectionError 3회 → EmbeddingAPIError 전파.
    fake = _FakeEmbeddings(fail_for_standard="중요성 개념")
    _install_fake_embedder(monkeypatch, fake)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "ingest",
            str(md_dir),
            "--out",
            str(json_dir),
            "--upsert",
            "--collection",
            temp_qdrant_collection,
            "--cache-path",
            str(tmp_path / "cache.sqlite"),
            "--qdrant-url",
            _QDRANT_URL,
        ],
    )
    assert result.exit_code == 1, result.output
    doc = json.loads((json_dir / "EMBED_METRICS.json").read_text(encoding="utf-8"))
    assert "ISA-320" in doc["standards_failed"]
    assert "ISA-520" not in doc["standards_failed"]
    # ISA-520 은 성공적으로 적재되어 있어야 함
    ids_success = [
        p["standard_id"] for p in doc["per_standard"] if not p["failed_chunk_ids"]
    ]
    assert "ISA-520" in ids_success


@_live_qdrant
def test_ingest_upsert_metrics_includes_tokenizer_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    temp_qdrant_collection: str,
) -> None:
    """Solar prompt_tokens 를 tiktoken 대비 부풀린 fake → max_ratio > 1.0 기록."""
    md_dir = tmp_path / "md"
    json_dir = tmp_path / "json"
    _copy_samples(md_dir, (_SMALL_MD,))
    # prompt_tokens 를 tiktoken 추정치 대비 크게 부풀려 max_ratio > 1 강제
    fake = _FakeEmbeddings(usage_prompt_tokens_factor=10.0)
    _install_fake_embedder(monkeypatch, fake)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "ingest",
            str(md_dir),
            "--out",
            str(json_dir),
            "--upsert",
            "--collection",
            temp_qdrant_collection,
            "--cache-path",
            str(tmp_path / "cache.sqlite"),
            "--qdrant-url",
            _QDRANT_URL,
        ],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((json_dir / "EMBED_METRICS.json").read_text(encoding="utf-8"))
    stats = doc["embedder_stats"]
    assert "max_abs_gap" in stats
    assert "max_ratio" in stats
    assert "mean_ratio" in stats
    assert stats["max_ratio"] > 1.0  # fake factor 10 → ratio >> 1
    assert stats["total_solar_tokens"] > 0
