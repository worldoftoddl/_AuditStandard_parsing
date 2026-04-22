# FRMK Structure Profile — 인증업무개념체계(2022년 개정)_전문

**작성자**: `audit-standard-domain-reviewer` (team `audit-parser-phase4`)
**작성일**: 2026-04-22
**대상 파일**: `raw/인증업무개념체계(2022년 개정)_전문.docx` (339 KB)
**파싱 방식**: `zipfile + xml.etree` (`tmp/phase4_deepscan.py` 재현 가능)
**합의 `standard_id`**: **`FRMK-1`** (internal identifier; display = IAASB "International Framework for Assurance Engagements" / KICPA "인증업무개념체계")
**Collection**: `audit_standards_인증업무개념체계_2022`
**관련 합의**: [`docs/checkpoint_4_prep.md §1.3.4`](./checkpoint_4_prep.md) (chunk_id regex v1.2.0), [§2.2.2](./checkpoint_4_prep.md) (classify_kind 재설계 초안), [§0.2.2](./checkpoint_4_prep.md) (unknown 3-tier gate)

---

## 1. 개요

`FRMK-1` 은 **단일 framework document** 로, 감사·인증업무의 개념적 기초를 정의한다. KICPA 번역본 기준 1 개 기준서 (standard_id = `FRMK-1`, standard_no = `"1"`). IAASB 로드맵상 향후 개정 시 `FRMK-2` 로 자연 확장.

**파싱 난이도**: **LOW (3 DOCX 중 가장 쉬움)** — `heading 2` 스타일 21건으로 section 경계가 명시적으로 marker 처리됨.

---

## 2. 문서 구조 (실측)

### 2.1 최상위 구조

| 영역 | 범위 | 처리 |
|---|---|---|
| 타이틀 + 발행 정보 | `tbl[3x3]` wrapper 내 para 0~37 | **skip** (title page) |
| 개정개요 prelude | 38~131 (List Paragraph + 바탕글) | **skip** (team-lead 결정 — §2.4 참조) |
| 주 본문 | 132~ (heading 2 구조) | chunk 생성 |
| 보론 (부록) | 149~ 끝 | chunk 생성 + appendix_index |

**주의**: 문서 전체가 outer `tbl[3x3]` wrapper 안에 있다. docx_reader 는 **top-level table 도 iterate** 하여 내부 `<w:p>` 를 flat 화해야 한다 (현 Phase 1 `docx_reader.py` 의 body-children-only iteration 은 이 케이스 미커버).

### 2.2 Section 경계 (heading 2 전수 실측)

`tests/fixtures/phase4_profile_samples.json` 에 JSON 형태로 동기화. 21개 `heading 2` 파라그래프:

| idx | heading 2 텍스트 | 해석 |
|---|---|---|
| 132 | `문단번호` | **skip** — 테이블 column header 성격 |
| 133 | `서론1-4` | `intro` — 문단 1~4 |
| 134 | `윤리 원칙과 품질관리기준5-9` | `ethical_requirements_and_quality` — 문단 5~9 |
| 135 | `인증업무의 의의10-11` | `assurance_definition` — 문단 10~11 |
| 136 | `입증업무와 직접업무12-13` | `attestation_vs_direct` |
| 137 | `합리적 확신업무와 제한적 확신업무14-16` | `reasonable_vs_limited_assurance` |
| 138 | `개념체계의 범위17-19` | `framework_scope` |
| 139 | `비인증업무보고서20-21` | `non_assurance_reports` |
| 140 | `인증업무의 전제조건22-25` | `assurance_preconditions` |
| 141 | `인증업무의 구성 요소26` | `assurance_components` |
| 142 | `삼자관계27-38` | `three_party_relationship` |
| 143 | `기초인증대상39-41` | `underlying_subject_matter` |
| 144 | `준거기준42-49` | `criteria` |
| 145 | `증거50-82` | `evidence` |
| 146 | `인증보고서83-92` | `assurance_report` |
| 147 | `기타 사항93-95` | `other_matters` |
| 148 | `인증인 명칭의 부적절한 사용96` | `inappropriate_use_of_name` |
| 149 | `보론: 역할과 책임` | `appendix` (un-numbered) |
| 150 | `보론 1: 회계감사기준위원회가 제정한 기준 등의 상호 관계…` | `appendix_index=1` |
| 151 | `보론 2: 입증업무와 직접업무` | `appendix_index=2` |
| 152 | `보론 3: 인증업무의 당사자` | `appendix_index=3` |

