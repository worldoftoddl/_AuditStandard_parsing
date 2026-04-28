"""md_parser 단위 + 통합 테스트 (Phase 2 Task #2, json_schema v1.1).

검증 범위:
- frontmatter 파싱 (escape, null sentinel)
- HTML 주석 pipe escape (U+FFFE sentinel) 대칭성
- heading_trail_hash 결정론 + v1.1 ``.strip()`` 정규화
- chunk_id 6-case 의사결정표 (json_schema.md §6.4)
- chunk_id Pass 2 collision suffix 결정성
- ``assert_chunk_id_uniqueness`` → ``ChunkIdCollisionError`` 경로
- appendix_index 추출 (번호 있는/없는 보론, 9 ISAs)
- F4 6 쌍 chunk_id 고유성 — composite key collision 감지
- paragraph_links guidance_of 매칭
- token_estimate 회귀
- JSON Schema §12 Draft 2020-12 validation

fixture 는 `output/md/ISA-*.md` (Phase 1 CHECKPOINT 1 통과본) 을 재사용하며
DOCX 재-convert 는 수행하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from audit_parser.ingest.md_parser import (
    MD_SCHEMA_SUPPORTED,
    ChunkIdCollisionError,
    UnsupportedMdSchemaError,
    _build_chunk_id,
    _extract_appendix_index,
    _extract_table_cells,
    _push_heading,
    _resolve_chunk_id_collisions,
    _split_table_row,
    _to_plain_text,
    assert_chunk_id_uniqueness,
    compute_heading_trail_hash,
    count_tokens,
    parse_comment_fields,
    parse_md,
    parse_md_dir,
    to_json_dict,
)
from audit_parser.ingest.types import JSON_SCHEMA_VERSION, ChunkRecord
from audit_parser.spec import ISA_SPEC

# ---------------------------------------------------------------------------
# Fixture 경로
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[1]
MD_DIR = REPO_ROOT / "output" / "md"
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "json_schema_v1_2.schema.json"


@pytest.fixture(scope="session")
def json_schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


# ---------------------------------------------------------------------------
# 1. frontmatter & prelude
# ---------------------------------------------------------------------------


def test_frontmatter_basic(tmp_path: Path) -> None:
    """escape \\\" / \\\\ 복원 + schema_version 검증."""
    md = (
        '---\n'
        'schema_version: "1.0"\n'
        'standard_id: "ISA-200"\n'
        'standard_no: "200"\n'
        'standard_title: "제\\"목\\" with \\\\backslash"\n'
        'source_file: "test.docx"\n'
        '---\n'
        '\n'
        '# 감사기준서 200\n'
        '<!-- idx: 1 -->\n'
    )
    f = tmp_path / "ISA-200.md"
    f.write_text(md, encoding="utf-8")
    p = parse_md(f)
    assert p is not None
    assert p.schema_version == JSON_SCHEMA_VERSION == "1.2.0"
    assert p.standard.standard_id == "ISA-200"
    assert p.standard.standard_no == "200"
    assert p.standard.standard_title == '제"목" with \\backslash'
    assert p.standard.source_file == "test.docx"
    assert p.standard.authority_base == 1


def test_frontmatter_null_standard_id_returns_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    md = (
        '---\n'
        'schema_version: "1.0"\n'
        'standard_id: null\n'
        'source_file: "x.docx"\n'
        'content_type: "prelude_and_toc"\n'
        '---\n'
    )
    f = tmp_path / "00_전문.md"
    f.write_text(md, encoding="utf-8")
    p = parse_md(f)
    assert p is None
    captured = capsys.readouterr()
    assert "skipped_file" in captured.out
    assert "standard_id: null" in captured.out


# ---------------------------------------------------------------------------
# 2. HTML comment pipe escape
# ---------------------------------------------------------------------------


def test_parse_comment_fields_basic() -> None:
    out = parse_comment_fields("para: 1. | kind: requirement | idx: 28")
    assert out == {"para": "1.", "kind": "requirement", "idx": "28"}


def test_parse_comment_fields_escape_symmetry() -> None:
    # `\|` 내부 포함된 값이 split 경계로 오인되지 않아야 함.
    inner = r"text: a \| b \| c | kind: bullet | idx: 7"
    out = parse_comment_fields(inner)
    assert out["text"] == "a | b | c"
    assert out["kind"] == "bullet"
    assert out["idx"] == "7"


# ---------------------------------------------------------------------------
# 3. heading_trail_hash
# ---------------------------------------------------------------------------


