"""`audit_parser.ingest.qdrant_writer` 테스트 (Phase 3 Task #3).

**전략**: localhost Qdrant (v1.17.1) 를 실제 호출 — 테스트마다
``__test_qw_<uuid>__`` 이름으로 격리된 collection 생성·삭제 (테스트 후
cleanup). ``Embedder`` 는 실 API 를 호출하지 않는 ``_FakeEmbedder`` 로 대체해
Solar 비용 0.

커버 범위 (≥12 cases):

1. ``ensure_collection`` — vectors_config 2 종 4096 cosine 확인
2. 재호출 idempotent
3. payload index 11 종 생성 확인 (payload_schema)
4. ``chunk_id_to_point_id`` 결정성 (동일 입력 → 동일 UUID, 이종 → 다른 UUID)
5. minimal ParsedStandard (2 chunks) upsert → count == 3 (chunks + summary)
6. Re-upsert 동일 입력 → points_upserted 동일, payload_drift=0
7. payload drift 감지 — content 변경 시 drift 카운트 증가
8. Summary point kind='standard_summary' 1 건 생성 확인
9. ``dry_run=True`` — Qdrant 호출 0 (count 변화 없음)
10. table_cells list[list[str]] 왕복 보존
11. F4 suffix chunk (paragraph_id=null + ``#{source_idx}``) 적재 성공
12. ``prune_stale=True`` — 기존 id 중 미포함 삭제
13. UUID namespace RFC 4122 표준 — 하드코드 값 회귀
14. summary fallback — scope/definitions 모두 null → standard_id-기반 텍스트
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import pytest
from qdrant_client import QdrantClient

from audit_parser.ingest.embedder import EMBED_DIM, EmbeddingResult
from audit_parser.ingest.qdrant_writer import (
    _QDRANT_POINT_NAMESPACE,
    COLLECTION_DEFAULT,
    KIND_STANDARD_SUMMARY,
    VECTOR_PASSAGE,
    VECTOR_SUMMARY,
    QdrantWriter,
    QdrantWriterConfig,
    chunk_id_to_point_id,
)
from audit_parser.ingest.types import (
    ChunkRecord,
    ParsedStandard,
    StandardRecord,
    StandardSummary,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

QDRANT_URL = "http://localhost:6333"


def _qdrant_alive() -> bool:
    try:
        httpx.get(f"{QDRANT_URL}/healthz", timeout=2.0).raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _qdrant_alive(),
    reason=f"Qdrant at {QDRANT_URL} not reachable — skip live tests",
)


# ---------------------------------------------------------------------------
# Fakes / fixtures
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Embedder 의 최소 모의. 실제 API 호출 0."""

    def __init__(self) -> None:
        self.passage_calls: list[str] = []

    def _vec(self, text: str) -> tuple[float, ...]:
        # deterministic — text hash 로 첫 원소만 다르게
        h = abs(hash(text)) % 10_000
        base = h / 10_000
        return (base,) + (0.0,) * (EMBED_DIM - 1)

    def _now(self) -> str:
        return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )

    def embed_passage(self, text: str) -> EmbeddingResult:
        self.passage_calls.append(text)
        return EmbeddingResult(
            vector=self._vec(text),
            role="passage",
            model="embedding-passage",
            tiktoken_tokens=10,
            solar_tokens=10,
            cached=False,
            embedded_at=self._now(),
        )

    def embed_passages(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self.embed_passage(t) for t in texts]


@pytest.fixture
def writer() -> Iterator[QdrantWriter]:
    client = QdrantClient(url=QDRANT_URL, timeout=30)
    w = QdrantWriter(QdrantWriterConfig(url=QDRANT_URL), client=client)
    yield w


@pytest.fixture
def temp_collection(writer: QdrantWriter) -> Iterator[str]:
    name = f"__test_qw_{uuid.uuid4().hex[:8]}__"
    try:
        yield name
    finally:
        try:
            writer.delete_collection(name)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass


