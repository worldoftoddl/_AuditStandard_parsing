# ISQM-1 Structure Profile — 품질관리기준서1 (2018년 제정) 국어전문

**작성자**: `audit-standard-domain-reviewer` (team `audit-parser-phase4`)
**작성일**: 2026-04-22
**대상 파일**: `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` (87 KB)
**파싱 방식**: `zipfile + xml.etree` (`tmp/phase4_deepscan.py` + `tmp/phase4_isqm_table.py` 재현 가능)
**합의 `standard_id`**: **`ISQM-1`** (단일 KICPA 2018 번역본. IAASB ISQM 2 / ISA 220 Revised 는 본 Phase 4 scope 외 — §7 참조)
**Collection**: `audit_standards_품질관리기준서_2018`
**관련 합의**: [`docs/checkpoint_4_prep.md §1.3.4`](./checkpoint_4_prep.md), [§0.3.3](./checkpoint_4_prep.md) (ISQM 2 Scope 외), [§2.2.2](./checkpoint_4_prep.md)

---

## 1. 개요

`ISQM-1` 은 KICPA 가 2018년 제정한 품질관리기준서 1 의 국어 전문. IAASB ISQC 1 / 현 ISQM 1 (2020 IAASB 개정) 의 한국어 전신. 단일 standard.

**파싱 난이도**: **HIGH (3 DOCX 중 가장 복잡)**. 문서 content 전체가 **2-column 수동 table layout** (col[0] = paragraph_id as text, col[1] = body text) 으로 구성되어 있어 Phase 1 `docx_reader.py` / `numbering.py` / `structure.py` 의 style-inherited numPr 기반 파싱 경로로 **커버 불가**. Phase 4b 에서 **신규 `ISQMTableBodyParser`** 구현 필요.

---

## 2. 문서 구조 (실측)

### 2.1 최상위 구조 — 3개 table

`tmp/phase4_deepscan.py` + `tmp/phase4_isqm_table.py` 실측:

| Table | 크기 | 내용 | 처리 |
|---|---|---|---|
| #0 | `tbl[3x3]` | 타이틀 + 메타 (회계감사기준위원회, 연월 등) | **skip** |
| #1 | `tbl[244x1]` | 목차 (TOC) — 'Contents' / 'TOC Body' style | **skip** (ISA 00_전문.md skip 규약 재사용) |
| #2 | **`tbl[236x2]`** | **주 본문 (body)** — 2-column: col[0]=paragraph_id text, col[1]=body content | **chunk 생성 대상** |

### 2.2 Body table (`tbl[236x2]`) 레이아웃 — 핵심 발견

**⚠ 이 문서의 paragraph_id 는 numPr 이 아니라 cell 내부 plain text 로 저장되어 있다**. Phase 1 ISA / ISQM IAASB 번역본의 "style-inherited numId" 패턴과 **근본적으로 다름**.

`tmp/phase4_isqm_table.py` 실측 (236×2 table 앞 row 50):

| row | col[0] | col[1] | 해석 |
|---|---|---|---|
| 0 | `"1"` | body text w/ style `NumberedParagraph1` | paragraph_id=1 |
| 1 | `"2"` | body text | paragraph_id=2 |
| 2 | `"3"` | body text (multi-paragraph) | paragraph_id=3 |
| **3** | `""` | `"이 품질관리기준서의 효력"` | **sub-section heading** (col[0] 비어있음) |
| 4 | `"4"` | body text | paragraph_id=4 |
| **5** | `"한4-1"` | body text | paragraph_id="한4-1" (**KICPA 국내 추가 관례**) |
| 6-10 | `"5"`, `"6"`, `"7"`, `"8"`, `"9"` | body | |
| **11** | `""` (style NumberedParagraph1) | `"시행일"` | **section heading** |
| 12 | `"10"` | body | |
| **15** | `"11"` | body (+ `(a)`, `(b)`, ... sub-items in same cell) | paragraph_id=11, multi-paragraph cell |

### 2.3 Body table 파싱 규약 (Phase 4b parser-implementer 구현 명세)

