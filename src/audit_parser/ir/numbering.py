"""`word/numbering.xml` 파싱 + 카운터 replay 엔진 — Phase 1 Task #3.

DOCX 문단번호(`1.`, `A1.`, `(a)`, `(i)`…) 는 본문 텍스트에 저장되지 않고
`w:numPr/w:numId` + `w:ilvl` 조합을 `numbering.xml` 의 `lvlText` 템플릿에 대입해
Word 가 렌더 시점에 생성한다. 본 모듈은 그 상태를 파이썬 쪽에서 그대로 replay 해
`NumberedParagraph` 로 방출한다.

설계 근거는 `docs/numbering_strategy.md` (§3 분류 규칙, §4 카운터 알고리즘,
§5 fallback 정책, §6 인터페이스 초안). abstractNumId 화이트리스트를 사용하지 않고
`lvlText` + `numFmt` 패턴으로 동적 분류하므로 핵심 5 개 계열 {15, 51, 70, 98, 140}
이외의 신규 abstractNum 도 자동 포섭된다. 미지 조합은 `UNKNOWN_NUMBERING` + 단일
`UserWarning` 으로 태깅하고 파싱을 중단하지 않는다.
"""

from __future__ import annotations

import warnings
import zipfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from lxml import etree

from audit_parser.ir._xml import safe_fromstring
from audit_parser.ir.types import BlockKind

NumFmt = Literal[
    "decimal",
    "lowerLetter",
    "lowerRoman",
    "upperLetter",
    "upperRoman",
    "bullet",
]

_NUM_FMT_VALUES: Final[frozenset[str]] = frozenset(
    {"decimal", "lowerLetter", "lowerRoman", "upperLetter", "upperRoman", "bullet"}
)

_W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMAP: Final[dict[str, str]] = {"w": _W_NS}


def _qn(tag: str) -> str:
    prefix, _, local = tag.partition(":")
    return f"{{{_NSMAP[prefix]}}}{local}"


_TAG_NUMBERING: Final = _qn("w:numbering")
_TAG_ABSTRACT_NUM: Final = _qn("w:abstractNum")
_TAG_NUM: Final = _qn("w:num")
_TAG_LVL: Final = _qn("w:lvl")
_TAG_LVL_TEXT: Final = _qn("w:lvlText")
_TAG_NUM_FMT: Final = _qn("w:numFmt")
_TAG_START: Final = _qn("w:start")
_TAG_SUFF: Final = _qn("w:suff")
_TAG_ABSTRACT_NUM_ID: Final = _qn("w:abstractNumId")
_TAG_LVL_OVERRIDE: Final = _qn("w:lvlOverride")
_TAG_START_OVERRIDE: Final = _qn("w:startOverride")
_ATTR_ABSTRACT_NUM_ID: Final = _qn("w:abstractNumId")
_ATTR_NUM_ID: Final = _qn("w:numId")
_ATTR_ILVL: Final = _qn("w:ilvl")
_ATTR_VAL: Final = _qn("w:val")

_MAX_ILVL: Final = 9  # Word spec: ilvl 0..8


# ---------------------------------------------------------------------------
# 데이터클래스
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class LevelDef:
    """abstractNum 의 단일 ilvl 레벨 정의."""

    ilvl: int
    lvl_text: str
    num_fmt: NumFmt
    start: int
    suff: str | None


@dataclass(slots=True, frozen=True)
class AbstractNumDef:
    """재사용 가능한 번호 스타일 템플릿 (최대 9 단계)."""

    abstract_num_id: str
    levels: Mapping[int, LevelDef]


@dataclass(slots=True, frozen=True)
class NumDef:
    """본문 문단이 실제로 참조하는 numId 인스턴스."""

    num_id: str
    abstract_num_id: str
    level_overrides: Mapping[int, int]


@dataclass(slots=True, frozen=True)
class NumberingRaw:
    """디버깅·재분류용 원본 numPr 스냅샷."""

    num_id: str | None
    ilvl: int | None
    abstract_num_id: str | None
    lvl_text: str | None
    num_fmt: NumFmt | None


