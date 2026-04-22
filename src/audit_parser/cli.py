"""CLI entry point — ``audit-parser convert`` / ``audit-parser ingest``.

``convert`` 는 Phase 1 Stage 1 (docx → structured MD) 를 담당하며 C7
(``unknown_numbering`` 5% 임계) 을 종료 코드로 강제한다. ``ingest`` 는 Phase 2
Stage 2b (MD → JSON) 기본 경로에 Phase 3 ``--upsert`` 확장을 얹어 Upstage Solar
임베딩 + Qdrant 적재까지 수행한다.
"""

from __future__ import annotations

import json
import os
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from audit_parser.convert import write_markdown_files
from audit_parser.ingest.qdrant_writer import COLLECTION_DEFAULT
from audit_parser.ir import (
    BlockKind,
    NumberingEngine,
    iter_blocks,
    iter_body,
    parse_numbering_from_docx,
)

if TYPE_CHECKING:
    from audit_parser.ingest.embedder import EmbedStats
    from audit_parser.ingest.qdrant_writer import UpsertResult
    from audit_parser.ingest.types import ParsedStandard

app = typer.Typer(help="Audit standards DOCX parsing pipeline.")

# -- convert -----------------------------------------------------------------

_DOCX_ARG = typer.Argument(..., exists=True, file_okay=True, dir_okay=False)
_OUT_OPT = typer.Option(Path("output/md/"), "--out", "-o")
_DRY_RUN_OPT = typer.Option(False, "--dry-run")
_UNKNOWN_THRESHOLD_OPT = typer.Option(
    0.05,
    "--unknown-threshold",
    min=0.0,
    max=1.0,
    help="unknown_numbering / total_blocks 가 이 값 초과 시 exit 1 (C7).",
)


@app.command()
def convert(
    docx: Path = _DOCX_ARG,
    out: Path = _OUT_OPT,
    dry_run: bool = _DRY_RUN_OPT,
    unknown_threshold: float = _UNKNOWN_THRESHOLD_OPT,
) -> None:
    """docx → structured markdown (Phase 1) — C7 UNKNOWN 임계 가드 포함."""
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx) as zf:
        abstract_nums, num_defs = parse_numbering_from_docx(zf)
    engine = NumberingEngine(abstract_nums, num_defs)
    source_file = docx.name
    # materialize — C7 ratio 계산 및 sample idx 로깅을 위해 한 번 적재.
    blocks = list(iter_blocks(iter_body(docx), engine))
    total_blocks = len(blocks)
    if dry_run:
        typer.echo(f"[dry-run] processed {total_blocks} blocks from {source_file}")
        return
    paths = write_markdown_files(blocks, source_file=source_file, out_dir=out)
    metrics = engine.metrics()
    unknown = metrics.get("unknown_numbering", 0)
    ratio = unknown / total_blocks if total_blocks else 0.0
    typer.echo(
        f"Wrote {len(paths)} files to {out} "
        f"(unknown_numbering={unknown}/{total_blocks}={ratio:.4%})"
    )
    if ratio > unknown_threshold:
        sample_idx = [
            i for i, b in enumerate(blocks) if b.kind is BlockKind.UNKNOWN_NUMBERING
        ][:3]
        typer.echo(
            f"ERROR: unknown_numbering 비율 {ratio:.4%} > 임계 {unknown_threshold:.4%} "
            f"(sample block idx: {sample_idx})",
            err=True,
        )
        raise typer.Exit(code=1)


# -- ingest ------------------------------------------------------------------

