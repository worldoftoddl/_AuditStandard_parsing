"""Stage 2a 메인 파서 — ``output/md/ISA-<nnn>.md`` → ``ParsedStandard``.

본 모듈은 Phase 1 `md_renderer.py` 가 생산한 Structured Markdown 을 역파싱해
`docs/json_schema.md` v1.1 스펙의 `ParsedStandard` 를 조립한다.

파이프라인 (5 단계):

1. ``_parse_frontmatter`` — YAML frontmatter (``---``…``---``) → `StandardRecord`.
   ``standard_id: null`` (prelude, 00_전문.md) 는 ``None`` 반환 + stdout 로그.
2. ``_parse_body`` — 라인 스캐너. heading/HTML 주석 분기로 heading_trail 스택
   복원 + 직전 content 묶음 축적.
3. ``_assemble_chunks`` — content 묶음 + HTML 주석 메타 → `ChunkRecord`
   (chunk_id **Pass 1** candidate — collision 미고려).
4. ``_resolve_chunk_id_collisions`` — chunk_id **Pass 2** — 동일 id 의 모든
   참여자에게 ``#{source_idx}`` suffix 부착 (first-only 금지, 결정적).
5. ``_build_paragraph_links`` — ``application_guidance`` chunks 에서
   ``parent_paragraph_id`` 매칭 → ``guidance_of`` 링크.
6. ``assert_chunk_id_uniqueness`` — 최종 emit 전 전역 고유성 가드.

설계 근거: `/home/shin/.claude/plans/rustling-painting-sparrow.md` (Task #2 승인판)
+ 2026-04-21 v1.1 MINOR bump (team-lead 확정).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

import tiktoken

from audit_parser.ingest.types import (
    JSON_SCHEMA_VERSION,
    ChunkRecord,
    ParagraphLink,
    ParsedStandard,
    StandardRecord,
    StandardSummary,
)
from audit_parser.spec import ISA_SPEC, AppendixExtractor, StandardSpec

# ---------------------------------------------------------------------------
# 상수 & 정규식
# ---------------------------------------------------------------------------

_FRONTMATTER_DELIM: Final = "---"
_FRONTMATTER_KEY_VAL_RE: Final = re.compile(r'^([a-zA-Z_]+):\s*(null|"(.*)")\s*$')

_HEADING_RE: Final = re.compile(r"^(#{1,6})\s+(.*)$")
_COMMENT_RE: Final = re.compile(r"^<!--\s*(.*?)\s*-->\s*$")

# HTML 주석 내부 field 단위 (pipe split — escape 대칭 처리 §10.2).
_COMMENT_FIELD_SPLIT_RE: Final = re.compile(r"\s*\|\s*")
_COMMENT_KV_RE: Final = re.compile(r"^([a-z_]+):\s*(.*)$")
_ESCAPED_PIPE_SENTINEL: Final = "￾"  # U+FFFE noncharacter

_APPENDIX_RE: Final = re.compile(r"^보론\s*(\d+)\b")
_APPENDIX_UNNUMBERED_RE: Final = re.compile(r"^보론(?!\s*\d)")

_SCOPE_HEADING_TEXT: Final = "이 감사기준서의 범위"
_APPENDIX_HEADING_TOKEN: Final = "보론 1"

# TOC leak post-filter (I1, Task #6 CP2 rework + Task #7 Critic C-P2-2 MUST-FIX).
# Phase 1 `structure.py` 의 PRE_TOC→TOC→STANDARD_BODY state machine 이 TOC 표
# 2×N 헤더 cell (`목차` / `문단번호`) 을 STANDARD_BODY 로 분류하는 boundary leak
# 이 35/36 ISA 에서 총 70 건 발생. Phase 2 에서 post-filter 로 제거 — Phase 1
# state machine 수정은 CP1 재검증 부담으로 v1.2 미래 작업으로 연기. F4
# canonical suffix / paragraph_links / heading_trail_hash / appendix_index 에
# 영향 없음 (leak 은 전부 paragraph_body + section=None + paragraph_id=None).
_TOC_NOISE: Final = frozenset({"목차", "문단번호"})

# C-P2-5 (Task #7 Critic SHOULD-FIX) — MD frontmatter schema drift fail-fast.
# Phase 1 `md_renderer.py` 의 `SCHEMA_VERSION` 상수와 json_schema.md 의
# `JSON_SCHEMA_VERSION` 은 **독립 카운터** (json_schema.md §2.3). Phase 1 MD
# bump 시 Phase 2 가 silent 하게 잘못된 파싱을 수행하지 않도록 진입부에서
# 명시적으로 supported 집합 확인.
MD_SCHEMA_SUPPORTED: Final = frozenset({"1.0"})

# MD table 구분자 행 regex — `| --- | --- |` 형태. cell-level `\|` escape 는 §10.2
# 규약대로 복원 대상.
_TABLE_SEPARATOR_RE: Final = re.compile(r"^\s*\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|\s*$")
_TABLE_ROW_RE: Final = re.compile(r"^\s*\|.*\|\s*$")

# chunk 대상 kind — json_schema.md §5.4. heading / toc_entry 제외.
_CHUNK_KINDS: Final = frozenset(
    {
        "requirement",
        "application_guidance",
        "sub_item",
        "bullet",
        "paragraph_body",
        "table",
        "block_quote",
        "unknown_numbering",
    }
)

# tiktoken encoder 는 프로세스당 1회 init (가격 ~50ms).
_TOKEN_ENCODING: Final = tiktoken.get_encoding("cl100k_base")


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------


class ChunkIdCollisionError(RuntimeError):
    """Pass 2 suffix 부착 후에도 남은 chunk_id 중복 — fatal.

    v1.1 §6.4 — 2-Pass 알고리즘은 sha1[:8] + ``#{source_idx}`` 조합으로 전역
    고유를 보장하지만, 이론적 하위 충돌 (동일 hash + 동일 source_idx) 은
    ``assert_chunk_id_uniqueness`` 가 감지해 이 예외를 발생시킨다. 발생 시
    heading 텍스트 보강 또는 source_idx 재계수 필요.
    """


class UnsupportedMdSchemaError(ValueError):
    """MD frontmatter ``schema_version`` 이 `MD_SCHEMA_SUPPORTED` 집합 밖 — fatal.

    C-P2-5 (Task #7 Critic SHOULD-FIX). Phase 1 `md_renderer.py` 의
    ``SCHEMA_VERSION`` 이 bump 되었는데 Phase 2 파서가 해당 MINOR/MAJOR 변경에
    대응하지 못한 상태로 JSON 을 생성하면 의미가 달라진 content_text /
    paragraph_id 가 silent 하게 흘러갈 위험이 있다. ``parse_md`` 진입부에서
    fail-fast 로 차단.
    """


# ---------------------------------------------------------------------------
# 공개 헬퍼
# ---------------------------------------------------------------------------


def compute_heading_trail_hash(heading_trail: Sequence[str]) -> str:
    """heading_trail → 8 자리 sha1 hex.

    json_schema.md §6.2 정의 (v1.1) — 각 element ``.strip()`` 적용 후
    ``json.dumps(..., ensure_ascii=False, separators=(",", ":"))`` canonical
    form + sha1(utf-8)[:8].

    ``.strip()`` 정규화는 v1.1 MINOR bump 에서 추가됨 — render 과정에서 공백이
    섞여 들어와도 hash 가 동일하게 유지되도록 보장 (heading 원소 의미 손상 없는
    범위 내 공백 정규화).
    """
    normalized = [h.strip() for h in heading_trail]
    canonical = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha1(canonical.encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:8]


def parse_comment_fields(inner: str) -> dict[str, str]:
    """HTML 주석 내부 ``key: val | key: val`` → dict.

    json_schema.md §10.2 pipe escape 대칭 (U+FFFE sentinel). 현 Phase 1 MD 는
    escape 미사용이나 파서는 향후 ISQM 1 대비 필수 지원.
    """
    placeholder = inner.replace(r"\|", _ESCAPED_PIPE_SENTINEL)
    parts = _COMMENT_FIELD_SPLIT_RE.split(placeholder)
    out: dict[str, str] = {}
    for part in parts:
        m = _COMMENT_KV_RE.match(part)
        if m is None:
            continue
        key = m.group(1)
        val = m.group(2).replace(_ESCAPED_PIPE_SENTINEL, "|")
        out[key] = val
    return out


def count_tokens(text: str) -> int:
    """tiktoken cl100k_base 기반 token 수. Upstage Solar 보수 추정."""
    return len(_TOKEN_ENCODING.encode(text))


def _is_toc_leak_chunk(chunk: ChunkRecord) -> bool:
    """Phase 1 TOC boundary leak 판별 (I1, CP2 rework).

    세 조건 동시 충족 시 TOC 표 header cell (`목차` / `문단번호`) 가 body 로
    분류된 noise chunk:

    1. ``kind == "paragraph_body"``
    2. ``section is None`` (정상 body 는 intro/definitions/requirements/
       application_guidance/appendix 중 하나 부여)
    3. ``content_text.strip()`` ∈ ``{"목차", "문단번호"}``

    F4 canonical suffix, paragraph_links, heading_trail_hash 계산에는 영향
    없음 — 본 chunk 들은 paragraph_id=None 이라 collision 참여도, guidance_of
    target 도 아님.
    """
    if chunk.kind != "paragraph_body" or chunk.section is not None:
        return False
    return (chunk.content_text or "").strip() in _TOC_NOISE


def assert_chunk_id_uniqueness(chunks: Sequence[ChunkRecord]) -> None:
    """Pass 2 이후 chunk_id 전역 고유성 강제 (json_schema.md §6.4 v1.1).

    ``_resolve_chunk_id_collisions`` 가 모든 chunks 에 ``#{source_idx}`` suffix
    를 부착했더라도 이론상 ``(hash, source_idx)`` 2-level 충돌 가능성이 남음.
    본 함수는 최종 emit 직전 중복을 감지해 ``ChunkIdCollisionError`` 를
    raise — md_parser 오염된 JSON 이 downstream 으로 흘러가지 않도록 보장한다.

    Raises:
        ChunkIdCollisionError: 중복 chunk_id 발견 시, 중복 id 와 소속 source_idx
            목록을 메시지에 포함.
    """
    seen: dict[str, list[int]] = {}
    for c in chunks:
        seen.setdefault(c.chunk_id, []).append(c.source_idx)
    dupes = {cid: idxs for cid, idxs in seen.items() if len(idxs) > 1}
    if dupes:
        detail = "; ".join(f"{cid} -> source_idx={idxs}" for cid, idxs in dupes.items())
        raise ChunkIdCollisionError(f"duplicate chunk_id after Pass 2: {detail}")


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def parse_md(
    md_path: Path,
    *,
    spec: StandardSpec | None = None,
) -> ParsedStandard | None:
    """단일 MD 파일 파싱. prelude(standard_id: null) → None 반환.

    v1.1: 최종 return 직전 ``assert_chunk_id_uniqueness`` 를 호출해 기준서 범위
    내 전역 chunk_id 고유성을 강제한다. Pass 2 (``_resolve_chunk_id_collisions``)
    가 sha1[:8] 충돌 시에도 ``#{source_idx}`` suffix 로 해소하지만, 극히 낮은
    확률의 2-level 충돌 (동일 hash + 동일 source_idx) 을 대비해 최종 가드로
    ``ChunkIdCollisionError`` 를 발생시킨다.

    v1.2 (Phase 4b-1): ``spec: StandardSpec`` 주입. ``ISA_SPEC`` default 로 기존
    콜러 backward-compat 유지. ``spec.validate_standard_id`` 가 frontmatter 의
    ``standard_id`` 를 해당 spec prefix alt 에 fail-fast 매칭. ``spec.appendix_extractor``
    가 heading_trail 내부 보론 heading 을 ``(appendix_index, special_appendix_name)``
    로 변환 (B-v2 — Critic 2026-04-22).

    v1.2 (Phase 4c c2): ``spec=None`` default 채택 — frontmatter ``standard_id``
    prefix 로 ``get_spec_for_standard_id`` 자동 dispatch. ISA backward-compat:
    frontmatter standard_id 가 ``ISA-*`` 이면 ISA_SPEC 이 자연 선택되므로 기존
    36 ISA JSON 바이트 동등 보장. Explicit ``spec=ISA_SPEC`` / ``spec=ISQM_SPEC``
    override 도 여전히 허용 (테스트용 / prelude 00_전문.md 의 standard_id=null
    처리용).
    """
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    frontmatter, body_start = _parse_frontmatter(lines)

    # C-P2-5 fail-fast — Phase 1 MD schema drift 조기 차단. prelude 포함 모든
    # MD 가 대상 (skip 결정 이전에 수행) — 미래 MD schema bump 시 prelude/ISA
    # 양쪽 모두 drift 감지.
    md_schema_version = frontmatter.get("schema_version", "__MISSING__")
    if md_schema_version not in MD_SCHEMA_SUPPORTED:
        raise UnsupportedMdSchemaError(
            f"{md_path.name}: unsupported MD schema_version={md_schema_version!r} "
            f"(supported: {sorted(MD_SCHEMA_SUPPORTED)})"
        )

    if frontmatter.get("standard_id") == "__NULL__":
        # prelude 또는 00_전문.md — JSON 생성 대상 아님.
        print(f"skipped_file: {md_path.name} (standard_id: null)", file=sys.stdout)
        return None

    standard = _build_standard_record(frontmatter)
    # v1.2 (c2) — spec auto-dispatch when not explicitly provided. Uses frontmatter
    # standard_id prefix → SPEC_REGISTRY lookup. Explicit ``spec=ISA_SPEC`` caller
    # override still honoured (backward-compat + test injection).
    if spec is None:
        from audit_parser.spec import get_spec_for_standard_id
        spec = get_spec_for_standard_id(standard.standard_id)
    # v1.2 — spec prefix alt 매칭 검증 (fail-fast). Auto-dispatched spec 은 이미
    # ``get_spec_for_standard_id`` 내부에서 validate 되었으나 explicit override 는
    # 여전히 prefix 불일치 가능 — 2중 guard.
    spec.validate_standard_id(standard.standard_id)
    raw_chunks, scope_parts, definitions_parts = _parse_body(
        lines[body_start:], standard.standard_no
    )
    chunks = tuple(
        _assemble_chunks(raw_chunks, standard.authority_base, standard.standard_id, spec=spec)
    )
    # I1 (CP2 rework) — Phase 1 TOC boundary leak 후처리.
    chunks = tuple(c for c in chunks if not _is_toc_leak_chunk(c))
    chunks = _resolve_chunk_id_collisions(chunks)
    # Pass 3 — 4000 토큰 초과 청크 분할 (§9.3/§9.4). 지연 import 로 순환 회피.
    from audit_parser.ingest.chunk_splitter import split_oversized_chunks

    chunks = split_oversized_chunks(chunks, standard_id=standard.standard_id)
    paragraph_links = _build_paragraph_links(chunks, standard.standard_no)
    summary = _build_summary(scope_parts, definitions_parts)
    # v1.1 최종 고유성 가드 — Pass 2 + Pass 3 후에도 충돌이 남으면 즉시 실패.
    assert_chunk_id_uniqueness(chunks)
    return ParsedStandard(
        schema_version=JSON_SCHEMA_VERSION,
        standard=standard,
        summary=summary,
        chunks=chunks,
        paragraph_links=paragraph_links,
    )


def parse_md_dir(md_dir: Path, *, spec: StandardSpec = ISA_SPEC) -> list[ParsedStandard]:
    """디렉토리 전체 파싱. 00_전문.md skip, ISA-*.md 만 ISA 숫자 오름차순.

    v1.2: ``spec`` 주입. default = ISA_SPEC (backward-compat). Phase 4b-2 의
    ISQM/ASSR/FRMK 전용 디렉토리는 해당 spec 주입 필요.
    """
    results: list[ParsedStandard] = []
    md_files = sorted(
        md_dir.glob("ISA-*.md"),
        key=lambda p: int(p.stem.split("-")[1]),
    )
    for md_path in md_files:
        parsed = parse_md(md_path, spec=spec)
        if parsed is not None:
            results.append(parsed)
    return results


def to_json_dict(parsed: ParsedStandard) -> dict[str, object]:
    """ParsedStandard → JSON 직렬화용 dict. 필드 순서는 json_schema.md §12 준수."""
    return {
        "schema_version": parsed.schema_version,
        "standard": {
            "standard_id": parsed.standard.standard_id,
            "standard_no": parsed.standard.standard_no,
            "standard_title": parsed.standard.standard_title,
            "source_file": parsed.standard.source_file,
            "authority_base": parsed.standard.authority_base,
        },
        "summary": {
            "scope_text": parsed.summary.scope_text,
            "scope_markdown": parsed.summary.scope_markdown,
            "definitions_text": parsed.summary.definitions_text,
            "definitions_markdown": parsed.summary.definitions_markdown,
            "embedding": list(parsed.summary.embedding) if parsed.summary.embedding else None,
            "embedded_at": parsed.summary.embedded_at,
            "embedding_model": parsed.summary.embedding_model,
        },
        "chunks": [_chunk_to_json(c) for c in parsed.chunks],
        "paragraph_links": [
            {"source": link.source, "target": link.target, "link_type": link.link_type}
            for link in parsed.paragraph_links
        ],
    }


# ---------------------------------------------------------------------------
# 내부 — frontmatter
# ---------------------------------------------------------------------------


def _parse_frontmatter(lines: Sequence[str]) -> tuple[dict[str, str], int]:
    """`---` 블록 파싱 → (mapping, body 시작 line idx).

    ``null`` literal 은 sentinel ``"__NULL__"`` 로 normalize (dict 값이 Optional 이
    될 경우 mypy strict 에 걸리지 않도록 str 유지).
    """
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        raise ValueError("Missing frontmatter opening ---")
    result: dict[str, str] = {}
    idx = 1
    while idx < len(lines):
        line = lines[idx].strip()
        if line == _FRONTMATTER_DELIM:
            return result, idx + 1
        m = _FRONTMATTER_KEY_VAL_RE.match(line)
        if m is not None:
            key = m.group(1)
            if m.group(2) == "null":
                result[key] = "__NULL__"
            else:
                quoted = m.group(3)
                # backslash unescape — md_renderer._escape_yaml_string 역.
                result[key] = quoted.replace('\\"', '"').replace("\\\\", "\\")
        idx += 1
    raise ValueError("Missing frontmatter closing ---")


def _build_standard_record(frontmatter: Mapping[str, str]) -> StandardRecord:
    standard_id = frontmatter["standard_id"]
    standard_no = frontmatter["standard_no"]
    standard_title = frontmatter.get("standard_title", "")
    if standard_title == "__NULL__":
        standard_title = ""
    source_file = frontmatter["source_file"]
    return StandardRecord(
        standard_id=standard_id,
        standard_no=standard_no,
        standard_title=standard_title,
        source_file=source_file,
        authority_base=1,
    )


# ---------------------------------------------------------------------------
# 내부 — body 스캔
# ---------------------------------------------------------------------------


class _RawChunk:
    """조립 전 content 묶음 + 메타. 단순 mutable container (private)."""

    __slots__ = (
        "paragraph_id",
        "kind",
        "section",
        "heading_trail",
        "parent_paragraph_id",
        "is_application_guidance",
        "source_idx",
        "content_lines",
    )

    def __init__(
        self,
        *,
        paragraph_id: str | None,
        kind: str,
        section: str | None,
        heading_trail: tuple[str, ...],
        parent_paragraph_id: str | None,
        is_application_guidance: bool,
        source_idx: int,
        content_lines: list[str],
    ) -> None:
        self.paragraph_id = paragraph_id
        self.kind = kind
        self.section = section
        self.heading_trail = heading_trail
        self.parent_paragraph_id = parent_paragraph_id
        self.is_application_guidance = is_application_guidance
        self.source_idx = source_idx
        self.content_lines = content_lines


_SummaryPart = tuple[tuple[str, ...], list[str]]


def _parse_body(
    lines: Sequence[str],
    standard_no: str,
) -> tuple[list[_RawChunk], list[_SummaryPart], list[_SummaryPart]]:
    """body → raw chunks + summary 추출 보조.

    Returns:
        (raw_chunks, scope_parts, definitions_parts) — scope/definitions 는
        (heading_trail snapshot, content_markdown lines) 튜플 리스트로 저장하여
        Summary 조립 시 markdown/text 양쪽 복원 가능.
    """
    raw_chunks: list[_RawChunk] = []
    scope_parts: list[_SummaryPart] = []
    definitions_parts: list[_SummaryPart] = []

    # heading_trail 스택 — index 0 = heading level 1.
    heading_stack: list[str] = []
    pending_content: list[str] = []
    current_section: str | None = None

    for line in lines:
        stripped = line.rstrip("\r")
        comment_match = _COMMENT_RE.match(stripped)
        heading_match = _HEADING_RE.match(stripped)

        if heading_match is not None and comment_match is None:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).rstrip()
            _push_heading(heading_stack, level, heading_text)
            pending_content = []
            continue

        if comment_match is not None:
            inner = comment_match.group(1)
            fields = parse_comment_fields(inner)
            new_section = _handle_comment_line(
                fields=fields,
                heading_stack=heading_stack,
                current_section=current_section,
                pending_content=pending_content,
                raw_chunks=raw_chunks,
                scope_parts=scope_parts,
                definitions_parts=definitions_parts,
                standard_no=standard_no,
            )
            current_section = new_section
            pending_content = []
            continue

        if stripped == "":
            pending_content.append("")
            continue
        pending_content.append(stripped)

    return raw_chunks, scope_parts, definitions_parts


def _handle_comment_line(
    *,
    fields: Mapping[str, str],
    heading_stack: list[str],
    current_section: str | None,
    pending_content: list[str],
    raw_chunks: list[_RawChunk],
    scope_parts: list[_SummaryPart],
    definitions_parts: list[_SummaryPart],
    standard_no: str,
) -> str | None:
    """HTML 주석 1 개 처리 + 필요 시 raw_chunk/summary append.

    Returns:
        갱신된 current_section (heading 주석의 ``section:`` 키가 섹션 전이 신호).
    """
    # 1) heading 주석 — `section:` 또는 단일 `idx:` 만.
    if "para" not in fields and "kind" not in fields:
        if "section" in fields:
            return fields["section"]
        return current_section
    # 2) chunk 주석.
    kind = fields["kind"]
    if kind not in _CHUNK_KINDS:
        return current_section
    source_idx = int(fields["idx"])
    paragraph_id = fields.get("para")
    parent = fields.get("parent")
    is_app_guidance = kind == "application_guidance"
    trail = tuple(heading_stack)
    content_lines = _tidy_pending_content(pending_content)
    raw_chunks.append(
        _RawChunk(
            paragraph_id=paragraph_id,
            kind=kind,
            section=current_section,
            heading_trail=trail,
            parent_paragraph_id=parent,
            is_application_guidance=is_app_guidance,
            source_idx=source_idx,
            content_lines=content_lines,
        )
    )
    # Summary 수집 — scope (heading_trail 끝이 범위) / definitions (section).
    if trail and trail[-1] == _SCOPE_HEADING_TEXT:
        scope_parts.append((trail, list(content_lines)))
    if current_section == "definitions":
        definitions_parts.append((trail, list(content_lines)))
    elif (
        standard_no == "1200"
        and current_section == "appendix"
        and any(h.startswith(_APPENDIX_HEADING_TOKEN) for h in trail)
    ):
        # ISA-1200 `보론 1 용어의 정의` = 용어의 정의 역할 (json_schema.md §4).
        definitions_parts.append((trail, list(content_lines)))
    return current_section


def _push_heading(stack: list[str], level: int, text: str) -> None:
    """heading_stack 을 level 에 맞춰 truncate 후 text push."""
    target_depth = level  # level 1 → depth 1 (index 0 만 보유)
    if target_depth <= 0:
        return
    # level 이 현재 depth 보다 얕거나 같으면 자신 이상 제거.
    while len(stack) >= target_depth:
        stack.pop()
    # depth-1 개까지는 동일 유지, index level-1 에 push.
    while len(stack) < target_depth - 1:
        stack.append("")  # gap-fill (source docx 가 H1 skip 할 때 방어)
    stack.append(text)


def _tidy_pending_content(lines: Iterable[str]) -> list[str]:
    """pending_content 에서 trailing 빈 줄 제거 + leading 빈 줄 제거."""
    buf = list(lines)
    while buf and buf[0] == "":
        buf.pop(0)
    while buf and buf[-1] == "":
        buf.pop()
    return buf


# ---------------------------------------------------------------------------
# 내부 — chunk 조립
# ---------------------------------------------------------------------------


def _assemble_chunks(
    raw_chunks: Iterable[_RawChunk],
    authority_base: int,
    standard_id: str,
    *,
    spec: StandardSpec,
) -> Iterable[ChunkRecord]:
    for raw in raw_chunks:
        heading_trail = raw.heading_trail
        heading_trail_hash = compute_heading_trail_hash(heading_trail)
        content_markdown = "\n".join(raw.content_lines)
        paragraph_id = raw.paragraph_id if raw.paragraph_id else None
        content_text = _to_plain_text(content_markdown, paragraph_id=paragraph_id, kind=raw.kind)
        appendix_index, special_appendix_name = _extract_appendix_data(
            raw.section, heading_trail, spec.appendix_extractor
        )
        table_cells = _extract_table_cells(raw.kind, raw.content_lines)
        # chunk_id 는 collision 미고려 preliminary 형태. _resolve_chunk_id_collisions
        # 가 F4 pair 감지 시 source_idx suffix 부착.
        chunk_id = _build_chunk_id(
            standard_id=standard_id,
            section=raw.section,
            heading_trail_hash=heading_trail_hash,
            paragraph_id=paragraph_id,
            kind=raw.kind,
            source_idx=raw.source_idx,
            collision=False,
        )
        token_estimate = count_tokens(content_text)
        yield ChunkRecord(
            chunk_id=chunk_id,
            paragraph_id=paragraph_id,
            kind=raw.kind,
            section=raw.section,
            appendix_index=appendix_index,
            heading_trail=heading_trail,
            heading_trail_hash=heading_trail_hash,
            content_text=content_text,
            content_markdown=content_markdown,
            authority=authority_base,
            parent_paragraph_id=raw.parent_paragraph_id,
            is_application_guidance=raw.is_application_guidance,
            token_estimate=token_estimate,
            chunk_index=0,
            chunk_of=1,
            source_idx=raw.source_idx,
            special_appendix_name=special_appendix_name,
            part_of=None,
            table_cells=table_cells,
        )


def _resolve_chunk_id_collisions(chunks: tuple[ChunkRecord, ...]) -> tuple[ChunkRecord, ...]:
    """§6.4 확장 의사결정표 — collision 발생 시 `#{source_idx}` suffix 부착.

    동일 ``(standard_id, section, heading_trail_hash, paragraph_id)`` 조합이 2 개
    이상일 때 두 chunk 모두에 source_idx suffix 를 붙여 전역 고유 확보.
    F4 6 쌍 (ISA-250 `12.`, ISA-260 `5.`/`6.`, ISA-300 `7.`/`10.`, ISA-701 `4.`) +
    동일 heading 하위 sub_item `(a)`/`(b)` 등이 주 대상.
    """
    if not chunks:
        return chunks
    grouped: dict[str, list[int]] = {}
    for i, c in enumerate(chunks):
        grouped.setdefault(c.chunk_id, []).append(i)
    colliding_indices: set[int] = set()
    for ids in grouped.values():
        if len(ids) > 1:
            colliding_indices.update(ids)
    if not colliding_indices:
        return chunks
    # 바뀌는 chunk 만 새로 생성 (dataclass.replace 대신 새 객체 생성 for frozen+slots).
    out: list[ChunkRecord] = []
    for i, c in enumerate(chunks):
        if i not in colliding_indices:
            out.append(c)
            continue
        new_id = f"{c.chunk_id}#{c.source_idx}"
        out.append(
            ChunkRecord(
                chunk_id=new_id,
                paragraph_id=c.paragraph_id,
                kind=c.kind,
                section=c.section,
                appendix_index=c.appendix_index,
                heading_trail=c.heading_trail,
                heading_trail_hash=c.heading_trail_hash,
                content_text=c.content_text,
                content_markdown=c.content_markdown,
                authority=c.authority,
                parent_paragraph_id=c.parent_paragraph_id,
                is_application_guidance=c.is_application_guidance,
                token_estimate=c.token_estimate,
                chunk_index=c.chunk_index,
                chunk_of=c.chunk_of,
                source_idx=c.source_idx,
                part_of=c.part_of,
                table_cells=c.table_cells,
                embedding=c.embedding,
                embedded_at=c.embedded_at,
                embedding_model=c.embedding_model,
            )
        )
    return tuple(out)


def _to_plain_text(
    markdown: str,
    *,
    paragraph_id: str | None = None,
    kind: str | None = None,
) -> str:
    """content_markdown → content_text. 탭/leading bullet/HTML 주석 제거 + 공백 normalize."""
    # HTML 주석 제거 (안전장치 — 정상 경로에서는 comment 분기로 들어오지 않으므로 무효).
    no_comments = re.sub(r"<!--.*?-->", "", markdown)
    # 탭 제거, 연속 공백 단일화.
    tabless = no_comments.replace("\t", " ")
    collapsed = re.sub(r"[  ]+", " ", tabless)
    # bullet marker (•) 와 인용 prefix (> ) 제거 — plain 의미 추출 우선.
    cleaned = re.sub(r"^\s*•\s*", "", collapsed, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*>\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\[\?\]\s*", "", cleaned, flags=re.MULTILINE)
    # paragraph_id prefix 제거 — json_schema.md §5 예시 `"7.\t..." → "..."`.
    if paragraph_id and kind in {"requirement", "application_guidance", "sub_item"}:
        pattern = rf"^\s*{re.escape(paragraph_id)}\s+"
        cleaned = re.sub(pattern, "", cleaned, count=1)
    # 여러 줄 → 단일 문자열 (개행 유지로 문단 경계 보존).
    return cleaned.strip()


def _extract_table_cells(
    kind: str,
    content_lines: Sequence[str],
) -> tuple[tuple[str, ...], ...] | None:
    """json_schema.md §5.1 ``table_cells`` 추출.

    - ``kind == "table"`` → MD table row inverse-parse (separator 행 skip,
      cell 별 ``\\|`` / ``\\\\`` unescape, ``<br>`` → 실제 개행 복원).
    - ``kind == "block_quote"`` → 1×1 그리드로 승격 (원본 quote 텍스트 단일 cell).
    - 그 외 → ``None``.
    """
    if kind == "table":
        rows: list[tuple[str, ...]] = []
        for line in content_lines:
            if not _TABLE_ROW_RE.match(line):
                continue
            if _TABLE_SEPARATOR_RE.match(line):
                continue
            rows.append(_split_table_row(line))
        return tuple(rows) if rows else None
    if kind == "block_quote":
        stripped = [re.sub(r"^\s*>\s?", "", ln) for ln in content_lines if ln]
        joined = "\n".join(stripped).strip()
        return ((joined,),)
    return None


def _split_table_row(line: str) -> tuple[str, ...]:
    """MD table row → cell tuple. ``\\|`` escape 대칭 (§10.2)."""
    protected = line.replace(r"\|", _ESCAPED_PIPE_SENTINEL)
    stripped = protected.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    parts = stripped.split("|")
    cells: list[str] = []
    for p in parts:
        cell = p.strip()
        cell = cell.replace(_ESCAPED_PIPE_SENTINEL, "|")
        cell = cell.replace("<br>", "\n")
        cell = cell.replace("\\\\", "\\")
        cells.append(cell)
    return tuple(cells)


def _extract_appendix_index(section: str | None, heading_trail: Sequence[str]) -> int | None:
    """Legacy shim — 기존 ISA-only 호출부가 튜플 unpack 없이 int 만 요구.

    v1.2 주입형 콜러는 ``_extract_appendix_data`` 를 직접 사용. 본 함수는
    ISA_SPEC 기본 extractor 를 경유하여 backward-compat 을 유지한다.
    """
    idx, _name = _extract_appendix_data(section, heading_trail, ISA_SPEC.appendix_extractor)
    return idx


def _extract_appendix_data(
    section: str | None,
    heading_trail: Sequence[str],
    appendix_extractor: AppendixExtractor,
) -> tuple[int | None, str | None]:
    """v1.2 B-v2 (Domain Reviewer 2026-04-22) — section=APPENDIX 인 경우만 호출.

    ``heading_trail`` 을 역순 순회하며 ``appendix_extractor`` 가 처음으로
    non-``(None, None)`` 튜플을 반환하는 heading 에서 멈춤. ISA/ISQM/ASSR 은
    extractor 가 ``(N, None)`` 또는 ``(1, None)`` 반환. FRMK 만
    un-numbered 보론 heading 에서 ``(None, <title>)`` 반환.
    """
    if section != "appendix":
        return None, None
    for heading in reversed(heading_trail):
        idx, name = appendix_extractor(heading)
        if idx is not None or name is not None:
            return idx, name
    return None, None


def _build_chunk_id(
    *,
    standard_id: str,
    section: str | None,
    heading_trail_hash: str,
    paragraph_id: str | None,
    kind: str,
    source_idx: int,
    chunk_index: int = 0,
    chunk_of: int = 1,
    collision: bool = False,
) -> str:
    """json_schema.md §6.4 확장 의사결정표 — 6 케이스.

    공식: ``{standard_id}:{section}:{heading_trail_hash}:{pid_or_fallback}``
    where ``standard_id = "ISA-" + standard_no`` (v1.1 §6.4 확정).

    ``collision=True`` 이면 ``pid != ""`` + ``chunk_of == 1`` 조합에도
    ``#{source_idx}`` suffix 를 부착 (F4 대응). ``_assemble_chunks`` 는 항상
    False 로 호출하고 ``_resolve_chunk_id_collisions`` 가 사후에 suffix 부착.

    실측 예시 (§6.4 표):
    - ``ISA-300:requirements:a1b2c3d4:8.`` (no collision)
    - ``ISA-300:requirements:aaaaaaaa:7.#2237`` (F4 collision)
    - ``ISA-1200:appendix:c5f9e4a3:table#1669`` (pid="")
    """
    section_token = section or "none"
    base = f"{standard_id}:{section_token}:{heading_trail_hash}"
    if paragraph_id:
        body = f"{base}:{paragraph_id}"
        if collision:
            body = f"{body}#{source_idx}"
        if chunk_of > 1:
            return f"{body}#{chunk_index}"
        return body
    body = f"{base}:{kind}#{source_idx}"
    if chunk_of > 1:
        return f"{body}#{chunk_index}"
    return body


# ---------------------------------------------------------------------------
# 내부 — summary
# ---------------------------------------------------------------------------


def _build_summary(
    scope_parts: Sequence[tuple[tuple[str, ...], list[str]]],
    definitions_parts: Sequence[tuple[tuple[str, ...], list[str]]],
) -> StandardSummary:
    scope_md, scope_text = _aggregate_summary_part(scope_parts)
    defs_md, defs_text = _aggregate_summary_part(definitions_parts)
    # scope_text 가 "" (빈 문자열) 이면 None 으로 정규화 — §4 필드 타입 str | null.
    return StandardSummary(
        scope_text=scope_text,
        scope_markdown=scope_md,
        definitions_text=defs_text,
        definitions_markdown=defs_md,
    )


def _aggregate_summary_part(
    parts: Sequence[tuple[tuple[str, ...], list[str]]],
) -> tuple[str | None, str | None]:
    if not parts:
        return None, None
    md_chunks: list[str] = []
    for _trail, content_lines in parts:
        if not content_lines:
            continue
        md_chunks.append("\n".join(content_lines))
    if not md_chunks:
        return None, None
    markdown = "\n\n".join(md_chunks)
    plain = _to_plain_text(markdown)
    return markdown, plain


# ---------------------------------------------------------------------------
# 내부 — paragraph_links
# ---------------------------------------------------------------------------


def _build_paragraph_links(
    chunks: Sequence[ChunkRecord],
    standard_no: str,
) -> tuple[ParagraphLink, ...]:
    # 기준서 내 paragraph_id → ChunkRecord 인덱스 (F4 대응: heading_trail scope 고려).
    # 단순 map 은 ISA-300 `7.` 중복 케이스에서 잘못 매칭 가능. heading_trail 을
    # ancestor 로 공유하는 가장 가까운 requirement chunk 를 선택.
    by_paragraph: dict[str, list[ChunkRecord]] = {}
    for c in chunks:
        # split 후속 조각 (chunk_index > 0) 은 target 후보 제외 — 원본 첫 조각만
        # guidance_of 링크의 target 이 됨 (§6.3/§9.4 분할 결과 링크 불변).
        if c.paragraph_id and c.kind == "requirement" and c.chunk_index == 0:
            by_paragraph.setdefault(c.paragraph_id, []).append(c)

    links: list[ParagraphLink] = []
    for c in chunks:
        if c.kind != "application_guidance" or c.parent_paragraph_id is None:
            continue
        candidates = by_paragraph.get(c.parent_paragraph_id, [])
        target = _choose_parent_candidate(c, candidates)
        if target is None:
            print(
                f"[md_parser] dangling parent: standard={standard_no} chunk={c.chunk_id} "
                f"parent_paragraph_id={c.parent_paragraph_id}",
                file=sys.stderr,
            )
            continue
        links.append(
            ParagraphLink(
                source=c.chunk_id,
                target=target.chunk_id,
                link_type="guidance_of",
            )
        )
    return tuple(links)


def _choose_parent_candidate(
    source: ChunkRecord,
    candidates: Sequence[ChunkRecord],
) -> ChunkRecord | None:
    """F4 대응 — 여러 후보 중 heading_trail 공유 prefix 가 가장 긴 chunk 선택."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    best: ChunkRecord | None = None
    best_shared = -1
    for cand in candidates:
        shared = _shared_prefix_len(source.heading_trail, cand.heading_trail)
        if shared > best_shared:
            best = cand
            best_shared = shared
    return best


def _shared_prefix_len(a: Sequence[str], b: Sequence[str]) -> int:
    length = 0
    for x, y in zip(a, b, strict=False):
        if x == y:
            length += 1
        else:
            break
    return length


# ---------------------------------------------------------------------------
# 직렬화 helper
# ---------------------------------------------------------------------------


def _chunk_to_json(c: ChunkRecord) -> dict[str, object]:
    table_cells_json: list[list[str]] | None = None
    if c.table_cells is not None:
        table_cells_json = [list(row) for row in c.table_cells]
    return {
        "chunk_id": c.chunk_id,
        "paragraph_id": c.paragraph_id,
        "kind": c.kind,
        "section": c.section,
        "appendix_index": c.appendix_index,
        "special_appendix_name": c.special_appendix_name,
        "heading_trail": list(c.heading_trail),
        "heading_trail_hash": c.heading_trail_hash,
        "content_text": c.content_text,
        "content_markdown": c.content_markdown,
        "authority": c.authority,
        "parent_paragraph_id": c.parent_paragraph_id,
        "is_application_guidance": c.is_application_guidance,
        "token_estimate": c.token_estimate,
        "chunk_index": c.chunk_index,
        "chunk_of": c.chunk_of,
        "source_idx": c.source_idx,
        "part_of": c.part_of,
        "table_cells": table_cells_json,
        "embedding": list(c.embedding) if c.embedding else None,
        "embedded_at": c.embedded_at,
        "embedding_model": c.embedding_model,
    }


__all__ = [
    "MD_SCHEMA_SUPPORTED",
    "ChunkIdCollisionError",
    "UnsupportedMdSchemaError",
    "assert_chunk_id_uniqueness",
    "compute_heading_trail_hash",
    "count_tokens",
    "parse_comment_fields",
    "parse_md",
    "parse_md_dir",
    "to_json_dict",
]
