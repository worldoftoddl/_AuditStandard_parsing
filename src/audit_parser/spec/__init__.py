"""Standard specification registry — Phase 4b abstraction over prefix-specific parsing.

Phase 4b-1 provides the :class:`StandardSpec` dataclass and ``ISA_SPEC`` default
that preserves Phase 1-3 ISA behavior. Phase 4b-2 will add ``ISQM_SPEC`` /
``ASSR_SPEC`` / ``FRMK_SPEC`` and dispatcher hooks for non-ISA body parsers.

See :mod:`audit_parser.spec.standard_spec` for the dataclass contract and
:mod:`audit_parser.spec.isa_spec` for the ISA default.
"""

from __future__ import annotations

from audit_parser.spec.isa_spec import ISA_SPEC
from audit_parser.spec.standard_spec import (
    AppendixExtractor,
    StandardSpec,
    isa_default_appendix_extractor,
)

__all__ = [
    "AppendixExtractor",
    "ISA_SPEC",
    "StandardSpec",
    "isa_default_appendix_extractor",
]
