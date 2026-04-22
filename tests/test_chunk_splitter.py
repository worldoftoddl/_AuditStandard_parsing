"""chunk_splitter 단위 + 통합 테스트 (Phase 2 Task #3).

검증 범위:
- §9.3 분할 분기 (passthrough / atomic / table / paragraph)
- §9.4 table row-wise split + header 복제
- `bullet` / `sub_item` list atomicity → ChunkSplitError
- 단일 row > soft_limit → ChunkSplitError
- Idempotency — 첫 조각 chunk_id 불변 (§8.1)
- part_of / chunk_of / chunk_index 규약
- ISA-1200 66×2 table 실측 3 조각 분할
- 전수 회귀 — 36 ISA 파싱 후 chunk 수 변동 + 전역 고유성
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from audit_parser.ingest import (
    SOFT_LIMIT,
    ChunkRecord,
    ChunkSplitError,
    parse_md,
    parse_md_dir,
    split_oversized_chunks,
)
from audit_parser.ingest.md_parser import assert_chunk_id_uniqueness, count_tokens

REPO_ROOT = Path(__file__).resolve().parents[1]
MD_DIR = REPO_ROOT / "output" / "md"


def _require_md_dir() -> None:
    if not MD_DIR.exists():
        pytest.skip(f"{MD_DIR} 없음 — Phase 1 convert 선행 필요")


# ---------------------------------------------------------------------------
# 테스트 헬퍼 — 가상 ChunkRecord 팩토리
# ---------------------------------------------------------------------------


def _make_chunk(
    *,
    chunk_id: str = "ISA-000:requirements:aaaaaaaa:1.",
    kind: str = "paragraph_body",
    paragraph_id: str | None = None,
    content_text: str = "",
    content_markdown: str | None = None,
    table_cells: tuple[tuple[str, ...], ...] | None = None,
    source_idx: int = 100,
) -> ChunkRecord:
    md = content_markdown if content_markdown is not None else content_text
    return ChunkRecord(
        chunk_id=chunk_id,
        paragraph_id=paragraph_id,
        kind=kind,
        section="requirements",
        appendix_index=None,
        heading_trail=("감사기준서 000",),
        heading_trail_hash="aaaaaaaa",
        content_text=content_text,
        content_markdown=md,
        authority=1,
        parent_paragraph_id=None,
        is_application_guidance=False,
        token_estimate=count_tokens(content_text),
        chunk_index=0,
        chunk_of=1,
        source_idx=source_idx,
        part_of=None,
        table_cells=table_cells,
    )


def _make_table_chunk(rows: int, cell_filler: str = "정의 텍스트") -> ChunkRecord:
    """rows × 2 컬럼 table chunk 생성. header = ('용어', '정의')."""
    header = ("용어", "정의")
    body = tuple((f"용어{i}", f"{cell_filler} {i}") for i in range(1, rows))
    cells = (header, *body)
    # markdown 렌더링 (한 행씩 pipe 구분).
    lines = [
        "| " + " | ".join(header) + " |",
        "| --- | --- |",
        *("| " + " | ".join(row) + " |" for row in body),
    ]
    md = "\n".join(lines)
    text = "\n".join(" ".join(row) for row in cells)
    return _make_chunk(
        chunk_id="ISA-1200:appendix:d3ec59bd:table#1669",
        kind="table",
        paragraph_id=None,
        content_text=text,
        content_markdown=md,
        table_cells=cells,
        source_idx=1669,
    )


# ---------------------------------------------------------------------------
# 1. 빈 입력 / passthrough (threshold 경계)
# ---------------------------------------------------------------------------


def test_split_empty_returns_empty() -> None:
    assert split_oversized_chunks([], standard_id="ISA-000") == ()


def test_split_below_threshold_passthrough() -> None:
    c = _make_chunk(content_text="짧은 문단 샘플.")
    out = split_oversized_chunks([c], standard_id="ISA-000")
    assert out == (c,)
    # 동일 객체여야 함 (hot-path 회피 — 수정 없이 반환).
    assert out[0] is c


def test_split_exact_soft_limit_passthrough() -> None:
    # soft_limit tokens 짜리 텍스트 생성 (한국어 단어 약 300 개).
    text = "감사인은 감사의견을 형성한다. " * 300
    tok = count_tokens(text)
    if tok > SOFT_LIMIT:
        text = "감사인은 감사의견을 형성한다. " * (300 * SOFT_LIMIT // tok)
    c = _make_chunk(content_text=text)
    assert c.token_estimate <= SOFT_LIMIT
    out = split_oversized_chunks([c], standard_id="ISA-000")
    assert out == (c,)


# ---------------------------------------------------------------------------
# 2. atomic kind (block_quote / unknown_numbering)
# ---------------------------------------------------------------------------


def test_block_quote_over_limit_passthrough_with_warn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    big_text = "인용구 문장입니다. " * 1500  # > SOFT_LIMIT
    c = _make_chunk(kind="block_quote", content_text=big_text)
    assert c.token_estimate > SOFT_LIMIT
    out = split_oversized_chunks([c], standard_id="ISA-000")
    assert len(out) == 1 and out[0] is c
    err = capsys.readouterr().err
    assert "atomic passthrough" in err
    assert "block_quote" in err


def test_unknown_numbering_over_limit_passthrough_with_warn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    big_text = "패턴 미매치 문단. " * 1500
    c = _make_chunk(kind="unknown_numbering", content_text=big_text)
    out = split_oversized_chunks([c], standard_id="ISA-000")
    assert len(out) == 1 and out[0] is c
    assert "atomic passthrough" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 3. list atomicity (bullet / sub_item) → ChunkSplitError
# ---------------------------------------------------------------------------


def test_bullet_over_limit_raises() -> None:
    c = _make_chunk(kind="bullet", content_text="bullet item 원자성." * 1500)
    with pytest.raises(ChunkSplitError) as exc:
        split_oversized_chunks([c], standard_id="ISA-000")
    assert "bullet" in str(exc.value)


def test_sub_item_over_limit_raises() -> None:
    c = _make_chunk(kind="sub_item", content_text="sub_item 원자성." * 1500)
    with pytest.raises(ChunkSplitError):
        split_oversized_chunks([c], standard_id="ISA-000")


# ---------------------------------------------------------------------------
# 4. table row-wise split (§9.4)
# ---------------------------------------------------------------------------


def test_table_over_limit_splits_with_header_replication() -> None:
    c = _make_table_chunk(rows=100, cell_filler="이것은 긴 정의 문장입니다." * 5)
    assert c.token_estimate > SOFT_LIMIT
    out = split_oversized_chunks([c], standard_id="ISA-1200")
    assert len(out) >= 2
    # 모든 조각 header 복제 확인.
    assert c.table_cells is not None
    header = c.table_cells[0]
    for sub in out:
        assert sub.table_cells is not None
        assert sub.table_cells[0] == header
        assert sub.token_estimate <= SOFT_LIMIT


def test_table_split_first_chunk_id_unchanged() -> None:
    """Idempotency §8.1 — 첫 조각 chunk_id 는 입력과 동일."""
    c = _make_table_chunk(rows=100, cell_filler="긴 정의." * 5)
    out = split_oversized_chunks([c], standard_id="ISA-1200")
    assert out[0].chunk_id == c.chunk_id
    assert out[0].chunk_index == 0
    assert out[0].part_of is None
    assert out[0].chunk_of == len(out)


def test_table_split_subsequent_chunk_ids() -> None:
    c = _make_table_chunk(rows=100, cell_filler="긴 정의." * 5)
    out = split_oversized_chunks([c], standard_id="ISA-1200")
    for i, sub in enumerate(out[1:], start=1):
        assert sub.chunk_id == f"{c.chunk_id}#{i}"
        assert sub.chunk_index == i
        assert sub.part_of == c.chunk_id
        assert sub.chunk_of == len(out)


def test_table_single_row_over_limit_raises() -> None:
    # 극단적으로 긴 단일 row 생성.
    header = ("용어", "정의")
    huge_cell = "매우 긴 정의 문장입니다. " * 2000  # » SOFT_LIMIT
    cells = (header, ("단일항목", huge_cell))
    md_lines = [
        "| " + " | ".join(header) + " |",
        "| --- | --- |",
        "| 단일항목 | " + huge_cell + " |",
    ]
    c = _make_chunk(
        chunk_id="ISA-999:appendix:xxxxxxxx:table#999",
        kind="table",
        paragraph_id=None,
        content_text=header[0] + " " + header[1] + "\n" + "단일항목 " + huge_cell,
        content_markdown="\n".join(md_lines),
        table_cells=cells,
        source_idx=999,
    )
    with pytest.raises(ChunkSplitError) as exc:
        split_oversized_chunks([c], standard_id="ISA-999")
    assert "single table row" in str(exc.value)


# ---------------------------------------------------------------------------
# 5. F4 Pass 2 suffix 와 split suffix 공존 검증
# ---------------------------------------------------------------------------


def test_split_composes_after_pass2_suffix() -> None:
    """F4 collision suffix 가 붙은 chunk_id (`...#2237`) 를 split 하면
    `...#2237#1` 형태로 덧붙어 충돌 없이 고유해야 함."""
    base = _make_table_chunk(rows=80, cell_filler="긴 정의." * 5)
    # F4-like Pass 2 suffix 부착된 입력으로 만들기.
    c = dataclasses.replace(base, chunk_id=base.chunk_id + "#2237")
    out = split_oversized_chunks([c], standard_id="ISA-1200")
    assert out[0].chunk_id.endswith("#2237")
    for i, sub in enumerate(out[1:], start=1):
        assert sub.chunk_id == f"{c.chunk_id}#{i}"
        assert "#2237#" in sub.chunk_id
    # assert_chunk_id_uniqueness 통과 검증.
    assert_chunk_id_uniqueness(out)


# ---------------------------------------------------------------------------
# 6. 통합 — ISA-1200 실측
# ---------------------------------------------------------------------------


def test_isa_1200_table_splits_into_three_parts() -> None:
    _require_md_dir()
    p = parse_md(MD_DIR / "ISA-1200.md")
    assert p is not None
    parts = [c for c in p.chunks if c.chunk_of > 1]
    assert len(parts) == 3, f"ISA-1200 table 3 조각 기대, got {len(parts)}"
    # chunk_index 0,1,2 순
    parts_sorted = sorted(parts, key=lambda x: x.chunk_index)
    assert [c.chunk_index for c in parts_sorted] == [0, 1, 2]
    assert all(c.chunk_of == 3 for c in parts_sorted)
    # part_of 관계
    first = parts_sorted[0]
    assert first.part_of is None
    for later in parts_sorted[1:]:
        assert later.part_of == first.chunk_id
    # 모든 조각 토큰 ≤ SOFT_LIMIT
    for c in parts_sorted:
        assert c.token_estimate <= SOFT_LIMIT, f"{c.chunk_id}: {c.token_estimate}"
    # header 복제
    assert first.table_cells is not None
    header = first.table_cells[0]
    for later in parts_sorted[1:]:
        assert later.table_cells is not None
        assert later.table_cells[0] == header


def test_all_isa_no_chunks_exceed_soft_limit_after_split() -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR)
    over = [
        (p.standard.standard_id, c.chunk_id, c.token_estimate, c.kind)
        for p in parsed
        for c in p.chunks
        if c.token_estimate > SOFT_LIMIT and c.kind != "block_quote"
    ]
    # block_quote 는 atomic 이므로 초과 허용. 그 외 kind 는 0 이어야 함.
    assert over == [], f"post-split over-limit (non-quote): {over}"


def test_all_isa_chunk_ids_unique_after_split() -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR)
    all_ids = [c.chunk_id for p in parsed for c in p.chunks]
    assert len(all_ids) == len(set(all_ids)), "split 후 전역 chunk_id 충돌"


def test_paragraph_links_target_exists_after_split() -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR)
    for p in parsed:
        by_id = {c.chunk_id: c for c in p.chunks}
        for link in p.paragraph_links:
            assert link.source in by_id, f"{p.standard.standard_id}: 없는 source {link.source}"
            assert link.target in by_id, f"{p.standard.standard_id}: 없는 target {link.target}"


# ---------------------------------------------------------------------------
# 7. Critic β-1 — chunk_id suffix chain 2-level guard
# ---------------------------------------------------------------------------


def test_suffix_chain_two_level_guard(capsys: pytest.CaptureFixture[str]) -> None:
    """Critic β-1 (docs/checkpoint_4_prep.md §1.8) — 재분할 대상 chunk 가
    이미 Pass 3 split 결과 (``chunk_of > 1``) 인 경우:

    * 분할 금지 (결과에 원본 그대로 포함)
    * stderr 에 warning 로그 출력 ("2-level suffix guard")
    * ChunkSplitError 미발생 (atomic passthrough 와 동일 의미)

    Phase 4b-1 현 시점 split 경로는 1회만 호출되어 ``chunk_of > 1`` 재진입이
    발생하지 않음 — 본 가드는 future-safe (Phase 4b-2 ISQMTable/ASSR 2차 split
    경로 확장 시 자동 발동).

    **판정 기준**: chunk metadata (``chunk_of``). chunk_id 문자열 파싱 방식은
    fallback ``{kind}#{source_idx}`` 의 natural ``#`` 와 suffix chain ``#`` 를
    구분할 수 없어 false-positive 를 유발함 — metadata semantic 이 안전.
    """
    # SOFT_LIMIT 초과 보장.
    base = _make_table_chunk(rows=150, cell_filler="매우 긴 정의 텍스트 내용. " * 10)
    assert base.token_estimate > SOFT_LIMIT, (
        f"factory sanity: token_estimate={base.token_estimate} 이 SOFT_LIMIT 초과여야 함"
    )
    # chunk_of = 3 (이미 3-way split 완료) + chunk_index = 1 (두 번째 조각) 로
    # 설정 — Pass 3 재호출 시 3-level suffix 를 유발할 상태.
    already_split = dataclasses.replace(
        base,
        chunk_id=base.chunk_id + "#1",  # split suffix 포함 (semantic consistency)
        chunk_of=3,
        chunk_index=1,
        part_of=base.chunk_id,
    )

    out = split_oversized_chunks([already_split], standard_id="ISA-1200")

    # 1) 분할 금지 — 입력 그대로 1 건만 반환.
    assert len(out) == 1, f"chunk_of>1 은 분할 금지, got {len(out)} parts"
    assert out[0].chunk_id == already_split.chunk_id
    assert out[0].chunk_of == 3  # metadata 보존
    # 2) ChunkSplitError 미발생 — silent passthrough.
    # 3) 로그 검증 — stderr 에 "2-level suffix guard" 문자열 포함.
    err = capsys.readouterr().err
    assert "2-level suffix guard" in err, (
        f"expected warning 'guard' in stderr, got: {err!r}"
    )
    assert already_split.chunk_id in err, "warning 에 chunk_id 포함되어야 함"
    assert "chunk_of=3" in err, "warning 에 metadata (chunk_of) 포함되어야 함"


def test_suffix_chain_guard_precedes_atomic_check() -> None:
    """2-level suffix 가드가 ATOMIC_KINDS / LIST_KINDS 체크보다 우선.

    예: kind='bullet' + chunk_of > 1 edge — guard 가 먼저 발동해 silent
    passthrough. bullet atomicity 위반 ``ChunkSplitError`` 은 발동하지 않음.
    """
    base = _make_chunk(
        chunk_id="ISA-300:requirements:aaaaaaaa:7.#0",
        kind="bullet",
        content_text="긴 bullet. " * 2000,  # SOFT_LIMIT 초과
    )
    already_split = dataclasses.replace(base, chunk_of=2, chunk_index=0)
    # guard 가 먼저 잡아야 — ChunkSplitError raise 되지 않음.
    out = split_oversized_chunks([already_split], standard_id="ISA-300")
    assert len(out) == 1
    assert out[0].chunk_id == already_split.chunk_id
    assert out[0].chunk_of == 2
