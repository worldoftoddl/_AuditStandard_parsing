# ASSR Structure Profile — 역사적 재무정보 이외 인증업무기준 (2022년 개정) / ISAE 3000

**작성자**: `audit-standard-domain-reviewer` (team `audit-parser-phase4`)
**작성일**: 2026-04-22
**대상 파일**: `raw/역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문(개정개요 포함).docx` (374 KB)
**파싱 방식**: `zipfile + xml.etree` (`tmp/phase4_deepscan.py` 재현 가능)
**합의 `standard_id`**: **`ASSR-3000`** (단일 standard = KICPA 번역 ISAE 3000 Revised)
**Collection**: `audit_standards_기타인증업무기준_2022`
**관련 합의**: [`docs/checkpoint_4_prep.md §1.3.4`](./checkpoint_4_prep.md), [§2.2.2](./checkpoint_4_prep.md), [§0.2.2](./checkpoint_4_prep.md)

---

## 1. 개요

`ASSR-3000` 은 KICPA 가 **IAASB 의 ISAE 3000 (Revised)** 을 국어로 번역·수록한 단일 standard. 문서 내 `ISAE 3000` 10회 언급 확인 (`tmp/phase4_deepscan.json`). 다른 ISAE 번호 (3400, 3410 등) 는 scope 외 — Phase 5+ 통합 시 `ASSR-3400` 등 으로 동일 namespace 확장 (regex `ASSR-\d{3,4}$` 이미 수용).

**파싱 난이도**: **MED (3 DOCX 중 중간)** — heading style 없이 text-regex 기반 section 경계 판별 + body content 가 대형 `tbl[427x2]` 안에 있음.

---

## 2. 문서 구조 (실측)

### 2.1 최상위 구조

| 영역 | 범위 | 처리 |
|---|---|---|
| 타이틀 + 발행 정보 | 문단 0~37 (`tbl[3x3]` + body 혼재) | **skip** (title page) |
| 개정개요 prelude | 문단 38~274 (`List Paragraph` + 바탕글 style) | **skip** (team-lead 결정 §2.4) |
| 주 본문 + 적용지침 | 문단 275~ (`tbl[427x2]` 내부) | chunk 생성 |

**주의**: 주 본문 전체가 outer `tbl[427x2]` wrapper 안에 있음. `docx_reader.py` recursive descent mode 필수 (§6.1 참조).

### 2.2 Section 경계 (text regex 기반)

ASSR 은 `heading N` style 을 사용하지 않는다. Section 경계 판별은 **text regex match** 로 수행. 실측 boundaries (`tmp/phase4_deepscan.json ASSR.candidate_boundaries`):

| 위치 | text | container | 역할 |
|---|---|---|---|
| prelude (skip 대상) | | | |
| idx 63 | `개요` | body | prelude I |
| idx 67 | `개정 배경` | body | prelude II |
| idx 72 | `개정 기준서의 주요 내용` | body | prelude III |
| idx 175 | `주요 개정 이슈` | body | prelude IV |
| **주 본문 (tbl[427x2]) — 요구사항 본문** | | | |
| idx 275 | `서론` | tbl[427x2] | **`intro`** |
| idx 322 | `시행일` | tbl[427x2] | **`effective_date`** (ISQM 과 동일 section) |
| idx 327 | `목적` | tbl[427x2] | **`purpose`** |
| idx 338 | `용어의 정의` | tbl[427x2] | **`definitions`** |
| idx 382 | `요구사항` | tbl[427x2] | **`requirements`** |
| idx 480 | `품질관리` | tbl[427x2] | `requirements` 하위 (요구사항의 quality control 영역) |
| **주 본문 (tbl[427x2]) — 적용 및 기타 설명자료** | | | |
| idx 814 | `목적` | tbl[427x2] | **`application`** (두 번째 등장 — 적용지침 내 section) |
| idx 821 | `용어의 정의` | tbl[427x2] | `application` |
| idx 1162 | `품질관리` | tbl[427x2] | `application` |
| idx 1505 | `모니터링 절차를 통한 법규 요구사항의 준수` | tbl[427x2] | `application` 세부 |
| idx 1898 | `인증업무 수행과정에서 실시된 자문의 성격, 범위와 그 결론` | tbl[427x2] | `application` 세부 |

### 2.3 section 전환 판별 알고리즘

