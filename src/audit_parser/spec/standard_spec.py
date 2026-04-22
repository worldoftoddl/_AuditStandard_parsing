"""Per-standard parsing specification — Phase 4b StandardSpec abstraction.

``StandardSpec`` encapsulates prefix-specific differences between ISA / ISQM /
ASSR / FRMK parsing paths. Phase 4b-1 introduces the dataclass with ISA-only
behavior preserved; Phase 4b-2 will add ``body_parser``, ``section_detector``,
``prelude_skip`` fields (with safe defaults) for ISQM/ASSR/FRMK.

The ``AppendixExtractor`` signature is intentionally **frozen** at Phase 4b-1 —
the four Phase 4b-2 spec files will inject different callables but the type
remains ``Callable[[str], tuple[int | None, str | None]]``. See
``docs/checkpoint_4_prep.md §1.3.4`` for the 3-party-agreed ``standard_id``
regex that each spec compiles into ``standard_id_regex``.

Appendix extraction background (json_schema.md §7.2.1 + B-v2 — Domain Reviewer
Q1 정정 2026-04-22):

* ISA: numbered ``보론 N`` → ``(N, None)``, un-numbered ``보론`` → ``(1, None)``.
* FRMK: numbered → ``(N, None)``, un-numbered ``보론: 역할과 책임`` →
  ``(None, "역할과 책임")`` (captured in ``special_appendix_name`` payload
  field). The ``special_appendix_name`` field is added to ``ChunkRecord`` in
  Phase 4b-1 (v1.2.0 MINOR bump) for forward-compatibility — ISA runs always
  emit ``None`` so existing 36 JSON files remain semantically equivalent.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Appendix extraction callable
# ---------------------------------------------------------------------------


AppendixExtractor = Callable[[str], tuple[int | None, str | None]]
"""Heading text → ``(appendix_index, special_appendix_name)``.

Contract (per-heading, not heading_trail):

