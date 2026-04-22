"""Tests for ``audit_parser.spec`` — Phase 4b-1 foundation.

Scope (4b-1):

* ``test_standard_id_backward_compat`` — `docs/checkpoint_4_prep.md §1.3.4` 12-row
  matching cases + `tests/fixtures/phase4_profile_samples.json` 24-case fixture.
  Verifies the v1.2.0 ``standard_id`` regex matches ISA backward-compat + rejects
  out-of-scope strings.
* ``test_isa_default_appendix_extractor_*`` — spot checks on ISA default
  behavior (numbered / un-numbered / non-appendix).
* ``test_format_standard_id_*`` — composition + regex validation.

In-scope commit 3 additions:

* ``test_isa_reparse_semantic_equivalence`` — ISA_SPEC 로 36 MD 재파싱 →
  기존 JSON 과 ``{chunks, paragraph_links, standard, summary}`` 구조 equal
  (embedding 필드 제외).
* ``test_isa_chunk_id_bit_equal`` — 재파싱 chunk_id 집합 == 기존 chunk_id
  집합 (8,590 set equality).
* ``test_special_appendix_name_isa_default_null`` — ISA 모든 chunk 에서
  ``special_appendix_name is None`` 확인 (36 JSON 전수).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from audit_parser.ingest.md_parser import parse_md, to_json_dict
from audit_parser.ir.types import Section
from audit_parser.spec import (
    ISA_SPEC,
    AppendixExtractor,
    isa_default_appendix_extractor,
)

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_JSON_DIR = REPO_ROOT / "output" / "json"
OUTPUT_MD_DIR = REPO_ROOT / "output" / "md"


# ---------------------------------------------------------------------------
# Helpers — live-directory precondition
# ---------------------------------------------------------------------------


def _require_isa_output_present() -> list[Path]:
    """Gate — 36 ISA JSON + MD 파일 양쪽 존재 확인. gitignore 대상이라
    CI 환경에서 없을 수 있으므로 skip 우아하게 처리."""
    json_paths = sorted(OUTPUT_JSON_DIR.glob("ISA-*.json"))
    md_paths = sorted(OUTPUT_MD_DIR.glob("ISA-*.md"))
    if len(json_paths) != 36 or len(md_paths) != 36:
        pytest.skip(
            f"output/json {len(json_paths)}/36 or output/md {len(md_paths)}/36 "
            "not present — skipping ISA reparse equivalence gate"
        )
    return json_paths


_EMBEDDING_FIELDS = frozenset({"embedding", "embedded_at", "embedding_model"})

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase4_profile_samples.json"


@pytest.fixture(scope="module")
def backward_compat_cases() -> list[dict[str, object]]:
    """Load 24 backward-compat cases from Phase 4a Scout fixture."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = data["standard_id_backward_compat_test_cases"]["cases"]
    assert isinstance(cases, list)
    assert len(cases) >= 24, f"expected ≥24 backward_compat cases, got {len(cases)}"
    return cases


# §1.3.4 추가 12-row 매칭 사례표 (checkpoint_4_prep.md). fixture 가 이미
# 24-case 를 커버하지만 spec 표의 정합성도 in-code 검증.
SPEC_MATCHING_TABLE_V1_2_0: list[tuple[str, bool, str]] = [
    # (input, match, note)
    ("ISA-200", True, "v1.1.x 호환"),
    ("ISA-1200", True, "v1.1.x 호환"),
    ("ISQM-1", True, "IAASB ISQM 1"),
    ("ISQM-2", True, "IAASB ISQM 2 + Critic α"),
    ("ISQM-10", True, "Critic α 확장 여유"),
    ("ISQM-99", True, "Critic α 확장 여유"),
    ("ASSR-3000", True, "ISAE 3000"),
    ("ASSR-3410", True, "향후 ISAE 3410 여지"),
    ("FRMK-1", True, "A3 균일 prefix-N"),
    ("FRMK-2", True, "2030+ 개정 확장"),
    ("ISQM-100", False, "3-digit scope out"),
    ("ASSR-99999", False, "5-digit scope out"),
    ("ISA-1", False, "3-digit minimum"),
    ("ISA-12345", False, "4-digit maximum"),
    ("ISA-220R", False, "revised suffix scope out"),
    ("FRMK", False, "prefix-only false-positive 거부"),
    ("ISA", False, "same"),
    ("ISQM", False, "same"),
    ("ASSR", False, "same"),
]


# ---------------------------------------------------------------------------
# standard_id backward-compat regex tests
# ---------------------------------------------------------------------------