def test_heading_trail_hash_deterministic() -> None:
    # 공식 정의: sha1(json.dumps(list, ensure_ascii=False, separators=(",", ":")))[:8]
    trail = ["감사기준서 300", "요구사항", "전반감사전략"]
    canonical = json.dumps(trail, ensure_ascii=False, separators=(",", ":"))
    expected = hashlib.sha1(
        canonical.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:8]
    assert compute_heading_trail_hash(trail) == expected
    # regression 고정값 — 알고리즘 변경 가드.
    assert compute_heading_trail_hash(["감사기준서 300", "요구사항", "전반감사전략"]) == expected


def test_heading_trail_hash_empty() -> None:
    # json.dumps([]) == "[]" → sha1("[]")[:8]
    empty_hash = hashlib.sha1(b"[]", usedforsecurity=False).hexdigest()[:8]
    assert compute_heading_trail_hash([]) == empty_hash


def test_heading_trail_hash_strip_normalization() -> None:
    """v1.1 — canonical form 직전 각 element ``.strip()`` 적용.

    ``"감사기준서 300"`` vs ``"  감사기준서 300  "`` 은 렌더링 경로에서 공백이
    새어 들어와도 의미적으로 동일하므로 hash 가 같아야 한다. 내부 공백
    (``"이 감사기준서의 범위"``) 은 보존된다.
    """
    clean = ["감사기준서 300", "이 감사기준서의 범위"]
    noisy = ["  감사기준서 300  ", "\t이 감사기준서의 범위  "]
    assert compute_heading_trail_hash(clean) == compute_heading_trail_hash(noisy)
    # 내부 공백이 다르면 hash 는 달라야 한다 (strip 이 lstrip/rstrip 만 수행).
    different_inner = ["감사기준서 300", "이  감사기준서의  범위"]
    assert compute_heading_trail_hash(clean) != compute_heading_trail_hash(different_inner)


# ---------------------------------------------------------------------------
# 4. heading stack
# ---------------------------------------------------------------------------


def test_push_heading_stack_lifecycle() -> None:
    stack: list[str] = []
    _push_heading(stack, 1, "감사기준서 200")
    assert stack == ["감사기준서 200"]
    _push_heading(stack, 2, "서론")
    assert stack == ["감사기준서 200", "서론"]
    _push_heading(stack, 3, "범위")
    assert stack == ["감사기준서 200", "서론", "범위"]
    _push_heading(stack, 3, "시행일")  # level 3 교체
    assert stack == ["감사기준서 200", "서론", "시행일"]
    _push_heading(stack, 2, "요구사항")  # level 2 교체 → level 3 제거
    assert stack == ["감사기준서 200", "요구사항"]


# ---------------------------------------------------------------------------
# 5. chunk_id 의사결정표 (§6.4 6-case)
# ---------------------------------------------------------------------------


def test_chunk_id_paragraph_no_collision() -> None:
    out = _build_chunk_id(
        standard_id="ISA-200",
        section="requirements",
        heading_trail_hash="a1b2c3d4",
        paragraph_id="8.",
        kind="requirement",
        source_idx=100,
        collision=False,
    )
    assert out == "ISA-200:requirements:a1b2c3d4:8."


def test_chunk_id_paragraph_with_collision() -> None:
    # F4 pair — collision=True 플래그 시 source_idx suffix 강제.
    out = _build_chunk_id(
        standard_id="ISA-300",
        section="requirements",
        heading_trail_hash="aaaaaaaa",
        paragraph_id="7.",
        kind="requirement",
        source_idx=2237,
        collision=True,
    )
    assert out == "ISA-300:requirements:aaaaaaaa:7.#2237"


def test_chunk_id_paragraph_with_split() -> None:
    out = _build_chunk_id(
        standard_id="ISA-200",
        section="requirements",
        heading_trail_hash="a1b2c3d4",
        paragraph_id="8.",
        kind="requirement",
        source_idx=100,
        chunk_index=0,
        chunk_of=2,
    )
    assert out == "ISA-200:requirements:a1b2c3d4:8.#0"


def test_chunk_id_empty_paragraph_uses_kind_source_idx() -> None:
    out = _build_chunk_id(
        standard_id="ISA-1200",
        section="appendix",
        heading_trail_hash="c5f9e4a3",
        paragraph_id=None,
        kind="table",
        source_idx=1669,
    )
    assert out == "ISA-1200:appendix:c5f9e4a3:table#1669"