### 2.3 heading 2 텍스트 normalize 규칙

heading 2 텍스트에 **문단번호 범위가 suffix 로 embed** 되어 있다 (예: `서론1-4`, `삼자관계27-38`). 파싱 시 반드시 **정제**:

```python
_HEADING_RANGE_RE = re.compile(r"(\d+(?:-\d+)?)\s*$")

def normalize_framework_heading(text: str) -> tuple[str, str | None]:
    """'서론1-4' → ('서론', '1-4').  '보론 1: ...' → (text, None).
    Appendix (보론) heading 은 range suffix 가 없으므로 그대로 반환."""
    m = _HEADING_RANGE_RE.search(text.strip())
    if m and not text.strip().startswith("보론"):
        clean = text[:m.start()].strip()
        return clean, m.group(1)
    return text.strip(), None
```

### 2.4 개정개요 prelude skip 규약

**team-lead 결정 (2026-04-22)** 및 **parser-implementer DM Issue 2** 반영:

- **범위**: 첫 `heading 2 == "문단번호"` (idx=132) 이전까지의 모든 블록 = prelude → skip.
- **실측 구간**: 문단 0~131 (title + 개정 배경/주요 내용/주요 개정 이슈 등)
- **근거**: `개정개요` 섹션은 meta/preface 성격. 감사 실무 질의 시 검색 대상 아님. ISA 00_전문.md skip 규약과 동일 패턴.
- **StandardSpec 주입**: `FRMK_SPEC.prelude_end_marker = ("heading_2", "문단번호")` — Phase 4b parser-implementer 구현.

---

## 3. 문단번호 체계

### 3.1 주 본문 요구사항 번호

- 패턴: `%1.` + decimal, ilvl=0 → `REQUIREMENT`
- 실측 23건 (`tmp/phase4_deepscan.json FRMK.classified_kind_distribution.requirement`)
- Phase 1 ISA 규칙과 동일 — 추가 classify_kind override 불필요

### 3.2 하위 항목 `(%1)` at ilvl=0

- 패턴: `(%1)` + (decimal | lowerLetter | lowerRoman), ilvl=0
- 실측 84건 — Phase 4 핵심 확장 대상
- **Phase 4b override**: `FRMK_SPEC.classify_kind` 에서 → `BlockKind.PARAGRAPH_BODY` + `paragraph_id = "(1)"` / `"(a)"` / `"(i)"` 보존 (parser-implementer 대안 c)
- ISA 회귀 영향: 0건 (ISA MD 전수 grep 확인됨 — `parser-implementer DM Issue 3`)

### 3.3 Prelude 번호 (skip 대상)

- 패턴: `%1.` + upperRoman, ilvl=0 (`I. II. III. IV.`)
- 실측 4건 — 모두 개정개요 prelude 내부 → **skip 처리로 classify_kind 도달 안 함** (§2.4 prelude skip)

### 3.4 Bullet / sub_item

- 일반 Phase 1 규칙 준수: bullet 81건, sub_item (ilvl≥1) 12건

### 3.5 unknown_numbering 예상치

§0.2.2 3-tier gate 적용 — extension 후 예상:

| 단계 | 값 | 판정 |
|---|---|---|
| 확장 전 (direct numPr) | 43.14% (88/204) | ABORT (원시 기준) |
| Extension + prelude skip 후 | **≤ 0.5%** (84 PARAGRAPH_BODY + 4 skip = unknown 원천 소거) | **PASS (예상)** — Phase 4b-3 실측 확인 의무 |

---

## 4. Section enum 초안 (`FRMKSection`)

Phase 4b parser-implementer 가 `src/audit_parser/spec/frmk_spec.py` 에 구현:

```python
from enum import StrEnum

class FRMKSection(StrEnum):
    INTRO = "intro"                                     # 서론 1-4
    ETHICAL_REQUIREMENTS_AND_QUALITY = "ethical_requirements_and_quality"  # 윤리 원칙과 품질관리기준 5-9
    ASSURANCE_DEFINITION = "assurance_definition"       # 인증업무의 의의 10-11
    ATTESTATION_VS_DIRECT = "attestation_vs_direct"     # 입증업무와 직접업무 12-13
    REASONABLE_VS_LIMITED_ASSURANCE = "reasonable_vs_limited_assurance"  # 14-16
    FRAMEWORK_SCOPE = "framework_scope"                 # 개념체계의 범위 17-19
    NON_ASSURANCE_REPORTS = "non_assurance_reports"     # 비인증업무보고서 20-21
    ASSURANCE_PRECONDITIONS = "assurance_preconditions" # 인증업무의 전제조건 22-25
    ASSURANCE_COMPONENTS = "assurance_components"       # 인증업무의 구성 요소 26
    THREE_PARTY_RELATIONSHIP = "three_party_relationship"  # 삼자관계 27-38
    UNDERLYING_SUBJECT_MATTER = "underlying_subject_matter"  # 기초인증대상 39-41
    CRITERIA = "criteria"                               # 준거기준 42-49
    EVIDENCE = "evidence"                               # 증거 50-82
    ASSURANCE_REPORT = "assurance_report"               # 인증보고서 83-92
    OTHER_MATTERS = "other_matters"                     # 기타 사항 93-95
    INAPPROPRIATE_USE_OF_NAME = "inappropriate_use_of_name"  # 인증인 명칭의 부적절한 사용 96
    APPENDIX = "appendix"                               # 보론 1/2/3/un-numbered
```

**JSON Schema `section` union (Phase 4b v1.2 MINOR bump)**: 위 17개 값이 `section` enum 에 추가 (ISA 17개 + ISQM N개 + ASSR N개 와 합산 union).

---

## 5. StandardSpec 초안 (Phase 4b 구현 hand-off)

```python
# src/audit_parser/spec/frmk_spec.py (Phase 4b 예정)
from audit_parser.spec.standard_spec import StandardSpec
from audit_parser.ir.types import BlockKind
from audit_parser.ir.numbering import classify_kind as _isa_classify_kind

def _frmk_classify_kind(lvl_text, num_fmt, ilvl):
    # FRMK override: ilvl=0 괄호형 열거 → PARAGRAPH_BODY (paragraph_id 보존은 caller 책임)
    if ilvl == 0 and lvl_text in {"(%1)", "(%1.)", "%1)"}:
        return BlockKind.PARAGRAPH_BODY
    # Prelude skip은 classify_kind 가 아닌 StandardSpec.prelude_end_marker 로 처리
    # (upperRoman %1. at ilvl=0 패턴도 여기 도달 안 함)
    return _isa_classify_kind(lvl_text, num_fmt, ilvl)

FRMK_SPEC = StandardSpec(
    prefix="FRMK",
    standard_id_regex=re.compile(r"^FRMK-\d$"),
    standard_no_regex=re.compile(r"^\d{1,4}$"),
    section_enum=FRMKSection,
    classify_kind=_frmk_classify_kind,
    prelude_skip=True,                                  # 개정개요 skip
    prelude_end_marker=("heading_2", "문단번호"),         # marker 이전까지 skip
    heading_range_strip=True,                           # "서론1-4" → "서론"
    collection_template="audit_standards_인증업무개념체계_{year}",
)
```

