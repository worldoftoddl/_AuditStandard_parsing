"""CLI entry point — `audit-parser convert` (Phase 1), `audit-parser ingest` (Phase 3 stub)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import typer

from audit_parser.convert import write_markdown_files
from audit_parser.ir import (
    NumberingEngine,
    iter_blocks,
    iter_body,
    parse_numbering_from_docx,
)

app = typer.Typer(help="Audit standards DOCX parsing pipeline.")

_DOCX_ARG = typer.Argument(..., exists=True, file_okay=True, dir_okay=False)
_OUT_OPT = typer.Option(Path("output/md/"), "--out", "-o")
_DRY_RUN_OPT = typer.Option(False, "--dry-run")


@app.command()
def convert(
    docx: Path = _DOCX_ARG,
    out: Path = _OUT_OPT,
    dry_run: bool = _DRY_RUN_OPT,
) -> None:
    """docx → structured markdown (Phase 1)."""
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx) as zf:
        abstract_nums, num_defs = parse_numbering_from_docx(zf)
    engine = NumberingEngine(abstract_nums, num_defs)
    source_file = docx.name
    blocks = iter_blocks(iter_body(docx), engine)
    if dry_run:
        count = sum(1 for _ in blocks)
        typer.echo(f"[dry-run] processed {count} blocks from {source_file}")
        return
    paths = write_markdown_files(blocks, source_file=source_file, out_dir=out)
    metrics = engine.metrics()
    typer.echo(
        f"Wrote {len(paths)} files to {out} "
        f"(unknown_numbering={metrics.get('unknown_numbering', 0)})"
    )


@app.command()
def ingest(json_path: str, collection: str) -> None:
    """json → Qdrant collection (Phase 3)."""
    typer.echo(f"ingest stub: {json_path} → {collection}")


if __name__ == "__main__":
    app()
