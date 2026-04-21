"""XML 파서 보안 래퍼 — Phase 1.5 C1.

lxml 기본 파서는 외부 엔티티 로드/XXE/엔티티 확장(billion laughs) 에 취약하다.
DOCX 내부 XML (`word/document.xml`, `word/numbering.xml`, `word/styles.xml`) 은 신뢰 범위
바깥의 사용자 제공 파일이므로 공격 벡터가 될 수 있다.

모든 ir/ 서브모듈은 `safe_fromstring` / `safe_parse` 를 통해서만 파싱한다.
직접 `etree.fromstring` / `etree.parse` 호출 금지.
"""

from __future__ import annotations

from typing import IO

from lxml import etree

_SECURE_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    huge_tree=False,
    load_dtd=False,
    dtd_validation=False,
)


def safe_fromstring(raw_xml: bytes) -> etree._Element:
    """bytes → Element. 엔티티 해결·DTD 로드·네트워크 fetch 전부 차단."""
    return etree.fromstring(raw_xml, parser=_SECURE_PARSER)


def safe_parse(source: IO[bytes]) -> etree._ElementTree:
    """file-like → ElementTree. 엔티티·DTD·네트워크 차단."""
    return etree.parse(source, parser=_SECURE_PARSER)


__all__ = ["safe_fromstring", "safe_parse"]
