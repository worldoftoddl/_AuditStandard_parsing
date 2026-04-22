"""Migrate output/json/*.json from v1.1.2 → v1.2.0 in-place.

Scope (Phase 4b-1 Commit 2):

* ``schema_version`` string replace (default ``"1.1.2"`` → ``"1.2.0"``).
* Inject ``"special_appendix_name": null`` into each ``chunks[]`` entry
  immediately after ``appendix_index`` to match json_schema v1.2.0 §12 required
  field ordering. All ISA chunks emit ``null`` — only FRMK-produced JSON (Phase
  4b-2 onwards) will carry non-null values.

Invariants preserved:

* ``chunk_id`` / ``embedding`` / ``embedded_at`` / ``embedding_model`` / all
  other payload fields — bit-equal.
* Qdrant re-embed **not required** (``.embed_cache.sqlite`` hits 100%).

Usage::

    # dry-run (prints planned mutations, no writes)
    python scripts/migrate_schema_v1_2.py output/json/*.json --dry-run

    # apply in place
    python scripts/migrate_schema_v1_2.py output/json/*.json

    # custom source version (e.g. Phase 4b-2 migrating 1.2.0 → 1.3.0)
    python scripts/migrate_schema_v1_2.py output/json/*.json \
        --old-version 1.2.0 --new-version 1.3.0

Exits non-zero if any file fails (missing key, already-migrated, malformed).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def migrate_file(
    path: Path,
    *,
    old_version: str = "1.1.2",
    new_version: str = "1.2.0",
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Migrate a single JSON file in place. Returns ``(changed, message)``.

    Behavior:

    * File already at ``new_version`` → idempotent no-op, returns
      ``(False, "already v{new_version}")``.
    * File at ``old_version`` → updates ``schema_version`` + injects
      ``special_appendix_name: null`` into every chunk missing the field.
    * File at unexpected version → returns ``(False, "unexpected v{...}")``.

    Raises:
        json.JSONDecodeError: on malformed JSON (caller aggregates).
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    current = data.get("schema_version")
    if current == new_version:
        return False, f"already v{new_version}"
    if current != old_version:
        return False, f"unexpected v{current!r} (want v{old_version})"

    # 1. schema_version bump
    data["schema_version"] = new_version

    # 2. Inject special_appendix_name: None into every chunk missing it.
    # Ordered insert — JSON dict preserves insertion order (Python 3.7+), so
    # we reconstruct each chunk dict with the new key positioned right after
    # appendix_index for spec §5.1 field-order consistency.
    chunks = data.get("chunks", [])
    for chunk in chunks:
        if "special_appendix_name" in chunk:
            continue
        # Rebuild dict preserving key order + inserting after appendix_index.
        new_chunk: dict[str, object] = {}
        for key, value in chunk.items():
            new_chunk[key] = value
            if key == "appendix_index":
                new_chunk["special_appendix_name"] = None
        chunk.clear()
        chunk.update(new_chunk)

    if dry_run:
        return True, (
            f"would migrate v{old_version} → v{new_version} "
            f"(+special_appendix_name in {len(chunks)} chunks)"
        )

    # Preserve the historical indent=2 + trailing newline convention
    # (see cli._write_json in Phase 2 Task #4).
    out = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(out, encoding="utf-8")
    return True, f"migrated v{old_version} → v{new_version} ({len(chunks)} chunks)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4b-1: migrate audit_parser JSON files schema_version."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="JSON file paths")
    parser.add_argument("--old-version", default="1.1.2")
    parser.add_argument("--new-version", default="1.2.0")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    n_changed = 0
    n_skipped = 0
    n_error = 0
    for path in sorted(args.paths):
        if not path.is_file():
            print(f"  ! {path}: not a file", file=sys.stderr)
            n_error += 1
            continue
        try:
            changed, msg = migrate_file(
                path,
                old_version=args.old_version,
                new_version=args.new_version,
                dry_run=args.dry_run,
            )
        except json.JSONDecodeError as exc:
            print(f"  ! {path}: JSON decode error {exc}", file=sys.stderr)
            n_error += 1
            continue
        mark = "~" if changed else "."
        print(f"  {mark} {path}: {msg}")
        if changed:
            n_changed += 1
        else:
            n_skipped += 1

    print(
        f"\nTotal: {n_changed} changed, {n_skipped} skipped, "
        f"{n_error} errors (dry_run={args.dry_run}).",
        file=sys.stderr,
    )
    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