`목적` / `용어의 정의` 등은 요구사항 본문과 적용지침에 **두 번 등장**. 이는 ISA 의 관례 "주 본문 5-section + 적용지침 (각 주제별 추가 설명)" 와 동일 패턴 — ISA 에서는 heading 2 style 로 구분되지만 ASSR 은 plain text.

**state machine (parser-implementer Phase 4b 구현)**:

```python
# ASSR_SPEC.section_detector
PRIMARY_SECTIONS = ["서론", "시행일", "목적", "용어의 정의", "요구사항"]
APPLICATION_MARKER = "요구사항"  # After "요구사항" section ends, next "목적" marks application start

state = "prelude"
current_section = None
for block in iter_blocks(tbl_427x2):
    t = block.text.strip()
    if state == "prelude_skip":
        continue  # Handled by prelude_end_marker
    if t == "서론":      state = "body_primary";     current_section = "intro"
    elif t == "시행일":   current_section = "effective_date"
    elif t == "목적" and state == "body_primary":     current_section = "purpose"
    elif t == "용어의 정의" and state == "body_primary": current_section = "definitions"
    elif t == "요구사항":  current_section = "requirements"
    # 적용 및 기타 설명자료 전환 감지
    elif t == "목적" and current_section == "requirements":
        state = "body_application"; current_section = "application"
    elif t == "용어의 정의" and state == "body_application":
        pass  # 여전히 application (section 갱신 안 함 — 지시어)
    else:
        yield block.with_section(current_section)
```

### 2.4 개정개요 prelude skip 규약

**team-lead 결정 (2026-04-22)** + **parser-implementer Issue 2** 반영:

- **범위**: 문단 0 ~ 문단 274 (주 본문 `tbl[427x2]` 시작 직전)
- **skip end marker**: 첫 `tbl[427x2]` 내부 paragraph 등장 지점 (idx=275, "서론")
- **StandardSpec 주입**: `ASSR_SPEC.prelude_end_marker = ("table_container", "tbl[427x2]", "서론")` — 3-tuple 로 "해당 table 컨테이너 내부에서 first '서론' 발견 시 skip 종료"
- **대체 방식**: `prelude_end_marker = ("text_match", "서론")` + `require_container = "table"` (구현 재량)

**감사 실무 질의 관련성**: 0 — 개정개요는 "IAASB 가 어떻게 ISAE 3000 을 개정했는지" 메타 설명. 감사 절차 검색 대상 아님.

---

## 3. 문단번호 체계

### 3.1 요구사항 번호

- 패턴: `%1.` + decimal, ilvl=0 → `REQUIREMENT`
- 실측 45건 (`tmp/phase4_deepscan.json ASSR.classified_kind_distribution.requirement`)
- Phase 1 ISA 규칙 그대로 — 추가 override 없음

### 3.2 하위 항목 `(%1)` at ilvl=0 — **Phase 4 핵심 확장 대상**

- 패턴: `(%1)` + (decimal | lowerLetter | lowerRoman), ilvl=0
- 실측 **221건** (3 DOCX 중 최다)
- 실측 상세 (top 3 pattern):
  - `(%1) + lowerLetter @ ilvl=0` — 다수 (예: `업무팀의 구성원과 업무품질관리검토자...`)
  - `(%1) + decimal @ ilvl=0` — 정의 항목 성격 (예: `인증인(Practitioner)`, `입증업무와 직접업무`)
  - `(%1) + lowerRoman @ ilvl=0` — (i), (ii), ... 형식
- **Phase 4b override**: `ASSR_SPEC.classify_kind` 에서:
  ```python
  if ilvl == 0 and lvl_text in {"(%1)", "(%1.)", "%1)"}:
      return BlockKind.PARAGRAPH_BODY  # + paragraph_id="(1)"/"(a)"/"(i)" 보존
  ```
- JSON Schema 변경 없음 (기존 `PARAGRAPH_BODY` enum 재활용)
- chunk_id 자연 노출 예: `ASSR-3000:definitions:{h}:(1)`, `ASSR-3000:requirements:{h}:(a)`

### 3.3 Prelude 번호 (skip 대상)

- 패턴: `%1.` + upperRoman, ilvl=0 (`I. II. III. IV.`)
- 실측 4건 — 모두 개정개요 prelude 내부
- `prelude_end_marker` 로 chunk 생성 이전 단계에서 skip → classify_kind 도달 안 함

### 3.4 기타 (Phase 1 규칙 준수)

- Bullet 260건
- Sub_item (ilvl≥1) 37건

