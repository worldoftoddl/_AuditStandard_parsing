"""`audit_parser.ingest.embedder` 단위 테스트 (Phase 3 Task #2).

실 Upstage Solar API 를 호출하지 않고 ``monkeypatch`` 로 ``client.embeddings
.create`` 를 대체해 결정론 검증. 커버 범위 (≥14 cases):

1. cache miss → API 1회 → 재호출 시 hit (call count 검증)
2. cache_key 결정성 (동일 model/role/text 동일 키)
3. role 분리 (passage vs query 는 다른 키)
4. batch 순서 보존 (N 입력 → N 출력, index 일치)
5. batch 부분 hit — cache 있는 것만 제외하고 API 호출
6. retry: RateLimitError 2회 후 성공
7. retry 소진: APIConnectionError 3회 → EmbeddingAPIError
8. pre-flight overflow → EmbeddingOverflowError
9. 응답 차원 불일치 → EmbeddingDimError
10. usage.prompt_tokens=None 허용 (solar_tokens=None 보관)
11. struct pack/unpack float32 회귀 (tolerance)
12. WAL mode 활성 확인 (PRAGMA journal_mode)
13. stats 누적 — api_calls / cached_hits / max_ratio
14. close() 후 재초기화시 cache 재사용
15. AuthenticationError 즉시 전파 (retry 없음)
16. integrity_check 실패 시 .corrupt.* 백업 + 재생성 (F4)
17. check_same_thread=False — 다른 thread 에서 읽기 가능 (F4)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest

from audit_parser.ingest import embedder as emb_mod
from audit_parser.ingest.embedder import (
    EMBED_DIM,
    HARD_LIMIT_TOKENS,
    MODEL_PASSAGE,
    MODEL_QUERY,
    Embedder,
    EmbeddingAPIError,
    EmbeddingDimError,
    EmbeddingOverflowError,
    EmbeddingResult,
    _compute_cache_key,
    _pack_vector,
    _unpack_vector,
)

# ---------------------------------------------------------------------------
# Fake OpenAI client — monkeypatch 로 주입
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
    model: str = MODEL_PASSAGE
    object: str = "list"


class _FakeEmbeddings:
    """``client.embeddings`` 의 최소 모의. create 호출 기록 + scripted 응답."""

    def __init__(
        self,
        *,
        dim: int = EMBED_DIM,
        usage_prompt_tokens: int | None = 10,
        raise_sequence: list[BaseException] | None = None,
    ) -> None:
        self.dim = dim
        self.usage_prompt_tokens = usage_prompt_tokens
        self.raise_sequence: list[BaseException] = list(raise_sequence or [])
        self.calls: list[dict[str, Any]] = []
        self._counter = 0

    def create(  # noqa: A002 — SDK 시그니처
        self,
        *,
        input: list[str] | str,  # noqa: A002
        model: str,
    ) -> _FakeEmbeddingResponse:
        received = list(input) if isinstance(input, list) else [input]
        self.calls.append({"input": received, "model": model})
        if self.raise_sequence:
            exc = self.raise_sequence.pop(0)
            raise exc
        texts = input if isinstance(input, list) else [input]
        data: list[_FakeEmbeddingItem] = []
        for i, _t in enumerate(texts):
            self._counter += 1
            # deterministic vector: 선두는 텍스트 인덱스 + counter 로 구분 → 회귀 용이
            vec = [float(i) / max(1, self.dim)] * self.dim
            data.append(_FakeEmbeddingItem(embedding=vec, index=i))
        usage: _FakeUsage | None = None
        if self.usage_prompt_tokens is not None:
            usage = _FakeUsage(prompt_tokens=self.usage_prompt_tokens)
        return _FakeEmbeddingResponse(data=data, usage=usage, model=model)


class _FakeOpenAI:
    def __init__(self, *, embeddings: _FakeEmbeddings) -> None:
        self.embeddings = embeddings


def _make_embedder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake: _FakeEmbeddings | None = None,
    usage: int | None = 10,
    max_retries: int = 3,
) -> tuple[Embedder, _FakeEmbeddings]:
    fake_emb = fake or _FakeEmbeddings(usage_prompt_tokens=usage)

    def _fake_ctor(*, api_key: str, base_url: str) -> _FakeOpenAI:  # noqa: ARG001
        return _FakeOpenAI(embeddings=fake_emb)

    monkeypatch.setattr(emb_mod, "OpenAI", _fake_ctor)
    monkeypatch.setenv("UPSTAGE_API_KEY", "sk-test-fake")
    cache_path = tmp_path / "cache.sqlite"
    # _RETRY_BASE_SECONDS 를 0 으로 덮어 retry 테스트 가속
    monkeypatch.setattr(emb_mod, "_RETRY_BASE_SECONDS", 0.0)
    embedder = Embedder(cache_path=cache_path, max_retries=max_retries)
    return embedder, fake_emb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cache_miss_then_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """cache miss → API 1회 → 재호출 시 API 호출 없음."""
    embedder, fake = _make_embedder(tmp_path, monkeypatch)
    r1 = embedder.embed_passage("안녕 감사기준")
    assert r1.cached is False
    assert len(r1.vector) == EMBED_DIM
    assert fake.calls and fake.calls[0]["model"] == MODEL_PASSAGE
    assert embedder.stats.api_calls == 1

    r2 = embedder.embed_passage("안녕 감사기준")
    assert r2.cached is True
    assert len(fake.calls) == 1  # no extra API call
    assert embedder.stats.cached_hits == 1
    assert r1.vector == r2.vector
    embedder.close()


def test_cache_key_deterministic() -> None:
    """동일 (model, role, text) → 동일 16-hex 키."""
    k1 = _compute_cache_key("embedding-passage", "passage", "foo")
    k2 = _compute_cache_key("embedding-passage", "passage", "foo")
    assert k1 == k2
    assert len(k1) == 16


def test_role_separates_cache_keys() -> None:
    """role=passage / role=query 는 서로 다른 key (저장소 충돌 방지)."""
    kp = _compute_cache_key("embedding-passage", "passage", "text")
    kq = _compute_cache_key("embedding-query", "query", "text")
    assert kp != kq


def test_batch_preserves_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """embed_passages: 입력 N → 출력 N, 순서 + content 보존."""
    embedder, fake = _make_embedder(tmp_path, monkeypatch)
    texts = [f"sample text #{i}" for i in range(5)]
    results = embedder.embed_passages(texts)
    assert len(results) == 5
    for i, r in enumerate(results):
        assert r.role == "passage"
        assert r.model == MODEL_PASSAGE
        assert len(r.vector) == EMBED_DIM
        # fake 는 position i 에 따라 vector[0] 값을 다르게 준다.
        assert r.vector[0] == pytest.approx(float(i) / EMBED_DIM)
    assert fake.calls[0]["input"] == texts
    embedder.close()


def test_batch_partial_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """batch 중 일부는 cache hit → API call 은 miss 항목만."""
    embedder, fake = _make_embedder(tmp_path, monkeypatch)
    embedder.embed_passage("precached")
    assert len(fake.calls) == 1
    results = embedder.embed_passages(["precached", "new-a", "new-b"])
    assert len(results) == 3
    assert results[0].cached is True
    assert results[1].cached is False
    assert results[2].cached is False
    # 두 번째 API 호출은 miss 2건만
    assert len(fake.calls) == 2
    assert fake.calls[1]["input"] == ["new-a", "new-b"]
    embedder.close()


def test_retry_succeeds_after_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RateLimitError 2회 후 성공 → 총 호출 3회."""
    raises: list[BaseException] = [
        openai.RateLimitError(
            "rate",
            response=httpx.Response(429, request=httpx.Request("POST", "http://x")),
            body=None,
        ),
        openai.RateLimitError(
            "rate",
            response=httpx.Response(429, request=httpx.Request("POST", "http://x")),
            body=None,
        ),
    ]
    fake = _FakeEmbeddings(raise_sequence=raises)
    embedder, _ = _make_embedder(tmp_path, monkeypatch, fake=fake, max_retries=3)
    r = embedder.embed_passage("retry path")
    assert r.cached is False
    assert len(fake.calls) == 3
    embedder.close()