_INGEST_PATH_ARG = typer.Argument(..., exists=True, help="MD 디렉토리 또는 단일 MD 파일.")
_INGEST_OUT_OPT = typer.Option(Path("output/json/"), "--out", "-o")
_SINGLE_OPT = typer.Option(
    False,
    "--single",
    help="path 를 단일 MD 로 취급 (디렉토리 대신).",
)
# Phase 3 (--upsert) 옵션 ------------------------------------------------------
_UPSERT_OPT = typer.Option(
    False,
    "--upsert",
    help="JSON 쓰기 후 Upstage 임베딩 → Qdrant 적재 (Phase 3 Stage 2b).",
)
_COLLECTION_OPT = typer.Option(
    COLLECTION_DEFAULT,
    "--collection",
    help=f"Qdrant collection 명. 기본: {COLLECTION_DEFAULT}.",
)
_BATCH_SIZE_OPT = typer.Option(
    32,
    "--batch-size",
    min=1,
    max=128,
    help="Embedder batch 크기 (Upstage 입력 list 길이).",
)
_QDRANT_BATCH_SIZE_OPT = typer.Option(
    64,
    "--qdrant-batch-size",
    min=1,
    max=256,
    help="Qdrant upsert 배치 크기 (point 수).",
)
_QDRANT_URL_OPT = typer.Option(
    None,
    "--qdrant-url",
    help="Qdrant URL override (기본: $QDRANT_URL 또는 http://localhost:6333).",
)
_QDRANT_API_KEY_OPT = typer.Option(
    None,
    "--qdrant-api-key",
    help="Qdrant API key override (기본: $QDRANT_API_KEY).",
)
_CACHE_PATH_OPT = typer.Option(
    None,
    "--cache-path",
    help="Embedder SQLite 캐시 경로 (기본: ./.embed_cache.sqlite).",
)
_METRICS_OUT_OPT = typer.Option(
    None,
    "--metrics-out",
    help="EMBED_METRICS.json 저장 경로 (기본: <out>/EMBED_METRICS.json).",
)
_UPSERT_DRY_RUN_OPT = typer.Option(
    False,
    "--dry-run",
    help="--upsert 와 함께: Qdrant 호출 스킵, embedder 캐시 warm-up 만 수행.",
)
_PRUNE_STALE_OPT = typer.Option(
    False,
    "--prune-stale",
    help="--upsert 와 함께: 해당 standard_id 의 기존 point 중 새 batch 에 없는 것 삭제.",
)
_ENSURE_COLLECTION_OPT = typer.Option(
    True,
    "--ensure-collection/--no-ensure-collection",
    help="--upsert 시작 전 collection + payload index 생성 (idempotent).",
)


