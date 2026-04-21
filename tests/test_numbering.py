"""`numbering.py` 단위·통합 테스트.

- A: 실제 DOCX 기반 통합 (raw/0. ~ 2025 개정.docx 가 없으면 skip)
- B: 합성 fixture 기반 engine replay
- C: helper 순수함수
"""

from __future__ import annotations

import json
import warnings
import zipfile
from pathlib import Path
from types import MappingProxyType

import pytest

from audit_parser.ir.docx_reader import open_docx_zip
from audit_parser.ir.numbering import (
    AbstractNumDef,
    LevelDef,
    NumberedParagraph,
    NumberingEngine,
    NumDef,
    classify_kind,
    format_counter,
    parse_numbering_from_docx,
    parse_numbering_xml,
    render_lvl_text,
)
from audit_parser.ir.types import BlockKind

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "isa_profile_samples.json"
_REAL_DOCX = Path(__file__).resolve().parents[1] / "raw" / "0. 회계감사기준 전문(2025 개정).docx"


# ---------------------------------------------------------------------------
# Fixtures — 합성 abstractNum / numDef
# ---------------------------------------------------------------------------


def _make_abstract_application() -> AbstractNumDef:
    """abstractNum 51 / 15 계열 (적용지침)."""
    levels: dict[int, LevelDef] = {
        0: LevelDef(ilvl=0, lvl_text="A%1.", num_fmt="decimal", start=1, suff=None),
        1: LevelDef(ilvl=1, lvl_text="", num_fmt="bullet", start=1, suff=None),
        2: LevelDef(ilvl=2, lvl_text="○", num_fmt="bullet", start=1, suff=None),
        3: LevelDef(ilvl=3, lvl_text="%4.", num_fmt="decimal", start=1, suff=None),
        4: LevelDef(ilvl=4, lvl_text="%5.", num_fmt="lowerRoman", start=1, suff=None),
    }
    return AbstractNumDef(abstract_num_id="51", levels=MappingProxyType(levels))


def _make_abstract_requirement() -> AbstractNumDef:
    """abstractNum 70 / 98 / 140 계열 (요구사항)."""
    levels: dict[int, LevelDef] = {
        0: LevelDef(ilvl=0, lvl_text="%1.", num_fmt="decimal", start=1, suff=None),
        1: LevelDef(ilvl=1, lvl_text="(%2)", num_fmt="lowerLetter", start=1, suff=None),
        2: LevelDef(ilvl=2, lvl_text="(%3)", num_fmt="lowerRoman", start=1, suff=None),
        3: LevelDef(ilvl=3, lvl_text="%4.", num_fmt="lowerLetter", start=1, suff=None),
    }
    return AbstractNumDef(abstract_num_id="140", levels=MappingProxyType(levels))


def _make_abstract_bullet() -> AbstractNumDef:
    """abstractNum 72 (bullet) — 실측 numId=8 이 참조."""
    levels: dict[int, LevelDef] = {
        0: LevelDef(ilvl=0, lvl_text="", num_fmt="bullet", start=1, suff=None),
        1: LevelDef(ilvl=1, lvl_text="○", num_fmt="bullet", start=1, suff=None),
    }
    return AbstractNumDef(abstract_num_id="72", levels=MappingProxyType(levels))


def _build_engine() -> NumberingEngine:
    abstract_nums = {
        "51": _make_abstract_application(),
        "140": _make_abstract_requirement(),
        "72": _make_abstract_bullet(),
    }
    num_defs = {
        # 실측 top_numId_usage 10 건 중 합성 가능한 것
        "86": NumDef(num_id="86", abstract_num_id="140", level_overrides=MappingProxyType({})),
        "118": NumDef(num_id="118", abstract_num_id="51", level_overrides=MappingProxyType({})),
        "8": NumDef(num_id="8", abstract_num_id="72", level_overrides=MappingProxyType({})),
        # lvlOverride 테스트용 — abstractNum 140 의 ilvl=0 을 5 부터 시작
        "override": NumDef(
            num_id="override",
            abstract_num_id="140",
            level_overrides=MappingProxyType({0: 5}),
        ),
    }
    return NumberingEngine(MappingProxyType(abstract_nums), MappingProxyType(num_defs))