def test_retry_exhausted_raises_api_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """APIConnectionError 3회 → EmbeddingAPIError."""
    req = httpx.Request("POST", "http://x")
    raises: list[BaseException] = [
        openai.APIConnectionError(request=req),
        openai.APIConnectionError(request=req),
        openai.APIConnectionError(request=req),
    ]
    fake = _FakeEmbeddings(raise_sequence=raises)
    embedder, _ = _make_embedder(tmp_path, monkeypatch, fake=fake, max_retries=3)
    with pytest.raises(EmbeddingAPIError):
        embedder.embed_passage("fail")
    assert len(fake.calls) == 3
    embedder.close()


def test_authentication_error_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AuthenticationError 는 retry 없이 즉시 raise."""
    resp = httpx.Response(401, request=httpx.Request("POST", "http://x"))
    raises: list[BaseException] = [
        openai.AuthenticationError("unauthorized", response=resp, body=None)
    ]
    fake = _FakeEmbeddings(raise_sequence=raises)
    embedder, _ = _make_embedder(tmp_path, monkeypatch, fake=fake, max_retries=3)
    with pytest.raises(openai.AuthenticationError):
        embedder.embed_passage("nope")
    # retry 없음
    assert len(fake.calls) == 1
    embedder.close()


def test_preflight_token_overflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HARD_LIMIT_TOKENS 초과 입력은 API 호출 없이 EmbeddingOverflowError."""
    embedder, fake = _make_embedder(tmp_path, monkeypatch)

    def _fake_count_tokens(_text: str) -> int:
        return HARD_LIMIT_TOKENS + 1

    monkeypatch.setattr(emb_mod, "count_tokens", _fake_count_tokens)
    with pytest.raises(EmbeddingOverflowError):
        embedder.embed_passage("anything")
    assert fake.calls == []
    embedder.close()