@dataclass(slots=True, frozen=True)
class NumberedParagraph:
    """`NumberingEngine.advance()` 의 반환값 — 한 문단에 확정된 번호·kind 결과."""

    kind: BlockKind
    paragraph_id: str
    counter_tuple: tuple[int, ...]
    numbering_suppressed: bool
    numbering_raw: NumberingRaw


# ---------------------------------------------------------------------------
# XML 파서
# ---------------------------------------------------------------------------


def parse_numbering_xml(
    raw_xml: bytes,
) -> tuple[Mapping[str, AbstractNumDef], Mapping[str, NumDef]]:
    """`word/numbering.xml` 바이트를 파싱해 `(abstract_nums, num_defs)` 반환."""
    root = safe_fromstring(raw_xml)
    abstract_nums: dict[str, AbstractNumDef] = {}
    num_defs: dict[str, NumDef] = {}

    for abs_elem in root.iter(_TAG_ABSTRACT_NUM):
        abs_id = abs_elem.get(_ATTR_ABSTRACT_NUM_ID)
        if abs_id is None:
            continue
        levels: dict[int, LevelDef] = {}
        for lvl_elem in abs_elem.findall(_TAG_LVL):
            level = _parse_level(lvl_elem)
            if level is not None:
                levels[level.ilvl] = level
        abstract_nums[abs_id] = AbstractNumDef(
            abstract_num_id=abs_id,
            levels=MappingProxyType(levels),
        )

    for num_elem in root.iter(_TAG_NUM):
        entry = _parse_num_def(num_elem)
        if entry is not None:
            num_defs[entry.num_id] = entry

    return MappingProxyType(abstract_nums), MappingProxyType(num_defs)


def _parse_num_def(num_elem: etree._Element) -> NumDef | None:
    num_id = num_elem.get(_ATTR_NUM_ID)
    if num_id is None:
        return None
    abs_ref = num_elem.find(_TAG_ABSTRACT_NUM_ID)
    if abs_ref is None:
        return None
    abs_val = abs_ref.get(_ATTR_VAL)
    if abs_val is None:
        return None
    overrides: dict[int, int] = {}
    for ovr_elem in num_elem.findall(_TAG_LVL_OVERRIDE):
        pair = _parse_level_override(ovr_elem)
        if pair is not None:
            overrides[pair[0]] = pair[1]
    return NumDef(
        num_id=num_id,
        abstract_num_id=abs_val,
        level_overrides=MappingProxyType(overrides),
    )


def _parse_level_override(ovr_elem: etree._Element) -> tuple[int, int] | None:
    ilvl_attr = ovr_elem.get(_ATTR_ILVL)
    if ilvl_attr is None:
        return None
    try:
        ilvl = int(ilvl_attr)
    except ValueError:
        return None
    start_ovr = ovr_elem.find(_TAG_START_OVERRIDE)
    if start_ovr is None:
        return None
    start_val = start_ovr.get(_ATTR_VAL)
    if start_val is None:
        return None
    try:
        return ilvl, int(start_val)
    except ValueError:
        return None


def parse_numbering_from_docx(
    zf: zipfile.ZipFile,
) -> tuple[Mapping[str, AbstractNumDef], Mapping[str, NumDef]]:
    """DOCX zip 에서 `word/numbering.xml` 을 읽어 파싱. 없으면 빈 매핑 + warn."""
    try:
        with zf.open("word/numbering.xml") as stream:
            raw = stream.read()
    except KeyError:
        warnings.warn(
            "[numbering] word/numbering.xml missing in DOCX — no abstractNums loaded",
            UserWarning,
            stacklevel=2,
        )
        return MappingProxyType({}), MappingProxyType({})
    return parse_numbering_xml(raw)


