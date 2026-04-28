# Repository Guidelines

## Project Structure & Module Organization

This Python 3.12 package converts audit-standard DOCX files into Markdown, JSON, and Qdrant records. Core code lives in `src/audit_parser/`:

- `ir/`: DOCX reading, numbering, XML helpers, and intermediate representation types.
- `spec/`: standard-specific parsing rules for ISA, ISQM, ASSR, FRMK, and shared dispatch.
- `convert/`: Markdown rendering from parsed structure.
- `ingest/`: Markdown parsing, chunk splitting, embeddings, and Qdrant writes.

Tests are in `tests/`, with reusable samples in `tests/fixtures/`. Design notes are in `docs/`. Generated data belongs in `output/`, and source DOCX files belong in `raw/`; both are local artifacts.

## Build, Test, and Development Commands

- `uv sync`: install project dependencies from `pyproject.toml` and `uv.lock`.
- `pip install -e ".[dev]"`: editable install with pytest, Ruff, mypy, and JSON Schema tools.
- `docker compose up -d`: start local Qdrant on `localhost:6333`.
- `audit-parser convert "raw/<file>.docx" --out output/md/`: convert DOCX to structured Markdown.
- `pytest`: run the full test suite.
- `ruff check src/ tests/`: lint source and tests.
- `ruff format src/ tests/`: format Python files.
- `mypy src/`: run strict type checks.

## Coding Style & Naming Conventions

Use Python 3.12 syntax and type annotations throughout. Ruff enforces a 100-character line length plus `E`, `F`, `W`, `I`, `UP`, `B`, and `C90` rules. Keep modules focused on pipeline stages and prefer explicit dataclasses/types for parsed structures. Use snake_case for modules, functions, variables, and tests. Preserve identifiers such as `ISA-200`, `ISQM`, and `FRMK` in fixtures and output paths.

## Testing Guidelines

The project uses pytest. Add tests under `tests/test_<feature>.py` and place structured sample inputs in `tests/fixtures/` when reused across cases. Prefer regression tests for parser behavior, numbering edge cases, schema compliance, and CLI flows. Run `pytest`, `ruff check src/ tests/`, and `mypy src/` before opening a PR.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit-style messages: `feat(spec): ...`, `refactor(ingest): ...`, `docs(isqm): ...`. Keep the type and optional scope specific, and mention phase/checkpoint context when relevant.

Pull requests should include a short summary, changed pipeline stage, test results, linked issue or phase document, and sample output paths when parser behavior changes.

## Security & Configuration Tips

Do not commit `.env`, raw DOCX files, generated `output/` data, embedding caches, or Qdrant storage. Keep API keys in `.env`, and document any new required variables in README or project configuration.
