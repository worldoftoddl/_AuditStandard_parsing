"""Qdrant 업서트 (Phase 3 Stage 2b).

`docs/json_schema.md §13` payload 매핑 + §8.4 idempotency + Critic F1/F3
반영.

### 주요 설계 결정

**F1 — per-point optional named vectors (v1.1.2 rework, 2026-04-22)**
Phase 2 chunk point 의 named vector ``summary`` 에 동일 값을 복제하면
8,590 × 4096 × 4B ≈ 140MB 중복 저장이 발생. 대신 기준서당 1 건
``kind='standard_summary'`` point 를 추가 (36 points) 해 summary 검색은
해당 36 points 만 대상으로 필터링한다. Qdrant 는 named-vectors 를
**per-point optional** 로 허용하므로 chunk point 는 ``{"passage": vec}`` 만,
summary point 는 ``{"summary": vec}`` 만 심어 0-벡터 패딩을 제거 — 결과적으로
``indexed_vectors_count == points_count`` (기존 2× 대비 절반 절감).

**F3 — 결정론 UUID 네임스페이스**
``_QDRANT_POINT_NAMESPACE`` 는 RFC 4122 표준 DNS 네임스페이스 UUID
(``6ba7b810-9dad-11d1-80b4-00c04fd430c8``) 고정. ``chunk_id_to_point_id`` 는
``uuid5(namespace, chunk_id)`` — re-ingest 시 안정.

**F4/F5 — SQLite 캐시 & summary 주입**
``embedder.Embedder`` 의 캐시를 공유 — summary text 가 fallback 포함 동일하면
재호출 0.

### 공개 API

- :class:`QdrantWriter` — 단일 서비스 클래스
- :class:`QdrantWriterConfig` — 접속 설정
- :class:`UpsertResult` — 업서트 결과 요약
- :data:`COLLECTION_DEFAULT` — 기본 collection 이름 (CLAUDE.md §5)
- :func:`chunk_id_to_point_id` — 유틸 (tests/CLI 공유)
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from audit_parser.ingest.embedder import EMBED_DIM, HARD_LIMIT_TOKENS, EmbeddingResult
from audit_parser.ingest.types import (
    ChunkRecord,
    ParsedStandard,
    StandardRecord,
    StandardSummary,
)

if TYPE_CHECKING:
    from audit_parser.ingest.embedder import Embedder


logger = logging.getLogger(__name__)

# Qdrant point id union — ``PointStruct.id`` 필드 실타입.
_PointId = int | str | uuid.UUID


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

COLLECTION_DEFAULT: Final = "audit_standards_회계감사기준_2025"
VECTOR_PASSAGE: Final = "passage"
VECTOR_SUMMARY: Final = "summary"
HNSW_M: Final = 16
HNSW_EF_CONSTRUCT: Final = 200

# RFC 4122 표준 DNS namespace. Critic F3 — 명시 상수로 stabilize.
_QDRANT_POINT_NAMESPACE: Final = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

KIND_STANDARD_SUMMARY: Final = "standard_summary"

# §13 / checkpoint_3_prep.md §6.2 — 11 개 indexed 필드
_KEYWORD_INDEXES: Final[tuple[str, ...]] = (
    "standard_id",
    "standard_no",
    "chunk_id",
    "paragraph_id",
    "kind",
    "section",
    "heading_trail_hash",
    "parent_paragraph_id",
    "part_of",
)
_INTEGER_INDEXES: Final[tuple[str, ...]] = ("appendix_index",)
_BOOL_INDEXES: Final[tuple[str, ...]] = ("is_application_guidance",)

_DEFAULT_UPSERT_BATCH: Final = 64


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------


class QdrantWriterError(Exception):
    """qdrant_writer 계열 기본 예외."""


def _assert_isa_baseline_vector(
    collection: str, slot: str, vparams: VectorParams
) -> None:
    """Single named-vector slot baseline check (Phase 4b-1 stub)."""
    if int(vparams.size) != EMBED_DIM:
        raise SchemaDriftError(
            f"{collection}.{slot}: vector size {vparams.size} != baseline {EMBED_DIM}"
        )
    if vparams.distance != Distance.COSINE:
        raise SchemaDriftError(
            f"{collection}.{slot}: distance {vparams.distance} != Distance.COSINE"
        )
    # HNSW config per-vector. None = inherit collection default — Phase 4b-1
    # stub 는 named 값만 검증.
    if vparams.hnsw_config is None:
        return
    if vparams.hnsw_config.m != HNSW_M:
        raise SchemaDriftError(
            f"{collection}.{slot}: HNSW m={vparams.hnsw_config.m} != {HNSW_M}"
        )
    if vparams.hnsw_config.ef_construct != HNSW_EF_CONSTRUCT:
        raise SchemaDriftError(
            f"{collection}.{slot}: HNSW ef_construct="
            f"{vparams.hnsw_config.ef_construct} != {HNSW_EF_CONSTRUCT}"
        )


class IngestIncompleteError(QdrantWriterError):
    """Critic y (2026-04-22) — post-upsert count < expected 불일치.

    Phase 4e 에서 3 collection 각각 `expected_points (source-of-truth JSON) vs
    actual_points (Qdrant client.count)` 대조 시 발동. Phase 4b-1 에서는 signature
    reservation + stub 만 — 실 count 비교 로직은 Phase 4e 본 구현.
    """


class SchemaDriftError(QdrantWriterError):
    """Critic z (2026-04-22) — collection 의 HNSW / vector dim / distance /
    payload index 가 spec 기대값과 불일치.

    Phase 4b-1 stub 은 ISA baseline (named vectors passage+summary / 4096d /
    cosine / HNSW m=16 ef=200) 하드코딩 검증. Phase 4b-2 에서 spec.qdrant_config()
    주입형으로 일반화. mismatch 발견 시 caller 에 ``--force`` 옵션으로 재생성 안내.
    """


class QdrantWriteError(QdrantWriterError):
    """Batch 업서트 재시도 소진 실패."""

    def __init__(
        self, collection: str, failed_chunk_ids: Sequence[str], cause: BaseException | None = None
    ) -> None:
        super().__init__(
            f"upsert failed — collection={collection!r} "
            f"failed={len(failed_chunk_ids)} cause={cause!r}"
        )
        self.collection = collection
        self.failed_chunk_ids = tuple(failed_chunk_ids)
        self.cause = cause


# ---------------------------------------------------------------------------
# 데이터클래스
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class QdrantWriterConfig:
    """Qdrant 클라이언트 접속 설정. 기본값은 CLAUDE.md §2 docker-compose."""

    url: str = "http://localhost:6333"
    api_key: str | None = None
    prefer_grpc: bool = False
    timeout: int = 30


@dataclass(slots=True)
class UpsertResult:
    """단일 ``upsert_parsed`` 호출 결과."""

    collection: str
    points_upserted: int = 0
    payload_drift_count: int = 0
    stale_suffix_deleted: int = 0
    summary_upserted: bool = False
    elapsed_seconds: float = 0.0
    failed_chunk_ids: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------


def chunk_id_to_point_id(chunk_id: str) -> str:
    """``chunk_id`` → 결정론 UUID5 (RFC 4122)."""
    return str(uuid.uuid5(_QDRANT_POINT_NAMESPACE, chunk_id))


def _standard_summary_chunk_id(standard_id: str) -> str:
    """standard_summary point 의 안정 식별자 — ``{standard_id}:summary``."""
    return f"{standard_id}:summary"


def _content_text_hash(text: str) -> str:
    """C-P2-1 fallback 준비용 sha1(content_text) 전장."""
    return hashlib.sha1(text.encode()).hexdigest()


def _compose_summary_text(std: StandardRecord, summary: StandardSummary) -> str:
    """``scope + definitions`` 공백 연결. 둘 다 null 이면 ``standard_id — title``."""
    parts: list[str] = []
    if summary.scope_text:
        parts.append(summary.scope_text)
    if summary.definitions_text:
        parts.append(summary.definitions_text)
    if parts:
        return "\n\n".join(parts)
    title = std.standard_title or ""
    return f"{std.standard_id} — {title}".rstrip(" —")


# Summary embedding safety margin: HARD_LIMIT_TOKENS(4000) - 50 = 3950 tokens.
# ISA-200/ISA-1200 summary (scope + 대량 definitions) 가 HARD_LIMIT 를 초과해
# EmbeddingOverflowError 발생 — 임베딩용으로만 절삭, payload 는 full 유지.
_SUMMARY_EMBED_TOKEN_LIMIT: Final = HARD_LIMIT_TOKENS - 50


def _truncate_for_summary_embedding(text: str) -> str:
    """tiktoken cl100k_base 기준 ``_SUMMARY_EMBED_TOKEN_LIMIT`` 토큰으로 절삭.

    payload 에는 full text 유지, 임베딩 벡터만 절삭된 text 를 사용. Solar
    tokenizer 는 한국어에서 tiktoken 대비 ~0.5× 이므로 3950 tiktoken 는
    Solar 기준 훨씬 여유 있음.
    """
    import tiktoken  # lazy import — md_parser 와 인코딩 공유 않고 독립 경로.

    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    if len(tokens) <= _SUMMARY_EMBED_TOKEN_LIMIT:
        return text
    truncated = encoding.decode(tokens[:_SUMMARY_EMBED_TOKEN_LIMIT])
    logger.warning(
        "summary text truncated for embedding: %d → %d tokens",
        len(tokens),
        _SUMMARY_EMBED_TOKEN_LIMIT,
    )
    return truncated


def _chunk_payload(std: StandardRecord, chunk: ChunkRecord) -> dict[str, object]:
    """§13 24 필드 + ``content_text_hash``. return 은 ``dict[str, object]`` —
    Qdrant 공식 ``Dict[str, Any]`` 와 호환 (object → Any 암묵 narrowing)."""
    """§13 24 필드 + ``content_text_hash`` (C-P2-1 준비)."""
    return {
        # 기준서 메타
        "standard_id": std.standard_id,
        "standard_no": std.standard_no,
        "source_file": std.source_file,
        "authority_base": std.authority_base,
        # chunk 메타
        "chunk_id": chunk.chunk_id,
        "paragraph_id": chunk.paragraph_id,
        "kind": chunk.kind,
        "section": chunk.section,
        "appendix_index": chunk.appendix_index,
        "heading_trail": list(chunk.heading_trail),
        "heading_trail_hash": chunk.heading_trail_hash,
        "parent_paragraph_id": chunk.parent_paragraph_id,
        "is_application_guidance": chunk.is_application_guidance,
        "authority": chunk.authority,
        "token_estimate": chunk.token_estimate,
        "chunk_index": chunk.chunk_index,
        "chunk_of": chunk.chunk_of,
        "source_idx": chunk.source_idx,
        "part_of": chunk.part_of,
        # 원본
        "content_text": chunk.content_text,
        "content_markdown": chunk.content_markdown,
        "table_cells": (
            [list(row) for row in chunk.table_cells] if chunk.table_cells is not None else None
        ),
        # 재임베딩 캐시
        "embedded_at": chunk.embedded_at,
        "embedding_model": chunk.embedding_model,
        # C-P2-1 fallback 준비 (payload open schema — json_schema 비침입)
        "content_text_hash": _content_text_hash(chunk.content_text),
    }


def _summary_payload(
    std: StandardRecord, summary: StandardSummary, embed_model: str, embedded_at: str
) -> dict[str, object]:
    """standard_summary point 의 payload. chunk 와 열거 가능한 공통 필드 유지."""
    composed = _compose_summary_text(std, summary)
    return {
        # 기준서 메타 동일
        "standard_id": std.standard_id,
        "standard_no": std.standard_no,
        "source_file": std.source_file,
        "authority_base": std.authority_base,
        # chunk-ish fallback
        "chunk_id": _standard_summary_chunk_id(std.standard_id),
        "paragraph_id": None,
        "kind": KIND_STANDARD_SUMMARY,
        "section": None,
        "appendix_index": None,
        "heading_trail": [],
        "heading_trail_hash": hashlib.sha1(f"summary:{std.standard_id}".encode()).hexdigest()[:8],
        "parent_paragraph_id": None,
        "is_application_guidance": False,
        "authority": std.authority_base,
        "token_estimate": 0,
        "chunk_index": 0,
        "chunk_of": 1,
        "source_idx": -1,
        "part_of": None,
        "content_text": composed,
        "content_markdown": composed,
        "table_cells": None,
        "embedded_at": embedded_at,
        "embedding_model": embed_model,
        "content_text_hash": _content_text_hash(composed),
    }


# ---------------------------------------------------------------------------
# QdrantWriter
# ---------------------------------------------------------------------------


class QdrantWriter:
    """Qdrant collection 생성 + named-vector 업서트 서비스.

    Args:
        config: 접속 설정. None 이면 기본 ``QdrantWriterConfig``.
        client: 사전 구축된 ``QdrantClient`` 주입 (테스트용). None 이면 자동 생성.
    """

    __slots__ = ("_client", "_config")

    def __init__(
        self,
        config: QdrantWriterConfig | None = None,
        *,
        client: QdrantClient | None = None,
    ) -> None:
        self._config: QdrantWriterConfig = config or QdrantWriterConfig()
        if client is not None:
            self._client = client
        else:
            self._client = QdrantClient(
                url=self._config.url,
                api_key=self._config.api_key,
                prefer_grpc=self._config.prefer_grpc,
                timeout=self._config.timeout,
            )

    @property
    def client(self) -> QdrantClient:
        """내부 client 노출 (tests / admin 용)."""
        return self._client

    # -- collection management ----------------------------------------------

    def ensure_collection(self, name: str = COLLECTION_DEFAULT) -> None:
        """Collection 생성 + payload index 11 종. 존재 시 idempotent."""
        vectors = {
            VECTOR_PASSAGE: VectorParams(
                size=EMBED_DIM,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCT),
            ),
            VECTOR_SUMMARY: VectorParams(
                size=EMBED_DIM,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCT),
            ),
        }
        if not self._client.collection_exists(name):
            self._client.create_collection(collection_name=name, vectors_config=vectors)
        self._ensure_indexes(name)

    def delete_collection(self, name: str) -> None:
        """테스트 및 full rebuild (Task #5) 용."""
        if self._client.collection_exists(name):
            self._client.delete_collection(name)

    def count(self, name: str = COLLECTION_DEFAULT) -> int:
        result = self._client.count(collection_name=name, exact=True)
        return int(result.count)

    def verify_collection_baseline(
        self,
        name: str = COLLECTION_DEFAULT,
        *,
        expected_points: int | None = None,
    ) -> dict[str, object]:
        """Phase 4b-1 stub (Critic y/z 합의) — ISA baseline invariant 검증.

        Checks (raises on mismatch):

        * Collection 존재 (``collection_exists``).
        * Named vectors ``{passage, summary}`` 모두 present, each 4096d
          cosine (``EMBED_DIM`` / ``Distance.COSINE``).
        * HNSW ``m == HNSW_M (16)``, ``ef_construct == HNSW_EF_CONSTRUCT (200)``
          (named vector scope — collection-level HNSW 가 named vector 별로
          지정됨).
        * ``expected_points`` 지정 시 ``actual == expected`` (Phase 4e invariant
          assertion pattern 의 stub 버전).

        Phase 4b-2 가 본 메서드를 spec-driven 으로 일반화 (``spec.qdrant_config()``
        주입) — 현 stub 은 ISA baseline (``HNSW_M/EF_CONSTRUCT/EMBED_DIM``) 모듈
        상수 고정. Phase 4e 에서 ``ingest_collection_with_verification`` 에 편입.

        Args:
            name: Qdrant collection 이름.
            expected_points: Optional — pre-count from ``output/json/*.json``.
                None 이면 count 검증 skip (schema 만 확인).

        Returns:
            dict with keys ``{"points_count", "passage_config", "summary_config"}`` —
            caller 가 검증 결과 기록 용 (EMBED_METRICS.json 확장).

        Raises:
            SchemaDriftError: collection 없음 / named vector 누락 / dim /
                distance / HNSW 불일치.
            IngestIncompleteError: ``expected_points`` 와 actual 불일치.
        """
        if not self._client.collection_exists(name):
            raise SchemaDriftError(f"collection {name!r} does not exist")

        info = self._client.get_collection(name)
        vectors_config = info.config.params.vectors
        # vectors_config 은 dict[name, VectorParams] — named vectors.
        if not isinstance(vectors_config, dict):
            raise SchemaDriftError(
                f"{name}: expected named vectors dict, got {type(vectors_config).__name__}"
            )
        if set(vectors_config) != {VECTOR_PASSAGE, VECTOR_SUMMARY}:
            raise SchemaDriftError(
                f"{name}: named vectors mismatch — expected "
                f"{{'{VECTOR_PASSAGE}', '{VECTOR_SUMMARY}'}}, got {sorted(vectors_config)}"
            )

        for slot in (VECTOR_PASSAGE, VECTOR_SUMMARY):
            _assert_isa_baseline_vector(name, slot, vectors_config[slot])

        actual_points = self.count(name)
        if expected_points is not None and actual_points != expected_points:
            raise IngestIncompleteError(
                f"{name}: expected {expected_points} points, got {actual_points}"
            )

        return {
            "points_count": actual_points,
            "passage_config": {
                "size": int(vectors_config[VECTOR_PASSAGE].size),
                "distance": str(vectors_config[VECTOR_PASSAGE].distance),
            },
            "summary_config": {
                "size": int(vectors_config[VECTOR_SUMMARY].size),
                "distance": str(vectors_config[VECTOR_SUMMARY].distance),
            },
        }

    def _ensure_indexes(self, name: str) -> None:
        for field_name in _KEYWORD_INDEXES:
            self._create_index_safe(name, field_name, PayloadSchemaType.KEYWORD)
        for field_name in _INTEGER_INDEXES:
            self._create_index_safe(name, field_name, PayloadSchemaType.INTEGER)
        for field_name in _BOOL_INDEXES:
            self._create_index_safe(name, field_name, PayloadSchemaType.BOOL)

    def _create_index_safe(
        self, collection: str, field_name: str, schema: PayloadSchemaType
    ) -> None:
        try:
            self._client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=schema,
                wait=True,
            )
        except (UnexpectedResponse, ValueError) as exc:  # pragma: no cover — rare
            # 이미 존재하는 index 는 재생성 시 409/400 가능. 로그만 남김.
            logger.debug("payload index %s already present: %s", field_name, exc)

    # -- upsert -------------------------------------------------------------

    def upsert_parsed(
        self,
        parsed: ParsedStandard,
        embedder: Embedder,
        *,
        collection: str = COLLECTION_DEFAULT,
        batch_size: int = _DEFAULT_UPSERT_BATCH,
        dry_run: bool = False,
        prune_stale: bool = False,
    ) -> UpsertResult:
        """``ParsedStandard`` 1 건을 Qdrant 에 적재.

        1. 모든 chunk 텍스트를 passage 임베딩 (embedder 배치 활용).
        2. summary text 임베딩 (passage 모델 공유) — kind=standard_summary point 1 건.
        3. chunk point N 건 + summary point 1 건을 batch upsert.
        4. ``prune_stale=True`` 인 경우 같은 ``standard_id`` 하의 기존 points 중
           이번 upsert 에 없는 point_id 를 삭제.

        Args:
            parsed: md_parser 산출 ParsedStandard.
            embedder: passage 임베딩 + summary 임베딩 실행자.
            collection: 대상 collection 이름.
            batch_size: Qdrant upsert batch 크기 (실패 재시도 단위).
            dry_run: True 면 Qdrant 호출 0 (임베딩은 실행 — 캐시 warm-up).
            prune_stale: True 면 stale point 제거.
        """
        started = time.monotonic()
        result = UpsertResult(collection=collection)

        chunk_texts = [c.content_text for c in parsed.chunks]
        embed_results = embedder.embed_passages(chunk_texts)
        # summary 임베딩 (fallback 포함) — HARD_LIMIT 초과 시 임베딩 입력만 절삭.
        summary_text = _compose_summary_text(parsed.standard, parsed.summary)
        summary_embed = embedder.embed_passage(_truncate_for_summary_embedding(summary_text))

        if dry_run:
            result.elapsed_seconds = time.monotonic() - started
            return result

        # chunk point 조립
        chunk_points: list[PointStruct] = []
        chunk_point_ids: set[str] = set()
        for chunk, emb in zip(parsed.chunks, embed_results, strict=True):
            pid = chunk_id_to_point_id(chunk.chunk_id)
            chunk_point_ids.add(pid)
            payload = _chunk_payload(parsed.standard, chunk)
            payload["embedded_at"] = emb.embedded_at
            payload["embedding_model"] = emb.model
            # per-point named vectors — chunk point 는 passage 슬롯만.
            # Qdrant 는 collection 의 두 named slot 중 일부만 upsert 허용
            # (summary slot 은 이 point 에 인덱스 불생성) → 0-벡터 패딩 제거.
            chunk_points.append(
                PointStruct(
                    id=pid,
                    vector={VECTOR_PASSAGE: list(emb.vector)},
                    payload=payload,
                )
            )

        # summary point 조립
        summary_chunk_id = _standard_summary_chunk_id(parsed.standard.standard_id)
        summary_point_id = chunk_id_to_point_id(summary_chunk_id)
        summary_payload = _summary_payload(
            parsed.standard,
            parsed.summary,
            embed_model=summary_embed.model,
            embedded_at=summary_embed.embedded_at,
        )
        # per-point named vectors — summary point 는 summary 슬롯만.
        summary_point = PointStruct(
            id=summary_point_id,
            vector={VECTOR_SUMMARY: list(summary_embed.vector)},
            payload=summary_payload,
        )
        chunk_point_ids.add(summary_point_id)

        # payload drift 감지 (기존 hash 와 새 hash 비교)
        result.payload_drift_count = self._count_payload_drift(
            collection,
            chunk_points + [summary_point],
        )

        # batch upsert
        all_points = chunk_points + [summary_point]
        chunk_by_point: dict[_PointId, str] = {
            p.id: self._chunk_id_from_point(p) for p in all_points
        }
        failed = self._upsert_batches(
            collection,
            all_points,
            batch_size=batch_size,
            chunk_by_point=chunk_by_point,
        )
        result.points_upserted = len(all_points) - len(failed)
        result.summary_upserted = summary_point_id not in {
            chunk_id_to_point_id(cid) for cid in failed
        }
        result.failed_chunk_ids = tuple(failed)

        if prune_stale:
            result.stale_suffix_deleted = self._prune_stale(
                collection, parsed.standard.standard_id, chunk_point_ids
            )

        if failed:
            result.elapsed_seconds = time.monotonic() - started
            raise QdrantWriteError(collection, failed)

        result.elapsed_seconds = time.monotonic() - started
        return result

    @staticmethod
    def _chunk_id_from_point(point: PointStruct) -> str:
        payload = point.payload or {}
        chunk_id = payload.get("chunk_id")
        return str(chunk_id) if chunk_id is not None else str(point.id)

    def _count_payload_drift(self, collection: str, points: Iterable[PointStruct]) -> int:
        """기존 payload 의 ``content_text_hash`` 와 비교해 drift 계수."""
        drift = 0
        for p in points:
            try:
                existing = self._client.retrieve(
                    collection_name=collection,
                    ids=[p.id],
                    with_payload=True,
                    with_vectors=False,
                )
            except (UnexpectedResponse, ValueError):
                continue
            if not existing:
                continue
            old_payload = existing[0].payload or {}
            old_hash = old_payload.get("content_text_hash")
            new_payload = p.payload or {}
            new_hash = new_payload.get("content_text_hash")
            if old_hash is not None and new_hash is not None and old_hash != new_hash:
                drift += 1
        return drift

    def _upsert_batches(
        self,
        collection: str,
        points: list[PointStruct],
        *,
        batch_size: int,
        chunk_by_point: dict[_PointId, str],
    ) -> list[str]:
        failed: list[str] = []
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            ok = False
            last_exc: BaseException | None = None
            for attempt in range(3):
                try:
                    self._client.upsert(collection_name=collection, points=batch, wait=True)
                    ok = True
                    break
                except (UnexpectedResponse, ValueError) as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
            if not ok:
                for p in batch:
                    failed.append(chunk_by_point.get(p.id, str(p.id)))
                logger.warning(
                    "batch upsert failed after 3 retries: %d points, cause=%r",
                    len(batch),
                    last_exc,
                )
        return failed

    def _prune_stale(self, collection: str, standard_id: str, keep_point_ids: set[str]) -> int:
        """``standard_id`` 하의 기존 points 중 ``keep_point_ids`` 에 없는 것을 삭제."""
        existing_ids: list[str] = []
        offset: _PointId | None = None
        flt = Filter(must=[FieldCondition(key="standard_id", match=MatchValue(value=standard_id))])
        while True:
            response = self._client.scroll(
                collection_name=collection,
                scroll_filter=flt,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            records, offset = response
            for rec in records:
                pid = str(rec.id)
                if pid not in keep_point_ids:
                    existing_ids.append(pid)
            if offset is None:
                break
        if not existing_ids:
            return 0
        # PointIdsList 로 감싸 invariant list 변이 회피 (int|str|UUID 공변성 대응).
        selector: list[_PointId] = list(existing_ids)
        self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=selector),
            wait=True,
        )
        return len(existing_ids)

    # -- helper for standard-only summary upsert (tests) --------------------

    def summary_embedding_for(
        self,
        parsed: ParsedStandard,
        embedder: Embedder,
    ) -> EmbeddingResult:
        """summary 텍스트 임베딩을 반환 — CLI 및 tests 공유."""
        summary_text = _compose_summary_text(parsed.standard, parsed.summary)
        return embedder.embed_passage(_truncate_for_summary_embedding(summary_text))


__all__ = [
    "COLLECTION_DEFAULT",
    "HNSW_EF_CONSTRUCT",
    "HNSW_M",
    "KIND_STANDARD_SUMMARY",
    "VECTOR_PASSAGE",
    "VECTOR_SUMMARY",
    "IngestIncompleteError",
    "QdrantWriteError",
    "QdrantWriter",
    "QdrantWriterConfig",
    "QdrantWriterError",
    "SchemaDriftError",
    "UpsertResult",
    "chunk_id_to_point_id",
]