def _make_chunk(
    *,
    chunk_id: str,
    paragraph_id: str | None,
    kind: str = "paragraph_body",
    section: str | None = "body",
    appendix_index: int | None = None,
    heading_trail: tuple[str, ...] = ("ISA-200", "서론"),
    heading_trail_hash: str = "abcd1234",
    content_text: str = "본 기준은 감사인의 책임을 다룬다.",
    content_markdown: str | None = None,
    authority: int = 1,
    parent_paragraph_id: str | None = None,
    is_application_guidance: bool = False,
    token_estimate: int = 10,
    chunk_index: int = 0,
    chunk_of: int = 1,
    source_idx: int = 0,
    part_of: str | None = None,
    table_cells: tuple[tuple[str, ...], ...] | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        paragraph_id=paragraph_id,
        kind=kind,
        section=section,
        appendix_index=appendix_index,
        heading_trail=heading_trail,
        heading_trail_hash=heading_trail_hash,
        content_text=content_text,
        content_markdown=content_markdown if content_markdown is not None else content_text,
        authority=authority,
        parent_paragraph_id=parent_paragraph_id,
        is_application_guidance=is_application_guidance,
        token_estimate=token_estimate,
        chunk_index=chunk_index,
        chunk_of=chunk_of,
        source_idx=source_idx,
        part_of=part_of,
        table_cells=table_cells,
    )


def _make_parsed(
    chunks: tuple[ChunkRecord, ...],
    *,
    standard_id: str = "ISA-200",
    standard_no: str = "200",
    scope_text: str | None = "본 기준서의 범위는 ...",
    definitions_text: str | None = "용어의 정의는 ...",
) -> ParsedStandard:
    std = StandardRecord(
        standard_id=standard_id,
        standard_no=standard_no,
        standard_title="독립감사인의 전반적인 목적",
        source_file="0. 회계감사기준 전문(2025 개정).docx",
        authority_base=1,
    )
    summary = StandardSummary(
        scope_text=scope_text,
        scope_markdown=scope_text,
        definitions_text=definitions_text,
        definitions_markdown=definitions_text,
    )
    return ParsedStandard(
        schema_version="1.1.2",
        standard=std,
        summary=summary,
        chunks=chunks,
        paragraph_links=(),
    )


# ---------------------------------------------------------------------------
# Tests — 구조 & 유틸
# ---------------------------------------------------------------------------


def test_chunk_id_to_point_id_deterministic() -> None:
    """동일 chunk_id → 동일 UUID, 이종 → 다른 UUID."""
    a = chunk_id_to_point_id("ISA-200:body:abcd1234:12")
    b = chunk_id_to_point_id("ISA-200:body:abcd1234:12")
    c = chunk_id_to_point_id("ISA-200:body:abcd1234:13")
    assert a == b
    assert a != c
    # uuid 포맷
    uuid.UUID(a)
    uuid.UUID(c)


def test_namespace_is_rfc4122_dns() -> None:
    """Critic F3: namespace 하드코드 회귀 — RFC 4122 DNS."""
    assert str(_QDRANT_POINT_NAMESPACE) == "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def test_ensure_collection_creates_vectors_config(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    info = writer.client.get_collection(temp_collection)
    vectors = info.config.params.vectors
    assert vectors is not None
    # qdrant-client 1.17 returns dict[str, VectorParams] when named vectors.
    assert isinstance(vectors, dict)
    assert {VECTOR_PASSAGE, VECTOR_SUMMARY} <= set(vectors.keys())
    p = vectors[VECTOR_PASSAGE]
    assert p.size == EMBED_DIM
    assert p.distance.value.lower() == "cosine"