### 3.5 unknown_numbering 예상치 (§0.2.2 3-tier gate)

| 단계 | 값 | 판정 |
|---|---|---|
| 확장 전 (direct numPr) | 37.57% (213/567) | ABORT (원시 기준) |
| Extension + prelude skip 후 | **≤ 0.5%** (221 PARAGRAPH_BODY + 4 prelude skip = unknown 원천 소거) | **PASS (예상)** — Phase 4b-3 실측 확인 의무 |

---

## 4. Section enum 초안 (`ASSRSection`)

```python
class ASSRSection(StrEnum):
    INTRO = "intro"                     # 서론
    EFFECTIVE_DATE = "effective_date"   # 시행일
    PURPOSE = "purpose"                 # 목적 (주 본문)
    DEFINITIONS = "definitions"         # 용어의 정의 (주 본문)
    REQUIREMENTS = "requirements"       # 요구사항 (품질관리 하위 포함)
    APPLICATION = "application"         # 적용 및 기타 설명자료 (목적 / 용어의 정의 / 품질관리 / 세부)
    APPENDIX = "appendix"               # (if any)
```

주의: ASSR 는 Phase 1 ISA 의 `requirements` + `application` 2 section 모델과 정합. ISA 의 `overall_objective` / ISA-1200 전용 섹션 등은 ASSR 에 부재.

**JSON Schema `section` union 확장**: ISA 17 + ISQM N + FRMK 17 + ASSR 7 (위) + `"unknown"` / null → Phase 4b v1.2 MINOR bump 시 동기화.

---

## 5. StandardSpec 초안 (Phase 4b 구현 hand-off)

```python
# src/audit_parser/spec/assr_spec.py (Phase 4b 예정)
ASSR_SPEC = StandardSpec(
    prefix="ASSR",
    standard_id_regex=re.compile(r"^ASSR-\d{3,4}$"),
    standard_no_regex=re.compile(r"^\d{1,4}$"),
    section_enum=ASSRSection,
    classify_kind=_assr_classify_kind,  # (%1) ilvl=0 → PARAGRAPH_BODY
    prelude_skip=True,
    prelude_end_marker=("table_container", "tbl[427x2]", "서론"),
    section_detector=_assr_section_detector,  # §2.3 state machine
    collection_template="audit_standards_기타인증업무기준_{year}",
)
```

---

## 6. 대형 Table / Edge case

### 6.1 Body-in-table 레이아웃 (§6 공통)

ASSR 주 본문 전체가 `tbl[427x2]` wrapper 내부에 위치. `docx_reader.py` recursive descent 필수.

**tbl[427x2] 의 2-column 의미**: 실측 조사 결과 이는 ISQM-1 의 "col[0]=id, col[1]=body" 구조와는 **다르다** — ASSR 의 2-column 은 단순히 **본문을 감싸는 visual container** (여백 조정 목적). 실제 paragraph_id / text 는 cell 내부 `<w:p>` 의 numPr + text 에 정상 존재. 파싱 시 cell 경계를 무시하고 paragraph 를 flat 화하면 된다.

### 6.2 복수 table (전체 12개)

ASSR 는 tables 12개이나 본문 table 외에는 모두 소규모 (3×3, 7×1, 5×3, 1×1 등). 개정개요 prelude 영역의 설명용 표 — skip 대상에 포함되므로 parser 에서 무시.

### 6.3 대형 table split 여부

ASSR 내 최대 data table = `tbl[5x3]` 수준 → §9.4 대형 table 분할 (ISA-1200 66×2 유형) **불필요**. chunk_splitter 2-level assertion guard (§1.8) 도 영향 없음.

---

## 7. Phase 4b Exit gate 재측정 체크리스트

- [ ] `output/md/ASSR-3000.md` 생성 후 unknown_numbering % 재측정 — **≤ 0.5%** 목표
- [ ] prelude skip — 문단 0~274 chunk 생성 0건
- [ ] `section_detector` 상태전환 — `requirements` → `application` 전환 idx=814 근처에서 정확히 발화
- [ ] `(%1)` at ilvl=0 221건 전부 `PARAGRAPH_BODY + paragraph_id="(X)"` emit
- [ ] ISA 36 re-parse byte 동등 (ASSR_SPEC override ISA 영역 비침해)

---

*End of `docs/assurance_other_structure_profile.md` v1 — Phase 4a Scout 산출.*