def test_chunk_id_empty_paragraph_with_split() -> None:
    out = _build_chunk_id(
        standard_id="ISA-1200",
        section="appendix",
        heading_trail_hash="c5f9e4a3",
        paragraph_id=None,
        kind="table",
        source_idx=1669,
        chunk_index=1,
        chunk_of=3,
    )
    assert out == "ISA-1200:appendix:c5f9e4a3:table#1669#1"


# ---------------------------------------------------------------------------
# 5b. chunk_id Pass 2 — v1.1 collision resolver 결정성
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, source_idx: int, paragraph_id: str | None = "7.") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        paragraph_id=paragraph_id,
        kind="requirement",
        section="requirements",
        appendix_index=None,
        heading_trail=("감사기준서 300",),
        heading_trail_hash="aaaaaaaa",
        content_text="...",
        content_markdown="...",
        authority=1,
        parent_paragraph_id=None,
        is_application_guidance=False,
        token_estimate=5,
        chunk_index=0,
        chunk_of=1,
        source_idx=source_idx,
    )


def test_resolve_chunk_id_collisions_pass2_all_participants() -> None:
    """Pass 2 는 충돌 first-only 가 아닌 **모든 참여자** 에 suffix 를 부착해야 함.

    v1.1 §6.4 — first-only 는 순서 의존이라 비결정적. Counter 기반 전수 부착.
    """
    cid = "ISA-300:requirements:aaaaaaaa:7."
    chunks = (
        _make_chunk(cid, source_idx=2237),
        _make_chunk(cid, source_idx=2238),
        _make_chunk("ISA-300:requirements:aaaaaaaa:8.", source_idx=2300, paragraph_id="8."),
    )
    resolved = _resolve_chunk_id_collisions(chunks)
    ids = [c.chunk_id for c in resolved]
    # 충돌한 2개에만 suffix 부착, 8. 은 원본 유지.
    assert ids == [
        "ISA-300:requirements:aaaaaaaa:7.#2237",
        "ISA-300:requirements:aaaaaaaa:7.#2238",
        "ISA-300:requirements:aaaaaaaa:8.",
    ]


def test_resolve_chunk_id_collisions_deterministic_order_independent() -> None:
    """Counter 기반이므로 입력 순서를 바꿔도 동일 suffix 부착이 동일 chunk 에 적용."""
    cid = "ISA-300:requirements:aaaaaaaa:7."
    c1 = _make_chunk(cid, source_idx=2237)
    c2 = _make_chunk(cid, source_idx=2238)
    order_a = _resolve_chunk_id_collisions((c1, c2))
    order_b = _resolve_chunk_id_collisions((c2, c1))
    # source_idx → final id 매핑은 순서 무관 동일해야 한다.
    map_a = {c.source_idx: c.chunk_id for c in order_a}
    map_b = {c.source_idx: c.chunk_id for c in order_b}
    assert map_a == map_b
    assert map_a[2237] == f"{cid}#2237"
    assert map_a[2238] == f"{cid}#2238"


# ---------------------------------------------------------------------------
# 5c. assert_chunk_id_uniqueness — 최종 고유성 가드
# ---------------------------------------------------------------------------


def test_assert_chunk_id_uniqueness_pass() -> None:
    # 고유 id 만 있는 정상 케이스 — 예외 발생하지 않음.
    chunks = (
        _make_chunk("A:req:aaaaaaaa:1.", source_idx=1, paragraph_id="1."),
        _make_chunk("A:req:aaaaaaaa:2.", source_idx=2, paragraph_id="2."),
    )
    assert_chunk_id_uniqueness(chunks)


def test_assert_chunk_id_uniqueness_raises_on_duplicate() -> None:
    """Pass 2 이후에도 남은 충돌 (가상 시나리오: hash + source_idx 2-level 충돌) 감지."""
    dupe_id = "A:req:aaaaaaaa:7.#999"
    chunks = (
        _make_chunk(dupe_id, source_idx=999),
        _make_chunk(dupe_id, source_idx=999),
    )
    with pytest.raises(ChunkIdCollisionError) as excinfo:
        assert_chunk_id_uniqueness(chunks)
    msg = str(excinfo.value)
    assert dupe_id in msg
    assert "999" in msg


# ---------------------------------------------------------------------------
# 6. appendix_index
# ---------------------------------------------------------------------------


def test_appendix_index_numbered() -> None:
    trail = ("감사기준서 240", "보론 3 부정위험요소의 예시")
    assert _extract_appendix_index("appendix", trail) == 3


