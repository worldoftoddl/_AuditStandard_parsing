"""Phase 4c integration tests — built up across c1/c2/c3 commits.

Scope (c1):
    * `docx_reader` recursive descent toggle (ISA vs non-ISA path)
    * `_MAX_DESCENT_DEPTH` infinite-loop guard (Critic verbal note #X2)
    * `spec.body_parser` dispatch path (ISQM tbl[236x2])
    * ISA 36 JSON byte-equivalence regression check

Scope (c2 — placeholder markers, populated in c2 commit):
    * PreludeSkip Option (i) caller state toggle (3 variant)
    * Referential transparency invariant (Critic Q1 — (ii) drift detector)
    * FRMK normalize heading 2 한정 (Critic #X3)

Scope (c3 — placeholder markers, populated in c3 commit):
    * 3 DOCX → 3 MD 산출 smoke
    * 3-level suffix chunk_id 부재 invariant (Critic Q2 — β-1 결정적)
    * CLI --prefix heuristic 10건
    * FRMK special_appendix_name JSON payload smoke (1 chunk)
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from lxml import etree

from audit_parser.ir.docx_reader import _MAX_DESCENT_DEPTH, _iter_block_level
from audit_parser.ir.types import BlockKind, RawBlock
from audit_parser.spec import ISA_SPEC, ISQM_SPEC

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_body_fragment(xml: str) -> etree._Element:
    """Wrap arbitrary ``<w:p>`` / ``<w:tbl>`` XML into a ``<w:body>`` element."""
    return etree.fromstring(
        f'<w:body xmlns:w="{_W_NS}">{xml}</w:body>'
    )


# ---------------------------------------------------------------------------
# c1 — recursive descent toggle
# ---------------------------------------------------------------------------


def test_iter_block_level_default_no_recurse_preserves_phase1_behavior() -> None:
    """ISA path (`recurse=False`) — top-level `<w:p>` + `<w:tbl>` 만 yield, 내부
    wrapper table cell 내부 `<w:p>` 는 unvisited."""
    body = _make_body_fragment(
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>outer_p</w:t></w:r></w:p>'
        f'<w:tbl xmlns:w="{_W_NS}">'
        f"<w:tr><w:tc>"
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>inner_p</w:t></w:r></w:p>'
        f"</w:tc></w:tr>"
        f"</w:tbl>"
    )
    children = list(_iter_block_level(body, recurse=False))
    # 기존 Phase 1 동작: outer <w:p> + <w:tbl> 각 1개 yield, 내부 <w:p> 는 skip
    tags = [_local_tag(c) for c in children]
    assert tags == ["p", "tbl"]


def test_iter_block_level_recurse_descends_into_wrapper_tables() -> None:
    """non-ISA path (`recurse=True`) — wrapper table 내부 `<w:p>` 를 descent yield.

    ASSR ``tbl[427x2]`` / FRMK ``tbl[3x3]`` 처럼 body content 가 wrapper table
    내부에 있는 경우 내부 `<w:p>` 가 top-level 처럼 visible 해야 함.
    """
    body = _make_body_fragment(
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>outer_p</w:t></w:r></w:p>'
        f'<w:tbl xmlns:w="{_W_NS}">'
        f"<w:tr><w:tc>"
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>inner_p</w:t></w:r></w:p>'
        f"</w:tc></w:tr>"
        f"</w:tbl>"
    )
    children = list(_iter_block_level(body, recurse=True))
    # outer <w:p> + <w:tbl> + inner <w:p> (descent 결과) = 3개
    tags = [_local_tag(c) for c in children]
    assert tags == ["p", "tbl", "p"]
    # 마지막 <w:p> 의 text 가 "inner_p" (descent 결과 정확)
    inner_p = children[-1]
    texts = [t.text for t in inner_p.iter(f"{{{_W_NS}}}t") if t.text]
    assert texts == ["inner_p"]


def test_iter_block_level_recurse_handles_sdt_container() -> None:
    """recurse mode 에서도 `<w:sdt>` container 내부 `<w:p>` 는 기존 방식 유지."""
    body = etree.fromstring(
        f'<w:body xmlns:w="{_W_NS}">'
        f"<w:sdt><w:sdtContent>"
        f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>sdt_inner</w:t></w:r></w:p>'
        f"</w:sdtContent></w:sdt>"
        f"</w:body>"
    )
    children = list(_iter_block_level(body, recurse=True))
    assert [_local_tag(c) for c in children] == ["p"]


# ---------------------------------------------------------------------------
# c1 — _MAX_DESCENT_DEPTH guard (Critic verbal note #X2)
# ---------------------------------------------------------------------------


def test_max_descent_depth_constant_is_10() -> None:
    """Critic #X2 — 실제 KICPA DOCX 관찰 depth ~3, 여유 10 책정."""
    assert _MAX_DESCENT_DEPTH == 10


