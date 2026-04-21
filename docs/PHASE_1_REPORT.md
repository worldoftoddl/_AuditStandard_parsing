# Phase 1 완료 보고서 — docx → Structured Markdown

**기간**: 2026-04-20 ~ 2026-04-21
**판정**: ✅ CHECKPOINT 1 PASS + Phase 1.5 HIGH 이슈 전원 해결
**팀**: `audit-parser-phase1` (Agent Teams, in-process)

---

## 1. 개요

`raw/0. 회계감사기준 전문(2025 개정).docx` (1.6MB, ISA 36 기준서) 를 Qdrant-ready YAML frontmatter + HTML 주석 형식의 Structured Markdown 으로 변환하는 파이프라인 Stage 1 완성. `_IFRS_parsing` 2-stage 설계를 계승하되 (1) DOCX `word/numbering.xml` 자동넘버링 replay (IFRS 는 본문 내 번호 텍스트 존재), (2) 파일별 별도 Qdrant collection 네이밍 규약, (3) docx→md→json→Qdrant 4단계 명시화의 3가지 차별 요소 구현.

---

## 2. 팀 구성 및 협업 방식

| 역할 | 이름 | 소유 범위 | 권한 모드 |
|---|---|---|---|
| Leader | team-lead (main session) | 전체 조율 | default |
| Implementer | parser-implementer → parser-implementer-2 | `src/audit_parser/**`, `pyproject.toml`, `tests/test_*.py` | plan → **bypassPermissions** (재소환) |
| Domain Reviewer | audit-standard-domain-reviewer | `docs/**`, `tests/fixtures/**` | default |
| Critic | devils-advocate-critic | `docs/devils_advocate_checkpoint_1.md` | read-only |

Phase 0 방식과 동일한 4인 팀. Task #2 완료 직후 Implementer 를 `bypassPermissions` 모드로 재소환(`parser-implementer-2`) 하여 Task #3~ 권한 프롬프트 마찰 제거.

---

## 3. 구현 산출물

### 3.1 코드

| 파일 | LOC | 역할 |
|---|---:|---|
| `src/audit_parser/ir/types.py` | 128 | `RawBlock`·`Block` frozen dataclass + `BlockKind`·`Section` StrEnum |
| `src/audit_parser/ir/docx_reader.py` | 300 | `iter_body` — `w:p`/`w:tbl` 순회, styleId→display name 해석 |
| `src/audit_parser/ir/numbering.py` | 648 | `parse_numbering_xml` + `NumberingEngine.advance()` 동적 카운터, abstractNumId 공유 대응 |
| `src/audit_parser/ir/structure.py` | 282 | PRE_TOC→TOC→STANDARD_BODY 상태머신, section 매핑, heading_trail, 1×1 BLOCK_QUOTE 승격 |
| `src/audit_parser/ir/styles.py` | 197 | `word/styles.xml` 파싱 + `basedOn` 체인 재귀 순회 |
| `src/audit_parser/ir/_xml.py` | 36 | 하드닝된 lxml 파서 공통화 (XXE 방어) |
| `src/audit_parser/convert/md_renderer.py` | 358 | YAML frontmatter + HTML 주석 렌더러 |
| `src/audit_parser/cli.py` | 57 | Typer CLI — `convert`, `ingest` stub |
| **합계** | **2,006** | |

### 3.2 문서

| 파일 | LOC | 작성자 |
|---|---:|---|
| `docs/numbering_strategy.md` | 713 | Domain Reviewer — 동적 fallback 설계 + §10 abstractNumId-scoped 실구현 pseudocode |
| `docs/checkpoint_1_review.md` | 665 | Domain Reviewer — CHECKPOINT 1 검수 + R6 최종 PASS 섹션 |
| `docs/devils_advocate_checkpoint_1.md` | 376 | Critic — Phase 1 비판 11건 + CONDITIONAL GO |
| `docs/f4_known_duplicates.md` | 179 | Domain Reviewer — F4 잔존 6 쌍 전수 enumeration + Phase 2 composite key 제안 |

### 3.3 테스트

| 파일 | 케이스 수 | 대상 |
|---|---:|---|
| `tests/test_numbering.py` | 34 | parse_numbering_xml, NumberingEngine, format_counter, base-26 |
| `tests/test_structure.py` | 15 | 상태머신, section 매핑, BLOCK_QUOTE 승격, 보론 regex |
| `tests/test_md_renderer.py` | 24 | R1~R18 단위, F1~F3 I/O, C1~C2 CLI, E2E |
| `tests/test_styles.py` | 14 | styles.xml 파싱, basedOn 체인, cycle/depth 가드 |
| `tests/test_xml_safe.py` | 9 | XXE / billion laughs / external DTD |
| `tests/fixtures/style_numpr_cases.json` | — | F1 style 상속 회귀 |
| `tests/fixtures/shared_abstract_counter_cases.json` | — | F4 abstractNumId 공유 회귀 |
| `tests/fixtures/isa_profile_samples.json` | — | Phase 0 numbering 샘플 (재사용) |
| **합계** | **101 cases** | — |

