"""Upstage Solar 임베딩 + SQLite 캐시 (Phase 3 Stage 2b).

`docs/json_schema.md v1.1.2 §8.4 / §9.5` 와 `docs/checkpoint_3_prep.md §4.2`
요구사항 반영:

- ``embedding-passage`` / ``embedding-query`` 이원 모델 (4096d cosine).
- 캐시 키는 ``sha256(model + ':' + role + ':' + text)[:16]`` — chunk_id 독립,
  Phase 1 F4 suffix drift 영향 없음 (§8.4 2 조건 중 md_parser 불변 전제).
- ``response.usage.prompt_tokens`` 를 함께 수집해 tiktoken cl100k_base 대비 Solar
  실 토크나이저 오차를 aggregate 로 노출 (C-P2-6 calibration 인프라).
- ``embedded_sha1`` 캐시 필드는 C-P2-1 content-sha1 fallback 을 v1.2 MAJOR 에서
  도입할 때 필요한 전조로 유지 (현 버전은 Qdrant payload 의
  ``content_text_hash`` 와 함께만 쓰임).

실 API 호출은 ``openai.OpenAI`` 클라이언트(``base_url=SOLAR_BASE_URL``) 를 경유
하며 Retry 는 지수 backoff 3회 (RateLimit / APIConnection / Timeout). 단위
테스트는 ``tests/test_embedder.py`` 에서 ``monkeypatch`` 로 ``client.embeddings
.create`` 를 대체해 실 네트워크 호출 없이 검증한다.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import struct
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from audit_parser.ingest.md_parser import count_tokens

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

MODEL_PASSAGE: Final = "embedding-passage"
MODEL_QUERY: Final = "embedding-query"
EMBED_DIM: Final = 4096
SOLAR_BASE_URL: Final = "https://api.upstage.ai/v1"
HARD_LIMIT_TOKENS: Final = 4000
"""``json_schema.md §9.3`` Upstage passage 입력 상한."""

DEFAULT_BATCH_SIZE: Final = 32
DEFAULT_MAX_RETRIES: Final = 3
_RETRY_BASE_SECONDS: Final = 1.0

_VECTOR_STRUCT: Final = struct.Struct(f"<{EMBED_DIM}f")
"""little-endian float32 × 4096 = 16,384 bytes."""

_ROLE_PASSAGE: Final = "passage"
_ROLE_QUERY: Final = "query"

_DEFAULT_CACHE_PATH: Final = Path(".embed_cache.sqlite")


# ---------------------------------------------------------------------------
# 예외 계층
# ---------------------------------------------------------------------------


class EmbedError(Exception):
    """Upstage Solar 임베딩 계열 기본 예외."""


class EmbeddingOverflowError(EmbedError):
    """Pre-flight token 수가 ``HARD_LIMIT_TOKENS`` 를 초과 — chunk_splitter 회귀 방지용."""


class EmbeddingAPIError(EmbedError):
    """Upstage API retry 소진 후 최종 실패."""


class EmbeddingDimError(EmbedError):
    """응답 vector 차원이 ``EMBED_DIM`` 과 불일치 — 상위 collection 차원 위반 방지."""


# ---------------------------------------------------------------------------
# 데이터 구조
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class EmbeddingResult:
    """임베딩 1건 결과. SQLite 캐시 행과 1:1 매핑되며 qdrant_writer 소비."""

    vector: tuple[float, ...]
    role: str
    model: str
    tiktoken_tokens: int
    solar_tokens: int | None
    cached: bool
    embedded_at: str


@dataclass(slots=True)
class EmbedStats:
    """프로세스 수명 내 누적 통계. C-P2-6 calibration + Task #4 CLI 종료 요약."""

    api_calls: int = 0
    cached_hits: int = 0
    total_tiktoken_tokens: int = 0
    total_solar_tokens: int = 0
    solar_samples: int = 0
    max_abs_gap: int = 0
    max_ratio: float = 0.0

    def record(self, tiktoken_tokens: int, solar_tokens: int | None) -> None:
        self.total_tiktoken_tokens += tiktoken_tokens
        if solar_tokens is None:
            return
        self.solar_samples += 1
        self.total_solar_tokens += solar_tokens
        gap = abs(solar_tokens - tiktoken_tokens)
        if gap > self.max_abs_gap:
            self.max_abs_gap = gap
        if tiktoken_tokens > 0:
            ratio = solar_tokens / tiktoken_tokens
            if ratio > self.max_ratio:
                self.max_ratio = ratio

    def to_dict(self) -> dict[str, float | int]:
        mean_ratio = (
            self.total_solar_tokens / self.total_tiktoken_tokens
            if self.total_tiktoken_tokens
            else 0.0
        )
        return {
            "api_calls": self.api_calls,
            "cached_hits": self.cached_hits,
            "total_tiktoken_tokens": self.total_tiktoken_tokens,
            "total_solar_tokens": self.total_solar_tokens,
            "solar_samples": self.solar_samples,
            "max_abs_gap": self.max_abs_gap,
            "max_ratio": round(self.max_ratio, 6),
            "mean_ratio": round(mean_ratio, 6),
        }