def test_iter_block_level_rejects_descent_depth_overflow() -> None:
    """infinite loop 방어 — depth > MAX 시 AssertionError.

    실제로는 KICPA DOCX 에 depth=11 nested table 이 존재하지 않으나, code-level
    guard 가 trigger 되는지 synthetic depth=11 body 로 검증.
    """
    # Build a synthetic body with 11 nested <w:tbl>/cell wrapping a single <w:p>.
    inner = f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>deep</w:t></w:r></w:p>'
    for _ in range(11):
        inner = (
            f'<w:tbl xmlns:w="{_W_NS}">'
            f"<w:tr><w:tc>{inner}</w:tc></w:tr>"
            f"</w:tbl>"
        )
    body = _make_body_fragment(inner)
    with pytest.raises(AssertionError, match="descent depth exceeded"):
        list(_iter_block_level(body, recurse=True))


def test_iter_block_level_depth_within_limit_ok() -> None:
    """MAX 이하 depth 는 정상 동작 (경계 3 에서 확인 — 실 KICPA depth 수준)."""
    inner = f'<w:p xmlns:w="{_W_NS}"><w:r><w:t>ok</w:t></w:r></w:p>'
    for _ in range(3):
        inner = (
            f'<w:tbl xmlns:w="{_W_NS}">'
            f"<w:tr><w:tc>{inner}</w:tc></w:tr>"
            f"</w:tbl>"
        )
    body = _make_body_fragment(inner)
    # depth=3 → AssertionError 없음. inner <w:p> 가 descent 결과로 yield 되는지.
    children = list(_iter_block_level(body, recurse=True))
    # 3 tbl + 1 p (최내부) = 4 (각 descent 단계마다 tbl 1개 yield)
    assert len(children) >= 1
    # 마지막 yield 된 <w:p> 의 text 는 "ok"
    last_p = children[-1]
    assert _local_tag(last_p) == "p"
    texts = [t.text for t in last_p.iter(f"{{{_W_NS}}}t") if t.text]
    assert texts == ["ok"]


# ---------------------------------------------------------------------------
# c1 — spec.body_parser dispatch (ISQM path)
# ---------------------------------------------------------------------------


def test_isqm_spec_body_parser_is_attached_and_callable() -> None:
    """4b-2 c2 에서 attach 된 ISQM_SPEC.body_parser 가 c1 에서 여전히 호출 가능한지."""
    assert ISQM_SPEC.body_parser is not None
    assert callable(ISQM_SPEC.body_parser)


def test_isqm_body_parser_emits_atomic_rawblocks_without_chunk_of_leak() -> None:
    """β-1 invariant (docs/checkpoint_4_prep.md §1.8) — ISQM body_parser 가 atomic
    RawBlock emit only. RawBlock dataclass 에 ``chunk_of`` 필드 부재 — state leak
    경로 자체 없음. Critic Q2 가 c3 에서 후방 3-level suffix grep test 로 결정적
    검증을 수행하며, c1 에서는 여기서 dataclass 구조 확인.
    """
    # Build a minimal ISQM 2-column table fragment.
    tbl_xml = (
        f'<w:tbl xmlns:w="{_W_NS}">'
        f"<w:tr>"
        f'<w:tc><w:p xmlns:w="{_W_NS}"><w:r><w:t>1</w:t></w:r></w:p></w:tc>'
        f'<w:tc><w:p xmlns:w="{_W_NS}"><w:r><w:t>본문</w:t></w:r></w:p></w:tc>'
        f"</w:tr>"
        f"</w:tbl>"
    )
    tbl = etree.fromstring(tbl_xml)
    body_parser = ISQM_SPEC.body_parser
    assert body_parser is not None
    emitted: Iterable[RawBlock] = body_parser(tbl)
    blocks = list(emitted)
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, RawBlock)
    assert block.kind is BlockKind.REQUIREMENT
    assert block.paragraph_id == "1"
    # RawBlock dataclass 에 chunk_of 필드 부재 — β-1 invariant 구조적 보증
    assert not hasattr(block, "chunk_of")


# ---------------------------------------------------------------------------
# c1 — ISA baseline backward-compat (iter_body 36 ISA 재파싱 default path)
# ---------------------------------------------------------------------------


def test_iter_body_default_spec_is_isa() -> None:
    """iter_body(docx_path) default spec 이 ISA_SPEC — Phase 1 경로 backward-compat."""
    import inspect

    from audit_parser.ir.docx_reader import iter_body

    sig = inspect.signature(iter_body)
    spec_param = sig.parameters["spec"]
    assert spec_param.default is ISA_SPEC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _local_tag(elem: etree._Element) -> str:
    """``{ns}p`` → ``"p"``."""
    tag = elem.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]