# ---------------------------------------------------------------------------
# B. Engine 단위 테스트
# ---------------------------------------------------------------------------


def _advance(
    engine: NumberingEngine, pairs: list[tuple[str | None, int | None]]
) -> list[NumberedParagraph]:
    return [engine.advance(num_id, ilvl) for num_id, ilvl in pairs]


def test_requirement_counter_advances_monotonically() -> None:
    engine = _build_engine()
    results = _advance(engine, [("86", 0), ("86", 0), ("86", 0)])
    assert [r.paragraph_id for r in results] == ["1.", "2.", "3."]
    assert all(r.kind == BlockKind.REQUIREMENT for r in results)
    assert all(not r.numbering_suppressed for r in results)


def test_application_guidance_counter() -> None:
    engine = _build_engine()
    results = _advance(engine, [("118", 0), ("118", 0)])
    assert [r.paragraph_id for r in results] == ["A1.", "A2."]
    assert all(r.kind == BlockKind.APPLICATION_GUIDANCE for r in results)


def test_sub_item_descent_and_ascent() -> None:
    engine = _build_engine()
    results = _advance(engine, [("86", 0), ("86", 1), ("86", 1), ("86", 0)])
    ids = [r.paragraph_id for r in results]
    assert ids == ["1.", "(a)", "(b)", "2."]
    assert [r.kind for r in results] == [
        BlockKind.REQUIREMENT,
        BlockKind.SUB_ITEM,
        BlockKind.SUB_ITEM,
        BlockKind.REQUIREMENT,
    ]


def test_descent_resets_nested_counter() -> None:
    engine = _build_engine()
    results = _advance(
        engine,
        [("86", 0), ("86", 1), ("86", 1), ("86", 0), ("86", 1)],
    )
    ids = [r.paragraph_id for r in results]
    # (a), (b) 진행 후 ilvl=0 으로 올라갔다가 다시 ilvl=1 진입 → (a) 부터 리셋
    assert ids == ["1.", "(a)", "(b)", "2.", "(a)"]


def test_three_level_descent() -> None:
    engine = _build_engine()
    results = _advance(engine, [("86", 0), ("86", 1), ("86", 2)])
    assert [r.paragraph_id for r in results] == ["1.", "(a)", "(i)"]


def test_num_id_zero_is_suppressed() -> None:
    engine = _build_engine()
    result = engine.advance("0", None)
    assert result.kind == BlockKind.PARAGRAPH_BODY
    assert result.paragraph_id == ""
    assert result.numbering_suppressed is True


def test_num_id_none_is_plain_paragraph() -> None:
    engine = _build_engine()
    result = engine.advance(None, None)
    assert result.kind == BlockKind.PARAGRAPH_BODY
    assert result.paragraph_id == ""
    assert result.numbering_suppressed is False


def test_bullet_yields_empty_paragraph_id() -> None:
    engine = _build_engine()
    result = engine.advance("8", 0)
    assert result.kind == BlockKind.BULLET
    assert result.paragraph_id == ""


def test_missing_num_id_warns_and_tags_unknown() -> None:
    engine = _build_engine()
    with pytest.warns(UserWarning, match="missing numId=9999"):
        result = engine.advance("9999", 0)
    assert result.kind == BlockKind.UNKNOWN_NUMBERING
    assert result.paragraph_id == ""
    assert result.numbering_raw.num_id == "9999"


def test_warning_is_emitted_once_per_key() -> None:
    engine = _build_engine()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        engine.advance("9999", 0)
        engine.advance("9999", 0)
        engine.advance("9999", 0)
    # 3 회 호출해도 동일 키라 warn 1 회만
    missing_warns = [w for w in caught if "missing numId=9999" in str(w.message)]
    assert len(missing_warns) == 1


def test_lvl_override_applies_start_value() -> None:
    engine = _build_engine()
    result = engine.advance("override", 0)
    assert result.kind == BlockKind.REQUIREMENT
    assert result.paragraph_id == "5."


def test_independent_counters_per_num_id() -> None:
    engine = _build_engine()
    results = _advance(engine, [("86", 0), ("118", 0), ("86", 0), ("118", 0)])
    assert [r.paragraph_id for r in results] == ["1.", "A1.", "2.", "A2."]