```python
# src/audit_parser/spec/isqm_spec.py + src/audit_parser/ir/isqm_table_parser.py (신규, Phase 4b)

def parse_isqm_body_table(tbl_elem, *, numbering_engine) -> Iterable[RawBlock]:
    """ISQM-1 전용 2-column body table parser.
    
    레이아웃:
      col[0]: paragraph_id as plain text.
        - '1', '2', ..., '10', ..., '57' 등 숫자
        - '한4-1', '한18-1', '한25-1' 등 KICPA 국내 추가 ('한' prefix)
        - 공백 = section heading row
      col[1]: body content (multi-<w:p> 허용)
        - 첫 <w:p> = requirement 본문
        - 이후 <w:p> = '(a)', '(b)', '(i)' 등 sub_item (문단 번호 없음, 본문 텍스트에 (a) 포함)
    """
    heading_stack: list[str] = []  # [section, sub_section]
    current_section: str | None = None
    current_subsection: str | None = None
    
    for row in tbl_elem.findall(".//w:tr"):
        cells = row.findall("w:tc")
        if len(cells) != 2:
            continue
        
        col0_text = _first_text(cells[0]).strip()
        col1_paras = list(cells[1].findall(".//w:p"))
        
        if not col0_text:
            # Section / sub-section heading row
            if not col1_paras:
                continue
            first_txt = _text(col1_paras[0]).strip()
            if first_txt in ISQM_SECTIONS:         # 서론 / 시행일 / 목적 / ...
                current_section = first_txt
                current_subsection = None
                continue
            if first_txt in ISQM_SUBSECTIONS:       # 독립성 / 업무팀의 배정 / ...
                current_subsection = first_txt
                continue
            # 기타 텍스트는 문맥상 사이드 노트 → paragraph_body 로 emit
            yield RawBlock(
                kind=BlockKind.PARAGRAPH_BODY, paragraph_id="",
                heading_trail=[current_section, current_subsection],
                text=first_txt, source_idx=...
            )
            continue
        
        # Regular numbered paragraph row
        paragraph_id = col0_text  # e.g. "1", "한4-1"
        # First <w:p> in col[1] = requirement body
        first_body = _text(col1_paras[0])
        yield RawBlock(
            kind=BlockKind.REQUIREMENT,
            paragraph_id=paragraph_id,
            heading_trail=[current_section, current_subsection],
            text=first_body, source_idx=...
        )
        # Subsequent <w:p> in col[1] = (a), (b), ... sub-items
        for sub_p in col1_paras[1:]:
            sub_text = _text(sub_p)
            # Extract sub-id like "(a)" / "(i)" from text prefix (no numPr)
            sub_id = _extract_sub_id(sub_text)  # → "(a)", "(b)", None
            yield RawBlock(
                kind=BlockKind.SUB_ITEM,
                paragraph_id=sub_id or "",
                parent_paragraph_id=paragraph_id,
                heading_trail=[current_section, current_subsection],
                text=sub_text, source_idx=...
            )
```

**핵심 차이점 vs ISA**:
- **paragraph_id 소스**: ISA 는 numPr + numbering.xml counter replay, ISQM-1 은 **table cell text**
- **sub_item 감지**: ISA 는 ilvl=1 numPr 로 감지, ISQM-1 은 cell 내부 **순서 + text prefix regex** `^\s*\(([a-z]|\d+|[ivx]+)\)` 로 감지
- **Section 경계**: ISA 는 heading 2 style, ISQM-1 은 **col[0] 비어있고 col[1] 이 ISQM_SECTIONS 매칭** 되는 row

### 2.4 실측 Section 목록 (body table 내부)

`tmp/phase4_deepscan.py` + row-by-row 실측 (Phase 4a) + **Phase 4c c3 실 convert WARNING 로그 수집 (N=143 stderr 로그 → 39 visible unique + 12 cutoff = 51 canonical 확장 대상, baseline 11 포함 시 `ISQM_SUBSECTIONS` 57 effective entries)** 통합 실측 결과.
Phase 4c c4 (`2c8446b`) 에서 `ISQM_SUBSECTIONS` frozenset 57 effective entries (11 baseline + 35 Domain canonical + 12 parser pre-emptive = 58 logical, `의견의 차이` 1건 Domain/parser 양측 독립 포함분 auto-dedupe) + `ISQM_TABLE_HEADERS` 신설 + `_strip_reference_suffix` canonical match 규약 반영 완료 (`src/audit_parser/spec/isqm_spec.py`). 본 §2.4 는 Phase 4c c5 / c6 (`docs-only`) 에서 도메인 rationale 문서화로 동기 bump.

#### 2.4.1 Primary sections (6 entries — `ISQM_SECTIONS`)

| section enum | heading text | 해석 |
|---|---|---|
| `intro` | `서론` | 이 품질관리기준서의 범위 / 효력 포함 (idx=65 in flat order) |
| `effective_date` | `시행일` | (idx=11 body table row) |
| `purpose` | `목적` | |
| `definitions` | `용어의 정의` | |
| `requirements` | `요구사항` | 리더십 / 윤리 / 인적 자원 / 의뢰인 관계 / 업무수행 / 모니터링 등 하위 |
| `application` | `적용 및 기타 설명자료` | 각 요구사항의 적용지침 |

#### 2.4.2 Sub-sections (57 effective entries — `ISQM_SUBSECTIONS`)

Phase 4b-2 Q5 initial 11 entries + Phase 4c c4 canonical 35 entries (Domain Reviewer 판정) + c4 pre-emptive 12 entries (parser-implementer + c5 Domain Reviewer confirm) = **총 58 logical entries** (`frozenset` auto-dedupe 로 실제 unique **57 entries** — `의견의 차이` 1건 Domain/parser 양측 독립 포함 시 frozenset 자동 중복 제거).