---

## 4. CHECKPOINT 1 검수 경과

### 4.1 최초 검수 → FAIL (2026-04-20)

Domain Reviewer 20-샘플 대조. 20개 중 12 pass / 7 fail / 1 partial. 근본 원인 3건 규명:

| ID | 심각도 | 내용 |
|---|---|---|
| F1 | **CRITICAL** | `numbering.py` 가 문단 직접 `<w:numPr>` 만 읽고 `word/styles.xml` style-level numPr 상속(체인 `basedOn`) 무시 — 820+ 문단 `paragraph_body` 오분류 |
| F2 | HIGH | ISA-1200 custom heading 2 9개 section enum 미매핑 — 기준서 전체 intro 축약 |
| F3 | MED | An → n parent 링크 끊김 (F1 의존) |

정량 영향: ISA-200 req 24 + app 82 = 106 손실, ISA-1200 req 152 전량 손실, ISA-500 app 64 손실 등 12 ISA 합 **820+ 문단**.

### 4.2 1차 rework → PARTIAL_PASS → F4 발견

`src/audit_parser/ir/styles.py` 신규 + `docx_reader.py` 에 styleId→basedOn 재귀 상속 주입. F1/F2/F3 모두 해결. 그러나 F1 수정으로 숨어 있던 **F4 (abstractNumId 카운터 공유 미구현)** 표면화.

| ID | 심각도 | 증거 |
|---|---|---|
| F4 | **CRITICAL** | 서로 다른 `w:num` 이 동일 `w:abstractNumId` 공유 (예: numId 57/105 → abstract 51). numId 별 독립 카운터로 A1 중복 93 종 발생. ISA-200 TOC `적용 A1-A83` 단일 연속 스트림 명세 위반 |

### 4.3 2차 rework → CHECKPOINT 1 PASS

abstractNumId-scoped 카운터로 전환. `reset()` 시 `override_applied` set 도 초기화. 동시에 F5 (ISA-1200 보론 heading 2 `^보론\s*\d+\b` regex 매칭) 통합 처리. 최종 실측:

| 지표 | 값 | 기준 |
|---|---:|---|
| total blocks | 11,267 | — |
| ISA 경계 탐지 | 36/36 | 200..1200 완전 집합 |
| BLOCK_QUOTE 승격 | 58 | profile §4.2 실측 58 **정확 일치** |
| TABLE 유지 | 16 | profile §4.1 ≈16 **정확 일치** |
| is_toc 블록 | 761 | profile §6.1 764 ± 3 |
| `section: appendix` | 43 (ISA-1200 2 포함) | — |
| unknown_numbering | 6 / 11267 = **0.053%** | 임계 5% |
| ISA-550 numId=86 독립 reset | first REQ = `1.` | 회귀 가드 |
| top-level duplicate markers | 93 → **6 쌍(12건)** | Phase 2 composite key 이월 |
| 오탐(`보론적`/`보론자` 등) | 0 | word boundary `\b` 정상 |

**Go/No-Go**: GO.

---

## 5. Phase 1.5 — Devil's Advocate HIGH 이슈 fix

Critic 비판 11건 중 Phase 2 진입 전 필수 fix 판정:

### 5.1 C1 — lxml XXE/entity-expansion 방어 (Task #11)

`src/audit_parser/ir/_xml.py` 신규. 하드닝 파서 공통화:

```python
_SECURE_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True,
    huge_tree=False, load_dtd=False, dtd_validation=False,
)
```

`docx_reader.py`·`numbering.py`·`styles.py` 3 모듈 모든 XML 로딩 경로가 `safe_fromstring`/`safe_parse` 경유. 방어 커버리지:

- External entity (`file:///etc/passwd`) — 거부
- Billion laughs (exponential expansion) — 거부
- External DTD network fetch — 거부
- `parse_numbering_xml`/`parse_styles_xml` 경유 XXE — 거부
- 정상 benign XML — 통과

의존성 추가 없음 (`defusedxml` 미도입 — lxml 자체 옵션으로 충분).

### 5.2 C2 — numbering base-26 letter (Task #12)

`numbering.py::format_counter` 의 lowerLetter/upperLetter 27 이상 숫자 fallback → bijective base-26 `_to_alpha_base26`:

| value | result |
|---:|---|
| 1 | `a` |
| 26 | `z` |
| 27 | `aa` |
| 52 | `az` |
| 53 | `ba` |
| 702 | `zz` |
| 703 | `aaa` |
| 704 | `aab` |

현 ISA 는 27+ 미발생이나 Phase 2 파이프라인이 ISQM 1 / 인증업무개념체계에 적용될 때 트리거 가능성 제거.

### 5.3 C4 — F4 잔존 duplicates docs 기록 + strategy 동기화 (Task #13)