# Compiled once — the final v1.2.0 3-party-agreed regex. Matches ISA_SPEC's
# regex for ISA cases; for non-ISA cases we reference the full 4-alt regex.
_FULL_V1_2_REGEX = re.compile(r"^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)$")


def test_full_v1_2_regex_matches_checkpoint_4_prep_table() -> None:
    """docs/checkpoint_4_prep.md §1.3.4 표의 12 row 와 _FULL_V1_2_REGEX 일치."""
    for input_val, expected_match, note in SPEC_MATCHING_TABLE_V1_2_0:
        actual = bool(_FULL_V1_2_REGEX.fullmatch(input_val))
        assert actual == expected_match, (
            f"{input_val!r} expected match={expected_match} ({note}), "
            f"got match={actual}"
        )


def test_standard_id_backward_compat(
    backward_compat_cases: list[dict[str, object]],
) -> None:
    """24 fixture cases — full v1.2.0 regex behavior matches Scout Phase 4a."""
    for case in backward_compat_cases:
        input_val = case["input"]
        expected = case["match"]
        assert isinstance(input_val, str)
        assert isinstance(expected, bool)
        actual = bool(_FULL_V1_2_REGEX.fullmatch(input_val))
        reason = case.get("_reason") or case.get("_note") or ""
        assert actual == expected, (
            f"{input_val!r} expected match={expected}, got match={actual} "
            f"({reason})"
        )


def test_isa_spec_regex_accepts_all_isa_cases(
    backward_compat_cases: list[dict[str, object]],
) -> None:
    """ISA_SPEC.standard_id_regex 는 ISA alt 만 수용. 비-ISA 는 거부."""
    for case in backward_compat_cases:
        input_val = case["input"]
        alt = case.get("alt")
        assert isinstance(input_val, str)
        matched_by_isa = bool(ISA_SPEC.standard_id_regex.fullmatch(input_val))
        if case["match"] and alt == "ISA":
            assert matched_by_isa, f"{input_val!r} should match ISA_SPEC but didn't"
        elif case["match"] and alt != "ISA":
            # 다른 alt (ISQM/ASSR/FRMK) 에는 매칭되지만 ISA spec 은 거부해야 함.
            assert not matched_by_isa, (
                f"{input_val!r} alt={alt} should NOT match ISA_SPEC regex"
            )


# ---------------------------------------------------------------------------
# appendix_extractor tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "heading, expected_index, expected_name",
    [
        # Numbered (명시적 N)
        ("보론 1", 1, None),
        ("보론 2", 2, None),
        ("보론 6", 6, None),
        ("보론1", 1, None),  # 공백 없음 (ISA-530/580)
        ("보론 1: 회계감사기준위원회가 제정한 기준", 1, None),
        # Un-numbered (ISA 9종 대표 사례)
        ("보론", 1, None),
        ("보론(문단 1 참조)", 1, None),  # ISA-230
        ("보론 (문단 A8 참조)", 1, None),  # ISA-510
        ("보론. 내부회계관리제도 감사보고서 사례", 1, None),  # ISA-1100
        # Non-appendix
        ("서론", None, None),
        ("요구사항", None, None),
        ("", None, None),
        # Whitespace 경계
        ("  보론 3  ", 3, None),
    ],
)
def test_isa_default_appendix_extractor(
    heading: str, expected_index: int | None, expected_name: str | None
) -> None:
    """ISA default extractor — numbered/un-numbered/non-appendix spot checks."""
    idx, name = isa_default_appendix_extractor(heading)
    assert idx == expected_index, f"{heading!r} → idx expected {expected_index}, got {idx}"
    assert name == expected_name, f"{heading!r} → name expected {expected_name}, got {name}"


def test_isa_default_appendix_extractor_special_name_always_none() -> None:
    """ISA 는 모든 보론이 appendix_index 만 사용 — special_appendix_name 은 항상 None.

    B-v2 (Domain Reviewer Q1 정정 2026-04-22) 규약 준수 확인. FRMK_SPEC 만
    ``special_appendix_name`` 를 non-None 으로 emit 하도록 Phase 4b-2 에서 override.
    """
    samples = [
        "보론",
        "보론 1",
        "보론: 역할과 책임",  # FRMK-style un-numbered — ISA extractor 는 (1, None) 반환
        "보론 (문단 A8 참조)",
        "보론. 내부회계관리제도 감사보고서 사례",
    ]
    for heading in samples:
        _idx, name = isa_default_appendix_extractor(heading)
        assert name is None, (
            f"{heading!r} ISA extractor 가 special_appendix_name {name!r} 반환 — "
            f"ISA 는 항상 None 이어야 함 (B-v2 규약)"
        )