# --- F4 CHECKPOINT 1 2차 rework: abstractNumId 단위 counter 공유 ---


def _build_engine_with_shared_abstract() -> NumberingEngine:
    """F4 회귀 가드 — 동일 abstract 를 참조하는 복수 numId."""
    abstract_nums = {
        "98": _make_abstract_requirement_simple(),
    }
    num_defs = {
        # override 없음
        "119": NumDef(num_id="119", abstract_num_id="98", level_overrides=MappingProxyType({})),
        # override={0:1} — Word 관행상 "이 리스트는 1 부터 시작" 표기지만 abstract stream
        # 공유 관점에서는 첫 번째 override 만 유효해야 한다 (이후 재등장 시 리셋 금지).
        "582": NumDef(
            num_id="582", abstract_num_id="98", level_overrides=MappingProxyType({0: 1})
        ),
        "586": NumDef(
            num_id="586", abstract_num_id="98", level_overrides=MappingProxyType({0: 1})
        ),
    }
    return NumberingEngine(MappingProxyType(abstract_nums), MappingProxyType(num_defs))


def _make_abstract_requirement_simple() -> AbstractNumDef:
    levels: dict[int, LevelDef] = {
        0: LevelDef(ilvl=0, lvl_text="%1.", num_fmt="decimal", start=1, suff=None),
        1: LevelDef(ilvl=1, lvl_text="(%2)", num_fmt="lowerLetter", start=1, suff=None),
    }
    return AbstractNumDef(abstract_num_id="98", levels=MappingProxyType(levels))


def test_f4_shared_abstract_counter_is_continuous_across_num_ids() -> None:
    """같은 abstract 를 공유하는 numId 들은 하나의 counter stream 이어야 한다.

    실측 ISA-315 에서 abs=98 을 numId=119/582/586/589... 가 공유해 기존 구현은
    `1.`×7 중복을 발생시켰다.
    """
    engine = _build_engine_with_shared_abstract()
    results = _advance(engine, [("119", 0), ("582", 0), ("586", 0), ("119", 0)])
    assert [r.paragraph_id for r in results] == ["1.", "2.", "3.", "4."]


def test_f4_first_start_override_applied_once_per_abstract() -> None:
    """동일 abstract+ilvl 의 startOverride 는 최초 1 회만 적용 — 재등장 시 무효."""
    abstract_nums = {"98": _make_abstract_requirement_simple()}
    num_defs = {
        # 이 순서 (override 먼저) 로 등장해도 override 가 첫 1 회만 적용된 후 연속 증가.
        "alpha": NumDef(
            num_id="alpha", abstract_num_id="98", level_overrides=MappingProxyType({0: 10})
        ),
        "beta": NumDef(
            num_id="beta", abstract_num_id="98", level_overrides=MappingProxyType({0: 10})
        ),
    }
    engine = NumberingEngine(MappingProxyType(abstract_nums), MappingProxyType(num_defs))
    results = _advance(engine, [("alpha", 0), ("beta", 0), ("alpha", 0)])
    # alpha 첫 등장 override=10 → counter=10. beta override=10 재등장 → 무시, 11. 12.
    assert [r.paragraph_id for r in results] == ["10.", "11.", "12."]


def test_f4_reset_reenables_override_application() -> None:
    """reset() 이 override_applied 를 초기화해 기준서 경계에서 override 가 다시 먹힌다."""
    engine = _build_engine_with_shared_abstract()
    _advance(engine, [("582", 0)])  # override applied → 1.
    engine.reset()
    result = engine.advance("586", 0)
    # reset 후 (98,0) applied 플래그 초기화 → 586 의 override={0:1} 재적용 → 1.
    assert result.paragraph_id == "1."


def test_numbering_raw_preserved_on_normal_path() -> None:
    engine = _build_engine()
    result = engine.advance("86", 0)
    assert result.numbering_raw.num_id == "86"
    assert result.numbering_raw.abstract_num_id == "140"
    assert result.numbering_raw.lvl_text == "%1."
    assert result.numbering_raw.num_fmt == "decimal"


def test_metrics_reflects_kinds() -> None:
    engine = _build_engine()
    _advance(engine, [("86", 0), ("86", 0), ("118", 0), (None, None), ("0", None)])
    metrics = engine.metrics()
    assert metrics.get("requirement") == 2
    assert metrics.get("application_guidance") == 1
    assert metrics.get("paragraph_body") == 2