---

## 6. 대형 Table / Edge case

### 6.1 Outer wrapper table

문서 전체 outer `tbl[3x3]` wrapper 안에 paragraphs 존재. `docx_reader.py::iter_body_blocks` 는 현재 top-level `<w:p>` 와 `<w:tbl>` 만 iterate. Phase 4b 에서 **recursive descent mode** 추가 필수:

```python
def iter_all_paragraphs(body, inside_table=False):
    for child in body:
        if child.tag == "{...}p":
            yield child, inside_table
        elif child.tag == "{...}tbl":
            # Phase 4: FRMK wrapper, ISQM-1 body table, ASSR body table 모두 table 내부 para 를 chunk 로 emit
            yield from iter_all_paragraphs(child, inside_table=True)
        else:
            yield from iter_all_paragraphs(child, inside_table=inside_table)
```

`inside_table` 플래그는 payload 에 기록 (debug 용). Phase 4 3 DOCX 전부 inside_table 영역에서 content emit.

### 6.2 보론 (appendix) 4건 — 최종 합의 (Critic pushback 반영, 2026-04-22)

실측 4건:
- idx=149: `보론: 역할과 책임` (un-numbered)
- idx=150: `보론 1: 회계감사기준위원회가 제정한 기준 등의 상호 관계…`
- idx=151: `보론 2: 입증업무와 직접업무`
- idx=152: `보론 3: 인증업무의 당사자`

**핵심 충돌 vs ISA 규약**:

ISA `docs/json_schema.md §7.2.1` 는 "un-numbered 보론 = `appendix_index=1`" 로 규정 (9 ISA 에서 uniform). 그러나 FRMK 는 un-numbered 1 개 + numbered 3 개 (`보론 1/2/3`) **공존** 구조 → `appendix_index=1` 매핑 충돌.

**검토 4 대안 (Domain Reviewer 초안 + Critic pushback)**:

| 대안 | 처리 | 장점 | 단점 | 판정 |
|---|---|---|---|---|
| (A) FRMK 만 `appendix_index=0` | un-numbered=0, numbered=1/2/3 | 최소 변경 | ISA §7.2.1 "모두 1" 규약과 분기 — spec-aware validation 필요, JSON Schema 에 파편 분기 | **Critic pushback 수용 — 철회** |
| (B-v1) un-numbered = `null` (minimum 불변) | numbered 만 1/2/3, un-numbered 는 appendix_index=null | ISA 규약 훼손 없음 | "부록이지만 번호 없음" 검색 표현 불가, RAG UX 저하 | **철회** |
| (C) numbered offset → 2/3/4 | un-numbered=1, numbered=2/3/4 | ISA 규약 준수 | IAASB/KICPA 원문 "보론 1/2/3" 왜곡 | **철회** |
| **(B-v2, Critic 제안) `special_appendix_name` 신규 필드** | un-numbered: `appendix_index=null, special_appendix_name="역할과 책임"` / numbered: `appendix_index=1/2/3, special_appendix_name=null` | ISA 36 JSON **bit-level 불변**, FRMK spec isolate, un-numbered 보론의 **title 정보 payload 보존** (RAG UX 개선), Phase 5+ 에서 ISA 9 un-numbered 에도 선택적 채움 가능 | JSON Schema 확장 (신규 필드) — v1.2 MINOR bump 범위 내 | ✅ **확정 채택** |

**확정 채택 (B-v2, Critic §4.2 대안 B)** — 2026-04-22 3자 재합의:

- `chunks[].appendix_index`: `int | null` — un-numbered 는 **null**, numbered 는 기존 정수
- `chunks[].special_appendix_name`: **`str | null`** (v1.2 MINOR bump — 신규 optional 필드)
  - un-numbered FRMK 보론: `"역할과 책임"` (heading `보론: 역할과 책임` 에서 `보론:` 접두 제거 후 추출)
  - numbered FRMK 보론: `null` (appendix_index 에 이미 번호 정보 있음)
  - ISA 9 un-numbered 보론: **Phase 4 에서는 불변** (기본값 `null`, backward-compat 유지). Phase 5+ 에서 `docs/json_schema.md §7.2.1` 개정 시 선택적으로 채울 수 있음 (정본 식별자 확장).

**구현 세부** (Phase 4b parser-implementer commit):

```python
# src/audit_parser/spec/frmk_spec.py
def _frmk_extract_appendix(heading: str, idx: int) -> tuple[int | None, str | None]:
    """보론 heading → (appendix_index, special_appendix_name)."""
    if heading.startswith("보론:") or heading.startswith("보론 :"):
        # un-numbered: "보론: 역할과 책임" → (None, "역할과 책임")
        name = heading.split(":", 1)[1].strip()
        return (None, name)
    m = re.match(r"^보론\s*(\d+)\s*:?\s*(.*)", heading)
    if m:
        return (int(m.group(1)), None)
    return (None, None)

FRMK_SPEC = StandardSpec(
    ...
    appendix_extractor=_frmk_extract_appendix,  # heading → (idx, name) 튜플
    # default_unnumbered_appendix_index / appendix_map 필드는 폐기 (B-v2 채택으로 불필요)
)
```

**JSON Schema 변경 (v1.2 MINOR bump)**:

- `chunks[].special_appendix_name`: `{"type": ["string", "null"]}` 신규 optional 필드
- `chunks[].appendix_index`: **`minimum: 1` 유지** (원래대로 — relax 불필요)
- `additionalProperties: false` 이미 유지 → 신규 필드 추가만으로 backward-compat MINOR
- 36 ISA JSON 은 `schema_version` 문자열만 변경 + `special_appendix_name: null` 추가 in-place replace (재임베딩 불필요)

**근거**: Critic §4.2 대안 B 논거 수용 — (1) ISA 9 un-numbered 보론 대상 JSON 의 bit-level 불변 유지, (2) `special_appendix_name` 은 RAG UX 개선 부가 효과 (un-numbered 보론 title 로 검색 가능), (3) `StandardSpec` 추상화 의도 그대로 spec-specific 필드 활용, (4) §7.2.1 에 "FRMK 예외" 같은 파편 분기 최소화.

**v1.2 atomicity 6-file 영향 (업데이트)**: §12 `appendix_index.minimum` 변경 **철회**, 대신:
- `chunks[].special_appendix_name` 필드 추가 (§12 + fixture)
- `docs/json_schema.md §7.2.1a` 에 FRMK spec 처리 규약 주석 (기존 계획 유지, 내용만 (B-v2) 기준 재작성)

parser-implementer DM 재협의 필요 — 2026-04-22 수정 DM 발송 예정.

### 6.3 Large table (없음)

FRMK 의 tables 는 모두 14 개인데 최대 `tbl[3x3]` 수준 (wrapper 제외). 대형 table 분할 (§9.4) 필요 없음.

---

## 7. Phase 4b Exit gate 재측정 체크리스트

parser-implementer 가 Phase 4b-3 에서 수행:

- [ ] `output/md/FRMK-1.md` 생성 후 unknown_numbering % 재측정 — **≤ 0.5%** 목표 (3-tier PASS)
- [ ] `heading_range_strip` 적용 후 heading_trail 에 `"서론"` (range 제거본) 저장 확인
- [ ] prelude skip 확인 — 문단 0~131 chunk 생성 0건
- [ ] appendix 4건 `appendix_index` 0/1/2/3 매핑 확인
- [ ] ISA 36 re-parse byte 동등 (FRMK_SPEC override 가 ISA 영역 비침해)

---

*End of `docs/framework_structure_profile.md` v1 — Phase 4a Scout 산출. Phase 4b StandardSpec 구현 입력 자료.*