# ---------------------------------------------------------------------------
# format_standard_id / validate_standard_id tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "standard_no, expected_id",
    [
        ("200", "ISA-200"),
        ("450", "ISA-450"),
        ("1200", "ISA-1200"),
    ],
)
def test_format_standard_id_valid(standard_no: str, expected_id: str) -> None:
    """ISA_SPEC.format_standard_id 는 ``ISA-{N}`` 문자열 생성."""
    assert ISA_SPEC.format_standard_id(standard_no) == expected_id


@pytest.mark.parametrize(
    "bad_standard_no",
    [
        "",  # 빈 문자열
        "abc",  # 비숫자
        "12345",  # 5-digit (standard_no_regex max 4)
    ],
)
def test_format_standard_id_rejects_bad_standard_no(bad_standard_no: str) -> None:
    """standard_no_regex 불일치 시 ValueError."""
    with pytest.raises(ValueError, match="standard_no"):
        ISA_SPEC.format_standard_id(bad_standard_no)


def test_format_standard_id_rejects_composed_id_out_of_isa_range() -> None:
    """standard_no 는 regex 통과하지만 composed id 가 ISA alt 밖인 경우.

    예: standard_no="1" 는 ``^\\d{1,4}$`` 통과하지만 composed "ISA-1" 는
    ``^ISA-\\d{3,4}$`` 에 불일치 — 2차 방어선 발동.
    """
    with pytest.raises(ValueError, match="standard_id"):
        ISA_SPEC.format_standard_id("1")


def test_validate_standard_id_accepts_isa_ids() -> None:
    """ISA_SPEC.validate_standard_id 는 ISA- alt 만 통과."""
    for valid in ("ISA-200", "ISA-450", "ISA-1200", "ISA-999"):
        ISA_SPEC.validate_standard_id(valid)  # no raise


@pytest.mark.parametrize(
    "bad_id",
    [
        "ISA-1",  # 3-digit minimum
        "ISA-12345",  # 4-digit maximum
        "ISQM-1",  # 다른 prefix
        "FRMK-1",  # 다른 prefix
        "ISA",  # prefix-only
        "",
    ],
)
def test_validate_standard_id_rejects_non_isa(bad_id: str) -> None:
    """비-ISA 또는 경계 밖 id 는 ValueError."""
    with pytest.raises(ValueError, match="standard_id"):
        ISA_SPEC.validate_standard_id(bad_id)


# ---------------------------------------------------------------------------
# dataclass invariants
# ---------------------------------------------------------------------------


def test_standard_spec_is_frozen() -> None:
    """StandardSpec 은 ``frozen=True`` — 런타임 필드 재할당 금지."""
    with pytest.raises(AttributeError):
        ISA_SPEC.prefix = "ISQM"  # type: ignore[misc]


def test_standard_spec_slots_enforced() -> None:
    """``slots=True`` — 임의 속성 추가 금지.

    frozen+slots 조합 시 non-slotted 속성 set 은 CPython 내부적으로 ``TypeError``
    (super().__setattr__ 체크 경로) 로 전파됨. frozen 단독이면 ``AttributeError``
    (FrozenInstanceError). 두 예외 중 하나는 반드시 발생해야 함.
    """
    with pytest.raises((AttributeError, TypeError)):
        ISA_SPEC.extra_field = "nope"  # type: ignore[attr-defined]


def test_isa_spec_section_enum_is_section() -> None:
    """ISA_SPEC.section_enum 은 기존 ``Section`` StrEnum (ir.types)."""
    assert ISA_SPEC.section_enum is Section
    assert issubclass(Section, type(Section.INTRO))  # sanity check


def test_isa_spec_prefix_literal() -> None:
    assert ISA_SPEC.prefix == "ISA"


def test_appendix_extractor_type_alias_is_callable() -> None:
    """``AppendixExtractor`` 는 callable 타입 — 런타임 isinstance 검증은
    불가능하지만 ``ISA_SPEC.appendix_extractor`` 가 적절히 invoke 가능."""
    extractor: AppendixExtractor = ISA_SPEC.appendix_extractor
    assert callable(extractor)
    assert extractor("보론 3") == (3, None)


# ---------------------------------------------------------------------------
# ISA re-parse semantic equivalence (Commit 3 — Exit gate 핵심)
# ---------------------------------------------------------------------------