# ---------------------------------------------------------------------------
# C. Helper 순수함수
# ---------------------------------------------------------------------------


def test_classify_kind_decimal_requirement() -> None:
    assert classify_kind("%1.", "decimal", 0) == BlockKind.REQUIREMENT


def test_classify_kind_decimal_application_guidance() -> None:
    assert classify_kind("A%1.", "decimal", 0) == BlockKind.APPLICATION_GUIDANCE


def test_classify_kind_unknown_ilvl_zero_pattern() -> None:
    # strategy §3.3 비표준: ilvl=0 이면서 (%1) lowerLetter
    assert classify_kind("(%1)", "lowerLetter", 0) == BlockKind.UNKNOWN_NUMBERING


def test_classify_kind_sub_item() -> None:
    assert classify_kind("(%2)", "lowerLetter", 1) == BlockKind.SUB_ITEM


def test_classify_kind_bullet_any_ilvl() -> None:
    assert classify_kind("", "bullet", 0) == BlockKind.BULLET
    assert classify_kind("○", "bullet", 2) == BlockKind.BULLET


def test_format_counter_lower_letter() -> None:
    assert format_counter(1, "lowerLetter") == "a"
    assert format_counter(3, "lowerLetter") == "c"


def test_format_counter_upper_letter() -> None:
    assert format_counter(1, "upperLetter") == "A"


def test_format_counter_roman_numerals() -> None:
    assert format_counter(1, "lowerRoman") == "i"
    assert format_counter(4, "lowerRoman") == "iv"
    assert format_counter(9, "lowerRoman") == "ix"
    assert format_counter(14, "upperRoman") == "XIV"


def test_format_counter_lower_letter_base26_extension() -> None:
    """Phase 1.5 C2: lowerLetter 는 26 초과 시 base-26 spreadsheet-style 확장.

    이전 구현은 26 초과 시 숫자 fallback (`27` 을 `"27"` 로 렌더) 이었으나 Word 의
    실제 동작은 `aa`, `ab`, …, `az`, `ba`, … 이다. bijective base-26 (자리에 0 없음).
    """
    assert format_counter(1, "lowerLetter") == "a"
    assert format_counter(26, "lowerLetter") == "z"
    assert format_counter(27, "lowerLetter") == "aa"
    assert format_counter(52, "lowerLetter") == "az"
    assert format_counter(53, "lowerLetter") == "ba"
    assert format_counter(702, "lowerLetter") == "zz"
    assert format_counter(703, "lowerLetter") == "aaa"
    assert format_counter(704, "lowerLetter") == "aab"


def test_format_counter_upper_letter_base26_extension() -> None:
    """upperLetter 는 lowerLetter 의 .upper() — base-26 동작 공유."""
    assert format_counter(1, "upperLetter") == "A"
    assert format_counter(26, "upperLetter") == "Z"
    assert format_counter(27, "upperLetter") == "AA"
    assert format_counter(702, "upperLetter") == "ZZ"
    assert format_counter(703, "upperLetter") == "AAA"


def test_render_lvl_text_uses_correct_level_format() -> None:
    abstract = _make_abstract_requirement()
    # counter_tuple = (1, 2) → ilvl=1 의 lowerLetter 로 %2 를 렌더
    rendered = render_lvl_text("(%2)", (1, 2), abstract)
    assert rendered == "(b)"


def test_render_lvl_text_handles_literal_only() -> None:
    abstract = _make_abstract_requirement()
    assert render_lvl_text("○", (1,), abstract) == "○"


# ---------------------------------------------------------------------------
# A. DOCX 통합 테스트 (실파일 있을 때만)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason="실제 DOCX 없음")
def test_parse_real_docx_numbering() -> None:
    with open_docx_zip(_REAL_DOCX) as zf:
        abstract_nums, num_defs = parse_numbering_from_docx(zf)
    # 실측상 abstractNum 200+ / numDef 700+
    assert len(abstract_nums) >= 100
    assert len(num_defs) >= 300

    # fixture 의 key_abstractNums 5 개 교차검증
    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    for abs_id, ilvl_map in fixture["key_abstractNums"].items():
        assert abs_id in abstract_nums, f"abstractNum {abs_id} 누락"
        levels = abstract_nums[abs_id].levels
        for ilvl_key, expected in ilvl_map.items():
            ilvl = int(ilvl_key.removeprefix("ilvl_"))
            actual = levels.get(ilvl)
            assert actual is not None, f"{abs_id}.{ilvl_key} 누락"
            assert actual.lvl_text == expected["lvlText"]
            assert actual.num_fmt == expected["numFmt"]


