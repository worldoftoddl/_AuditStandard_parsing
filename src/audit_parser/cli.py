import typer

app = typer.Typer(help="Audit standards DOCX parsing pipeline.")


@app.command()
def convert(docx: str, out: str = "output/md/") -> None:
    """docx → structured markdown (Phase 1)."""
    typer.echo(f"convert stub: {docx} → {out}")


@app.command()
def ingest(json_path: str, collection: str) -> None:
    """json → Qdrant collection (Phase 3)."""
    typer.echo(f"ingest stub: {json_path} → {collection}")


if __name__ == "__main__":
    app()