# ---------------------------------------------------------------------------
# 캐시 저장소
# ---------------------------------------------------------------------------


_CREATE_SQL: Final = """
CREATE TABLE IF NOT EXISTS embeddings (
    cache_key       TEXT    PRIMARY KEY,
    role            TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    vector          BLOB    NOT NULL,
    tiktoken_tokens INTEGER NOT NULL,
    solar_tokens    INTEGER,
    embedded_at     TEXT    NOT NULL,
    embedded_sha1   TEXT    NOT NULL
) WITHOUT ROWID;
"""
_INDEX_SQL: Final = "CREATE INDEX IF NOT EXISTS ix_embeddings_role ON embeddings(role);"


def _pack_vector(vec: Sequence[float]) -> bytes:
    if len(vec) != EMBED_DIM:
        raise EmbeddingDimError(
            f"expected vector dim={EMBED_DIM}, got {len(vec)}"
        )
    return _VECTOR_STRUCT.pack(*vec)


def _unpack_vector(buf: bytes) -> tuple[float, ...]:
    return _VECTOR_STRUCT.unpack(buf)


def _compute_cache_key(model: str, role: str, text: str) -> str:
    digest = hashlib.sha256(f"{model}:{role}:{text}".encode()).hexdigest()
    return digest[:16]


def _compute_text_sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def _now_iso_utc() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _PendingBatchItem:
    """batch 호출용 — 원본 입력 순번 유지."""

    original_index: int
    text: str
    cache_key: str
    tiktoken_tokens: int