def test_parse_numbering_xml_from_minimal_synthetic() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <w:numbering xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
      <w:abstractNum w:abstractNumId='70'>
        <w:lvl w:ilvl='0'>
          <w:start w:val='1'/>
          <w:numFmt w:val='decimal'/>
          <w:lvlText w:val='%1.'/>
        </w:lvl>
        <w:lvl w:ilvl='1'>
          <w:start w:val='1'/>
          <w:numFmt w:val='lowerLetter'/>
          <w:lvlText w:val='(%2)'/>
        </w:lvl>
      </w:abstractNum>
      <w:num w:numId='86'>
        <w:abstractNumId w:val='70'/>
      </w:num>
      <w:num w:numId='999'>
        <w:abstractNumId w:val='70'/>
        <w:lvlOverride w:ilvl='0'>
          <w:startOverride w:val='7'/>
        </w:lvlOverride>
      </w:num>
    </w:numbering>"""
    abstract_nums, num_defs = parse_numbering_xml(xml)
    assert "70" in abstract_nums
    level0 = abstract_nums["70"].levels[0]
    assert level0.lvl_text == "%1."
    assert level0.num_fmt == "decimal"
    assert num_defs["86"].abstract_num_id == "70"
    assert num_defs["86"].level_overrides == {}
    assert num_defs["999"].level_overrides[0] == 7


# ---------------------------------------------------------------------------
# D. NumberingEngine.reset() — 기준서 경계 대응 (Task #4)
# ---------------------------------------------------------------------------


def test_reset_clears_counters() -> None:
    """기준서가 numId 86 을 공유하더라도 reset 후 1. 부터 재시작해야 한다."""
    engine = _build_engine()
    first = _advance(engine, [("86", 0), ("86", 0), ("86", 0)])
    assert [r.paragraph_id for r in first] == ["1.", "2.", "3."]
    engine.reset()
    second = _advance(engine, [("86", 0), ("86", 0)])
    assert [r.paragraph_id for r in second] == ["1.", "2."]


def test_reset_preserves_parsed_defs() -> None:
    engine = _build_engine()
    engine.advance("86", 0)
    engine.reset()
    # 동일 engine 으로 새 numId 접근 가능
    result = engine.advance("118", 0)
    assert result.kind == BlockKind.APPLICATION_GUIDANCE
    assert result.paragraph_id == "A1."


def test_reset_preserves_warnings_dedup() -> None:
    engine = _build_engine()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        engine.advance("9999", 0)
        engine.reset()
        engine.advance("9999", 0)
        engine.advance("9999", 0)
    missing_warns = [w for w in caught if "missing numId=9999" in str(w.message)]
    assert len(missing_warns) == 1


def test_reset_reapplies_lvl_override() -> None:
    """lvlOverride 보유 numId 는 reset 후에도 override start 값을 적용해야 한다."""
    engine = _build_engine()
    first = _advance(engine, [("override", 0), ("override", 0)])
    assert [r.paragraph_id for r in first] == ["5.", "6."]
    engine.reset()
    second = engine.advance("override", 0)
    assert second.paragraph_id == "5."  # override start=5 재적용


def test_missing_numbering_xml_in_docx_returns_empty(tmp_path: Path) -> None:
    # numbering.xml 이 없는 최소 DOCX
    fake = tmp_path / "empty.docx"
    with zipfile.ZipFile(fake, "w") as zf:
        zf.writestr("word/document.xml", "<dummy/>")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with zipfile.ZipFile(fake, "r") as zf:
            abstract_nums, num_defs = parse_numbering_from_docx(zf)
    assert len(abstract_nums) == 0
    assert len(num_defs) == 0
    assert any("numbering.xml missing" in str(w.message) for w in caught)