def _parse_level(lvl_elem: etree._Element) -> LevelDef | None:
    ilvl_attr = lvl_elem.get(_ATTR_ILVL)
    if ilvl_attr is None:
        return None
    try:
        ilvl = int(ilvl_attr)
    except ValueError:
        return None

    lvl_text_elem = lvl_elem.find(_TAG_LVL_TEXT)
    lvl_text = (lvl_text_elem.get(_ATTR_VAL) if lvl_text_elem is not None else "") or ""

    num_fmt_elem = lvl_elem.find(_TAG_NUM_FMT)
    raw_fmt = num_fmt_elem.get(_ATTR_VAL) if num_fmt_elem is not None else None
    num_fmt: NumFmt = raw_fmt if raw_fmt in _NUM_FMT_VALUES else "decimal"  # type: ignore[assignment]

    start_elem = lvl_elem.find(_TAG_START)
    start_val: int = 1
    if start_elem is not None:
        raw_start = start_elem.get(_ATTR_VAL)
        if raw_start is not None:
            try:
                start_val = int(raw_start)
            except ValueError:
                start_val = 1

    suff_elem = lvl_elem.find(_TAG_SUFF)
    suff = suff_elem.get(_ATTR_VAL) if suff_elem is not None else None

    return LevelDef(ilvl=ilvl, lvl_text=lvl_text, num_fmt=num_fmt, start=start_val, suff=suff)


# ---------------------------------------------------------------------------
# Helpers — 분류·렌더
# ---------------------------------------------------------------------------


def classify_kind(lvl_text: str, num_fmt: NumFmt, ilvl: int) -> BlockKind:
    """strategy §3.1, §3.2 규칙. abstract_num_id 비의존."""
    if num_fmt == "bullet":
        return BlockKind.BULLET
    if ilvl >= 1:
        return BlockKind.SUB_ITEM
    if num_fmt == "decimal":
        if lvl_text == "%1.":
            return BlockKind.REQUIREMENT
        if lvl_text == "A%1.":
            return BlockKind.APPLICATION_GUIDANCE
    return BlockKind.UNKNOWN_NUMBERING


_ROMAN_UNITS: Final = (
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)


def _to_roman(value: int) -> str:
    if value <= 0:
        return str(value)
    remain = value
    out: list[str] = []
    for unit_val, unit_str in _ROMAN_UNITS:
        while remain >= unit_val:
            out.append(unit_str)
            remain -= unit_val
    return "".join(out)


def _to_alpha_base26(value: int) -> str:
    """1→'a', 26→'z', 27→'aa', 52→'az', 53→'ba', 702→'zz', 703→'aaa' …

    Word 의 `lowerLetter`/`upperLetter` 는 26 초과 시 spreadsheet-style 복수 자릿수로
    확장된다 (bijective base-26, 0 없음). 이전 구현은 26 초과 시 숫자 fallback
    이었으나 실제 Word 렌더와 어긋나 `(aa)` 같은 라벨을 `27` 로 노출했다.
    """
    if value < 1:
        raise ValueError(f"_to_alpha_base26: value must be >= 1, got {value}")
    letters: list[str] = []
    remaining = value
    while remaining > 0:
        remaining -= 1
        letters.append(chr(ord("a") + remaining % 26))
        remaining //= 26
    return "".join(reversed(letters))


def format_counter(value: int, num_fmt: NumFmt) -> str:
    """카운터 값 → 렌더 문자열. bullet → ''. letter 는 base-26 확장."""
    if num_fmt == "bullet":
        return ""
    if num_fmt == "decimal":
        return str(value)
    if num_fmt == "lowerLetter":
        return _to_alpha_base26(value)
    if num_fmt == "upperLetter":
        return _to_alpha_base26(value).upper()
    if num_fmt == "lowerRoman":
        return _to_roman(value)
    if num_fmt == "upperRoman":
        return _to_roman(value).upper()
    return str(value)


def render_lvl_text(
    lvl_text: str,
    counter_tuple: tuple[int, ...],
    abstract_num: AbstractNumDef,
) -> str:
    """`lvlText` 의 `%N` placeholder 를 ilvl=N-1 의 numFmt 로 렌더."""
    result = lvl_text
    for i, val in enumerate(counter_tuple, start=1):
        placeholder = f"%{i}"
        if placeholder not in result:
            continue
        level_for_i = abstract_num.levels.get(i - 1)
        fmt: NumFmt = level_for_i.num_fmt if level_for_i is not None else "decimal"
        result = result.replace(placeholder, format_counter(val, fmt))
    return result