- `docs/numbering_strategy.md` §4.1 에 `⚠️ DEPRECATED` 배너, §10 abstractNumId-scoped 실구현 pseudocode 병기 (advance/reset/override guard)
- `docs/f4_known_duplicates.md` 신규 — **실측 재스캔 결과 3 건 → 6 쌍(12건) 로 정정**:

| standard | paragraph_id |
|---|---|
| ISA-250 | `12.` |
| ISA-260 | `5.` |
| ISA-260 | `6.` |
| ISA-300 | `7.` |
| ISA-300 | `10.` |
| ISA-701 | `4.` |

Phase 2 composite key 제안: `(standard_no, section, sha1(heading_trail)[:8], paragraph_id)`. `md_parser`·`chunk_splitter`·`qdrant_writer` 필독 체크리스트 §5 에 명문화.

---

## 6. 최종 품질 지표

| 항목 | 값 |
|---|---:|
| pytest | **101 / 101 green** |
| ruff check | clean |
| mypy --strict | clean (12 source files, `Any` 0건) |
| `output/md/*.md` | 37 파일 (`00_전문.md` + ISA-200..1200 36개) |
| 총 MD 라인 수 | 34,569 |
| ISA 본문 평균 | 872 라인 (최소 221 ISA-520 / 최대 3,546 ISA-315) |
| schema_version | `"1.0"` (37 파일 전수) |

---

## 7. Phase 2 로 이월되는 이슈

### 7.1 Devil's Advocate MED 3건 — Phase 2 설계 시 명시 결정

| ID | 내용 | 제안 |
|---|---|---|
| C4 | F4 잔존 6 쌍 unique key | composite key `(standard_no, section, sha1(heading_trail)[:8], paragraph_id)` |
| C5 | `Section.APPENDIX` 단일 enum — 보론 1/2/3 payload 필터 불가 | `appendix_index: int | None` 필드 추가 |
| C7 | UNKNOWN 5% 임계 CLI 자동 fail 부재 | `convert` 종료 시 강제 exit code |

### 7.2 MED 4건 + LOW 2건 — Phase 2 진행 중 점진 개선

- **C3** descent ilvl skip 시 `(0)` silent corruption
- **C6** `_xml_para_text` 가 `w:hyperlink`/`w:smartTag` nested run 손실
- **C8** `schema_version="1.0"` MD/JSON 의미 공유 → 한쪽 bump 시 호환성 정책
- **C9** `_resolve_style_chain` depth/cycle silent None
- **C10** 1×1 표 BLOCK_QUOTE 승격이 cell 개수만 검사 — shading 휴리스틱 부재
- **C11** HTML 주석 `|` pipe 직렬화 fragility

---

## 8. Phase 2 팀 소환 시 브리핑 필수 항목

1. `docs/checkpoint_1_review.md` §R6 — CHECKPOINT 1 PASS 근거 전수
2. `docs/f4_known_duplicates.md` — 6 쌍 duplicate + composite key 제안
3. `docs/numbering_strategy.md` §10 — abstractNumId-scoped 실구현 pseudocode (strategy 문서와 implementation diverge 방지)
4. `docs/devils_advocate_checkpoint_1.md` — MED 3건(C4/C5/C7) 우선 처리, 기타 백로그
5. `output/md/` 실제 37 파일 구조 — HTML 주석 메타(`<!-- para, kind, section, authority, idx -->`) 파싱 규격 확정 필요

---

## 9. 커밋 대상 파일

### 신규
- `docs/PHASE_1_REPORT.md` (본 문서)
- `docs/numbering_strategy.md`
- `docs/checkpoint_1_review.md`
- `docs/devils_advocate_checkpoint_1.md`
- `docs/f4_known_duplicates.md`
- `src/audit_parser/ir/{_xml,docx_reader,numbering,structure,styles,types}.py`
- `src/audit_parser/py.typed` (mypy marker)
- `src/audit_parser/convert/md_renderer.py`
- `tests/test_{numbering,structure,md_renderer,styles,xml_safe}.py`
- `tests/fixtures/{style_numpr_cases,shared_abstract_counter_cases}.json`

### 수정
- `docs/isa_structure_profile.md` — R6 연동 업데이트
- `pyproject.toml` — `lxml-stubs` dev 의존성
- `src/audit_parser/cli.py` — convert stub → 실구현
- `src/audit_parser/{convert,ir}/__init__.py` — public re-export

### 제외 (gitignore)
- `raw/` — 원본 DOCX
- `output/md/` — 파이프라인 산출물
- `tmp/` — Phase 0 Domain Reviewer scratch
- `.env` — API 키
- `.claude/` — 팀·세션 상태

---

## 10. 다음 Phase

**Phase 2 — Stage 2a: MD → JSON**. PLAN.md §4 Phase 2 에 정의. 착수 전 준비:

1. 현 Phase 1 팀 정리 (`TeamDelete` 예정, 본 커밋 후 사용자 승인 시점)
2. Phase 2 신규 팀 소환 — parser-implementer-2(Phase 2), audit-standard-domain-reviewer, devils-advocate-critic
3. Phase 2 브리핑에 §8 항목 모두 포함
