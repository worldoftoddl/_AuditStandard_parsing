"""Per-standard parsing specification — Phase 4b StandardSpec abstraction.

``StandardSpec`` encapsulates prefix-specific differences between ISA / ISQM /
ASSR / FRMK parsing paths. Phase 4b-1 introduced the dataclass with ISA-only
behavior; Phase 4b-2 extends with ``body_parser`` / ``section_detector`` /
``prelude_skip`` fields (all ``None`` default → ISA path unchanged).

The ``AppendixExtractor`` signature is intentionally **frozen** at Phase 4b-1 —
the four Phase 4b-2 spec files inject different callables but the type
remains ``Callable[[str], tuple[int | None, str | None]]``. See
``docs/checkpoint_4_prep.md §1.3.4`` for the 3-party-agreed ``standard_id``
regex that each spec compiles into ``standard_id_regex``.

Phase 4b-2 3-party LOCK (2026-04-23 — Critic direct LOCK + Domain Reviewer
PASS + team-lead APPROVE) adds three optional callables. All callers in Phase
4b-2 scope still invoke ``parse_md`` / ``render_markdown`` with ``spec=ISA_SPEC``
(explicit or default), so the ISA byte-equivalence exit gate is preserved by
construction. Phase 4c/4d wiring (prefix dispatcher → md_parser spec-aware call)
is out of scope.

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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    # Phase 4b-2 forward-refs — actual usage happens in Phase 4c wiring
    # (md_parser / docx_reader spec-aware dispatch). Type aliases below mention
    # these for documentation + strict typing without runtime import cost.
    from lxml import etree

    from audit_parser.ir.numbering import NumberingEngine
    from audit_parser.ir.styles import StyleIndex
    from audit_parser.ir.types import RawBlock

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
# Phase 4b-2 dispatch callable types
# ---------------------------------------------------------------------------


BodyParser = Callable[
    ["etree._Element", "NumberingEngine", "StyleIndex"],
    "Iterable[RawBlock]",
]
"""XML-level body parser — dispatch alternative to Phase 1 ``docx_reader.iter_body``.

Receives the already-parsed document body element, the numbering engine, and
the style index. Returns an ``Iterable[RawBlock]`` consumed by Phase 1
``structure.py`` state machine. ``None`` value (default in ISA_SPEC) selects
the legacy Phase 1 path.

Phase 4b-2 wiring:
    ``ISQM_SPEC.body_parser = parse_isqm_body_table`` (``ir/isqm_table_parser.py``)

Phase 4c wiring will add the ``if spec.body_parser is not None: ...`` branch
inside ``docx_reader.iter_blocks`` — β-1 invariant: body_parser emits atomic
``RawBlock`` only; chunk splitting remains ``chunk_splitter.split_oversized_chunks``'
sole responsibility (see ``docs/checkpoint_4_prep.md §1.8``).
"""


SectionDetector = Callable[["RawBlock", str | None], str | None]
"""Text-based section state machine — dispatch alternative to heading-style detect.

Receives ``(block, current_section)`` and returns the next section name (or
``None`` to keep current). ISA uses ``heading 2`` style + text map, so leaves
this as ``None``. ASSR has no ``heading N`` style — its ``_assr_section_detector``
closure implements the state machine described in
``docs/assurance_other_structure_profile.md §2.3``.
"""


PreludeSkip = Callable[["RawBlock"], bool]
"""Marker matcher returning ``True`` when the block ENDS the prelude region.

Caller (Phase 4c ``md_parser`` / ``docx_reader``) maintains ``in_prelude: bool``
state. Invoked per-block; on ``True`` return, caller toggles ``in_prelude=False``
AND skips the marker block itself. Pre-marker blocks are skipped by caller
state, not by this callable. Interpretation **(i)** per Critic v1.1 LOCK
2026-04-23 — alternatives **(ii) stateful filter** / **(iii) declarative
tuple** explicitly NOT chosen.

Three known markers expressed as stateless predicates:

* ISQM: ``lambda b: b.kind is BlockKind.TABLE and len(b.table_cells or ()) >= 200``
  (the ``tbl[236x2]`` body table entry).
* ASSR: ``lambda b: b.text.strip() == "서론" and b._inside_table`` (the
  ``tbl[427x2]`` body's first ``서론`` heading).
* FRMK: ``lambda b: b.style == "heading 2" and b.text.strip().startswith("문단번호")``.
"""


# ---------------------------------------------------------------------------
# StandardSpec dataclass
# ---------------------------------------------------------------------------


StandardPrefix = Literal["ISA", "ISQM", "FRMK", "ASSR"]


@dataclass(slots=True, frozen=True)
class StandardSpec:
    """Per-standard parsing configuration injected into md_parser / md_renderer.

    Phase 4b-1 core surface: ``prefix``, regex validators, ``section_enum``,
    ``appendix_extractor``, ``format_standard_id`` / ``validate_standard_id``.

    Phase 4b-2 additions (all ``None`` default → ISA path untouched):

    * ``body_parser``: XML-level body iterator override
    * ``section_detector``: text-based section state machine
    * ``prelude_skip``: marker matcher for revision-preface skip

    Phase 4b-2 itself ships the fields + factories on ISQM/ASSR/FRMK spec
    instances; **actual dispatch wiring** (docx_reader / structure / md_parser
    branching) is Phase 4c scope. The ISA re-parse byte-equivalence exit gate
    is enforced by keeping ISA_SPEC's three new fields at ``None``.

    Attributes:
        prefix: 4-prefix alphabet literal. Composes ``standard_id`` together
            with ``standard_no``.
        standard_id_regex: Compiled regex validating ``standard_id`` strings.
            v1.2.0 per-prefix alt subset of
            ``^(ISA-\\d{3,4}|ISQM-\\d{1,2}|ASSR-\\d{3,4}|FRMK-\\d)$``.
        standard_no_regex: Compiled regex validating ``standard_no`` strings.
            v1.2.0 ``^\\d{1,4}$`` (relaxed from v1.1.x ``^\\d{3,4}$`` to
            accommodate ISQM-1 / FRMK-1 single-digit).
        section_enum: Section enum class. ISA uses
            :class:`audit_parser.ir.types.Section`. ISQM/ASSR/FRMK spec files
            introduce their own StrEnum subclasses.
        appendix_extractor: Heading-level callable. See
            :data:`AppendixExtractor`.
        body_parser: Optional XML body dispatcher. See :data:`BodyParser`.
        section_detector: Optional text-based section machine. See
            :data:`SectionDetector`.
        prelude_skip: Optional prelude-end marker matcher. See
            :data:`PreludeSkip` — caller-owned state, stateless predicate.
    """

    prefix: StandardPrefix
    standard_id_regex: re.Pattern[str]
    standard_no_regex: re.Pattern[str]
    section_enum: type[StrEnum]
    appendix_extractor: AppendixExtractor = isa_default_appendix_extractor
    body_parser: BodyParser | None = None
    section_detector: SectionDetector | None = None
    prelude_skip: PreludeSkip | None = None

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
    "BodyParser",
    "PreludeSkip",
    "SectionDetector",
    "StandardPrefix",
    "StandardSpec",
    "isa_default_appendix_extractor",
]
