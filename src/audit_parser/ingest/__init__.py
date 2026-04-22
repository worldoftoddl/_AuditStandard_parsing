"""Stage 2 ``ingest`` 서브패키지 — MD → JSON → Qdrant.

Phase 2 범위:
- `md_parser`: MD → `ParsedStandard` (Pass 1 조립 + Pass 2 collision suffix).
- `chunk_splitter`: Pass 3 — 4000 토큰 초과 chunk 분할 (§9.3/§9.4).

Phase 3 범위:
- `embedder`: Upstage Solar 임베딩 + SQLite 캐시 (WAL, integrity_check).
- `qdrant_writer`: Collection 생성 + named-vectors + payload 업서트.
"""

from audit_parser.ingest.chunk_splitter import (
    HARD_LIMIT,
    SOFT_LIMIT,
    ChunkSplitError,
    split_oversized_chunks,
)
from audit_parser.ingest.embedder import (
    EMBED_DIM,
    HARD_LIMIT_TOKENS,
    MODEL_PASSAGE,
    MODEL_QUERY,
    SOLAR_BASE_URL,
    Embedder,
    EmbeddingAPIError,
    EmbeddingDimError,
    EmbeddingOverflowError,
    EmbeddingResult,
    EmbedError,
    EmbedStats,
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
from audit_parser.ingest.qdrant_writer import (
    COLLECTION_DEFAULT,
    HNSW_EF_CONSTRUCT,
    HNSW_M,
    KIND_STANDARD_SUMMARY,
    VECTOR_PASSAGE,
    VECTOR_SUMMARY,
    QdrantWriteError,
    QdrantWriter,
    QdrantWriterConfig,
    QdrantWriterError,
    UpsertResult,
    chunk_id_to_point_id,
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
    "COLLECTION_DEFAULT",
    "EMBED_DIM",
    "HARD_LIMIT",
    "HARD_LIMIT_TOKENS",
    "HNSW_EF_CONSTRUCT",
    "HNSW_M",
    "JSON_SCHEMA_VERSION",
    "KIND_STANDARD_SUMMARY",
    "MD_SCHEMA_SUPPORTED",
    "MODEL_PASSAGE",
    "MODEL_QUERY",
    "SOFT_LIMIT",
    "SOLAR_BASE_URL",
    "VECTOR_PASSAGE",
    "VECTOR_SUMMARY",
    "ChunkIdCollisionError",
    "ChunkRecord",
    "ChunkSplitError",
    "EmbedError",
    "EmbedStats",
    "Embedder",
    "EmbeddingAPIError",
    "EmbeddingDimError",
    "EmbeddingOverflowError",
    "EmbeddingResult",
    "ParagraphLink",
    "ParsedStandard",
    "QdrantWriteError",
    "QdrantWriter",
    "QdrantWriterConfig",
    "QdrantWriterError",
    "StandardRecord",
    "StandardSummary",
    "UnsupportedMdSchemaError",
    "UpsertResult",
    "assert_chunk_id_uniqueness",
    "chunk_id_to_point_id",
    "compute_heading_trail_hash",
    "count_tokens",
    "parse_comment_fields",
    "parse_md",
    "parse_md_dir",
    "split_oversized_chunks",
    "to_json_dict",
]
