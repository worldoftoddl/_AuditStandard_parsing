"""Stage 2 ``ingest`` 서브패키지 — MD → JSON → Qdrant.

Phase 2 범위:
- `md_parser`: MD → `ParsedStandard` (Pass 1 조립 + Pass 2 collision suffix).
- `chunk_splitter`: Pass 3 — 4000 토큰 초과 chunk 분할 (§9.3/§9.4).

Phase 3 범위 (미구현):
- `embedder`: Upstage Solar 임베딩.
- `qdrant_writer`: Collection 업서트.
"""

from audit_parser.ingest.chunk_splitter import (
    HARD_LIMIT,
    SOFT_LIMIT,
    ChunkSplitError,
    split_oversized_chunks,
)
from audit_parser.ingest.md_parser import (
    MD_SCHEMA_SUPPORTED,
    ChunkIdCollisionError,
    UnsupportedMdSchemaError,
    assert_chunk_id_uniqueness,
    compute_heading_trail_hash,
    count_tokens,
    parse_comment_fields,
    parse_md,
    parse_md_dir,
    to_json_dict,
)
from audit_parser.ingest.types import (
    JSON_SCHEMA_VERSION,
    ChunkRecord,
    ParagraphLink,
    ParsedStandard,
    StandardRecord,
    StandardSummary,
)

__all__ = [
    "HARD_LIMIT",
    "JSON_SCHEMA_VERSION",
    "MD_SCHEMA_SUPPORTED",
    "SOFT_LIMIT",
    "ChunkIdCollisionError",
    "ChunkRecord",
    "ChunkSplitError",
    "ParagraphLink",
    "ParsedStandard",
    "StandardRecord",
    "StandardSummary",
    "UnsupportedMdSchemaError",
    "assert_chunk_id_uniqueness",
    "compute_heading_trail_hash",
    "count_tokens",
    "parse_comment_fields",
    "parse_md",
    "parse_md_dir",
    "split_oversized_chunks",
    "to_json_dict",
]