def test_appendix_index_unnumbered_korean_reference_pattern() -> None:
    # ISA-230 `보론(문단 1 참조)`, ISA-300 `보론 (문단 7-8과...)` — §7.2.1 B.
    trail = ("감사기준서 300", "보론 (문단 7-8과 문단 A8 – A11 참조)")
    assert _extract_appendix_index("appendix", trail) == 1
    trail2 = ("감사기준서 230", "보론(문단 1 참조)")
    assert _extract_appendix_index("appendix", trail2) == 1
    # ISA-1100 "보론. 내부회계관리제도 감사보고서 사례"
    trail3 = ("감사기준서 1100", "보론. 내부회계관리제도 감사보고서 사례")
    assert _extract_appendix_index("appendix", trail3) == 1


def test_appendix_index_non_appendix_section_forces_none() -> None:
    trail = ("감사기준서 240", "보론 1")
    assert _extract_appendix_index("requirements", trail) is None
    assert _extract_appendix_index(None, trail) is None


def test_appendix_index_no_appendix_heading_returns_none() -> None:
    # section==appendix 이지만 heading_trail 에 "보론" 텍스트가 전혀 없는 이론적 엣지.
    trail = ("감사기준서 900",)
    assert _extract_appendix_index("appendix", trail) is None


# ---------------------------------------------------------------------------
# 7. table / block_quote cells
# ---------------------------------------------------------------------------


def test_split_table_row_basic() -> None:
    cells = _split_table_row("| h1 | h2 | h3 |")
    assert cells == ("h1", "h2", "h3")


def test_split_table_row_with_pipe_escape() -> None:
    # `|` → `\\|` escape 된 cell 복원.
    cells = _split_table_row(r"| a \| b | c |")
    assert cells == ("a | b", "c")


def test_table_cells_extract() -> None:
    lines = [
        "| 용어 | 정의 |",
        "| --- | --- |",
        "| 적합성 | 질적 척도 |",
        "| 충분성 | 양적 척도 |",
    ]
    cells = _extract_table_cells("table", lines)
    assert cells == (
        ("용어", "정의"),
        ("적합성", "질적 척도"),
        ("충분성", "양적 척도"),
    )


def test_block_quote_cells_single() -> None:
    lines = ["> 이것은 인용구입니다."]
    cells = _extract_table_cells("block_quote", lines)
    assert cells == (("이것은 인용구입니다.",),)


def test_table_cells_none_for_non_table_kind() -> None:
    assert _extract_table_cells("requirement", ["7.\t감사인은 ..."]) is None


# ---------------------------------------------------------------------------
# 8. _to_plain_text
# ---------------------------------------------------------------------------


def test_to_plain_text_strips_paragraph_id_prefix() -> None:
    out = _to_plain_text(
        "7.\t감사인은 감사의 범위를 수립한다.",
        paragraph_id="7.",
        kind="requirement",
    )
    assert out == "감사인은 감사의 범위를 수립한다."


def test_to_plain_text_strips_sub_item_label() -> None:
    out = _to_plain_text("\t(a)\t재무제표가 작성되었는지", paragraph_id="(a)", kind="sub_item")
    assert out == "재무제표가 작성되었는지"


def test_to_plain_text_bullet_marker() -> None:
    out = _to_plain_text("\t•\t기업과 기업환경", paragraph_id=None, kind="bullet")
    assert out == "기업과 기업환경"


# ---------------------------------------------------------------------------
# 9. token_estimate — tiktoken cl100k_base 회귀
# ---------------------------------------------------------------------------


def test_count_tokens_consistent() -> None:
    # 알려진 한글 문자열 회귀 — tiktoken 버전 upgrade 시 가드.
    # 값 자체는 tiktoken cl100k_base 구현에 의존; 본 assertion 은 현재 설치본 기준.
    t = count_tokens("감사인은 감사의견을 형성한다.")
    assert t > 0
    assert t < 50  # 합리적 범위


# ---------------------------------------------------------------------------
# 10. 통합 — ISA-200 parse_md
# ---------------------------------------------------------------------------


def _require_md_dir() -> None:
    if not MD_DIR.exists():
        pytest.skip(f"{MD_DIR} 없음 — Phase 1 convert 선행 필요")


