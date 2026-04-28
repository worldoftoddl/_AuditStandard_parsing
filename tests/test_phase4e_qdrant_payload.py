"""Phase 4e Qdrant payload and target mapping regression tests."""

from __future__ import annotations

import pytest
import typer

from audit_parser.cli import _phase4e_targets
from audit_parser.ingest.qdrant_writer import _chunk_payload, _summary_payload
from audit_parser.ingest.types import ChunkRecord, StandardRecord, StandardSummary


def _standard() -> StandardRecord:
    return StandardRecord(
        standard_id="FRMK-1",
        standard_no="1",
        standard_title="인증업무개념체계",
        source_file="인증업무개념체계(2022년 개정)_전문.docx",
        authority_base=1,
    )


def test_chunk_payload_preserves_special_appendix_name() -> None:
    """FRMK un-numbered appendix title must survive into Qdrant payload."""
    chunk = ChunkRecord(
        chunk_id="FRMK-1:appendix:abcd1234:paragraph_body#1",
        paragraph_id=None,
        kind="paragraph_body",
        section="appendix",
        appendix_index=None,
        heading_trail=("FRMK-1", "보론: 역할과 책임"),
        heading_trail_hash="abcd1234",
        content_text="역할과 책임 본문",
        content_markdown="역할과 책임 본문",
        authority=1,
        parent_paragraph_id=None,
        is_application_guidance=False,
        token_estimate=10,
        chunk_index=0,
        chunk_of=1,
        source_idx=42,
        special_appendix_name="역할과 책임",
    )

    payload = _chunk_payload(_standard(), chunk)

    assert payload["special_appendix_name"] == "역할과 책임"
    assert payload["appendix_index"] is None


def test_summary_payload_sets_special_appendix_name_null() -> None:
    """standard_summary point keeps the same payload key with null value."""
    summary = StandardSummary(
        scope_text=None,
        scope_markdown=None,
        definitions_text=None,
        definitions_markdown=None,
    )

    payload = _summary_payload(
        _standard(),
        summary,
        embed_model="embedding-passage",
        embedded_at="2026-04-28T00:00:00Z",
    )

    assert payload["kind"] == "standard_summary"
    assert payload["special_appendix_name"] is None


def test_phase4e_targets_are_deterministic() -> None:
    targets = _phase4e_targets(None)

    assert targets == [
        ("ISQM-1", "audit_standards_품질관리기준서_2018"),
        ("ASSR-3000", "audit_standards_기타인증업무기준_2022"),
        ("FRMK-1", "audit_standards_인증업무개념체계_2022"),
    ]


def test_phase4e_targets_can_filter_by_collection_or_standard_id() -> None:
    assert _phase4e_targets("FRMK-1") == [
        ("FRMK-1", "audit_standards_인증업무개념체계_2022")
    ]
    assert _phase4e_targets("audit_standards_품질관리기준서_2018") == [
        ("ISQM-1", "audit_standards_품질관리기준서_2018")
    ]


def test_phase4e_targets_reject_unknown_target() -> None:
    with pytest.raises(typer.BadParameter):
        _phase4e_targets("audit_standards_unknown")
