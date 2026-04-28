"""Phase 4f retrieval evaluation and Qdrant smoke checks.

The script intentionally keeps the evaluation small and deterministic:

* verify all four Qdrant collections against local JSON point counts;
* run an ISQM Mini Golden dataset with Recall@5 and MRR@10;
* run a two-stage summary -> passage smoke query for each collection.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from audit_parser.ingest.embedder import Embedder
from audit_parser.ingest.qdrant_writer import (
    COLLECTION_DEFAULT,
    VECTOR_PASSAGE,
    VECTOR_SUMMARY,
    QdrantWriter,
    QdrantWriterConfig,
)

ISQM_COLLECTION = "audit_standards_품질관리기준서_2018"
ASSR_COLLECTION = "audit_standards_기타인증업무기준_2022"
FRMK_COLLECTION = "audit_standards_인증업무개념체계_2022"

COLLECTION_JSON_PATTERNS: dict[str, tuple[str, ...]] = {
    COLLECTION_DEFAULT: ("ISA-*.json",),
    ISQM_COLLECTION: ("ISQM-1.json",),
    ASSR_COLLECTION: ("ASSR-3000.json",),
    FRMK_COLLECTION: ("FRMK-1.json",),
}

SMOKE_QUERIES: tuple[tuple[str, str, str], ...] = (
    (
        "SMOKE-ISA",
        COLLECTION_DEFAULT,
        "회계추정치와 관련 공시에 대한 감사에서 경영진 추정치 평가",
    ),
    (
        "SMOKE-ISQM",
        ISQM_COLLECTION,
        "품질관리시스템 운영책임과 리더십 책임",
    ),
    (
        "SMOKE-ASSR",
        ASSR_COLLECTION,
        "제한적 확신업무 결론과 인증업무 위험",
    ),
    (
        "SMOKE-FRMK",
        FRMK_COLLECTION,
        "인증업무에서 역할과 책임은 어떻게 구분되는가",
    ),
)


@dataclass(slots=True, frozen=True)
class GoldenSeed:
    query_id: str
    query_text: str
    category: str
    expected_chunk_ids: tuple[str, ...]
    expected_standard_ids: tuple[str, ...]
    lang_mix: str


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_golden_dataset(path: Path) -> list[GoldenSeed]:
    seeds: list[GoldenSeed] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        seeds.append(
            GoldenSeed(
                query_id=str(item["query_id"]),
                query_text=str(item["query_text"]),
                category=str(item["category"]),
                expected_chunk_ids=tuple(str(v) for v in item["expected_chunk_ids"]),
                expected_standard_ids=tuple(str(v) for v in item["expected_standard_ids"]),
                lang_mix=str(item["lang_mix"]),
            )
        )
        if not seeds[-1].expected_chunk_ids:
            raise ValueError(f"{path}:{line_no}: expected_chunk_ids must not be empty")
    return seeds


def expected_points_by_collection(json_dir: Path) -> dict[str, int]:
    expected: dict[str, int] = {}
    for collection, patterns in COLLECTION_JSON_PATTERNS.items():
        paths: list[Path] = []
        for pattern in patterns:
            paths.extend(sorted(json_dir.glob(pattern)))
        if not paths:
            raise FileNotFoundError(f"no JSON files for {collection}: patterns={patterns}")
        chunk_count = sum(len(_load_json(path).get("chunks", [])) for path in paths)
        expected[collection] = chunk_count + len(paths)
    return expected


def verify_collections(
    *,
    qdrant_url: str,
    qdrant_api_key: str | None,
    expected_points: dict[str, int],
) -> list[dict[str, Any]]:
    writer = QdrantWriter(
        QdrantWriterConfig(url=qdrant_url, api_key=qdrant_api_key, timeout=30)
    )
    rows: list[dict[str, Any]] = []
    for collection, expected in expected_points.items():
        # Existing Phase 3 ISA collections may predate Phase 4e's
        # `special_appendix_name` payload index. This is additive and does not
        # rewrite points.
        writer.ensure_collection(collection)
        baseline = writer.verify_collection_baseline(collection, expected_points=expected)
        info = writer.client.get_collection(collection)
        rows.append(
            {
                "collection": collection,
                "indexes_ensured": True,
                "expected_points": expected,
                "actual_points": baseline["points_count"],
                "status": str(info.status),
                "optimizer_status": str(info.optimizer_status),
                "segments_count": info.segments_count,
                "payload_index_count": len(info.payload_schema),
                "passage_config": baseline["passage_config"],
                "summary_config": baseline["summary_config"],
            }
        )
    return rows


def _query_points(
    client: QdrantClient,
    *,
    collection: str,
    query_vector: tuple[float, ...],
    using: str,
    limit: int,
    query_filter: models.Filter | None = None,
) -> list[Any]:
    response = client.query_points(
        collection_name=collection,
        query=list(query_vector),
        using=using,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return list(response.points)


def _hit_to_dict(point: Any, rank: int) -> dict[str, Any]:
    payload = point.payload or {}
    text = str(payload.get("content_text") or "")
    return {
        "rank": rank,
        "score": round(float(point.score), 6),
        "chunk_id": payload.get("chunk_id"),
        "standard_id": payload.get("standard_id"),
        "kind": payload.get("kind"),
        "section": payload.get("section"),
        "heading_trail": payload.get("heading_trail"),
        "content_preview": text[:180].replace("\n", " "),
    }


def evaluate_mini_golden(
    *,
    client: QdrantClient,
    embedder: Embedder,
    seeds: list[GoldenSeed],
    collection: str,
    recall_k: int,
    mrr_k: int,
) -> dict[str, Any]:
    per_query: list[dict[str, Any]] = []
    category_counts: dict[str, int] = defaultdict(int)
    category_hits: dict[str, int] = defaultdict(int)
    reciprocal_sum = 0.0
    search_limit = max(recall_k, mrr_k)

    for seed in seeds:
        vector = embedder.embed_query(seed.query_text).vector
        points = _query_points(
            client,
            collection=collection,
            query_vector=vector,
            using=VECTOR_PASSAGE,
            limit=search_limit,
        )
        expected = set(seed.expected_chunk_ids)
        hit_rank: int | None = None
        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            if payload.get("chunk_id") in expected:
                hit_rank = rank
                break

        recall_hit = hit_rank is not None and hit_rank <= recall_k
        reciprocal_rank = 0.0
        if hit_rank is not None and hit_rank <= mrr_k:
            reciprocal_rank = 1.0 / hit_rank

        category_counts[seed.category] += 1
        if recall_hit:
            category_hits[seed.category] += 1
        reciprocal_sum += reciprocal_rank

        per_query.append(
            {
                "query_id": seed.query_id,
                "query_text": seed.query_text,
                "category": seed.category,
                "lang_mix": seed.lang_mix,
                "expected_chunk_ids": list(seed.expected_chunk_ids),
                "hit_rank": hit_rank,
                f"recall_at_{recall_k}": recall_hit,
                f"reciprocal_rank_at_{mrr_k}": round(reciprocal_rank, 6),
                "top_results": [
                    _hit_to_dict(point, rank)
                    for rank, point in enumerate(points[:search_limit], start=1)
                ],
            }
        )

    total = len(seeds)
    hits = sum(1 for item in per_query if item[f"recall_at_{recall_k}"])
    category_recall = {
        category: round(category_hits[category] / count, 6)
        for category, count in sorted(category_counts.items())
    }
    lang_mix_counts: dict[str, int] = defaultdict(int)
    lang_mix_hits: dict[str, int] = defaultdict(int)
    for item in per_query:
        lang_mix = str(item["lang_mix"])
        lang_mix_counts[lang_mix] += 1
        if item[f"recall_at_{recall_k}"]:
            lang_mix_hits[lang_mix] += 1

    return {
        "collection": collection,
        "seed_count": total,
        f"recall_at_{recall_k}": round(hits / total, 6) if total else 0.0,
        f"mrr_at_{mrr_k}": round(reciprocal_sum / total, 6) if total else 0.0,
        f"category_recall_at_{recall_k}": category_recall,
        f"lang_mix_recall_at_{recall_k}": {
            lang_mix: round(lang_mix_hits[lang_mix] / count, 6)
            for lang_mix, count in sorted(lang_mix_counts.items())
        },
        "thresholds": {
            f"recall_at_{recall_k}": 0.6,
            f"mrr_at_{mrr_k}": 0.5,
            f"ko_en_recall_at_{recall_k}": 0.4,
        },
        "per_query": per_query,
    }


def _standard_filter(standard_ids: list[str]) -> models.Filter | None:
    if not standard_ids:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="standard_id",
                match=models.MatchAny(any=standard_ids),
            )
        ]
    )


def run_smoke_queries(
    *,
    client: QdrantClient,
    embedder: Embedder,
    summary_limit: int,
    passage_limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query_id, collection, query_text in SMOKE_QUERIES:
        vector = embedder.embed_query(query_text).vector
        summary_points = _query_points(
            client,
            collection=collection,
            query_vector=vector,
            using=VECTOR_SUMMARY,
            limit=summary_limit,
        )
        stage1_standard_ids = []
        for point in summary_points:
            payload = point.payload or {}
            standard_id = payload.get("standard_id")
            if isinstance(standard_id, str) and standard_id not in stage1_standard_ids:
                stage1_standard_ids.append(standard_id)

        passage_points = _query_points(
            client,
            collection=collection,
            query_vector=vector,
            using=VECTOR_PASSAGE,
            limit=passage_limit,
            query_filter=_standard_filter(stage1_standard_ids),
        )
        rows.append(
            {
                "query_id": query_id,
                "collection": collection,
                "query_text": query_text,
                "stage1_summary_top": [
                    _hit_to_dict(point, rank)
                    for rank, point in enumerate(summary_points, start=1)
                ],
                "stage1_standard_ids": stage1_standard_ids,
                "stage2_passage_top": [
                    _hit_to_dict(point, rank)
                    for rank, point in enumerate(passage_points, start=1)
                ],
            }
        )
    return rows


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("tests/fixtures/isqm_mini_golden_dataset.jsonl"),
    )
    parser.add_argument("--json-dir", type=Path, default=Path("output/json"))
    parser.add_argument("--cache-path", type=Path, default=Path(".embed_cache.sqlite"))
    parser.add_argument(
        "--qdrant-url",
        default=os.environ.get("QDRANT_URL", "http://localhost:6333"),
    )
    parser.add_argument("--qdrant-api-key", default=os.environ.get("QDRANT_API_KEY"))
    parser.add_argument(
        "--mini-out",
        type=Path,
        default=Path("output/phase4_mini_golden_results.json"),
    )
    parser.add_argument(
        "--smoke-out",
        type=Path,
        default=Path("output/phase4_search_smoke_results.json"),
    )
    parser.add_argument("--recall-k", type=int, default=5)
    parser.add_argument("--mrr-k", type=int, default=10)
    parser.add_argument("--summary-limit", type=int, default=3)
    parser.add_argument("--passage-limit", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    expected_points = expected_points_by_collection(args.json_dir)
    collection_status = verify_collections(
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
        expected_points=expected_points,
    )

    client = QdrantClient(url=args.qdrant_url, api_key=args.qdrant_api_key, timeout=30)
    seeds = load_golden_dataset(args.dataset)
    with Embedder(cache_path=args.cache_path) as embedder:
        mini = evaluate_mini_golden(
            client=client,
            embedder=embedder,
            seeds=seeds,
            collection=ISQM_COLLECTION,
            recall_k=args.recall_k,
            mrr_k=args.mrr_k,
        )
        smoke = run_smoke_queries(
            client=client,
            embedder=embedder,
            summary_limit=args.summary_limit,
            passage_limit=args.passage_limit,
        )
        embedder_stats = embedder.stats.to_dict()

    common = {
        "generated_at": _utc_now(),
        "qdrant_url": args.qdrant_url,
        "collection_status": collection_status,
        "embedder_stats": embedder_stats,
    }
    _write_json(
        args.mini_out,
        {
            **common,
            "dataset": str(args.dataset),
            "mini_golden": mini,
        },
    )
    _write_json(
        args.smoke_out,
        {
            **common,
            "smoke_queries": smoke,
        },
    )

    recall_key = f"recall_at_{args.recall_k}"
    mrr_key = f"mrr_at_{args.mrr_k}"
    print(
        "Phase 4f Mini Golden: "
        f"{recall_key}={mini[recall_key]} {mrr_key}={mini[mrr_key]} "
        f"seeds={mini['seed_count']}"
    )
    print(f"Wrote {args.mini_out} and {args.smoke_out}")


if __name__ == "__main__":
    main()