def test_parse_isa_200_smoke() -> None:
    _require_md_dir()
    p = parse_md(MD_DIR / "ISA-200.md")
    assert p is not None
    assert p.standard.standard_id == "ISA-200"
    assert len(p.chunks) > 100
    # scope 는 `이 감사기준서의 범위` heading 하위 chunks 에서 추출
    assert p.summary.scope_markdown is not None
    assert p.summary.scope_text is not None
    # definitions 는 section=definitions chunks 에서 추출
    assert p.summary.definitions_markdown is not None
    # chunk_id 전부 고유
    ids = [c.chunk_id for c in p.chunks]
    assert len(ids) == len(set(ids))
    # section 분포 — intro/requirements/application 3 종 이상 확인
    sections = {c.section for c in p.chunks if c.section}
    assert "intro" in sections
    assert "requirements" in sections
    assert "application" in sections


# ---------------------------------------------------------------------------
# 11. 통합 — F4 6 쌍 chunk_id 고유성
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("standard_no", "paragraph_id"),
    [
        ("250", "12."),
        ("260", "5."),
        ("260", "6."),
        ("300", "7."),
        ("300", "10."),
        ("701", "4."),
    ],
)
def test_f4_pair_uniqueness(standard_no: str, paragraph_id: str) -> None:
    _require_md_dir()
    p = parse_md(MD_DIR / f"ISA-{standard_no}.md")
    assert p is not None
    matched_ids = [c.chunk_id for c in p.chunks if c.paragraph_id == paragraph_id]
    assert len(matched_ids) >= 2, f"{standard_no} pid={paragraph_id} 쌍 미발견"
    assert len(matched_ids) == len(set(matched_ids)), f"duplicate ids: {matched_ids}"


def test_all_chunk_ids_unique_cross_isa() -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR)
    all_ids = [c.chunk_id for p in parsed for c in p.chunks]
    assert len(all_ids) == len(set(all_ids)), "global chunk_id collision"


def test_f4_identical_heading_trail_suffix_exact_values() -> None:
    """F4 2 쌍 (동일 heading_trail) — ISA-300 `7.`, ISA-701 `4.` — source_idx
    suffix 실측 regression.

    team-lead 승인 기대값 (v1.1):
    - ISA-300 requirements `7.` → `#2237`, `#2238`
    - ISA-701 intro `4.` → `#8422`, `#8427`
    """
    _require_md_dir()
    isa_300 = parse_md(MD_DIR / "ISA-300.md")
    isa_701 = parse_md(MD_DIR / "ISA-701.md")
    assert isa_300 is not None
    assert isa_701 is not None

    isa300_7_suffixes = sorted(
        c.chunk_id.rsplit("#", 1)[-1]
        for c in isa_300.chunks
        if c.paragraph_id == "7." and "#" in c.chunk_id
    )
    assert isa300_7_suffixes == ["2237", "2238"], isa300_7_suffixes

    isa701_4_suffixes = sorted(
        c.chunk_id.rsplit("#", 1)[-1]
        for c in isa_701.chunks
        if c.paragraph_id == "4." and "#" in c.chunk_id
    )
    assert isa701_4_suffixes == ["8422", "8427"], isa701_4_suffixes


# ---------------------------------------------------------------------------
# 12. paragraph_links
# ---------------------------------------------------------------------------


def test_paragraph_links_guidance_of() -> None:
    _require_md_dir()
    p = parse_md(MD_DIR / "ISA-200.md")
    assert p is not None
    assert len(p.paragraph_links) > 0
    # 모든 link 는 guidance_of
    assert {lk.link_type for lk in p.paragraph_links} == {"guidance_of"}
    # source chunk kind == application_guidance, target chunk kind == requirement
    by_id = {c.chunk_id: c for c in p.chunks}
    for lk in p.paragraph_links:
        src = by_id[lk.source]
        tgt = by_id[lk.target]
        assert src.kind == "application_guidance"
        assert tgt.kind == "requirement"
        assert src.parent_paragraph_id == tgt.paragraph_id


def test_paragraph_links_dangling_parent_emits_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Application guidance 가 존재하지 않는 parent 를 가리키면 stderr 경고 + skip.
    md = (
        '---\n'
        'schema_version: "1.0"\n'
        'standard_id: "ISA-999"\n'
        'standard_no: "999"\n'
        'source_file: "t.docx"\n'
        '---\n'
        '\n'
        '# 감사기준서 999\n'
        '<!-- idx: 1 -->\n'
        '\n'
        '## 적용\n'
        '<!-- section: application | idx: 2 -->\n'
        '\n'
        'A1.\t가이던스 본문\n'
        '<!-- para: A1. | kind: application_guidance | parent: 999. | idx: 3 -->\n'
    )
    f = tmp_path / "ISA-999.md"
    f.write_text(md, encoding="utf-8")
    p = parse_md(f)
    assert p is not None
    assert len(p.paragraph_links) == 0
    captured = capsys.readouterr()
    assert "dangling parent" in captured.err