def test_response_dim_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """응답 vector dim ≠ 4096 → EmbeddingDimError."""
    fake = _FakeEmbeddings(dim=4095)
    embedder, _ = _make_embedder(tmp_path, monkeypatch, fake=fake)
    with pytest.raises(EmbeddingDimError):
        embedder.embed_passage("bad dim")
    embedder.close()


def test_usage_missing_prompt_tokens_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """usage.prompt_tokens 가 응답에 없으면 solar_tokens=None."""
    embedder, _ = _make_embedder(tmp_path, monkeypatch, usage=None)
    r = embedder.embed_passage("no usage")
    assert r.solar_tokens is None
    # 캐시 round-trip 에서도 None 보존
    r2 = embedder.embed_passage("no usage")
    assert r2.cached is True
    assert r2.solar_tokens is None
    embedder.close()


def test_vector_pack_unpack_roundtrip() -> None:
    """struct pack/unpack — float32 손실 내 tolerance."""
    src = tuple(float(i) / 1000 for i in range(EMBED_DIM))
    buf = _pack_vector(src)
    assert len(buf) == EMBED_DIM * 4
    back = _unpack_vector(buf)
    assert len(back) == EMBED_DIM
    for a, b in zip(src, back, strict=True):
        assert abs(a - b) < 1e-5