# ---------------------------------------------------------------------------
# NumberingEngine — 카운터 replay
# ---------------------------------------------------------------------------


class NumberingEngine:
    """DOCX 1 개에 대한 numId 별 카운터 상태.

    문단 순서대로 `advance(num_id, ilvl)` 을 호출하면 `NumberedParagraph` 를 반환한다.
    순서가 어긋나면 카운터가 오염되므로 `iter_body` 의 yield 순서를 절대 위반해서는
    안 된다.
    """

    __slots__ = (
        "_abstract_nums",
        "_num_defs",
        "_counters",
        "_starts",
        "_last_ilvl",
        "_override_applied",
        "_seen_warnings",
        "_metrics",
    )

    def __init__(
        self,
        abstract_nums: Mapping[str, AbstractNumDef],
        num_defs: Mapping[str, NumDef],
    ) -> None:
        self._abstract_nums = abstract_nums
        self._num_defs = num_defs
        # F4 (CHECKPOINT 1 2차 rework): counter 저장소를 numId → abstractNumId 기반으로
        # 변경. `word/numbering.xml` 은 동일 abstractNumId 를 여러 numId 로 참조하도록
        # 허용하므로 numId 별 독립 카운터는 "적용지침 A1~A83 단일 연속" 같은 의미 스트림을
        # 쪼갠다 (예: ISA-570 에서 `1.`×3, `A1.`×2). 이하 3 개 사전 key 는 전부
        # abstractNumId (string) 이다.
        self._counters: dict[str, list[int]] = {}
        self._starts: dict[str, list[int]] = {}
        self._last_ilvl: dict[str, int | None] = {}
        # startOverride 가 해당 (abstractNumId, ilvl) 의 **최초 1 회만** 적용되도록 기록.
        # reviewer 지시문은 `(numId, ilvl)` 표기였으나 실측 DOCX 에서 동일 abstract 를
        # 공유하는 다수 numId 가 각자 `override={0:1}` 를 갖고 있어 그대로 구현하면
        # numId 전환마다 counter 가 리셋(예: ISA-315 의 `1.`×7). 올바른 의도는
        # "abstract stream 의 첫 시작만 재조정" 이므로 abstract 단위 1 회 적용으로 해석.
        # reset() (기준서 경계) 에서 함께 초기화.
        self._override_applied: set[tuple[str, int]] = set()
        self._seen_warnings: set[tuple[str, ...]] = set()
        self._metrics: dict[BlockKind, int] = {}

    # -- public ------------------------------------------------------------

    def advance(self, num_id: str | None, ilvl: int | None) -> NumberedParagraph:
        if num_id is None:
            return self._emit_plain(num_id=None, ilvl=ilvl, suppressed=False)
        if num_id == "0":
            return self._emit_plain(num_id="0", ilvl=ilvl, suppressed=True)

        resolved = self._resolve_level(num_id, ilvl)
        if isinstance(resolved, NumberedParagraph):
            return resolved
        num_def, abstract, level = resolved
        # ilvl 가 None 이면 `_resolve_level` 이 위에서 NumberedParagraph 를 반환했다.
        assert ilvl is not None
        return self._emit_numbered(num_id, ilvl, num_def, abstract, level)

    def _resolve_level(
        self, num_id: str, ilvl: int | None
    ) -> NumberedParagraph | tuple[NumDef, AbstractNumDef, LevelDef]:
        """fallback 분기들을 한 곳으로 모은 helper. 정상 경로면 (num_def, abstract, level)."""
        num_def = self._num_defs.get(num_id)
        if num_def is None:
            self._warn_once(
                ("num_id_missing", num_id),
                f"[numbering] missing numId={num_id} in numbering.xml "
                "→ tagging kind='unknown_numbering'",
            )
            return self._emit_unknown(
                NumberingRaw(
                    num_id=num_id, ilvl=ilvl, abstract_num_id=None, lvl_text=None, num_fmt=None
                )
            )

        abstract = self._abstract_nums.get(num_def.abstract_num_id)
        if abstract is None:
            self._warn_once(
                ("abstract_missing", num_def.abstract_num_id),
                f"[numbering] missing abstractNumId={num_def.abstract_num_id} "
                f"(referenced by numId={num_id}) → tagging kind='unknown_numbering'",
            )
            return self._emit_unknown(
                NumberingRaw(
                    num_id=num_id,
                    ilvl=ilvl,
                    abstract_num_id=num_def.abstract_num_id,
                    lvl_text=None,
                    num_fmt=None,
                )
            )

        if ilvl is None:
            self._warn_once(
                ("ilvl_missing", num_def.abstract_num_id, "None"),
                f"[numbering] numPr/ilvl missing for numId={num_id} "
                "→ tagging kind='unknown_numbering'",
            )
            return self._emit_unknown(
                NumberingRaw(
                    num_id=num_id,
                    ilvl=None,
                    abstract_num_id=num_def.abstract_num_id,
                    lvl_text=None,
                    num_fmt=None,
                )
            )

        level = abstract.levels.get(ilvl)
        if level is None:
            self._warn_once(
                ("ilvl_missing", num_def.abstract_num_id, str(ilvl)),
                f"[numbering] ilvl={ilvl} not defined in abstractNumId="
                f"{num_def.abstract_num_id} → tagging kind='unknown_numbering'",
            )
            return self._emit_unknown(
                NumberingRaw(
                    num_id=num_id,
                    ilvl=ilvl,
                    abstract_num_id=num_def.abstract_num_id,
                    lvl_text=None,
                    num_fmt=None,
                )
            )

        return num_def, abstract, level

    def _emit_numbered(
        self,
        num_id: str,
        ilvl: int,
        num_def: NumDef,
        abstract: AbstractNumDef,
        level: LevelDef,
    ) -> NumberedParagraph:
        abstract_id = abstract.abstract_num_id
        counters = self._ensure_counter_state(abstract)

        # F4: startOverride 는 `(abstractNumId, ilvl)` 단위로 현재 기준서 내에서 최초
        # 1 회만 적용한다. 재등장 시 무효 — 다수 numId 가 같은 abstract 를 공유하면서
        # 각자 override={0:1} 를 달고 있어도 stream 이 쪼개지지 않는다.
        override_key = (abstract_id, ilvl)
        if override_key not in self._override_applied:
            override = num_def.level_overrides.get(ilvl)
            if override is not None:
                counters[ilvl] = override - 1
            self._override_applied.add(override_key)

        prev = self._last_ilvl.get(abstract_id)
        if prev is not None and ilvl > prev:
            # descent: 하위 카운터를 start-1 로 리셋 — 이후 +=1 이 `start` 를 생성하도록.
            starts = self._starts[abstract_id]
            for lv in range(prev + 1, ilvl + 1):
                counters[lv] = starts[lv] - 1

        counters[ilvl] += 1
        counter_tuple = tuple(counters[: ilvl + 1])

        kind = classify_kind(level.lvl_text, level.num_fmt, ilvl)
        if kind == BlockKind.UNKNOWN_NUMBERING:
            self._warn_once(
                ("pattern_unknown", level.lvl_text, level.num_fmt),
                f"[numbering] unknown pattern: abstractNumId={num_def.abstract_num_id}, "
                f"ilvl={ilvl}, lvlText={level.lvl_text!r}, numFmt={level.num_fmt!r} "
                "→ tagging kind='unknown_numbering'",
            )
            paragraph_id = ""
        elif kind == BlockKind.BULLET:
            paragraph_id = ""
        else:
            paragraph_id = render_lvl_text(level.lvl_text, counter_tuple, abstract)

        self._last_ilvl[abstract_id] = ilvl
        self._bump_metric(kind)
        return NumberedParagraph(
            kind=kind,
            paragraph_id=paragraph_id,
            counter_tuple=counter_tuple,
            numbering_suppressed=False,
            numbering_raw=NumberingRaw(
                num_id=num_id,
                ilvl=ilvl,
                abstract_num_id=num_def.abstract_num_id,
                lvl_text=level.lvl_text,
                num_fmt=level.num_fmt,
            ),
        )

    def metrics(self) -> Mapping[str, int]:
        """strategy §5.5 — kind 별 누적 카운트."""
        return MappingProxyType({k.value: v for k, v in self._metrics.items()})

    def reset(self) -> None:
        """기준서 경계에서 카운터 상태를 초기화.

        `abstract_nums` / `num_defs` / `_seen_warnings` / `_metrics` 는 유지한다.
        근거: `docs/numbering_strategy.md §4.4` 옵션 A 가 "동일 numId 는 기준서 간
        재사용되지 않는다" 를 전제로 했으나, 실측에서 9 개 numId 가 2~8 개 기준서에
        공유되고 그 중 7 개는 `lvlOverride` 가 없음. 리셋 없이는 `paragraph_id` 가
        밀린다. `structure.py._enter_standard()` 에서 호출된다.
        """
        self._counters.clear()
        self._starts.clear()
        self._last_ilvl.clear()
        self._override_applied.clear()

    # -- internals ---------------------------------------------------------

    def _ensure_counter_state(self, abstract: AbstractNumDef) -> list[int]:
        """abstractNumId 단위로 counter/start 상태를 초기화 (최초 등장 시 1 회).

        기본 start 는 abstract.levels[ilvl].start 를 사용. numId 별 startOverride 는
        여기서 반영하지 않고 `_emit_numbered` 에서 (numId, ilvl) 첫 등장 시 1 회 적용.
        """
        abstract_id = abstract.abstract_num_id
        counters = self._counters.get(abstract_id)
        if counters is not None:
            return counters
        starts = [1] * _MAX_ILVL
        for lv in range(_MAX_ILVL):
            level = abstract.levels.get(lv)
            if level is not None:
                starts[lv] = level.start
        # 카운터 초기값: start - 1 (advance() 가 +1 수행하기 때문)
        state = [s - 1 for s in starts]
        self._counters[abstract_id] = state
        self._starts[abstract_id] = list(starts)
        self._last_ilvl[abstract_id] = None
        return state

    def _emit_plain(
        self, num_id: str | None, ilvl: int | None, suppressed: bool
    ) -> NumberedParagraph:
        self._bump_metric(BlockKind.PARAGRAPH_BODY)
        return NumberedParagraph(
            kind=BlockKind.PARAGRAPH_BODY,
            paragraph_id="",
            counter_tuple=(),
            numbering_suppressed=suppressed,
            numbering_raw=NumberingRaw(
                num_id=num_id,
                ilvl=ilvl,
                abstract_num_id=None,
                lvl_text=None,
                num_fmt=None,
            ),
        )

    def _emit_unknown(self, raw: NumberingRaw) -> NumberedParagraph:
        self._bump_metric(BlockKind.UNKNOWN_NUMBERING)
        return NumberedParagraph(
            kind=BlockKind.UNKNOWN_NUMBERING,
            paragraph_id="",
            counter_tuple=(),
            numbering_suppressed=False,
            numbering_raw=raw,
        )

    def _warn_once(self, key: tuple[str, ...], message: str) -> None:
        if key in self._seen_warnings:
            return
        self._seen_warnings.add(key)
        warnings.warn(message, UserWarning, stacklevel=3)

    def _bump_metric(self, kind: BlockKind) -> None:
        self._metrics[kind] = self._metrics.get(kind, 0) + 1


def advance_sequence(
    engine: NumberingEngine, pairs: Iterator[tuple[str | None, int | None]]
) -> Iterator[NumberedParagraph]:
    """편의 helper — `(num_id, ilvl)` sequence 를 engine 에 주입해 결과 스트림 반환."""
    for num_id, ilvl in pairs:
        yield engine.advance(num_id, ilvl)


__all__ = [
    "AbstractNumDef",
    "LevelDef",
    "NumDef",
    "NumFmt",
    "NumberedParagraph",
    "NumberingEngine",
    "NumberingRaw",
    "advance_sequence",
    "classify_kind",
    "format_counter",
    "parse_numbering_from_docx",
    "parse_numbering_xml",
    "render_lvl_text",
]