def test_ensure_collection_idempotent(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    # 재호출 시 예외 없음
    writer.ensure_collection(temp_collection)
    assert writer.client.collection_exists(temp_collection)


def test_payload_indexes_created(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    info = writer.client.get_collection(temp_collection)
    schema = info.payload_schema
    expected_keywords = {
        "standard_id",
        "standard_no",
        "chunk_id",
        "paragraph_id",
        "kind",
        "section",
        "heading_trail_hash",
        "parent_paragraph_id",
        "part_of",
    }
    missing = expected_keywords - set(schema.keys())
    assert not missing, f"missing keyword indexes: {missing}"
    assert "appendix_index" in schema
    assert "is_application_guidance" in schema
    # 총 11 index
    assert len(expected_keywords | {"appendix_index", "is_application_guidance"}) == 11


# ---------------------------------------------------------------------------
# Tests — upsert
# ---------------------------------------------------------------------------


def test_upsert_minimal_parsed(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(chunk_id="ISA-200:body:abcd1234:1", paragraph_id="1.", source_idx=1),
        _make_chunk(chunk_id="ISA-200:body:abcd1234:2", paragraph_id="2.", source_idx=2),
    )
    parsed = _make_parsed(chunks)
    fake = _FakeEmbedder()
    result = writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    # 2 chunks + 1 summary
    assert result.points_upserted == 3
    assert result.summary_upserted is True
    assert writer.count(temp_collection) == 3


def test_upsert_reupsert_idempotent(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(chunk_id="ISA-200:body:abcd1234:1", paragraph_id="1.", source_idx=1),
    )
    parsed = _make_parsed(chunks)
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    r2 = writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    assert r2.points_upserted == 2
    assert r2.payload_drift_count == 0
    assert writer.count(temp_collection) == 2


def test_upsert_detects_payload_drift(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    c1 = _make_chunk(
        chunk_id="ISA-200:body:abcd1234:1",
        paragraph_id="1.",
        source_idx=1,
        content_text="원본 텍스트 A",
    )
    parsed1 = _make_parsed((c1,))
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed1, fake, collection=temp_collection)  # type: ignore[arg-type]

    # content 만 변경
    c2 = _make_chunk(
        chunk_id="ISA-200:body:abcd1234:1",
        paragraph_id="1.",
        source_idx=1,
        content_text="변경 텍스트 B",
    )
    parsed2 = _make_parsed((c2,))
    r = writer.upsert_parsed(parsed2, fake, collection=temp_collection)  # type: ignore[arg-type]
    assert r.payload_drift_count >= 1


def test_summary_point_is_separate(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(chunk_id="ISA-200:body:abcd1234:1", paragraph_id="1.", source_idx=1),
    )
    parsed = _make_parsed(chunks)
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    summary_pid = chunk_id_to_point_id("ISA-200:summary")
    records = writer.client.retrieve(
        collection_name=temp_collection,
        ids=[summary_pid],
        with_payload=True,
        with_vectors=True,
    )
    assert len(records) == 1
    payload = records[0].payload or {}
    assert payload["kind"] == KIND_STANDARD_SUMMARY
    assert payload["standard_id"] == "ISA-200"


def test_dry_run_does_not_write(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(chunk_id="ISA-200:body:abcd1234:1", paragraph_id="1.", source_idx=1),
    )
    parsed = _make_parsed(chunks)
    fake = _FakeEmbedder()
    r = writer.upsert_parsed(parsed, fake, collection=temp_collection, dry_run=True)  # type: ignore[arg-type]
    assert r.points_upserted == 0
    assert writer.count(temp_collection) == 0
    # 임베딩 자체는 실행 (cache warm-up)
    assert len(fake.passage_calls) >= 1


def test_table_cells_roundtrip(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    cells: tuple[tuple[str, ...], ...] = (("헤더1", "헤더2"), ("값1", "값2"))
    chunks = (
        _make_chunk(
            chunk_id="ISA-200:body:abcd1234:1",
            paragraph_id=None,
            kind="table",
            source_idx=1,
            table_cells=cells,
        ),
    )
    parsed = _make_parsed(chunks)
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    pid = chunk_id_to_point_id("ISA-200:body:abcd1234:1")
    recs = writer.client.retrieve(
        collection_name=temp_collection, ids=[pid], with_payload=True
    )
    payload = recs[0].payload or {}
    assert payload["table_cells"] == [["헤더1", "헤더2"], ["값1", "값2"]]


def test_f4_suffix_chunk_ingests(
    writer: QdrantWriter, temp_collection: str
) -> None:
    """paragraph_id=null + `#{source_idx}` suffix chunk 적재."""
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(
            chunk_id="ISA-720:appendix:3d4ed148:paragraph_body#142",
            paragraph_id=None,
            kind="paragraph_body",
            section="appendix",
            appendix_index=2,
            source_idx=142,
        ),
    )
    parsed = _make_parsed(chunks, standard_id="ISA-720", standard_no="720")
    fake = _FakeEmbedder()
    r = writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    assert r.points_upserted == 2  # chunk + summary
    pid = chunk_id_to_point_id("ISA-720:appendix:3d4ed148:paragraph_body#142")
    recs = writer.client.retrieve(
        collection_name=temp_collection, ids=[pid], with_payload=True
    )
    assert len(recs) == 1
    assert recs[0].payload is not None
    assert recs[0].payload["paragraph_id"] is None
    assert recs[0].payload["appendix_index"] == 2


def test_prune_stale_removes_missing(
    writer: QdrantWriter, temp_collection: str
) -> None:
    writer.ensure_collection(temp_collection)
    c1 = _make_chunk(chunk_id="ISA-200:body:abcd1234:1", paragraph_id="1.", source_idx=1)
    c2 = _make_chunk(chunk_id="ISA-200:body:abcd1234:2", paragraph_id="2.", source_idx=2)
    parsed = _make_parsed((c1, c2))
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    assert writer.count(temp_collection) == 3  # 2 chunks + 1 summary

    # c2 제거 후 prune_stale=True
    parsed2 = _make_parsed((c1,))
    r = writer.upsert_parsed(
        parsed2,
        fake,  # type: ignore[arg-type]
        collection=temp_collection,
        prune_stale=True,
    )
    assert r.stale_suffix_deleted == 1
    assert writer.count(temp_collection) == 2  # c1 + summary


def test_summary_text_fallback_when_null(
    writer: QdrantWriter, temp_collection: str
) -> None:
    """scope/definitions 모두 null → fallback 사용."""
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(chunk_id="ISA-999:body:abcd1234:1", paragraph_id="1.", source_idx=1),
    )
    parsed = _make_parsed(
        chunks,
        standard_id="ISA-999",
        standard_no="999",
        scope_text=None,
        definitions_text=None,
    )
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]
    # fallback text 가 passage_calls 에 포함되어야 함
    assert any("ISA-999" in t for t in fake.passage_calls)