def test_wal_mode_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PRAGMA journal_mode == wal."""
    embedder, _ = _make_embedder(tmp_path, monkeypatch)
    row = embedder._conn.execute("PRAGMA journal_mode;").fetchone()
    assert row is not None
    assert row[0].lower() == "wal"
    embedder.close()


def test_stats_accumulates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """stats.api_calls / cached_hits / max_ratio 누적 — to_dict() 키 검증."""
    embedder, _ = _make_embedder(tmp_path, monkeypatch, usage=50)
    embedder.embed_passage("x" * 10)
    embedder.embed_passage("x" * 10)  # cache hit
    embedder.embed_passage("y" * 10)
    d = embedder.stats.to_dict()
    assert d["api_calls"] == 2
    assert d["cached_hits"] == 1
    assert d["total_tiktoken_tokens"] > 0
    assert d["total_solar_tokens"] == 100
    assert "max_ratio" in d and "mean_ratio" in d
    embedder.close()


def test_close_then_reopen_reuses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """close() 후 같은 경로로 재초기화 → 기존 cache hit."""
    cache_path = tmp_path / "persist.sqlite"

    def _factory(**kwargs: Any) -> tuple[Embedder, _FakeEmbeddings]:
        fake = _FakeEmbeddings()

        def _fake_ctor(*, api_key: str, base_url: str) -> _FakeOpenAI:  # noqa: ARG001
            return _FakeOpenAI(embeddings=fake)

        monkeypatch.setattr(emb_mod, "OpenAI", _fake_ctor)
        monkeypatch.setenv("UPSTAGE_API_KEY", "sk-test-fake")
        e = Embedder(cache_path=cache_path, **kwargs)
        return e, fake

    e1, fake1 = _factory()
    e1.embed_passage("persist me")
    assert len(fake1.calls) == 1
    e1.close()

    e2, fake2 = _factory()
    r = e2.embed_passage("persist me")
    assert r.cached is True
    assert fake2.calls == []  # no API call
    e2.close()


def test_corrupt_cache_triggers_backup_and_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """integrity_check 실패 시 .corrupt.* 백업 + 신규 DB 재생성 (Critic F4)."""
    cache_path = tmp_path / "corrupt.sqlite"
    # 유효하지 않은 SQLite 파일을 사전 생성
    cache_path.write_bytes(b"not-a-sqlite-file\x00" * 16)

    def _fake_ctor(*, api_key: str, base_url: str) -> _FakeOpenAI:  # noqa: ARG001
        return _FakeOpenAI(embeddings=_FakeEmbeddings())

    monkeypatch.setattr(emb_mod, "OpenAI", _fake_ctor)
    monkeypatch.setenv("UPSTAGE_API_KEY", "sk-test-fake")
    embedder = Embedder(cache_path=cache_path)

    # 신규 DB 에 정상 쓰기 가능해야 함
    embedder.embed_passage("after rebuild")
    # 백업 파일이 생성됐는지 확인
    siblings = [p.name for p in tmp_path.iterdir()]
    backups = [n for n in siblings if n.startswith("corrupt.sqlite.corrupt.")]
    assert backups, f"corrupt backup expected, got {siblings}"
    embedder.close()


def test_check_same_thread_false_allows_cross_thread_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_same_thread=False — 다른 thread 에서 connection 사용 가능 (F4)."""
    embedder, _ = _make_embedder(tmp_path, monkeypatch)
    embedder.embed_passage("thread-probe")

    results: list[EmbeddingResult | None] = [None]
    error_box: list[BaseException | None] = [None]

    def _reader() -> None:
        try:
            results[0] = embedder.get_cached("passage", "thread-probe")
        except BaseException as e:  # noqa: BLE001
            error_box[0] = e

    t = threading.Thread(target=_reader)
    t.start()
    t.join(timeout=5.0)
    assert error_box[0] is None, f"cross-thread access failed: {error_box[0]!r}"
    assert results[0] is not None
    assert results[0].cached is True
    embedder.close()


def test_query_model_uses_query_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """embed_query 는 MODEL_QUERY 로 요청해야 한다."""
    embedder, fake = _make_embedder(tmp_path, monkeypatch)
    embedder.embed_query("find me")
    assert fake.calls and fake.calls[0]["model"] == MODEL_QUERY
    embedder.close()
