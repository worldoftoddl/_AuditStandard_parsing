"""Task #5 — 36 JSON schema v1.1 전수 검증 + 실측 메트릭 수집.

실행:
    .venv/bin/python scripts/validate_json.py

산출:
    1. stdout — 메트릭 요약 (team-lead 보고용)
    2. output/json/METRICS.json — 기계가독 메트릭 (Domain Reviewer Task #6 참조용)

검증 항목 (team-lead Task #5 간소화 범위):
    - schema_version = "1.2.0" × 36 파일
    - Draft 2020-12 schema 검증 0 errors × 36 파일
    - 전역 chunk_id uniqueness
    - chunk kind / section / appendix_index / token_estimate 분포
    - paragraph_links 총 수 (기대 1,788)
    - F4 suffix 부착 chunk 수 (기대 4)
    - chunk_of > 1 분할 chunk 수 (기대 3)
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_DIR = REPO_ROOT / "output" / "json"
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "json_schema_v1_2.schema.json"
METRICS_OUT = JSON_DIR / "METRICS.json"

# Task #2 v1.1 에서 실측 고정된 canonical F4 pair (정확 suffix 값).
# 다른 collision 은 `(a)/(b)/(c)` 등 반복 sub_item 으로 자연 발생 — 총 F4 suffix
# chunk 수는 훨씬 많다 (한국어 ISA 특성). 본 스크립트는 canonical 4 건 존재
# 여부만 regression guard 로 확인한다.
F4_CANONICAL_CHUNK_IDS = {
    "ISA-300:requirements:94b679bc:7.#2237",
    "ISA-300:requirements:94b679bc:7.#2238",
    "ISA-701:intro:a7720376:4.#8422",
    "ISA-701:intro:a7720376:4.#8427",
}


def _percentile(values: list[int], pct: float) -> int:
    """sorted list 에서 percentile 값 반환 (nearest-rank)."""
    if not values:
        return 0
    k = max(0, min(len(values) - 1, int(round(pct / 100 * (len(values) - 1)))))
    return sorted(values)[k]


def main() -> int:  # noqa: C901  — 단일 보고서 스크립트 복잡도 허용
    if not JSON_DIR.exists():
        print(
            f"ERROR: {JSON_DIR} 미존재 — `audit-parser ingest output/md/` 선행 필요",
            file=sys.stderr,
        )
        return 2

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    json_paths = sorted(JSON_DIR.glob("ISA-*.json"))
    if not json_paths:
        print(f"ERROR: {JSON_DIR} 에 ISA-*.json 없음", file=sys.stderr)
        return 2

    # -- aggregated counters -------------------------------------------------
    kind_counter: Counter[str] = Counter()
    section_counter: Counter[str | None] = Counter()
    appendix_counter: Counter[int | None] = Counter()
    token_values: list[int] = []
    chunk_ids_global: list[str] = []
    paragraph_links_total = 0
    f4_suffix_chunks_total = 0
    f4_suffix_by_standard: Counter[str] = Counter()
    f4_canonical_found: set[str] = set()
    split_chunks = 0
    schema_versions: Counter[str] = Counter()

    per_file: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []

    for path in json_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        schema_versions[data.get("schema_version", "<missing>")] += 1

        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        if errors:
            validation_errors.append(
                {
                    "file": path.name,
                    "error_count": len(errors),
                    "first_error": {
                        "message": errors[0].message,
                        "path": list(errors[0].absolute_path),
                    },
                }
            )

        standard_no = data["standard"]["standard_no"]
        standard_id = data["standard"]["standard_id"]
        chunks = data["chunks"]

        per_file.append(
            {
                "file": path.name,
                "standard_id": standard_id,
                "standard_no": standard_no,
                "chunks": len(chunks),
                "paragraph_links": len(data["paragraph_links"]),
                "schema_version": data["schema_version"],
            }
        )

        paragraph_links_total += len(data["paragraph_links"])

        for c in chunks:
            kind_counter[c["kind"]] += 1
            section_counter[c.get("section")] += 1
            appendix_counter[c.get("appendix_index")] += 1
            token_values.append(int(c["token_estimate"]))
            chunk_ids_global.append(c["chunk_id"])
            if c.get("chunk_of", 1) > 1:
                split_chunks += 1
            # F4 suffix 탐지 — Pass 2 collision resolution 이 부착한
            # `#{source_idx}` 는 paragraph_id 뒤에 append 된다. fallback
            # chunk_id (e.g. `table#1669`) 는 paragraph_id null 이므로 배제.
            pid = c.get("paragraph_id")
            if (
                pid
                and c.get("chunk_index", 0) == 0
                and c["chunk_id"].endswith(f"{pid}#{c['source_idx']}")
            ):
                f4_suffix_chunks_total += 1
                f4_suffix_by_standard[standard_id] += 1
                if c["chunk_id"] in F4_CANONICAL_CHUNK_IDS:
                    f4_canonical_found.add(c["chunk_id"])

    # -- uniqueness ----------------------------------------------------------
    dupe_counter: Counter[str] = Counter(chunk_ids_global)
    duplicate_chunk_ids = [cid for cid, n in dupe_counter.items() if n > 1]

    # -- token stats ---------------------------------------------------------
    token_stats: dict[str, int] = {
        "count": len(token_values),
        "min": min(token_values) if token_values else 0,
        "max": max(token_values) if token_values else 0,
        "mean": int(statistics.mean(token_values)) if token_values else 0,
        "p50": _percentile(token_values, 50),
        "p95": _percentile(token_values, 95),
        "p99": _percentile(token_values, 99),
    }

    # -- F4 canonical regression -------------------------------------------
    f4_canonical_expected = sorted(F4_CANONICAL_CHUNK_IDS)
    f4_canonical_match = f4_canonical_found == F4_CANONICAL_CHUNK_IDS

    # -- summary -------------------------------------------------------------
    summary: dict[str, Any] = {
        "files_total": len(json_paths),
        "schema_validation": {
            "total": len(json_paths),
            "passed": len(json_paths) - len(validation_errors),
            "failed": len(validation_errors),
            "errors": validation_errors,
        },
        "schema_version_distribution": dict(schema_versions),
        "chunks_total": len(chunk_ids_global),
        "kind_distribution": dict(kind_counter.most_common()),
        "section_distribution": {
            str(k) if k is not None else "<null>": v
            for k, v in section_counter.most_common()
        },
        "appendix_index_distribution": {
            str(k) if k is not None else "<null>": v
            for k, v in sorted(
                appendix_counter.items(),
                key=lambda kv: (-1 if kv[0] is None else kv[0]),
            )
        },
        "token_estimate": token_stats,
        "paragraph_links_total": paragraph_links_total,
        "chunk_id_uniqueness": {
            "global_unique": len(duplicate_chunk_ids) == 0,
            "duplicate_count": len(duplicate_chunk_ids),
            "duplicate_samples": duplicate_chunk_ids[:10],
        },
        "f4_suffix_chunks": {
            "total": f4_suffix_chunks_total,
            "by_standard": dict(f4_suffix_by_standard.most_common()),
            "canonical_expected": f4_canonical_expected,
            "canonical_found": sorted(f4_canonical_found),
            "canonical_match": f4_canonical_match,
        },
        "split_chunks_total": split_chunks,
        "per_file": per_file,
    }

    METRICS_OUT.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # -- stdout 요약 ---------------------------------------------------------
    print("=" * 72)
    print("Task #5 — 36 JSON 검증 + 메트릭 요약")
    print("=" * 72)
    print(f"파일 수              : {len(json_paths)}")
    print(f"schema_version 분포  : {dict(schema_versions)}")
    print(
        f"Schema 검증          : {summary['schema_validation']['passed']}/"
        f"{summary['schema_validation']['total']} "
        f"(errors {summary['schema_validation']['failed']})"
    )
    print(f"총 chunks            : {len(chunk_ids_global)}")
    print(f"chunk_id 전역 unique : {summary['chunk_id_uniqueness']['global_unique']}")
    print(f"중복 chunk_id 개수   : {summary['chunk_id_uniqueness']['duplicate_count']}")
    print(f"분할 chunks (chunk_of>1) : {split_chunks}")
    print(
        f"F4 suffix chunks 총   : {f4_suffix_chunks_total} "
        f"(canonical 4 건 match={f4_canonical_match})"
    )
    print(f"paragraph_links 총 수 : {paragraph_links_total}")
    print()
    print("token_estimate stats :")
    for k, v in token_stats.items():
        print(f"  {k:5s} : {v}")
    print()
    print("kind 분포:")
    for k, v in kind_counter.most_common():
        print(f"  {k:25s} : {v}")
    print()
    print("section 분포:")
    for sec_key, sec_val in section_counter.most_common():
        print(f"  {str(sec_key):25s} : {sec_val}")
    print()
    print("appendix_index 분포:")
    for ap_key in sorted(
        appendix_counter.keys(),
        key=lambda x: (-1 if x is None else x),
    ):
        ap_val = appendix_counter[ap_key]
        print(f"  {str(ap_key):6s} : {ap_val}")
    print()
    print(f"METRICS 파일         : {METRICS_OUT.relative_to(REPO_ROOT)}")

    # exit code — 실패 조건
    failures: list[str] = []
    if summary["schema_validation"]["failed"] > 0:
        failures.append(f"schema 검증 실패 {summary['schema_validation']['failed']} 건")
    if not summary["chunk_id_uniqueness"]["global_unique"]:
        failures.append(
            f"chunk_id 중복 {summary['chunk_id_uniqueness']['duplicate_count']} 건"
        )
    if schema_versions.get("1.2.0", 0) != len(json_paths):
        failures.append("schema_version 비균일")
    if not f4_canonical_match:
        failures.append(
            f"F4 canonical chunk 누락 "
            f"(found {len(f4_canonical_found)}/{len(F4_CANONICAL_CHUNK_IDS)})"
        )

    if failures:
        print()
        print("=" * 72)
        print("FAIL:", " / ".join(failures))
        print("=" * 72)
        return 1

    print()
    print("=" * 72)
    print("PASS — 모든 검증 항목 통과")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