class Embedder:
    """Upstage Solar 호출 + SQLite 캐시.

    Args:
        api_key: ``UPSTAGE_API_KEY``. None 이면 ``os.environ`` 에서 로드.
        base_url: Upstage 엔드포인트. 기본 ``SOLAR_BASE_URL``.
        cache_path: SQLite 파일 경로. None 이면 프로젝트 루트 ``.embed_cache.sqlite``.
        model_passage: 문서 임베딩 모델명. 기본 ``embedding-passage``.
        model_query: 쿼리 임베딩 모델명. 기본 ``embedding-query``.
        max_retries: API 호출 지수 backoff 최대 재시도 수.
    """

    __slots__ = (
        "_base_url",
        "_cache_path",
        "_client",
        "_conn",
        "_max_retries",
        "_model_passage",
        "_model_query",
        "stats",
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = SOLAR_BASE_URL,
        cache_path: Path | None = None,
        model_passage: str = MODEL_PASSAGE,
        model_query: str = MODEL_QUERY,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.environ.get(
            "UPSTAGE_API_KEY"
        )
        if not resolved_key:
            raise EmbedError(
                "UPSTAGE_API_KEY 미설정 — .env 또는 생성자 인자로 지정 필요."
            )
        self._client: OpenAI = OpenAI(api_key=resolved_key, base_url=base_url)
        self._base_url: str = base_url
        self._model_passage: str = model_passage
        self._model_query: str = model_query
        self._max_retries: int = max(1, max_retries)
        self._cache_path: Path = cache_path if cache_path is not None else _DEFAULT_CACHE_PATH
        self._conn: sqlite3.Connection = self._open_cache(self._cache_path)
        self.stats: EmbedStats = EmbedStats()

    # -- cache lifecycle -----------------------------------------------------

    @staticmethod
    def _open_cache(path: Path) -> sqlite3.Connection:
        """SQLite WAL 모드 + integrity_check + 손상 시 자동 재구축 (Critic F4).

        1. parent dir 보장 + WAL/synchronous pragmas.
        2. ``PRAGMA integrity_check`` 결과가 "ok" 아니면 기존 파일을
           ``.embed_cache.sqlite.corrupt.<UTC_ts>`` 로 백업 후 새 DB 재생성.
        3. ``check_same_thread=False`` — 단일 프로세스 전제지만 multi-thread
           (향후 CLI 에서 thread pool) 에서 thread-local 패턴으로 쓸 수 있게
           허용. 동시성 정합은 SQLite 자체 journal_mode=WAL 로 보장.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        def _fresh(conn: sqlite3.Connection) -> sqlite3.Connection:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(_CREATE_SQL)
            conn.execute(_INDEX_SQL)
            return conn

        conn = sqlite3.connect(
            str(path),
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            # 신규 파일이면 integrity_check 는 단순 "ok" — 비용 무시할 수준.
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            ok = row is not None and row[0] == "ok"
        except sqlite3.DatabaseError:
            ok = False
        if not ok:
            # 1) 연결 닫기 → 2) 파일 백업 → 3) 재연결 후 스키마 재생성
            try:
                conn.close()
            except sqlite3.Error:  # pragma: no cover — defensive
                pass
            if path.exists():
                ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
                backup = path.with_name(f"{path.name}.corrupt.{ts}")
                try:
                    path.replace(backup)
                except OSError:  # pragma: no cover — filesystem race
                    path.unlink(missing_ok=True)
            conn = sqlite3.connect(
                str(path),
                isolation_level=None,
                check_same_thread=False,
            )
        return _fresh(conn)

    def close(self) -> None:
        """SQLite 연결 종료. 호출 후 재사용 불가."""
        try:
            self._conn.close()
        except sqlite3.Error:  # pragma: no cover — defensive
            pass

    def __enter__(self) -> Embedder:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- cache API (공개 — qdrant_writer / tests 공유) ------------------------

    def cache_key(self, role: str, text: str, model: str | None = None) -> str:
        """``sha256(model:role:text)[:16]`` 계산. role 은 'passage'/'query'."""
        if role not in {_ROLE_PASSAGE, _ROLE_QUERY}:
            raise ValueError(f"role must be passage|query, got {role!r}")
        resolved_model = model if model is not None else self._model_for(role)
        return _compute_cache_key(resolved_model, role, text)

    def get_cached(self, role: str, text: str) -> EmbeddingResult | None:
        """cache lookup. 없으면 None."""
        model = self._model_for(role)
        key = _compute_cache_key(model, role, text)
        return self._load(key)

    # -- public embed API ----------------------------------------------------

    def embed_passage(self, text: str) -> EmbeddingResult:
        """단일 passage 임베딩 (``embedding-passage``)."""
        return self._embed_one(text=text, role=_ROLE_PASSAGE)

    def embed_query(self, text: str) -> EmbeddingResult:
        """단일 query 임베딩 (``embedding-query``)."""
        return self._embed_one(text=text, role=_ROLE_QUERY)

    def embed_passages(self, texts: Sequence[str]) -> list[EmbeddingResult]:
        """batch passage 임베딩. 입력 순서 보존.

        구현 전략:
        1. 각 text 별 pre-flight token check + cache key 산출.
        2. cache miss 만 모아서 Upstage API 에 단일 호출 (list input).
        3. 응답을 원본 index 자리에 주입.
        """
        if not texts:
            return []
        model = self._model_passage
        results: list[EmbeddingResult | None] = [None] * len(texts)
        pending: list[_PendingBatchItem] = []
        for i, text in enumerate(texts):
            tok = count_tokens(text)
            if tok > HARD_LIMIT_TOKENS:
                raise EmbeddingOverflowError(
                    f"text[{i}] token_estimate={tok} > {HARD_LIMIT_TOKENS}"
                )
            key = _compute_cache_key(model, _ROLE_PASSAGE, text)
            hit = self._load(key)
            if hit is not None:
                self.stats.cached_hits += 1
                results[i] = hit
                continue
            pending.append(
                _PendingBatchItem(
                    original_index=i,
                    text=text,
                    cache_key=key,
                    tiktoken_tokens=tok,
                )
            )
        if pending:
            self._embed_batch_api(pending, model=model, role=_ROLE_PASSAGE, results=results)
        # narrow type — 모든 슬롯이 채워졌음을 단정.
        final: list[EmbeddingResult] = []
        for item in results:
            if item is None:  # pragma: no cover — defensive
                raise EmbedError("batch assembly lost a slot")
            final.append(item)
        return final

    # -- internal ------------------------------------------------------------

    def _model_for(self, role: str) -> str:
        return self._model_passage if role == _ROLE_PASSAGE else self._model_query

    def _embed_one(self, *, text: str, role: str) -> EmbeddingResult:
        tok = count_tokens(text)
        if tok > HARD_LIMIT_TOKENS:
            raise EmbeddingOverflowError(
                f"token_estimate={tok} > {HARD_LIMIT_TOKENS}"
            )
        model = self._model_for(role)
        key = _compute_cache_key(model, role, text)
        hit = self._load(key)
        if hit is not None:
            self.stats.cached_hits += 1
            return hit
        vectors, solar_tokens = self._call_api([text], model=model)
        vector = tuple(vectors[0])
        if len(vector) != EMBED_DIM:
            raise EmbeddingDimError(
                f"Solar returned dim={len(vector)}, expected {EMBED_DIM}"
            )
        self.stats.record(tok, solar_tokens)
        result = EmbeddingResult(
            vector=vector,
            role=role,
            model=model,
            tiktoken_tokens=tok,
            solar_tokens=solar_tokens,
            cached=False,
            embedded_at=_now_iso_utc(),
        )
        self._store(key=key, text=text, result=result)
        return result

    def _embed_batch_api(
        self,
        pending: list[_PendingBatchItem],
        *,
        model: str,
        role: str,
        results: list[EmbeddingResult | None],
    ) -> None:
        """pending 리스트를 ``DEFAULT_BATCH_SIZE`` 씩 잘라 API 호출 + 결과 주입."""
        for start in range(0, len(pending), DEFAULT_BATCH_SIZE):
            window = pending[start : start + DEFAULT_BATCH_SIZE]
            window_texts = [item.text for item in window]
            vectors, total_solar = self._call_api(window_texts, model=model)
            # Upstage 는 list input 에 대해 총 prompt_tokens 만 돌려주므로,
            # item 별 분배는 tiktoken ratio 근사. solar_tokens=None 이면 per-item None.
            tiktoken_total = sum(item.tiktoken_tokens for item in window)
            for vec, item in zip(vectors, window, strict=True):
                if len(vec) != EMBED_DIM:
                    raise EmbeddingDimError(
                        f"Solar returned dim={len(vec)}, expected {EMBED_DIM}"
                    )
                solar_per_item: int | None
                if total_solar is None or tiktoken_total == 0:
                    solar_per_item = None
                else:
                    solar_per_item = round(
                        total_solar * item.tiktoken_tokens / tiktoken_total
                    )
                self.stats.record(item.tiktoken_tokens, solar_per_item)
                result = EmbeddingResult(
                    vector=tuple(vec),
                    role=role,
                    model=model,
                    tiktoken_tokens=item.tiktoken_tokens,
                    solar_tokens=solar_per_item,
                    cached=False,
                    embedded_at=_now_iso_utc(),
                )
                self._store(key=item.cache_key, text=item.text, result=result)
                results[item.original_index] = result

    def _call_api(
        self, inputs: list[str], *, model: str
    ) -> tuple[list[list[float]], int | None]:
        """OpenAI 호환 ``embeddings.create`` 호출 + retry.

        Returns:
            (vectors, total_solar_tokens). total_solar_tokens 는 ``usage.prompt_tokens``
            가 없으면 None.
        """
        last_exc: Exception | None = None
        response = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.embeddings.create(
                    input=inputs,
                    model=model,
                )
                break
            except AuthenticationError:
                # 인증 오류는 재시도해도 의미 없음 — 상위 전파
                raise
            except (
                RateLimitError,
                APIConnectionError,
                APITimeoutError,
                httpx.TimeoutException,
            ) as exc:
                last_exc = exc
                if attempt == self._max_retries - 1:
                    break
                wait = _RETRY_BASE_SECONDS * (2**attempt)
                time.sleep(wait)
        if response is None:
            raise EmbeddingAPIError(
                f"Solar API retry exhausted ({self._max_retries}): {last_exc!r}"
            ) from last_exc
        # 정상 응답
        self.stats.api_calls += 1
        data = response.data
        vectors: list[list[float]] = [list(d.embedding) for d in data]
        usage = getattr(response, "usage", None)
        total_solar: int | None = None
        if usage is not None:
            maybe = getattr(usage, "prompt_tokens", None)
            if isinstance(maybe, int):
                total_solar = maybe
        return vectors, total_solar

    # -- cache I/O -----------------------------------------------------------

    def _load(self, key: str) -> EmbeddingResult | None:
        row = self._conn.execute(
            "SELECT vector, role, model, tiktoken_tokens, solar_tokens, embedded_at "
            "FROM embeddings WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        vec = _unpack_vector(row[0])
        return EmbeddingResult(
            vector=vec,
            role=row[1],
            model=row[2],
            tiktoken_tokens=row[3],
            solar_tokens=row[4],
            cached=True,
            embedded_at=row[5],
        )

    def _store(self, *, key: str, text: str, result: EmbeddingResult) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO embeddings "
            "(cache_key, role, model, vector, tiktoken_tokens, solar_tokens, "
            "embedded_at, embedded_sha1) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key,
                result.role,
                result.model,
                _pack_vector(result.vector),
                result.tiktoken_tokens,
                result.solar_tokens,
                result.embedded_at,
                _compute_text_sha1(text),
            ),
        )


# ---------------------------------------------------------------------------
# 편의 함수 — 기본 캐시를 쓰는 간편 helper. 지속 사용 시 Embedder 인스턴스 권장.
# ---------------------------------------------------------------------------


def iter_passage_texts(parsed_chunks: Iterable[object]) -> Iterable[str]:
    """ChunkRecord 시퀀스에서 ``content_text`` 를 순차 추출 (qdrant_writer 공용)."""
    for chunk in parsed_chunks:
        text = getattr(chunk, "content_text", None)
        if isinstance(text, str):
            yield text


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MAX_RETRIES",
    "EMBED_DIM",
    "HARD_LIMIT_TOKENS",
    "MODEL_PASSAGE",
    "MODEL_QUERY",
    "SOLAR_BASE_URL",
    "EmbedError",
    "EmbedStats",
    "Embedder",
    "EmbeddingAPIError",
    "EmbeddingDimError",
    "EmbeddingOverflowError",
    "EmbeddingResult",
    "iter_passage_texts",
]
