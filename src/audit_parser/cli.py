"""CLI entry point — `audit-parser convert` (Phase 1), `audit-parser ingest` (Phase 2 Stage 2b).

`convert` 는 Phase 1 Stage 1 (docx → structured MD) 를 담당하며 C7
(`unknown_numbering` 5% 임계) 을 종료 코드로 강제한다. `ingest` 는 Phase 2
Stage 2b (MD → JSON) 를 담당하며 Phase 3 에서 Qdrant 업로드로 확장된다.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from audit_parser.convert import write_markdown_files
from audit_parser.ir import (
    BlockKind,
    NumberingEngine,
    iter_blocks,
    iter_body,
    parse_numbering_from_docx,
)

if TYPE_CHECKING:
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


@app.command()
def ingest(
    path: Path = _INGEST_PATH_ARG,
    out: Path = _INGEST_OUT_OPT,
    single: bool = _SINGLE_OPT,
) -> None:
    """MD → JSON 일괄 또는 단건 (Phase 2 Stage 2b)."""
    # ingest 는 tiktoken 등 무거운 의존성이 있어 지연 import.
    from audit_parser.ingest import parse_md, parse_md_dir

    out.mkdir(parents=True, exist_ok=True)

    if single:
        if not path.is_file():
            raise typer.BadParameter(f"--single requires a file, got {path}")
        parsed = parse_md(path)
        if parsed is None:
            typer.echo(f"skipped (prelude): {path.name}")
            return
        written = _write_json(parsed, out)
        typer.echo(f"Wrote 1 file to {out}: {written.name}")
        return

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


def _write_json(parsed: ParsedStandard, out: Path) -> Path:
    """`ParsedStandard` → `out/ISA-{standard_no}.json` 직렬화."""
    from audit_parser.ingest import to_json_dict

    target = out / f"ISA-{parsed.standard.standard_no}.json"
    data = to_json_dict(parsed)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    app()