@app.command()
def ingest(
    path: Path = _INGEST_PATH_ARG,
    out: Path = _INGEST_OUT_OPT,
    single: bool = _SINGLE_OPT,
    upsert: bool = _UPSERT_OPT,
    collection: str = _COLLECTION_OPT,
    batch_size: int = _BATCH_SIZE_OPT,
    qdrant_batch_size: int = _QDRANT_BATCH_SIZE_OPT,
    qdrant_url: str | None = _QDRANT_URL_OPT,
    qdrant_api_key: str | None = _QDRANT_API_KEY_OPT,
    cache_path: Path | None = _CACHE_PATH_OPT,
    metrics_out: Path | None = _METRICS_OUT_OPT,
    dry_run: bool = _UPSERT_DRY_RUN_OPT,
    prune_stale: bool = _PRUNE_STALE_OPT,
    ensure_collection_flag: bool = _ENSURE_COLLECTION_OPT,
) -> None:
    """MD → JSON 일괄 또는 단건 (Phase 2 Stage 2b).

    ``--upsert`` 지정 시 JSON 산출 후 Upstage Solar 임베딩 → Qdrant 적재까지
    진행한다 (Phase 3 Stage 2b). per-standard 실패는 continue-on-error 로
    흡수하며 1건 이상 실패 시 exit 1 + ``EMBED_METRICS.json`` 에 실패 목록 기록.
    """
    # ingest 는 tiktoken 등 무거운 의존성이 있어 지연 import.
    from audit_parser.ingest import parse_md, parse_md_dir

    _validate_phase3_flags(
        upsert=upsert,
        collection=collection,
        batch_size=batch_size,
        qdrant_batch_size=qdrant_batch_size,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        cache_path=cache_path,
        metrics_out=metrics_out,
        dry_run=dry_run,
        prune_stale=prune_stale,
    )

    out.mkdir(parents=True, exist_ok=True)

    parsed_list: list[ParsedStandard]
    if single:
        if not path.is_file():
            raise typer.BadParameter(f"--single requires a file, got {path}")
        parsed = parse_md(path)
        if parsed is None:
            typer.echo(f"skipped (prelude): {path.name}")
            return
        written = _write_json(parsed, out)
        typer.echo(f"Wrote 1 file to {out}: {written.name}")
        parsed_list = [parsed]
    else:
        if not path.is_dir():
            raise typer.BadParameter(f"expected directory, got {path} (use --single?)")
        parsed_list = parse_md_dir(path)
        for parsed in parsed_list:
            _write_json(parsed, out)
        # parse_md_dir 는 ISA-*.md glob → 나머지(00_전문.md 등) 를 skip 으로 log.
        emitted = {f"ISA-{p.standard.standard_no}.md" for p in parsed_list}
        all_md = {p.name for p in path.glob("*.md")}
        for name in sorted(all_md - emitted):
            typer.echo(f"skipped: {name}")
        typer.echo(f"Wrote {len(parsed_list)} files to {out}")

    if not upsert:
        return

    # --- Phase 3 분기 ------------------------------------------------------
    # .env 는 CLI 경계에서 명시 로드 (Embedder / QdrantWriter 가 os.environ 를 읽음).
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover — python-dotenv 미설치 시 env 만으로 동작
        pass

    resolved_metrics_out = metrics_out if metrics_out is not None else (out / "EMBED_METRICS.json")
    _run_upsert(
        parsed_list=parsed_list,
        collection=collection,
        qdrant_batch_size=qdrant_batch_size,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        cache_path=cache_path,
        metrics_out=resolved_metrics_out,
        dry_run=dry_run,
        prune_stale=prune_stale,
        ensure_collection_flag=ensure_collection_flag,
    )


def _validate_phase3_flags(
    *,
    upsert: bool,
    collection: str,
    batch_size: int,
    qdrant_batch_size: int,
    qdrant_url: str | None,
    qdrant_api_key: str | None,
    cache_path: Path | None,
    metrics_out: Path | None,
    dry_run: bool,
    prune_stale: bool,
) -> None:
    """``--upsert`` 없이 Phase 3 파라미터 지정 시 조기 실패."""
    if upsert:
        return
    overrides: tuple[tuple[str, bool], ...] = (
        ("--collection", collection != COLLECTION_DEFAULT),
        ("--batch-size", batch_size != 32),
        ("--qdrant-batch-size", qdrant_batch_size != 64),
        ("--qdrant-url", qdrant_url is not None),
        ("--qdrant-api-key", qdrant_api_key is not None),
        ("--cache-path", cache_path is not None),
        ("--metrics-out", metrics_out is not None),
        ("--dry-run", dry_run),
        ("--prune-stale", prune_stale),
    )
    offending = [flag for flag, is_set in overrides if is_set]
    if offending:
        raise typer.BadParameter(
            f"--upsert required for Phase 3 flags: {', '.join(offending)}"
        )