* Numbered ``보론 N`` → ``(N, None)``.
* ISA un-numbered ``보론`` / ``보론: 제목`` / ``보론. 제목`` → ``(1, None)``.
* FRMK un-numbered ``보론: 역할과 책임`` → ``(None, "역할과 책임")``.
* Non-appendix heading (heading doesn't match 보론 pattern) → ``(None, None)``.

Callers (md_parser) iterate ``reversed(heading_trail)`` and stop at the first
heading that returns a non-``(None, None)`` tuple.
"""


_APPENDIX_NUMBERED_RE: Final = re.compile(r"^보론\s*(\d+)\b")
_APPENDIX_UNNUMBERED_RE: Final = re.compile(r"^보론(?!\s*\d)")


def isa_default_appendix_extractor(heading: str) -> tuple[int | None, str | None]:
    """ISA default extractor — preserves Phase 1-3 ``_extract_appendix_index`` logic.

    Args:
        heading: Single heading text (one element of ``heading_trail``).

    Returns:
        ``(appendix_index, special_appendix_name)``. ``special_appendix_name`` is
        always ``None`` for ISA — ISA un-numbered 보론 maps to
        ``appendix_index=1`` per json_schema.md §7.2.1.

    Examples:
        >>> isa_default_appendix_extractor("보론 1")
        (1, None)
        >>> isa_default_appendix_extractor("보론 (문단 A8 참조)")
        (1, None)
        >>> isa_default_appendix_extractor("보론. 내부회계관리제도 감사보고서 사례")
        (1, None)
        >>> isa_default_appendix_extractor("서론")
        (None, None)
    """
    stripped = heading.strip()
    numbered = _APPENDIX_NUMBERED_RE.match(stripped)
    if numbered:
        return int(numbered.group(1)), None
    if _APPENDIX_UNNUMBERED_RE.match(stripped):
        return 1, None
    return None, None


# ---------------------------------------------------------------------------
# StandardSpec dataclass
# ---------------------------------------------------------------------------


StandardPrefix = Literal["ISA", "ISQM", "FRMK", "ASSR"]


@dataclass(slots=True, frozen=True)
class StandardSpec:
    """Per-standard parsing configuration injected into md_parser / md_renderer.

    Phase 4b-1 surface: ``prefix``, regex validators, ``section_enum``,
    ``appendix_extractor``, ``format_standard_id`` helper.

    Phase 4b-2 will extend with ``body_parser`` (``"default"`` |
    ``"isqm_table"``) dispatcher, ``section_detector`` callable, ``prelude_skip``
    + ``prelude_end_marker`` for 3 DOCX, ``heading_range_strip`` for FRMK.
    Those additions are backward-compatible (new fields appended with defaults).

    Attributes:
        prefix: 4-prefix alphabet literal. Composes ``standard_id`` together
            with ``standard_no``.
        standard_id_regex: Compiled regex validating ``standard_id`` strings.
            Phase 4b-1 v1.2.0: per-prefix alt subset of
            ``^(ISA-\\d{3,4}|ISQM-\\d{1,2}|ASSR-\\d{3,4}|FRMK-\\d)$``.
        standard_no_regex: Compiled regex validating ``standard_no`` strings.
            Phase 4b-1 v1.2.0: ``^\\d{1,4}$`` (relaxed from v1.1.x ``^\\d{3,4}$``
            to accommodate ISQM-1 / FRMK-1 single-digit).
        section_enum: Section enum class for the standard. ISA uses
            :class:`audit_parser.ir.types.Section`. Phase 4b-2 will introduce
            ``ISQMSection`` / ``ASSRSection`` / ``FRMKSection`` per spec file.
        appendix_extractor: Heading-level callable. See
            :data:`AppendixExtractor`.
    """

    prefix: StandardPrefix
    standard_id_regex: re.Pattern[str]
    standard_no_regex: re.Pattern[str]
    section_enum: type[StrEnum]
    appendix_extractor: AppendixExtractor = isa_default_appendix_extractor

    def format_standard_id(self, standard_no: str) -> str:
        """Compose ``{PREFIX}-{N}`` identifier from a numeric standard_no.

        Phase 4b-1 consumer: ``md_renderer._format_standard_frontmatter``
        replaces the current hardcoded ``f'ISA-{standard_no}'`` with
        ``spec.format_standard_id(standard_no)``.

        Raises:
            ValueError: if ``standard_no`` does not match ``standard_no_regex``
                or the composed id does not match ``standard_id_regex``. The
                caller (md_renderer / md_parser) relies on this fail-fast to
                catch spec/input mismatch early.

        Examples:
            >>> from audit_parser.spec import ISA_SPEC
            >>> ISA_SPEC.format_standard_id("200")
            'ISA-200'
            >>> ISA_SPEC.format_standard_id("1200")
            'ISA-1200'
        """
        if not self.standard_no_regex.fullmatch(standard_no):
            raise ValueError(
                f"standard_no {standard_no!r} does not match "
                f"{self.prefix} pattern {self.standard_no_regex.pattern!r}"
            )
        composed = f"{self.prefix}-{standard_no}"
        if not self.standard_id_regex.fullmatch(composed):
            raise ValueError(
                f"composed standard_id {composed!r} does not match "
                f"{self.prefix} pattern {self.standard_id_regex.pattern!r}"
            )
        return composed

    def validate_standard_id(self, standard_id: str) -> None:
        """Assert ``standard_id`` matches this spec's regex (fail-fast).

        Used by md_parser when reading frontmatter — ensures the MD file's
        declared id belongs to this spec's prefix family.

        Raises:
            ValueError: on mismatch. Caller may catch to dispatch to a
                different spec, or re-raise as fatal.
        """
        if not self.standard_id_regex.fullmatch(standard_id):
            raise ValueError(
                f"standard_id {standard_id!r} does not match "
                f"{self.prefix} spec regex {self.standard_id_regex.pattern!r}"
            )


__all__ = [
    "AppendixExtractor",
    "StandardPrefix",
    "StandardSpec",
    "isa_default_appendix_extractor",
]