def test_per_point_named_vectors(
    writer: QdrantWriter, temp_collection: str
) -> None:
    """v1.1.2 F1 rework — chunk 는 passage 슬롯만, summary 는 summary 슬롯만.

    Qdrant named vectors 는 per-point optional — 각 point 는 collection 이 선언한
    두 슬롯 중 실제로 벡터를 심은 슬롯만 인덱스되고, 미기재 슬롯은 해당 point 에서
    인덱스되지 않는다. 0-벡터 패딩 제거로 ``indexed_vectors_count == points_count``.
    """
    writer.ensure_collection(temp_collection)
    chunks = (
        _make_chunk(chunk_id="ISA-200:body:abcd1234:1", paragraph_id="1.", source_idx=1),
    )
    parsed = _make_parsed(chunks)
    fake = _FakeEmbedder()
    writer.upsert_parsed(parsed, fake, collection=temp_collection)  # type: ignore[arg-type]

    # chunk point — passage 슬롯만 존재해야 한다.
    chunk_pid = chunk_id_to_point_id("ISA-200:body:abcd1234:1")
    chunk_recs = writer.client.retrieve(
        collection_name=temp_collection,
        ids=[chunk_pid],
        with_payload=False,
        with_vectors=True,
    )
    assert chunk_recs[0].vector is not None
    chunk_vec = chunk_recs[0].vector
    assert isinstance(chunk_vec, dict)
    assert set(chunk_vec.keys()) == {VECTOR_PASSAGE}, (
        f"chunk point must expose only passage slot — got {list(chunk_vec.keys())}"
    )
    passage_vec = chunk_vec[VECTOR_PASSAGE]
    assert isinstance(passage_vec, list)
    assert len(passage_vec) == EMBED_DIM

    # summary point — summary 슬롯만 존재해야 한다.
    summary_pid = chunk_id_to_point_id("ISA-200:summary")
    summary_recs = writer.client.retrieve(
        collection_name=temp_collection,
        ids=[summary_pid],
        with_payload=False,
        with_vectors=True,
    )
    assert summary_recs[0].vector is not None
    summary_vec = summary_recs[0].vector
    assert isinstance(summary_vec, dict)
    assert set(summary_vec.keys()) == {VECTOR_SUMMARY}, (
        f"summary point must expose only summary slot — got {list(summary_vec.keys())}"
    )
    summary_vec_values = summary_vec[VECTOR_SUMMARY]
    assert isinstance(summary_vec_values, list)
    assert len(summary_vec_values) == EMBED_DIM


def test_collection_default_name() -> None:
    """CLAUDE.md §5 — 기본 collection 이름 회귀."""
    assert COLLECTION_DEFAULT == "audit_standards_회계감사기준_2025"