def _write_json(parsed: ParsedStandard, out: Path) -> Path:
    """``ParsedStandard`` → ``out/ISA-{standard_no}.json`` 직렬화."""
    from audit_parser.ingest import to_json_dict

    target = out / f"ISA-{parsed.standard.standard_no}.json"
    data = to_json_dict(parsed)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _run_upsert(
    *,
    parsed_list: list[ParsedStandard],
    collection: str,
    qdrant_batch_size: int,
    qdrant_url: str | None,
    qdrant_api_key: str | None,
    cache_path: Path | None,
    metrics_out: Path,
    dry_run: bool,
    prune_stale: bool,
    ensure_collection_flag: bool,
) -> None:
    """Phase 3 ``--upsert`` 본체. Embedder + QdrantWriter 수명 관리 + metrics dump."""
    from audit_parser.ingest import (
        Embedder,
        EmbedError,
        QdrantWriter,
        QdrantWriterConfig,
        QdrantWriterError,
    )

    if not parsed_list:
        typer.echo("no parsed standards to upsert — skipping Phase 3.")
        return

    embedder = Embedder(cache_path=cache_path)
    qw_config = QdrantWriterConfig(
        url=qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333"),
        api_key=qdrant_api_key or os.environ.get("QDRANT_API_KEY") or None,
    )
    writer = QdrantWriter(qw_config)

    if ensure_collection_flag and not dry_run:
        writer.ensure_collection(collection)

    results: list[tuple[str, UpsertResult]] = []
    failed: list[str] = []
    t0 = time.perf_counter()
    try:
        for parsed in parsed_list:
            sid = parsed.standard.standard_id
            try:
                res = writer.upsert_parsed(
                    parsed,
                    embedder,
                    collection=collection,
                    batch_size=qdrant_batch_size,
                    dry_run=dry_run,
                    prune_stale=prune_stale,
                )
                results.append((sid, res))
                typer.echo(
                    f"[{sid}] upserted {res.points_upserted} / "
                    f"drift={res.payload_drift_count} / summary={res.summary_upserted} / "
                    f"{res.elapsed_seconds:.2f}s"
                )
                if res.failed_chunk_ids:
                    failed.append(sid)
            except (EmbedError, QdrantWriterError) as exc:
                typer.echo(
                    f"[{sid}] FAILED: {type(exc).__name__}: {exc}",
                    err=True,
                )
                failed.append(sid)
        total_elapsed = time.perf_counter() - t0
        _write_embed_metrics(
            metrics_out,
            results,
            failed,
            stats=embedder.stats,
            collection=collection,
            dry_run=dry_run,
            total_elapsed=total_elapsed,
        )
    finally:
        embedder.close()

    typer.echo(
        f"Done: {len(results)} standards, "
        f"{sum(r.points_upserted for _, r in results)} points, "
        f"{len(failed)} failed, {total_elapsed:.1f}s"
    )
    if failed:
        raise typer.Exit(code=1)


def _write_embed_metrics(
    metrics_out: Path,
    results: list[tuple[str, UpsertResult]],
    failed_standards: list[str],
    *,
    stats: EmbedStats,
    collection: str,
    dry_run: bool,
    total_elapsed: float,
) -> None:
    """EMBED_METRICS.json 작성 — Task #7 검수 및 C-P2-6 calibration 소비."""
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, object] = {
        "collection": collection,
        "dry_run": dry_run,
        "standards_processed": len(results),
        "standards_failed": failed_standards,
        "points_upserted_total": sum(r.points_upserted for _, r in results),
        "payload_drift_total": sum(r.payload_drift_count for _, r in results),
        "stale_suffix_deleted_total": sum(r.stale_suffix_deleted for _, r in results),
        "summary_upserted_total": sum(1 for _, r in results if r.summary_upserted),
        "elapsed_seconds_total": round(total_elapsed, 3),
        "embedder_stats": stats.to_dict(),
        "per_standard": [
            {
                "standard_id": sid,
                "collection": r.collection,
                "points_upserted": r.points_upserted,
                "payload_drift_count": r.payload_drift_count,
                "stale_suffix_deleted": r.stale_suffix_deleted,
                "summary_upserted": r.summary_upserted,
                "elapsed_seconds": round(r.elapsed_seconds, 3),
                "failed_chunk_ids": list(r.failed_chunk_ids),
            }
            for sid, r in results
        ],
    }
    metrics_out.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    app()