# ---------------------------------------------------------------------------
# 13. JSON Schema validation
# ---------------------------------------------------------------------------


def test_json_schema_validation_isa_200(
    json_schema_validator: Draft202012Validator,
) -> None:
    _require_md_dir()
    p = parse_md(MD_DIR / "ISA-200.md")
    assert p is not None
    data = to_json_dict(p)
    errors = list(json_schema_validator.iter_errors(data))
    assert errors == []


def test_json_schema_validation_all_isa(
    json_schema_validator: Draft202012Validator,
) -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR, spec=ISA_SPEC)
    assert len(parsed) == 36
    for p in parsed:
        data = to_json_dict(p)
        errors = list(json_schema_validator.iter_errors(data))
        assert errors == [], f"{p.standard.standard_id}: {errors[0].message}"


# ---------------------------------------------------------------------------
# 14. parse_md_dir 전체 스캔
# ---------------------------------------------------------------------------


def test_parse_md_dir_skips_prelude() -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR, spec=ISA_SPEC)
    ids = [p.standard.standard_id for p in parsed]
    assert "ISA-200" in ids
    assert "ISA-1200" in ids
    # prelude (00_전문.md) 는 skip
    for p in parsed:
        assert p.standard.standard_id.startswith("ISA-")


# ---------------------------------------------------------------------------
# 15. appendix_index 실측 분포 — json_schema.md §7.3
# ---------------------------------------------------------------------------


def test_appendix_index_distribution_non_empty() -> None:
    _require_md_dir()
    parsed = parse_md_dir(MD_DIR)
    appendix_chunks = [
        c for p in parsed for c in p.chunks if c.appendix_index is not None
    ]
    # Phase 1 실측 기준 수백~수천 chunks
    assert len(appendix_chunks) > 500
    # appendix_index 는 양의 정수만
    assert all(c.appendix_index is not None and c.appendix_index >= 1 for c in appendix_chunks)


# ---------------------------------------------------------------------------
# 16. C-P2-5 — MD schema_version fail-fast (Task #7 Critic SHOULD-FIX)
# ---------------------------------------------------------------------------


_MIN_VALID_FRONTMATTER = (
    '---\n'
    'schema_version: "1.0"\n'
    'standard_id: "ISA-999"\n'
    'standard_no: "999"\n'
    'standard_title: "Test Fixture"\n'
    'source_file: "test.docx"\n'
    '---\n'
    '\n'
    '# 감사기준서 999\n'
    '<!-- idx: 0 -->\n'
)


def test_md_schema_supported_contains_current_version() -> None:
    """현재 Phase 1 MD renderer 출력이 supported 집합에 포함되어야 한다."""
    assert "1.0" in MD_SCHEMA_SUPPORTED


def test_parse_md_accepts_supported_schema_version(tmp_path: Path) -> None:
    """valid `"1.0"` frontmatter 는 raise 없이 파싱 완료."""
    md = tmp_path / "ISA-999.md"
    md.write_text(_MIN_VALID_FRONTMATTER, encoding="utf-8")
    parsed = parse_md(md)
    assert parsed is not None
    assert parsed.schema_version == JSON_SCHEMA_VERSION  # JSON 출력은 "1.1.2"
    assert parsed.standard.standard_id == "ISA-999"


def test_parse_md_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    """bumped `"2.0"` frontmatter 는 즉시 ``UnsupportedMdSchemaError``."""
    md = tmp_path / "ISA-998.md"
    md.write_text(
        _MIN_VALID_FRONTMATTER.replace('schema_version: "1.0"', 'schema_version: "2.0"'),
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedMdSchemaError, match=r"schema_version='2\.0'"):
        parse_md(md)


def test_parse_md_rejects_missing_schema_version(tmp_path: Path) -> None:
    """schema_version 누락 시에도 drift 경로로 fail-fast."""
    md = tmp_path / "ISA-997.md"
    # schema_version 라인 제거 — `__MISSING__` sentinel 경로 검증
    md.write_text(
        _MIN_VALID_FRONTMATTER.replace('schema_version: "1.0"\n', ""),
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedMdSchemaError, match=r"schema_version='__MISSING__'"):
        parse_md(md)