def _strip_embedding_and_summary_vectors(
    parsed_json: dict[str, Any],
) -> dict[str, Any]:
    """재파싱 비교용 — embedding 필드를 JSON 구조에서 제거한 복사본 반환.

    재파싱 결과는 embedding 이 전부 ``None`` 이고 기존 JSON 은 populated.
    두 dict 를 structural equality 비교하려면 embedding 계열 필드를 양쪽에서
    제거해야 함.
    """
    stripped: dict[str, Any] = {}
    for key, value in parsed_json.items():
        if key == "chunks" and isinstance(value, list):
            stripped[key] = [
                {k: v for k, v in chunk.items() if k not in _EMBEDDING_FIELDS}
                for chunk in value
            ]
        elif key == "summary" and isinstance(value, dict):
            stripped[key] = {
                k: v for k, v in value.items() if k not in _EMBEDDING_FIELDS
            }
        else:
            stripped[key] = value
    return stripped


def test_isa_reparse_semantic_equivalence() -> None:
    """Exit gate #2: ISA 36 re-parse semantic 동등.

    ISA_SPEC 주입형 ``parse_md`` 재실행 결과가 output/json/ISA-*.json 과
    **embedding 계열 제외 전수 equal**. byte-level 차이는 ``schema_version``
    값 변화 + ``special_appendix_name`` 필드 추가만 허용 — 본 테스트는 v1.2.0
    migration 이후 실행되므로 두 쪽 모두 ``"1.2.0"`` + ``special_appendix_name``
    를 가짐.
    """
    existing_paths = _require_isa_output_present()
    for json_path in existing_paths:
        md_path = OUTPUT_MD_DIR / (json_path.stem + ".md")
        assert md_path.exists(), f"missing MD for {json_path.name}"

        existing = json.loads(json_path.read_text(encoding="utf-8"))
        parsed = parse_md(md_path, spec=ISA_SPEC)
        assert parsed is not None, f"parse_md returned None for {md_path.name}"
        reparsed = to_json_dict(parsed)

        existing_stripped = _strip_embedding_and_summary_vectors(existing)
        reparsed_stripped = _strip_embedding_and_summary_vectors(reparsed)

        assert existing_stripped == reparsed_stripped, (
            f"{json_path.name}: semantic equivalence failed. "
            f"existing keys={sorted(existing_stripped)} vs "
            f"reparsed keys={sorted(reparsed_stripped)}"
        )


def test_isa_chunk_id_bit_equal() -> None:
    """Exit gate #3: 재파싱 chunk_id 집합 == 기존 chunk_id 집합 (8,590 set)."""
    existing_paths = _require_isa_output_present()
    existing_chunk_ids: set[str] = set()
    reparsed_chunk_ids: set[str] = set()
    for json_path in existing_paths:
        md_path = OUTPUT_MD_DIR / (json_path.stem + ".md")
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        for c in existing["chunks"]:
            existing_chunk_ids.add(c["chunk_id"])
        parsed = parse_md(md_path, spec=ISA_SPEC)
        assert parsed is not None
        for c in parsed.chunks:
            reparsed_chunk_ids.add(c.chunk_id)

    assert len(existing_chunk_ids) == 8590, (
        f"existing chunk_id set size {len(existing_chunk_ids)} != 8590 "
        f"(Phase 3 F1 v1.1.2 실측값)"
    )
    assert existing_chunk_ids == reparsed_chunk_ids, (
        f"chunk_id set mismatch — only in existing: "
        f"{sorted(existing_chunk_ids - reparsed_chunk_ids)[:5]}... "
        f"only in reparsed: {sorted(reparsed_chunk_ids - existing_chunk_ids)[:5]}..."
    )


def test_special_appendix_name_isa_default_null() -> None:
    """B-v2 불변조건: ISA 36 JSON 의 모든 chunk 에서
    ``special_appendix_name`` 필드가 존재하고 값은 ``None``.

    FRMK 만 non-null — 해당 spec 은 Phase 4b-2 에서 추가.
    """
    existing_paths = _require_isa_output_present()
    for json_path in existing_paths:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        for c in data["chunks"]:
            assert "special_appendix_name" in c, (
                f"{json_path.name} chunk {c['chunk_id']!r} "
                f"missing special_appendix_name field"
            )
            assert c["special_appendix_name"] is None, (
                f"{json_path.name} chunk {c['chunk_id']!r} "
                f"special_appendix_name expected None, got "
                f"{c['special_appendix_name']!r} — ISA must always be None (B-v2)"
            )