**Math breakdown**: 11 baseline (Phase 4b-2 Q5) + 35 Domain canonical (Phase 4c c3 판정) + 12 parser pre-emptive (c4 preemptive, Domain c5 confirm) = 58 logical; dedupe `의견의 차이` (Domain list #32 + pre-emptive list #2) = 57 unique.

##### intro 하위 (2 entries)

- `이 품질관리기준서의 효력` (Phase 4b-2, idx=8 in body table)
- `이 품질관리기준서의 범위` (c4 pre-emptive, intro 하위 scope 소개)

##### definitions 하위 (1 entry)

- `"회계법인", "네트워크", "네트워크 회계법인"의 정의` — **smart quotes (U+201C/U+201D) 실측 보존** (KICPA 원문 사용). straight quote (`"`) 버전은 등록 안 됨.

##### requirements 하위 (36 entries)

**리더십 / 품질관리시스템 구성요소** (6 entries):

- `관련 요구사항의 적용과 준수` (Phase 4b-2)
- `품질관리시스템의 구성요소` (Phase 4b-2)
- `품질관리시스템의 문서화` (c4 pre-emptive)
- `회계법인내 품질에 대한 리더십 책임` (Phase 4b-2)
- `회계법인 품질관리시스템의 운영책임 지정` (c4 pre-emptive)
- `품질에 대한 내부문화의 촉진` (c4 pre-emptive)

**관련 윤리적 요구사항** (4 entries):

- `관련 윤리적 요구사항` (Phase 4b-2)
- `관련 윤리적 요구사항의 준수` (c4 canonical)
- `독립성` (Phase 4b-2)
- `유착위협` (c4 canonical)

**의뢰인 관계 및 업무 수용** (4 entries):

- `의뢰인 관계 및 특정 업무의 수용과 유지` (Phase 4b-2, space 포함 canonical)
- `의뢰인관계 및 특정 업무의 수용과 유지` (c4 canonical, **space typo variant** 보수적 등록)
- `의뢰인 관계의 유지` (c4 canonical)
- `의뢰인의 성실성` (c4 canonical)

**인적 자원 / 업무팀 / 업무 수행** (9 entries):

- `인적 자원` (Phase 4b-2)
- `업무팀의 배정` (Phase 4b-2)
- `업무팀` (c4 canonical)
- `업무수행이사` (c4 canonical)
- `적격성, 역량과 자원` (c4 pre-emptive)
- `업무의 수행` (Phase 4b-2)
- `업무수행품질의 일관성` (c4 canonical)
- `감독` (c4 canonical)
- `검토` (c4 canonical)

**업무 수행 — 자문 / 의견 차이 / 업무 해지** (3 entries):

- `자문` (c4 pre-emptive)
- `의견의 차이` (c4 canonical + c4 pre-emptive 양측 독립 포함)
- `업무의 해지` (c4 canonical)

**서면확인서 / 업무문서** (6 entries):

- `서면확인서` (c4 canonical)
- `업무문서화` (c4 canonical)
- `업무의 문서화` (c4 canonical, KICPA linguistic variant)
- `업무문서의 소유권` (c4 canonical)
- `업무문서의 보존` (c4 canonical)
- `업무문서의 비밀유지, 안전한 보관, 무결성, 접근성 및 재생가능성` (c4 canonical)

**최종업무파일 취합** (2 entries):

- `최종업무파일의 취합 완료` (c4 pre-emptive, space 포함)
- `최종업무파일의 취합완료` (c4 pre-emptive, **space-less variant** 보수적 등록)

**업무품질관리검토 (EQR)** (8 entries):

- `업무품질관리검토` (c4 canonical)
- `업무품질관리검토의 기준` (c4 canonical)
- `업무품질관리검토 의 성격, 시기 및 범위` (c4 canonical, **KICPA 인쇄 typo `검토 의` 공백 preserved**)
- `업무품질관리검토의 문서화` (c4 canonical)
- `업무품질관리검토자의 적격성 기준` (c4 canonical)
- `업무품질관리검토자의 객관성` (c4 canonical)
- `업무품질관리검토자의 자문` (c4 canonical)
- `충분하고 적합한 기술적 전문성, 경험 및 권한` (c4 pre-emptive, EQR reviewer 자격 상세)
- `상장기업에 대한 업무품질관리검토` (c4 canonical)

**모니터링 / 미비점 / 고충** (6 entries):

- `모니터링` (Phase 4b-2)
- `회계법인의 품질관리정책과 절차에 대한 모니터링` (c4 pre-emptive)
- `식별된 미비점에 대한 평가, 커뮤니케이션 및 해결` (c4 canonical)
- `미비점의 커뮤니케이션` (c4 canonical)
- `고충과 진정` (c4 canonical)
- `고충과 진정의 원천` (c4 canonical)
- `조사 정책과 절차` (c4 pre-emptive)

##### application 하위 (4 entries)

- `공공부문 감사조직에 특유한 고려 사항` (c4 canonical, space 포함)
- `공공부문 감사조직에 특유한 고려사항` (c4 canonical, **space-less variant** 보수적 등록)
- `소규모 회계법인에 특유한 고려 사항` (c4 canonical, space 포함)
- `소규모 회계법인에 특유한 고려사항` (c4 canonical, **space-less variant** 보수적 등록)

#### 2.4.3 TOC column header skip (`ISQM_TABLE_HEADERS`, Phase 4c c4 신설)

| heading | 처리 | 근거 |
|---|---|---|
| `문단번호` | **silent skip** (no WARNING) | ISQM body table `tbl[236x2]` 의 col[1] 제목 row (TOC 성격 — sub-section data 아님) |

`_emit_heading_or_fallback` 내부에서 `canonical ∈ ISQM_TABLE_HEADERS` 검사가 `ISQM_SECTIONS` / `ISQM_SUBSECTIONS` 검사보다 선행 → TOC row 는 fallback PARAGRAPH_BODY emit 없이 즉시 skip.

#### 2.4.4 Canonical strip 규약 (`_strip_reference_suffix`, Phase 4c c4 신설)

KICPA 2018 ISQM-1 body table 의 sub-section heading 은 **관련 요구사항의 문단 참조** 를 괄호 suffix 로 동반하는 경우가 다수 (143건 WARNING 중 약 70%). 예:

- `감독(문단 32(b) 참조)` → canonical `감독`
- `서면확인서 (문단 24 참조)` → canonical `서면확인서`
- `공공부문 감사조직에 특유한 고려 사항 (문단 26-28 관련)` → canonical `공공부문 감사조직에 특유한 고려 사항`

**regex**:

```python
_REFERENCE_SUFFIX_RE: Final = re.compile(r"\s*\(문단[^)]*(참조|관련)[^)]*\)\s*$")
```

`ISQM_SUBSECTIONS` lookup 전 `_strip_reference_suffix(text)` 적용 → 원본 DOCX 의 문단번호 변경에도 resilient. KICPA 개정 시 sub-section heading 자체가 변하지 않는 한 매칭 유지.

#### 2.4.5 KICPA 인쇄 typo preservation

Phase 4c c3/c4 실측 결과 KICPA 2018 원본 DOCX 에 다음 **인쇄 typo variant** 공존 확인:

| Canonical (정상) | Typo variant | 처리 |
|---|---|---|
| `공공부문 감사조직에 특유한 고려사항` | `공공부문 감사조직에 특유한 고려 사항` (공백) | **양 variant 등록** |
| `소규모 회계법인에 특유한 고려사항` | `소규모 회계법인에 특유한 고려 사항` (공백) | **양 variant 등록** |
| `의뢰인 관계 및 특정 업무의 수용과 유지` | `의뢰인관계 및 특정 업무의 수용과 유지` (공백 누락) | **양 variant 등록** |
| `업무품질관리검토의 성격, 시기 및 범위` | `업무품질관리검토 의 성격, 시기 및 범위` (공백 삽입) | **typo variant 만 실측 — 등록** |
| `최종업무파일의 취합완료` | `최종업무파일의 취합 완료` (공백) | **양 variant 등록** |

**판정 근거**: parser normalize 로직 (space strip regex) 적용 시 다른 heading (e.g. `"관련 요구사항"`, `"업무수행 이사"` 등 공백 의미 있는 term) 에 의도치 않은 side-effect 리스크. **양 variant frozenset 등록이 보수적 해결**. KICPA 2018 freeze data 기준.

**Smart quotes (U+201C/U+201D) preservation**: `"회계법인", "네트워크", "네트워크 회계법인"의 정의` heading 의 따옴표는 DOCX 원문의 smart quote (`"`, `"`). straight quote (`"`) 미사용 — unicode normalize 도 적용 금지.

#### 2.4.6 Schema 영향 (v1.2.0 범위 내 처리, Phase 4d 자동 수용)

§2.4 의 `ISQM_SUBSECTIONS` 57 effective entries + `ISQM_TABLE_HEADERS` 신설 + `_strip_reference_suffix` canonical match 규약은 **`docs/json_schema.md` v1.2.0 schema 범위 내에서 처리됨**. 별도 v1.3 bump 불필요.

| Schema 요소 | 영향 | 근거 |
|---|:-:|---|
| `schema_version` const | ❌ | v1.2.0 유지 |
| `section` enum | ❌ | sub-section 은 `heading_trail` 에 저장, `section` enum 은 primary 6건 유지 |
| `chunk_id` 구조 | ❌ | 4-segment 포맷 + suffix chain 불변 |
| `heading_trail_hash` 알고리즘 | ❌ | `sha1(cleaned text)` 유지 |
| `standard_id` / `standard_no` pattern | ❌ | v1.2.0 regex 유지 |
| `special_appendix_name` field | ❌ | Phase 4b-1 추가, c4/c5 미사용 |

**Phase 4d (MD → JSON) 진입 시**: `output/md/ISQM-1.md` 재생성분이 v1.2.0 schema 내에서 자동 수용. `section` literal union 확장 (`effective_date` 등 ISQM 고유 값) 은 Phase 4d 일괄 처리 (별도 MINOR bump). 36 ISA JSON bit-level 불변 유지.

#### 2.4.7 c3 WARNING 수렴 기록 (Phase 4c 3+2 공동 작업 결과)

| 단계 | 값 | 비고 |
|---|---:|---|
| c3 landing 직후 WARNING | **143건 (unique 39+12)** | `[isqm_table_parser] unregistered heading row` stderr |
| c4 `ISQM_SUBSECTIONS` 57 effective entries + canonical strip + TOC skip 적용 후 | **0건** (기대) | Phase 4c c4 landing 후 재 convert 검증 |
| c5 docs patch (본 §2.4 확장) | N/A | docs-only, convert 영향 없음 |

**Phase 4c 3+2 공동 작업 프로토콜** (ISQM Hook 1 + ASSR Hook 2 + FRMK Hook 3 + ASSR corner Hook 4) 완료. 파일 소유권 경계 엄수 (docs = domain reviewer / spec+parser+tests = parser-implementer) + atomic co-author commit (c4) + docs-only MINOR commit (c5) 분리.

### 2.5 KICPA 국내 추가 paragraph_id (`한{N}-{suffix}`)

실측 (`tmp/phase4_isqm_table.py` row 5, 30, 40):
- `한4-1`, `한18-1`, `한25-1` 등
- "한" prefix = KICPA 가 국제 ISQC 1 에 없는 국내 제도(외부감사법 등) 특유 사항을 추가한 문단
- chunk_id 에는 그대로 사용: `ISQM-1:requirements:{h}:한4-1`
- **chunk_id regex check (§1.3.2)**: `[^#\s:]+` 에 한글 포함 → 통과 ✓

---

## 3. 문단번호 체계

### 3.1 paragraph_id 출처 — numbering.xml 아닌 cell text

- ISQM-1 body 의 모든 paragraph_id ("1" ~ 약 57, 한4-1, 한18-1 등) 는 **numbering.xml 기반 auto-number 가 아님**.
- `word/numbering.xml` 에는 `abstractNumId=15` (적용지침 `A%1.` 계열) 1종만 존재. 실제 body requirements 는 style `NumberedParagraph1` (numId 없음) 사용.
- **style-inherited 도 아님** — `style_numpr["NumberedParagraph1"]` → `basedOn="a"` chain 조회 결과 numId=None.
- 따라서 Phase 1 `classify_kind` 호출 자체가 발생 안 함 (numbered_paragraphs 130건은 cell 내부 bullet/sub_item 전용).

### 3.2 cell 내부 sub-item 감지

- body cell col[1] 내부 `<w:p>[1:]` 의 텍스트 prefix regex:
  ```python
  _SUB_ID_RE = re.compile(r"^\s*\(([a-z]{1,2}|[가-힣]|[ivx]{1,4}|\d{1,2})\)\s*")
  ```
- 매칭 시 `paragraph_id = "(a)"` / `"(가)"` 등으로 emit
- 매칭 실패 시 `paragraph_id = ""` + `kind=PARAGRAPH_BODY` (continuation)

### 3.3 실제 발생한 numPr 패턴 (sub_item 용)

`tmp/phase4_prescan.json ISQM-1.top_numIds`:
- numId=16 : abstractNumId=15 (`A%1.` decimal) — 적용지침 하위 sub-item 용
- 기타 대부분 bullet

Phase 1 기존 classify_kind 가 그대로 처리 가능 (bullet / sub_item). ISQM-1 specific override는 **section-heading row 감지** 와 **col-based paragraph_id 추출** 이지 classify_kind 확장이 아님.

### 3.4 unknown_numbering 예상치 (§0.2.2 3-tier gate)

| 단계 | 값 | 판정 |
|---|---|---|
| 확장 전 (direct numPr direct) | 0% (130/130 bullet 로 분류됨) | PASS |
| ISQM table parser 적용 후 | **≤ 0.5%** (paragraph_id 는 table cell text 에서 추출 — numbering.xml 경유 없음, unknown 발생 원천 없음) | **PASS** |

ISQM-1 은 confusingly **unknown_numbering gate 기준으로는 처음부터 OK**. 하지만 **body content 를 chunk 로 추출하려면 신규 parser 가 필요**. 이 두 이슈는 orthogonal.

---

## 4. Section enum 초안 (`ISQMSection`)

```python
class ISQMSection(StrEnum):
    INTRO = "intro"                     # 서론 (이 품질관리기준서의 범위 / 효력 포함)
    EFFECTIVE_DATE = "effective_date"   # 시행일
    PURPOSE = "purpose"                 # 목적
    DEFINITIONS = "definitions"         # 용어의 정의
    REQUIREMENTS = "requirements"       # 요구사항 (관련 요구사항 적용/준수, 품질관리시스템 구성요소, 리더십, 윤리, 의뢰인 관계, 인적 자원, 업무 수행, 모니터링 하위 포함)
    APPLICATION = "application"         # 적용 및 기타 설명자료
    APPENDIX = "appendix"               # (예상 — ISQM-1 은 보론 존재 여부 실측 후 확정)
```

ISA Section enum 과 상당 부분 일치. ISQM 전용 추가 enum 은 없음. ISA `overall_objective` 는 ISA-200 전용이므로 ISQM 에서 미사용.

---

## 5. StandardSpec 초안 (Phase 4b 구현 hand-off)

```python
# src/audit_parser/spec/isqm_spec.py (Phase 4b 예정)
ISQM_SPEC = StandardSpec(
    prefix="ISQM",
    standard_id_regex=re.compile(r"^ISQM-\d{1,2}$"),
    standard_no_regex=re.compile(r"^\d{1,4}$"),
    section_enum=ISQMSection,
    classify_kind=_isa_classify_kind,   # ISA default 로 충분 — ISQM body 의 req/sub-item 은 table cell text 에서 직접 추출
    prelude_skip=True,
    prelude_end_marker=("table_index", 2),  # 3번째 table (index=2) = tbl[236x2] body 시작
    body_parser="isqm_table",           # 신규 parser_mode — docx_reader 가 분기
    collection_template="audit_standards_품질관리기준서_{year}",
)
```

**특이점 — `body_parser="isqm_table"`**: 기존 ISA / FRMK / ASSR 는 numPr + heading style 기반 일반 파서, ISQM-1 만 **전용 table parser** 분기. `docx_reader.py` 가 `spec.body_parser` 값에 따라 parser 선택.

---

## 6. 대형 Table / Edge case

### 6.1 Body-in-table 레이아웃 — 강제 descent

ISQM-1 은 body content 전체가 `tbl[236x2]` 내부. `docx_reader.py` recursive descent mode 필수.
단 FRMK / ASSR 과 달리 **cell 구조 자체가 의미** (col[0]/col[1] 구분 필요). 단순 flatten 아님.

### 6.2 Multi-paragraph cells

col[1] 에 여러 `<w:p>` 존재 — 첫번째는 requirement 본문, 이후는 `(a)/(b)/(i)` sub-items. parser 가 **cell 순서 + text prefix** 조합으로 disambiguate.

### 6.3 Empty rows (layout filler)

실측 `tmp/phase4_isqm_table.py` row 13 / 16 / 19 등 — col[0], col[1] 모두 비어있는 row 는 visual spacing 용. parser 에서 무시.

### 6.4 요구사항 body vs 적용지침 전환

body table 내부 idx~390 근처 `"적용 및 기타 설명자료"` section heading row 감지 시점부터 `current_section = "application"` 으로 state 전환. 이후 paragraph_id 형식은 **A1.` `A2.` 등 application guidance 번호** 예상 (ISA 와 동일 관례) — 실측 확인 TBD (Phase 4b-3 구현 시).

### 6.5 보론 (appendix) 존재 여부

body table 끝부분 실측 미완료 — Phase 4b 구현 시점 parser-implementer 가 확인. 없을 가능성 높음 (ISQM-1 은 간결한 기준서).

### 6.6 대형 table split (§9.4)

ISQM-1 의 data tables 는 없음 (body 를 감싸는 layout table 만 존재). §9.4 ISA-1200 66×2 식 분할 불필요.

---

## 7. ISQM 2 / ISA 220 Revised Scope 외 재확인

`docs/checkpoint_4_prep.md §0.3.3` 반영:
- IAASB 공식 세트 = **ISQM 1 + ISQM 2 + ISA 220 Revised** 3개 독립
- KICPA 2026-04-22 시점 번역본 제공 = **ISQM 1 만** (2018 KICPA 명칭 "품질관리기준서1")
- ISQM 2 (업무품질 관리검토) / ISA 220 Revised = KICPA 미제공 → Phase 5+ IAASB 원문 통합 검토
- 현 regex `^ISQM-\d{1,2}$` 가 ISQM 2 수용하므로 Phase 5 통합 시 regex 재bump 없음

---

## 8. Phase 4b Exit gate 재측정 체크리스트

- [ ] `output/md/ISQM-1.md` 생성 후 body table parser 산출 paragraph_id 전수 확인
  - 숫자 paragraph_id ("1" ~ 약 57)
  - 한글 prefix paragraph_id ("한4-1", "한18-1", "한25-1" 등) 3~5건
- [ ] Section heading 감지 — 서론/시행일/목적/용어의 정의/요구사항/적용 및 기타 설명자료 6개 섹션 전원 chunk boundary 올바름
- [ ] Sub-section heading 감지 — 요구사항 하위 8~10개 (리더십, 윤리, 인적 자원 등)
- [ ] Multi-paragraph cell 처리 — `(a)(b)(c)...` sub_item chunk 생성 + `parent_paragraph_id` 링크
- [ ] unknown_numbering 재측정 — **≤ 0.5%** (3-tier PASS)
- [ ] ISA 36 re-parse byte 동등 (ISQM parser 가 ISA 영역 비침해)

---

## 9. ISQM Mini Golden Dataset — Seed Pool Pre-draft (25 seeds)

> **Phase 4f Task #10 Mini Golden 측정용 seed pool**. `docs/checkpoint_4_prep.md §0.2.3` 권고 "20~30건 pre-draft" 반영. 초기 사용 10건 + 확장 시 n=15/20 case 별도 활용. 최종 선정은 Task #10 진입 시점 team-lead + 사용자 결정.

### 9.1 카테고리별 분포 (총 25건) — Plan v2 §7.1 5-category 체계 준수 (Critic §5 scope creep 반영)

> **Critic §5 pushback 수용 (2026-04-22)**: 초기 초안은 F 카테고리 (예비) 2건 신설이었으나 Plan v2 §7.1 A-E 5 카테고리 체계 scope creep 위반. F1/F2 (용어 정의) 를 **카테고리 B (위험평가 요소 / 품질목적) 하위 "용어 이해" 항목** 으로 재배치 — 총 seed 수 25 유지.

| Category | Seed 수 | 파일 저장 카테고리 코드 | 비고 |
|---|---:|---|---|
| A. 거버넌스 / 리더십 | 5 | `A` | |
| B. 위험평가 요소 / 품질목적 + **용어 이해** | **7** (기존 5 + F 편입 2) | `B` | ISQM 1 의 "용어의 정의" 는 품질관리 용어 이해의 기본 — B 영역 자연 포함 |
| C. 모니터링 / 개선 | 4 | `C` | |
| D. 참여감사인 / 업무팀 | 4 | `D` | |
| **E. 한/영 혼재 (핵심)** | **5 (필수 ≥3)** | `E` | |
| ~~F. 예비~~ | ~~2~~ | — | **폐기 — Critic §5 scope creep 반영** |

추가로 **Critic §5.3 single-author bias 대응** 을 위한 team-lead/user 주입 권고 slot 3건 (Plan v2 §7.4 cross-check 의무) 별도 + Critic §5.3 제안 추가 1건 (카테고리 B 에 "self-review threat 발견 시 품질관리시스템 후속 절차").

### 9.2 Seed 전문 (JSONL 형태 — `tests/fixtures/isqm_mini_golden_dataset.jsonl` 에 최종 commit)

Phase 4a pre-draft (ISQM-1 도메인 전문성 기반). `expected_chunk_ids` / `expected_paragraph_ids` 는 Phase 4e 적재 후 채워짐 (점수 평가용).

```jsonl
{"query_id": "ISQM-MG-A1", "query_text": "회계법인 대표자가 품질관리기준에 따른 업무 설계와 운영에 대해 어떤 책임을 지는가?", "category": "A", "expected_section": "requirements", "expected_paragraph_id_hints": ["18", "한18-1"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-A2", "query_text": "회계법인 최고경영자 또는 사원총회로부터 품질관리시스템 운영책임을 부여받은 사람의 적합성 요건은?", "category": "A", "expected_section": "requirements", "expected_paragraph_id_hints": ["19"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-A3", "query_text": "품질이 업무수행의 핵심이라는 내부문화를 촉진하기 위한 정책과 절차", "category": "A", "expected_section": "requirements", "expected_paragraph_id_hints": ["18"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-A4", "query_text": "품질관리시스템 설계 시 최고 감사파트너의 책임 범위", "category": "A", "expected_section": "requirements", "expected_paragraph_id_hints": ["18", "19", "한18-1"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-A5", "query_text": "회계법인 내 리더십 책임의 예시 (요구사항 + 적용지침)", "category": "A", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["18", "19", "A4", "A5"], "lang_mix": "ko"}

{"query_id": "ISQM-MG-B1", "query_text": "독립성 요구사항을 구성원에게 전달하고 준수를 확인하는 절차", "category": "B", "expected_section": "requirements", "expected_paragraph_id_hints": ["21", "22", "23"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-B2", "query_text": "장기간 동일 인증업무 참여 시 발생하는 유착위협 수용 가능 수준 경감을 위한 정책", "category": "B", "expected_section": "requirements", "expected_paragraph_id_hints": ["25", "한25-1"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-B3", "query_text": "의뢰인 관계 및 특정 업무를 수용·유지할지 판단할 때 고려해야 할 사항", "category": "B", "expected_section": "requirements", "expected_paragraph_id_hints": ["26", "27", "28"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-B4", "query_text": "ISQM 1 에서 요구하는 품질목적의 설정 절차", "category": "B", "expected_section_any": ["requirements", "purpose"], "expected_paragraph_id_hints": ["11", "16"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-B5", "query_text": "업무의 수용과 유지에 대한 정보 입수 후 조기에 알았더라면 거절했을 정보 대응", "category": "B", "expected_section": "requirements", "expected_paragraph_id_hints": ["28"], "lang_mix": "ko"}

{"query_id": "ISQM-MG-C1", "query_text": "연도별 모니터링 활동의 평가 및 보고", "category": "C", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["48", "49", "50"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-C2", "query_text": "품질관리시스템 모니터링을 통해 발견된 결함을 어떻게 평가하는가?", "category": "C", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["48", "51", "52"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-C3", "query_text": "품질관리시스템 문서화 요구사항의 최소 범위", "category": "C", "expected_section": "requirements", "expected_paragraph_id_hints": ["57"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-C4", "query_text": "불만 및 제보 처리 정책과 절차의 핵심 요소", "category": "C", "expected_section": "requirements", "expected_paragraph_id_hints": ["55", "56"], "lang_mix": "ko"}

{"query_id": "ISQM-MG-D1", "query_text": "업무팀 배정 시 업무수행이사 성명과 역할을 의뢰인 주요 경영자에게 커뮤니케이션", "category": "D", "expected_section": "requirements", "expected_paragraph_id_hints": ["30"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-D2", "query_text": "업무팀 구성원의 전문직 기준과 법규 요구사항 준수 역량 평가", "category": "D", "expected_section": "requirements", "expected_paragraph_id_hints": ["29", "31"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-D3", "query_text": "감사참여팀 품질관리의 핵심요소", "category": "D", "expected_section_any": ["requirements"], "expected_paragraph_id_hints": ["29", "30", "31", "32"], "lang_mix": "ko"}
{"query_id": "ISQM-MG-D4", "query_text": "업무품질관리검토자 (EQCR) 지정 대상 업무와 책임", "category": "D", "expected_section": "requirements", "expected_paragraph_id_hints": ["35", "36", "37", "38"], "lang_mix": "ko-en"}

{"query_id": "ISQM-MG-E1", "query_text": "engagement quality review 와 EQCR 의 차이", "category": "E", "expected_section": "requirements", "expected_paragraph_id_hints": ["35", "36"], "lang_mix": "ko-en"}
{"query_id": "ISQM-MG-E2", "query_text": "ISQM 1 의 monitoring and remediation process 와 한국 감사실무의 모니터링 절차", "category": "E", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["48", "49", "50", "51"], "lang_mix": "ko-en"}
{"query_id": "ISQM-MG-E3", "query_text": "network firm 이 제공하는 resources 를 품질관리시스템에 통합할 때 고려사항", "category": "E", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["29", "A32"], "lang_mix": "ko-en"}
{"query_id": "ISQM-MG-E4", "query_text": "reasonable assurance 관점에서 품질관리시스템의 설계 목적", "category": "E", "expected_section": "purpose", "expected_paragraph_id_hints": ["11"], "lang_mix": "ko-en"}
{"query_id": "ISQM-MG-E5", "query_text": "engagement partner responsibilities 관련 ISQM 1 요구사항과 적용지침의 매핑", "category": "E", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["18", "19", "A3", "A4"], "lang_mix": "ko-en"}

{"query_id": "ISQM-MG-B6", "query_text": "보고서일의 정의 — ISQM-1 용어의 정의 항목", "category": "B", "expected_section": "definitions", "expected_paragraph_id_hints": ["12"], "lang_mix": "ko", "_note": "Critic §5 scope creep 반영 — F1 → B6 재배치 (용어 이해 영역)"}
{"query_id": "ISQM-MG-B7", "query_text": "구성원 (관여자) 의 정의와 외부 전문가 포함 여부", "category": "B", "expected_section": "definitions", "expected_paragraph_id_hints": ["12"], "lang_mix": "ko-en", "_note": "Critic §5 scope creep 반영 — F2 → B7 재배치"}

# Critic §5.3 single-author bias 대응 추가 seed (Critic 제안):
{"query_id": "ISQM-MG-B8", "query_text": "감사인의 독립성 위반 (self-review threat) 이 발견되었을 때 품질관리시스템상 후속 절차", "category": "B", "expected_section_any": ["requirements", "application"], "expected_paragraph_id_hints": ["21", "22", "23", "24"], "lang_mix": "ko-en", "_note": "Critic §5.3 cross-check 제안 seed — self-review threat IAASB 핵심 용어"}
```

**note**: `expected_paragraph_id_hints` 는 pre-draft 예상치 — Phase 4e 적재 후 실제 Recall@5 계산 시 **`expected_chunk_ids`** 필드로 cp4 진입 시점에 대체 (Domain Reviewer 작업). 현 버전은 seed pool 의 **pool-level pre-draft** 만.

### 9.3 카테고리 E (한/영 혼재) 설계 의도 재확인

`docs/checkpoint_4_prep.md §3.3` 및 Plan v2 §7 에 따라 **필수 n ≥ 3 고정**. 5건 pre-draft 에서 Task #10 에서 3~5건 선별 가능. E1/E2 는 IAASB 영문 용어 (EQCR / monitoring / remediation) 와 KICPA 번역 용어 혼재 시나리오. E4/E5 는 ISQM 핵심 용어 (reasonable assurance / engagement partner) 의 영한 매핑.

### 9.4 n 확장 방침

Plan v2 §7 + `docs/checkpoint_4_prep.md §3` 안 A/B/C 중 **안 C (n=10 + 이중조건 판정) 기본**:
- 초기 10건 선정: A1, A2, B1, B2, C1, C2, D1, D2, E1, E2 (각 카테고리 상위 2건)
- CONDITIONAL 영역 진입 시 +10건 (A3-A5, B3-B5, C3-C4 = 10건) → n=20
- n=15 상향 안 B 채택 시: 초기 15건 (위 10 + E3, E4, E5, A3, B3)

---

## 10. Dependency on docx_reader.py 확장

Phase 4b parser-implementer 필수 작업:

1. **`docx_reader.iter_body_blocks`** recursive descent mode 활성화 (§6.1, 3 DOCX 공통)
2. **`spec.body_parser` dispatcher** — `"isqm_table"` 값이면 `ISQMTableBodyParser` 호출, 기본값은 현 Phase 1 통합 파서
3. **`ISQMTableBodyParser`** (신규) — §2.3 pseudocode 구현. `NumberingEngine` 대신 cell text 기반 paragraph_id 추출.
4. **section heading set**: `ISQM_SECTIONS`, `ISQM_SUBSECTIONS` 상수 목록 (본 §2.4 참조)
5. **`_extract_sub_id` helper** — col[1] 하위 `<w:p>` 의 `^\s*\([a-z가-힣ivx]+\)` prefix 추출

---

*End of `docs/isqm_structure_profile.md` v1 — Phase 4a Scout 산출. ISQM 고유 `ISQMTableBodyParser` 와 Mini Golden seed pool 25건 포함.*
