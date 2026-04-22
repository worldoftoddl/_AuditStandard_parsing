"""Stage 2a Pass 3 — 4000 토큰 초과 청크 분할 (json_schema.md §9.3 / §9.4).

`md_parser.parse_md` 가 Pass 1 chunk 조립 + Pass 2 collision suffix 부착을 마친
뒤, 본 모듈의 ``split_oversized_chunks`` 를 호출해 Upstage Solar passage API
상한 (4000 tokens) 을 넘는 청크를 §9.3 우선순위 (문단 > 문장 > 문자) 와 §9.4
테이블 규약 (row-wise split + header row 복제) 으로 분할한다.

설계 원칙:

1. **Idempotency 최우선 (§8.1)** — 첫 조각의 ``chunk_id`` 는 **입력 값 그대로**
   유지. 후속 조각만 ``#{chunk_index}`` suffix 를 부착. 재-임베딩 안정성.
2. **원자성 보호** — ``block_quote`` / ``unknown_numbering`` / ``bullet``
   / ``sub_item`` 은 분할 금지 (§9.4 quote 예외 + list item atomicity).
3. **Header 복제 (§9.4)** — table row-wise split 에서 첫 행(header) 을 모든
   subchunk 에 복제. Embedding bias 우려는 정확히 1 행만 복제하여 최소화.
4. **F4 Pass 2 suffix 호환** — 입력 ``chunk_id`` 가 ``...#2237`` 같은 Pass 2
   suffix 를 이미 포함해도, split 은 그 뒤에 단순히 ``#{chunk_index}`` 를 덧붙여
   ``...#2237#1`` 같이 깨끗이 합성 (§6.4 표 case 4).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from typing import Final

from audit_parser.ingest.types import ChunkRecord

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

SOFT_LIMIT: Final = 3500  # 분할 trigger (json_schema.md §9.3)
HARD_LIMIT: Final = 4000  # Upstage Solar passage API 상한 (monitoring 용)

# 분할 금지 kind — §9.4 + list item atomicity.
_ATOMIC_KINDS: Final = frozenset({"block_quote", "unknown_numbering"})
_LIST_KINDS: Final = frozenset({"bullet", "sub_item"})

# Critic β-1 (docs/checkpoint_4_prep.md §1.8) — chunk_id suffix chain
# 최대 2-level: F4 collision ``#source_idx`` (Pass 2) + split ``#chunk_index``
# (Pass 3). 재분할 (이미 Pass 3 를 거쳐 chunk_of > 1 인 chunk 를 Pass 3 재
# 호출) 은 3-level suffix 를 유발하므로 금지 — 분할 스킵 + warning 로그 →
# Domain Reviewer 수동 개입.
#
# 판정 기준은 **chunk metadata (chunk_of > 1)** — chunk_id 문자열 파싱은
# fallback ``{kind}#{source_idx}`` 의 natural ``#`` 와 suffix chain 의 ``#`` 를
# 구분 불가 (예: ``table#1669#2237`` 은 legitimate Pass 2 결과, ``table#1669#2237#1``
# 은 3-level). metadata 기반은 semantic 직접 검증이라 false-positive 없음.
# md_parser 가 split 을 1회만 호출하므로 현 시점 trigger 가능성 0 — future-safe
# (Phase 4b-2 ISQMTable/ASSR 2차 split 경로 확장 시 자동 발동).

# 한국어 + 영문 문장 종결 패턴. 문장부호 뒤 공백/개행을 경계로 split.
_SENTENCE_BOUNDARY_RE: Final = re.compile(r"(?<=[.!?。!?])\s+|(?<=[다요]\.)\s+|(?<=까\?)\s+")


class ChunkSplitError(RuntimeError):
    """분할 불가 케이스 (§9.4 edge).

    - `bullet` / `sub_item` 이 3,500 tokens 초과 — list item atomicity 위반.
    - table 의 단일 row 가 3,500 tokens 초과 — row 원자성 보호 위해 raise.
    """


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def split_oversized_chunks(
    chunks: Sequence[ChunkRecord],
    *,
    standard_id: str,
    soft_limit: int = SOFT_LIMIT,
) -> tuple[ChunkRecord, ...]:
    """token_estimate > soft_limit 인 chunk 를 §9.3/§9.4 규약으로 분할.

    Args:
        chunks: Pass 2 (collision suffix) 완료된 ChunkRecord 튜플.
        standard_id: 기준서 id (디버그 메시지용, chunk_id 내부 prefix 와 일치).
        soft_limit: 분할 trigger threshold. 기본값 ``SOFT_LIMIT`` (3500).

    Returns:
        분할 결과 tuple. 초과 chunk 가 없으면 입력 그대로 반환 (동일 객체).

    Raises:
        ChunkSplitError: list kind 초과 또는 단일 table row 초과 (분할 불가).
    """
    if not chunks:
        return tuple(chunks)
    # 초과 chunk 가 없으면 원본 그대로 (hot path 회피).
    if all(c.token_estimate <= soft_limit for c in chunks):
        return tuple(chunks)

    out: list[ChunkRecord] = []
    for c in chunks:
        if c.token_estimate <= soft_limit:
            out.append(c)
            continue
        # Critic β-1 (Phase 4b-1 §1.8) — 재분할 대상 chunk 가 이미 Pass 3 를
        # 거친 split 결과 (chunk_of > 1) 라면 추가 split 은 3-level suffix chain
        # 을 유발하므로 분할 금지 + 경고 로그 → manual intervention.
        if c.chunk_of > 1:
            print(
                f"[chunk_splitter] 2-level suffix guard: standard={standard_id} "
                f"chunk={c.chunk_id} kind={c.kind} tokens={c.token_estimate} "
                f"(> {soft_limit}, chunk_of={c.chunk_of} — 이미 split 완료, "
                f"3-level split 금지 — Critic β-1 / "
                f"docs/checkpoint_4_prep.md §1.8). Domain Reviewer 수동 개입.",
                file=sys.stderr,
            )
            out.append(c)
            continue
        if c.kind in _ATOMIC_KINDS:
            print(
                f"[chunk_splitter] atomic passthrough: standard={standard_id} "
                f"chunk={c.chunk_id} kind={c.kind} tokens={c.token_estimate} "
                f"(> {soft_limit}, 분할 금지)",
                file=sys.stderr,
            )
            out.append(c)
            continue
        if c.kind in _LIST_KINDS:
            raise ChunkSplitError(
                f"list item over soft_limit: standard={standard_id} "
                f"chunk={c.chunk_id} kind={c.kind} tokens={c.token_estimate} "
                f"(bullet/sub_item atomicity 위반)"
            )
        if c.kind == "table":
            out.extend(_split_table(c, soft_limit=soft_limit))
            continue
        out.extend(_split_paragraph(c, soft_limit=soft_limit))
    return tuple(out)


# ---------------------------------------------------------------------------
# 내부 — table 분할 (§9.4)
# ---------------------------------------------------------------------------


def _split_table(chunk: ChunkRecord, *, soft_limit: int) -> list[ChunkRecord]:
    """row-wise split + header 복제. 단일 row > soft_limit 이면 raise."""
    # 토큰 카운터는 md_parser 의 공개 헬퍼 재사용 (순환 import 회피 위해 지연 import).
    from audit_parser.ingest.md_parser import count_tokens

    if chunk.table_cells is None or len(chunk.table_cells) < 2:
        # header 만 있거나 데이터가 없으면 분할 불가 — 그대로 반환.
        return [chunk]
    header = chunk.table_cells[0]
    body = chunk.table_cells[1:]
    header_md = _row_to_md(header)
    sep_md = "| " + " | ".join(["---"] * len(header)) + " |"
    header_cost = count_tokens(header_md + "\n" + sep_md)

    buckets: list[list[tuple[str, ...]]] = []
    cur_rows: list[tuple[str, ...]] = []
    cur_cost = header_cost
    for body_row in body:
        row_md = _row_to_md(body_row)
        row_cost = count_tokens(row_md)
        if row_cost + header_cost > soft_limit:
            raise ChunkSplitError(
                f"single table row exceeds soft_limit: chunk={chunk.chunk_id} "
                f"row_tokens={row_cost} header_tokens={header_cost} "
                f"soft_limit={soft_limit}"
            )
        if cur_cost + row_cost > soft_limit and cur_rows:
            buckets.append(cur_rows)
            cur_rows = []
            cur_cost = header_cost
        cur_rows.append(body_row)
        cur_cost += row_cost
    if cur_rows:
        buckets.append(cur_rows)

    if len(buckets) <= 1:
        # 모든 row 가 1 bucket 에 들어갔다면 재분할 불필요 (token_estimate 재계산만
        # 필요할 수 있으나 상한 이내).
        return [chunk]

    subs: list[ChunkRecord] = []
    for idx, rows in enumerate(buckets):
        cells = (header, *rows)
        row_md_lines = [_row_to_md(r) for r in rows]
        new_md = "\n".join([header_md, sep_md, *row_md_lines])
        new_text = "\n".join(_cells_to_text_lines(cells))
        new_tokens = count_tokens(new_text)
        new_chunk_id = _build_split_chunk_id(chunk.chunk_id, idx)
        subs.append(
            ChunkRecord(
                chunk_id=new_chunk_id,
                paragraph_id=chunk.paragraph_id,
                kind=chunk.kind,
                section=chunk.section,
                appendix_index=chunk.appendix_index,
                heading_trail=chunk.heading_trail,
                heading_trail_hash=chunk.heading_trail_hash,
                content_text=new_text,
                content_markdown=new_md,
                authority=chunk.authority,
                parent_paragraph_id=chunk.parent_paragraph_id,
                is_application_guidance=chunk.is_application_guidance,
                token_estimate=new_tokens,
                chunk_index=idx,
                chunk_of=len(buckets),
                source_idx=chunk.source_idx,
                part_of=None if idx == 0 else chunk.chunk_id,
                table_cells=cells,
                embedding=chunk.embedding,
                embedded_at=chunk.embedded_at,
                embedding_model=chunk.embedding_model,
            )
        )
    return subs


def _row_to_md(row: Sequence[str]) -> str:
    return "| " + " | ".join(row) + " |"


def _cells_to_text_lines(cells: Sequence[Sequence[str]]) -> list[str]:
    """table_cells → content_text 후보 라인 (markdown pipe 제외, cell 을 공백 join).

    ``_to_plain_text`` 와 대칭 — row 당 공백 구분 단일 문자열. content_text 의
    용도는 embedding 이므로 구분자 의미 보존보다 가독성 우선.
    """
    return [" ".join(cell.strip() for cell in row) for row in cells]


# ---------------------------------------------------------------------------
# 내부 — 문단 분할 (§9.3)
# ---------------------------------------------------------------------------


def _split_paragraph(chunk: ChunkRecord, *, soft_limit: int) -> list[ChunkRecord]:
    """문단 경계 > 문장 경계 > 강제 문자 경계 3-tier greedy."""
    from audit_parser.ingest.md_parser import count_tokens

    text = chunk.content_text
    markdown = chunk.content_markdown

    # 1차 — 문단 (\n\n 기준).
    segments = _split_by_paragraph(text)
    buckets = _greedy_pack(segments, soft_limit=soft_limit)
    # 2차 — 문장 경계 (문단 하나가 여전히 초과 시 재split).
    if _any_over(buckets, soft_limit):
        expanded: list[str] = []
        for seg in segments:
            if count_tokens(seg) > soft_limit:
                expanded.extend(_split_by_sentence(seg))
            else:
                expanded.append(seg)
        buckets = _greedy_pack(expanded, soft_limit=soft_limit)
    # 3차 — 강제 char slice.
    if _any_over(buckets, soft_limit):
        print(
            f"[chunk_splitter] forced char-split: chunk={chunk.chunk_id} "
            f"tokens={chunk.token_estimate} (문단/문장 경계 분할로 해소 불가)",
            file=sys.stderr,
        )
        buckets = _slice_by_chars(text, soft_limit=soft_limit)

    if len(buckets) <= 1:
        return [chunk]

    # markdown 은 text bucket 과 동일한 경계로 분할 시도 (1:1 매핑 어려우면 text 사용).
    md_buckets = _align_markdown(markdown, buckets)

    subs: list[ChunkRecord] = []
    for idx, (text_seg, md_seg) in enumerate(zip(buckets, md_buckets, strict=True)):
        new_chunk_id = _build_split_chunk_id(chunk.chunk_id, idx)
        subs.append(
            ChunkRecord(
                chunk_id=new_chunk_id,
                paragraph_id=chunk.paragraph_id,
                kind=chunk.kind,
                section=chunk.section,
                appendix_index=chunk.appendix_index,
                heading_trail=chunk.heading_trail,
                heading_trail_hash=chunk.heading_trail_hash,
                content_text=text_seg,
                content_markdown=md_seg,
                authority=chunk.authority,
                parent_paragraph_id=chunk.parent_paragraph_id,
                is_application_guidance=chunk.is_application_guidance,
                token_estimate=count_tokens(text_seg),
                chunk_index=idx,
                chunk_of=len(buckets),
                source_idx=chunk.source_idx,
                part_of=None if idx == 0 else chunk.chunk_id,
                table_cells=None,
                embedding=chunk.embedding,
                embedded_at=chunk.embedded_at,
                embedding_model=chunk.embedding_model,
            )
        )
    return subs


def _split_by_paragraph(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_by_sentence(text: str) -> list[str]:
    parts = _SENTENCE_BOUNDARY_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _greedy_pack(segments: Sequence[str], *, soft_limit: int) -> list[str]:
    """토큰 예산 내에서 segments 를 bucket 단위로 greedy append."""
    from audit_parser.ingest.md_parser import count_tokens

    out: list[str] = []
    cur: list[str] = []
    cur_tok = 0
    for seg in segments:
        seg_tok = count_tokens(seg)
        if cur_tok + seg_tok > soft_limit and cur:
            out.append("\n\n".join(cur))
            cur = []
            cur_tok = 0
        cur.append(seg)
        cur_tok += seg_tok
    if cur:
        out.append("\n\n".join(cur))
    return out


def _any_over(buckets: Sequence[str], soft_limit: int) -> bool:
    from audit_parser.ingest.md_parser import count_tokens

    return any(count_tokens(b) > soft_limit for b in buckets)


def _slice_by_chars(text: str, *, soft_limit: int) -> list[str]:
    """최후 수단 — token encode 결과를 soft_limit 단위로 slice.

    문장/문단 경계를 무시하므로 semantic drift 발생. 호출 전 stderr warn 필수.
    """
    from audit_parser.ingest.md_parser import _TOKEN_ENCODING

    ids = _TOKEN_ENCODING.encode(text)
    out: list[str] = []
    for i in range(0, len(ids), soft_limit):
        out.append(_TOKEN_ENCODING.decode(ids[i : i + soft_limit]))
    return out


def _align_markdown(markdown: str, text_buckets: Sequence[str]) -> list[str]:
    """markdown 을 text bucket 수만큼 분할.

    대충 비례 기반 — text_bucket 수와 문단 분할 경계를 일치시킨다. 실측 0 건
    경로이므로 간단한 근사. 경계 불일치 시 text 를 markdown 대용으로 사용.
    """
    if len(text_buckets) == 1:
        return [markdown]
    parts = re.split(r"\n\s*\n", markdown.strip())
    if len(parts) >= len(text_buckets):
        # 문단 수가 bucket 수 이상 — 비례 bucket.
        buckets_out: list[list[str]] = [[] for _ in text_buckets]
        per = max(1, len(parts) // len(text_buckets))
        for i, p in enumerate(parts):
            target = min(i // per, len(text_buckets) - 1)
            buckets_out[target].append(p)
        return ["\n\n".join(b) for b in buckets_out]
    # fallback — text 를 markdown 대용 (semantic loss 없음, 단 포맷 소실).
    return list(text_buckets)


# ---------------------------------------------------------------------------
# 내부 — chunk_id 합성 (§6.4 split suffix)
# ---------------------------------------------------------------------------


def _build_split_chunk_id(original_id: str, chunk_index: int) -> str:
    """첫 조각(idx=0) 은 원본 id 그대로, 후속은 ``#{chunk_index}`` 부착.

    §6.4 표 case 2/4/6 구현 — Pass 2 suffix (``...#2237``) 가 이미 붙어있어도
    추가로 ``...#2237#1`` 합성 가능.
    """
    if chunk_index == 0:
        return original_id
    return f"{original_id}#{chunk_index}"


__all__ = [
    "HARD_LIMIT",
    "SOFT_LIMIT",
    "ChunkSplitError",
    "split_oversized_chunks",
]
