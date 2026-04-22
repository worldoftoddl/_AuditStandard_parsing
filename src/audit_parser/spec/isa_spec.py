"""ISA default spec — Phase 4b-1 wrapper preserving Phase 1-3 behavior.

``ISA_SPEC`` is the default injected into :func:`md_parser.parse_markdown` and
:func:`md_renderer.render_standard` so existing 36 ISA MD → JSON paths remain
bit-stable (excluding the v1.2.0 schema bump in-place fields
``schema_version`` + ``special_appendix_name: null``). See
``docs/checkpoint_4_prep.md §1.3.4`` for the 3-party-agreed regex and Phase 4b-1
plan §6 for the backward-compat requirement.

Design note — Phase 4b-2 will add ``ISQM_SPEC`` / ``ASSR_SPEC`` / ``FRMK_SPEC``
in their own modules; this file stays ISA-only to minimize import churn.
"""

from __future__ import annotations

import re
from typing import Final

from audit_parser.ir.types import Section
from audit_parser.spec.standard_spec import (
    StandardSpec,
    isa_default_appendix_extractor,
)

# Regex sources: ``docs/checkpoint_4_prep.md §1.3.4`` (v1.2.0 final).
# Compiled here per-spec so each spec owns its own Pattern object (re.compile
# is cached globally by Python, so no duplication cost).

_ISA_STANDARD_ID_RE: Final = re.compile(r"^ISA-\d{3,4}$")
_ISA_STANDARD_NO_RE: Final = re.compile(r"^\d{1,4}$")


ISA_SPEC: Final = StandardSpec(
    prefix="ISA",
    standard_id_regex=_ISA_STANDARD_ID_RE,
    standard_no_regex=_ISA_STANDARD_NO_RE,
    section_enum=Section,
    appendix_extractor=isa_default_appendix_extractor,
)


__all__ = ["ISA_SPEC"]
