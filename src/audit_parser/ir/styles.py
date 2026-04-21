"""`word/styles.xml` 파서 + style-level numPr 상속 해결기 — Phase 1 rework (F1).

CHECKPOINT 1 검수에서 발견된 치명적 결함: 파서가 문단-직속 `<w:pPr><w:numPr>` 만
해석하고 `word/styles.xml` 에 정의된 **스타일 레벨 기본 numPr** 을 상속하지 못해
ISA-200/500/1200 등 12 개 기준서에서 820+ 문단의 번호가 유실됨.

본 모듈은 styles.xml 에서 styleId → (display_name, based_on, num_id, ilvl) 을
추출하고, 문단 단위로 "문단 직속 → 스타일 → basedOn 재귀" 우선순위로 효과적
`(num_id, ilvl)` 을 계산한다.

근거: `docs/checkpoint_1_review.md §1` 및 domain-reviewer DM.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from lxml import etree

from audit_parser.ir._xml import safe_fromstring

_W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMAP: Final[dict[str, str]] = {"w": _W_NS}


def _qn(tag: str) -> str:
    prefix, _, local = tag.partition(":")
    return f"{{{_NSMAP[prefix]}}}{local}"


_TAG_STYLE: Final = _qn("w:style")
_TAG_NAME: Final = _qn("w:name")
_TAG_BASED_ON: Final = _qn("w:basedOn")
_TAG_PPR: Final = _qn("w:pPr")
_TAG_NUMPR: Final = _qn("w:numPr")
_TAG_NUMID: Final = _qn("w:numId")
_TAG_ILVL: Final = _qn("w:ilvl")
_ATTR_VAL: Final = _qn("w:val")
_ATTR_STYLE_ID: Final = _qn("w:styleId")

_MAX_BASED_ON_DEPTH: Final = 10


@dataclass(slots=True, frozen=True)
class StyleNumDefault:
    """styles.xml 의 `<w:style>` 한 엔트리 — numPr 및 basedOn 정보만 추출."""

    style_id: str
    based_on: str | None
    num_id: str | None
    ilvl: int | None


@dataclass(slots=True, frozen=True)
class StyleIndex:
    """styles.xml 을 한 번만 순회해 얻는 2 종 매핑의 번들.

    - ``display_names`` : styleId → 한국어 표시 이름 (heading 매핑·디버깅용)
    - ``num_defaults``  : styleId → `StyleNumDefault` (상속 해결용)
    """

    display_names: Mapping[str, str]
    num_defaults: Mapping[str, StyleNumDefault]


def parse_styles_xml(raw_xml: bytes) -> StyleIndex:
    """`word/styles.xml` 바이트 → (display_names, num_defaults) 2 중 매핑.

    display_name 이 없는 styleId 는 display_names 에서 생략하고 styleId 를 그대로
    사용하도록 호출자에서 fallback 한다.
    """
    root = safe_fromstring(raw_xml)
    display_names: dict[str, str] = {}
    num_defaults: dict[str, StyleNumDefault] = {}

    for style in root.findall(_TAG_STYLE):
        style_id = style.get(_ATTR_STYLE_ID)
        if style_id is None:
            continue

        name_elem = style.find(_TAG_NAME)
        if name_elem is not None:
            display = name_elem.get(_ATTR_VAL)
            if display is not None:
                display_names[style_id] = display

        num_defaults[style_id] = _extract_style_numpr(style, style_id)

    return StyleIndex(
        display_names=MappingProxyType(display_names),
        num_defaults=MappingProxyType(num_defaults),
    )


def _extract_style_numpr(style_elem: etree._Element, style_id: str) -> StyleNumDefault:
    based_on_elem = style_elem.find(_TAG_BASED_ON)
    based_on = based_on_elem.get(_ATTR_VAL) if based_on_elem is not None else None

    num_id: str | None = None
    ilvl: int | None = None
    numpr = style_elem.find(f"{_TAG_PPR}/{_TAG_NUMPR}")
    if numpr is not None:
        num_id_elem = numpr.find(_TAG_NUMID)
        if num_id_elem is not None:
            num_id = num_id_elem.get(_ATTR_VAL)
        ilvl_elem = numpr.find(_TAG_ILVL)
        if ilvl_elem is not None:
            raw_ilvl = ilvl_elem.get(_ATTR_VAL)
            if raw_ilvl is not None:
                try:
                    ilvl = int(raw_ilvl)
                except ValueError:
                    ilvl = None

    return StyleNumDefault(
        style_id=style_id,
        based_on=based_on,
        num_id=num_id,
        ilvl=ilvl,
    )


def resolve_paragraph_numPr(
    p_num_id: str | None,
    p_ilvl: int | None,
    style_id: str | None,
    num_defaults: Mapping[str, StyleNumDefault],
) -> tuple[str | None, int | None]:
    """문단 직속 → 스타일 → basedOn 체인 우선순위로 (num_id, ilvl) 확정.

    규칙 (`docs/checkpoint_1_review.md §1.5.1`):

    1. 문단 직속 `num_id` 가 있으면 (suppression 마커 '0' 포함) 그대로 사용.
       ilvl 은 문단 직속을 우선하고, 없으면 그대로 ``p_ilvl`` (``None`` 허용).
    2. 문단 직속이 없으면 ``style_id`` 의 ``StyleNumDefault`` 조회. numId 가 있으면
       그 스타일의 ilvl 을 사용. 문단이 ilvl 만 별도 지정했다면 문단 ilvl 이 우선.
    3. 스타일에 numId 가 없으면 ``based_on`` 을 재귀 추적 (최대 10 단계, cycle 방지).
       basedOn 체인 어디에도 numId 없으면 ``(None, p_ilvl)``.
    """
    if p_num_id is not None:
        return p_num_id, p_ilvl
    if style_id is None:
        return None, p_ilvl
    inherited = _resolve_style_chain(style_id, num_defaults, depth=0, visited=None)
    if inherited is None:
        return None, p_ilvl
    style_num_id, style_ilvl = inherited
    effective_ilvl = p_ilvl if p_ilvl is not None else style_ilvl
    return style_num_id, effective_ilvl


def _resolve_style_chain(
    style_id: str,
    num_defaults: Mapping[str, StyleNumDefault],
    depth: int,
    visited: set[str] | None,
) -> tuple[str, int] | None:
    """basedOn 체인을 재귀 추적해 처음으로 numId 가 정의된 조상 스타일의 (numId, ilvl) 반환.

    중간 조상이 ilvl 만 재정의했다면 그 값이 아래 후손보다 **덜 구체적**이므로 덮지 않는다
    (후손의 ilvl 이 더 구체적). basedOn 링크가 끊기거나 cycle 이면 ``None``.
    """
    if depth >= _MAX_BASED_ON_DEPTH:
        return None
    if visited is None:
        visited = set()
    if style_id in visited:
        return None
    visited.add(style_id)

    entry = num_defaults.get(style_id)
    if entry is None:
        return None
    if entry.num_id is not None:
        # 이 스타일 자체에 numId 가 있으면 이 지점에서 확정.
        effective_ilvl = entry.ilvl if entry.ilvl is not None else 0
        return entry.num_id, effective_ilvl
    if entry.based_on is None:
        return None
    parent = _resolve_style_chain(entry.based_on, num_defaults, depth + 1, visited)
    if parent is None:
        return None
    parent_num_id, parent_ilvl = parent
    # 본 스타일이 ilvl 만 override 했다면 후손 우선.
    effective_ilvl = entry.ilvl if entry.ilvl is not None else parent_ilvl
    return parent_num_id, effective_ilvl


__all__ = [
    "StyleIndex",
    "StyleNumDefault",
    "parse_styles_xml",
    "resolve_paragraph_numPr",
]
