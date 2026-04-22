"""Task #5 — 36 JSON Schema v1.1 전수 검증 회귀 테스트.

`output/json/` 에 36 ISA JSON 이 있을 때만 실행 (`audit-parser ingest` 선행).
CI 에서 자동 게이트가 되도록 skip 조건을 건다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_DIR = REPO_ROOT / "output" / "json"
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "json_schema_v1_1.schema.json"

F4_CANONICAL_CHUNK_IDS = {
    "ISA-300:requirements:94b679bc:7.#2237",
    "ISA-300:requirements:94b679bc:7.#2238",
    "ISA-701:intro:a7720376:4.#8422",
    "ISA-701:intro:a7720376:4.#8427",
}

_JSON_FILES = sorted(JSON_DIR.glob("ISA-*.json")) if JSON_DIR.exists() else []


@pytest.fixture(scope="session")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_all_isa_json_conform_to_schema_v1_1(validator: Draft202012Validator) -> None:
    assert len(_JSON_FILES) == 36, f"expected 36 JSON, got {len(_JSON_FILES)}"
    for path in _JSON_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        assert not errors, f"{path.name}: {[e.message for e in errors[:3]]}"
        assert data["schema_version"] == "1.1.2", path.name


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_chunk_id_global_unique_across_36_json() -> None:
    seen: dict[str, str] = {}
    for path in _JSON_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        for chunk in data["chunks"]:
            cid = chunk["chunk_id"]
            prev = seen.get(cid)
            assert prev is None, f"duplicate chunk_id {cid} in {path.name} and {prev}"
            seen[cid] = path.name


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_f4_canonical_suffix_chunks_present() -> None:
    """Task #2 v1.1 F4 실측 고정값 — Pass 2 collision suffix regression guard."""
    found: set[str] = set()
    for path in _JSON_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        for chunk in data["chunks"]:
            if chunk["chunk_id"] in F4_CANONICAL_CHUNK_IDS:
                found.add(chunk["chunk_id"])
    assert found == F4_CANONICAL_CHUNK_IDS, (
        f"canonical F4 chunks missing: {F4_CANONICAL_CHUNK_IDS - found}"
    )


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_paragraph_links_count_matches_task_2_report() -> None:
    """Task #2 도메인 보고: paragraph_links 총 1,788 (requirement ↔ application_guidance)."""
    total = 0
    for path in _JSON_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        total += len(data["paragraph_links"])
    assert total == 1788, f"paragraph_links 총 수 {total} != 1788"


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_no_chunk_exceeds_soft_limit_after_split() -> None:
    """Task #3 분할 후 모든 chunk 가 soft_limit 3500 이하 (table 분할 검증)."""
    for path in _JSON_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        for chunk in data["chunks"]:
            assert chunk["token_estimate"] <= 3500, (
                f"{path.name}: {chunk['chunk_id']} "
                f"token_estimate={chunk['token_estimate']} > 3500"
            )


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_isa_1200_table_split_produces_three_parts() -> None:
    """Task #3 실측: ISA-1200 66×2 용어표 → 3 part 분할."""
    isa_1200 = JSON_DIR / "ISA-1200.json"
    if not isa_1200.exists():
        pytest.skip("ISA-1200.json 없음")
    data = json.loads(isa_1200.read_text(encoding="utf-8"))
    split = [c for c in data["chunks"] if c["chunk_of"] > 1]
    assert len(split) == 3, f"ISA-1200 split chunks = {len(split)}, expected 3"
    assert {c["chunk_index"] for c in split} == {0, 1, 2}
    assert {c["chunk_of"] for c in split} == {3}


@pytest.mark.skipif(not _JSON_FILES, reason="output/json/ 에 36 JSON 필요 (ingest 선행)")
def test_no_toc_stopword_leak_chunks() -> None:
    """CP2 rework (I1): Phase 1 TOC boundary leak 전수 제거.

    `목차` / `문단번호` 만으로 구성된 chunk 는 post-filter 에 의해 0 건이어야
    한다. 35/36 ISA 에서 70 건 생성되던 것이 md_parser 의 `_is_toc_leak_chunk`
    필터로 제거됨.
    """
    leak = []
    for path in _JSON_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        for chunk in data["chunks"]:
            ct = (chunk.get("content_text") or "").strip()
            if (
                chunk["kind"] == "paragraph_body"
                and chunk["section"] is None
                and ct in {"목차", "문단번호"}
            ):
                leak.append((path.name, chunk["source_idx"], ct))
    assert not leak, f"TOC stopword leak chunks 발견 {len(leak)}건: {leak[:5]}"
