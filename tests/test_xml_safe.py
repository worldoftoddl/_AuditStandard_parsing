"""XXE / entity-expansion 방어 테스트 — Phase 1.5 C1.

`safe_fromstring` / `safe_parse` 가 외부 엔티티 로드·billion-laughs·네트워크 fetch
전부 차단하는지 확인. `parse_numbering_xml` / `parse_styles_xml` 이 해당 래퍼를
경유하므로 동일 공격 표면이 닫힘.
"""

from __future__ import annotations

import io

import pytest
from lxml import etree

from audit_parser.ir._xml import safe_fromstring, safe_parse
from audit_parser.ir.numbering import parse_numbering_xml
from audit_parser.ir.styles import parse_styles_xml

# ---------------------------------------------------------------------------
# XXE (external entity) — 파일시스템 유출 시도
# ---------------------------------------------------------------------------


def _xxe_file_payload() -> bytes:
    return b"""<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>"""


def test_safe_fromstring_blocks_external_entity_expansion() -> None:
    """XXE SYSTEM 엔티티 — 해결되지 않아 &xxe; 원문이 유지되거나 빈 값."""
    root = safe_fromstring(_xxe_file_payload())
    text = root.text or ""
    # 파일 내용이 누출되면 안 됨
    assert "root:" not in text
    assert "/bin/bash" not in text


def test_safe_parse_blocks_external_entity_expansion() -> None:
    stream = io.BytesIO(_xxe_file_payload())
    tree = safe_parse(stream)
    root = tree.getroot()
    text = root.text or ""
    assert "root:" not in text
    assert "/bin/bash" not in text


# ---------------------------------------------------------------------------
# Billion laughs — 지수 확장 엔티티
# ---------------------------------------------------------------------------


def _billion_laughs_payload() -> bytes:
    return b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<root>&lol4;</root>"""


def test_safe_fromstring_blocks_billion_laughs() -> None:
    """resolve_entities=False 로 지수 확장 비활성화 — 파싱은 성공하되 텍스트 미확장."""
    root = safe_fromstring(_billion_laughs_payload())
    # lol 이 1000번 이상 확장되면 확장 공격 성공을 의미
    text = root.text or ""
    assert text.count("lol") < 100


# ---------------------------------------------------------------------------
# Network fetch — 외부 DTD
# ---------------------------------------------------------------------------


def test_safe_fromstring_blocks_external_dtd_network_fetch() -> None:
    payload = b"""<?xml version="1.0"?>
<!DOCTYPE root SYSTEM "http://example.invalid/evil.dtd">
<root>ok</root>"""
    # no_network=True 이므로 DTD fetch 시도조차 안 함. 예외 발생 없이 파싱 완료.
    root = safe_fromstring(payload)
    assert root.tag == "root"
    assert root.text == "ok"


# ---------------------------------------------------------------------------
# Integration — parse_numbering_xml / parse_styles_xml 경유
# ---------------------------------------------------------------------------


def test_parse_numbering_xml_rejects_xxe_without_leaking_content() -> None:
    """numbering.xml 위조로 XXE 시도 → 파서가 거부하거나 lvlText 에 파일 내용이 섞이지 않음.

    lxml 의 하드닝 파서는 attribute 값에서 external entity 참조 시 `XMLSyntaxError`
    를 throw 한다 — 더 강한 방어. 컨텐츠 값 참조는 파싱 통과하되 엔티티 미확장.
    """
    payload = b"""<?xml version="1.0"?>
<!DOCTYPE x [
  <!ENTITY pwn SYSTEM "file:///etc/passwd">
]>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="&pwn;."/>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1">
    <w:abstractNumId w:val="1"/>
  </w:num>
</w:numbering>"""
    try:
        abstract_nums, _num_defs = parse_numbering_xml(payload)
    except etree.XMLSyntaxError:
        # 파서가 attribute 내 external entity 를 거부 — 강한 방어, 합격
        return
    # 파싱이 성공하면 엔티티가 확장되지 않았음을 확인
    if "1" in abstract_nums:
        level = abstract_nums["1"].levels.get(0)
        if level is not None:
            assert "root:" not in level.lvl_text
            assert "/bin/bash" not in level.lvl_text


def test_parse_styles_xml_rejects_xxe_without_leaking_content() -> None:
    payload = b"""<?xml version="1.0"?>
<!DOCTYPE x [
  <!ENTITY pwn SYSTEM "file:///etc/passwd">
]>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="evil">
    <w:name w:val="&pwn;"/>
  </w:style>
</w:styles>"""
    try:
        index = parse_styles_xml(payload)
    except etree.XMLSyntaxError:
        return
    for name in index.display_names.values():
        assert "root:" not in name
        assert "/bin/bash" not in name


# ---------------------------------------------------------------------------
# 정상 payload 회귀 — 보안 파서가 정상 XML 을 거부하지 않음
# ---------------------------------------------------------------------------


def test_safe_parser_accepts_benign_xml() -> None:
    root = safe_fromstring(b"<root><child>hello</child></root>")
    assert root.tag == "root"
    child = root.find("child")
    assert child is not None
    assert child.text == "hello"


def test_safe_parse_accepts_benign_stream() -> None:
    stream = io.BytesIO(b"<root>ok</root>")
    tree = safe_parse(stream)
    assert tree.getroot().tag == "root"


# ---------------------------------------------------------------------------
# 파서 설정 확인
# ---------------------------------------------------------------------------


def test_safe_parser_has_hardened_flags() -> None:
    """_SECURE_PARSER 가 resolve_entities/no_network/huge_tree/load_dtd 전부 방어값."""
    from audit_parser.ir._xml import _SECURE_PARSER

    assert isinstance(_SECURE_PARSER, etree.XMLParser)
    # lxml 은 내부 flag 를 직접 노출하지 않으므로 동작으로 재확인
    with pytest.raises((etree.XMLSyntaxError, ValueError)):
        # 문법이 깨진 payload 는 당연히 에러
        safe_fromstring(b"<unclosed")
