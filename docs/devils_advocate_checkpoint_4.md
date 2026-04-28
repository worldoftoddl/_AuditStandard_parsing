# Devil's Advocate — CHECKPOINT 4 비판 보고서 (WIP)

> **작성자**: `devils-advocate-critic` (read-only on `audit-parser-phase4`; writable file 1건: 본 문서)
> **작성일**: 2026-04-22 (scaffold) — Phase 4f 완료 시 최종화 예정
> **대상 산출물**: Phase 4 (StandardSpec + 3 DOCX → 3 Qdrant collection 일반화) 설계·구현·검수
> **참조 산출물** (현 시점 기준):
> - `docs/phase_4_plan.md` v2 (승인 대기 → 착수; 사용자 4조건 반영)
> - `PLAN.md §4 Phase 4, §5 리스크`
> - `docs/devils_advocate_checkpoint_{0,1,2,3}.md` (선행 Critic 보고서)
> - `docs/PHASE_3_REPORT.md`, `docs/json_schema.md v1.1.2`
> - `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` (88 KB)
> - `raw/역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문(개정개요 포함).docx` (383 KB)
> - `raw/인증업무개념체계(2022년 개정)_전문.docx` (347 KB)
>
> **상태**: Phase 4 **Pre-Kickoff 단계** 진행 중. 본 문서는 **scaffold (v0)** — Phase 4b~4e 완료 및 Mini Golden 실측 후 실수치로 보강. 현재 섹션들은 Plan v2 문서상 수치·가정 기반 선공격. **Phase 3 CP3 Critic scaffold 와 동일 프로토콜** 준수 — Pre-Kickoff 에서 scaffold 존재, Phase 4f 실측 후 v1 최종화.
>
> **팀-lead 승인 기록 (2026-04-22)**:
> - 4 pre-emptive DM 승인 — #7 (parser-implementer rollback) / #8 (Domain Reviewer unknown 임계) / #9 (Domain Reviewer drift 연환산) 즉시 DM 진행; #3 (Mini Golden 통계) 은 **3안 비교 제안 형식** 으로 Domain Reviewer 에 별도 DM + CP4 에서 최종 판정
> - Critic scaffold 의 Pre-Kickoff 단계 존재 명기 완료
> - Domain Reviewer PK-3 Prep 6-item 과 교차 참조 확보 (§14 Cross-Reference 인덱스 참조)

---

## 0a. Phase 4f Final Addendum (2026-04-28)

Phase 4b~4f 실측 후 최종 판정:

| 항목 | 실측 | Critic 판정 |
|---|---:|---|
| 4 collection point-count invariant | 10,387 / 10,387 | ✅ PASS |
| Payload index baseline | 12 / 12 fields | ✅ PASS |
| ISQM Mini Golden Recall@5 | 1.000000 | ✅ PASS |
| ISQM Mini Golden MRR@10 | 0.677083 | ✅ PASS |
| `ko_en` Recall@5 | 1.000000 | ✅ PASS |
| C-P2-1 realized annual invalidation | 0.0% | ✅ No trigger |
| Non-ISA-1200 split census | 0 additional split chunks | ✅ No §9.5 bump |

**Go/No-Go**: **GO to Phase 5**. Phase 4의 핵심 리스크였던 multi-standard
ingest, Qdrant schema parity, Mini Golden 한/영 혼재 검색은 통과했다.

남은 비판 사항:

1. ISQM/ASSR `section=null` 100%는 검색 품질을 막지는 않았지만 metadata filter
   precision을 제한한다. Phase 5 개선 후보로 남긴다.
2. `audit_standards_qdrant` 컨테이너는 실행 중이지만 compose 소유가 아니므로 Backup/DR
   작업 전에 운영 정리가 필요하다.
3. C-P2-1은 Phase 4 window에서 source DOCX revision이 없어 realized drift가 0%다.
   새 원본 개정이 발생하면 같은 공식을 재적용해야 한다.

근거 산출물:

- `docs/checkpoint_4_review.md`
- `docs/PHASE_4_REPORT.md`
- `tests/fixtures/isqm_mini_golden_dataset.jsonl`
- `scripts/phase4f_eval.py`
- `output/phase4_mini_golden_results.json` (gitignored)
- `output/phase4_search_smoke_results.json` (gitignored)

---

## 0. Executive Summary (Phase 4f final)

| 항목 | 최종 판정 | 비고 |
|---|---|---|
| Phase 5 진입 Go/No-Go | **GO** | 4b~4f 완료 + Mini Golden 통과 |
| Plan v2 구조적 수용 | ✅ 대부분 수용 | v1 대비 HNSW/Backup Phase 5 이월 등 4조건 반영됨 — 재반박 금지 |
| 남은 공격면 | 3건 | §0a final addendum |
| 블로커 수 | 0건 (HIGH) / 2건 (MED) | Phase 5 개선 후보 |

---

## 1. Plan v2 수용 사항 (재반박 금지 목록)

Plan v2 는 v1 대비 다음 4조건 수정 완료. Critic 재반박 금지, 추적만.

1. ✅ C-P2-8 sha1[:12] 확장 **폐기** (premature optimization)
2. ✅ HNSW externalize / Backup/DR **Phase 5 이월**
3. ✅ C-P3-D4 chunk_id regex **Pre-Kickoff (PK-2)** 로 승격
4. ✅ ISQM 한/영 혼재 분리 여부 **측정 기반 판정** (Mini Golden)

### 1.1 Pre-Kickoff 4 task 교차 참조

| PK-# | 담당 | Critic scaffold 연계 |
|---|---|---|
| PK-1 §0.3 Freeze Point | Domain Reviewer | `docs/checkpoint_4_prep.md §0.3` — ISQM 2 scope 명시 (§10) 와 연결 |
| PK-2 chunk_id regex 3자 합의 | Domain Reviewer + Implementer + **Critic** | `docs/checkpoint_4_prep.md §1` — Critic 3-axis 리스크 (하위 호환성 / Phase 5 backtracking / variant 간섭) 제출 예정 |
| PK-3 Prep 6-item | Domain Reviewer | `docs/checkpoint_4_prep.md §0` — 본 scaffold §4 (Mini Golden 통계), §8 (drift 연환산), §9 (unknown 임계) 제안 반영 요청 |
| PK-4 3 DOCX pre-scan | Domain Reviewer | `docs/checkpoint_4_prep.md §2` — 본 scaffold §9 (5% 임계 이중 gate) 반영 요청 |

---

## 1a. PK-2 chunk_id regex 3자 합의 — Critic empirical cross-check (2026-04-22)

Domain Reviewer `docs/checkpoint_4_prep.md §1` Draft A 에 대한 Critic 독립 실측 cross-check:

### 1a.1 Draft A regex

```regex
standard_id: ^(ISA-\d{3,4}|ISQM-\d|ASSR-\d{3,4}|FRMK)$
chunk_id   : ^(ISA-\d{3,4}|ISQM-\d|ASSR-\d{3,4}|FRMK):[a-z_]+:[0-9a-f]{8}:[^#\s:]+(#\d+(#\d+)?)?$
```

### 1a.2 실측 결과 (Python `.venv/bin/python` + regex, 2026-04-22)

| 축 | 결과 | 판정 |
|---|---|---|
| `standard_id` backward compat (36 ISA) | **36 / 36** 전수 PASS | ✅ |
| `chunk_id` backward compat (8,590 chunks) | **8,590 / 8,590** 전수 PASS | ✅ |
| `#` suffix depth 분포 | 0: 4,209 (48.9%) / 1: 4,379 (50.9%) / **2: 2 (0.02%)** / 3: 0 | ⚠ 2-level 제약 §1a.4 β |
| Adversarial 19 tests | 19 / 19 expected match (positive 8 / negative 11) | ✅ |

**결론**: Draft A 는 v1.1.2 → v1.2.0 전이에서 36 ISA / 8,590 chunk_id / embedding 전부 불변 유지 (byte-level diff 는 `schema_version` 필드 36곳만). Reviewer §1.3.3 주장 backward-compat MINOR 성립 empirical 확정.

### 1a.3 narrow 수정 제안 α — ISQM 미래 방어

Draft A: `ISQM-\d` → ISQM-1/2 만 수용, **ISQM-10+ 거부**. Phase 5 에서 IAASB 가 ISQM 10+ 발표 시 v1.3 MINOR bump 필요.

**제안 α**: `ISQM-\d` → `ISQM-\d{1,2}` — 비용 0 (현 36 ISA 및 적재 data 영향 없음). ISQM-99 까지 regex 수용.

- **Critic 선호**: α 채택
- **대안**: Draft A 원안 유지 (β') — scope 축소 원칙 부합, 미래 1회 bump 수용

### 1a.4 narrow 수정 제안 β — suffix chain 2-level 제약

현 `(#\d+(#\d+)?)?` 는 **최대 2-level `#` chain**. 실측 depth 2 는 ISA-1200 §9.4 table split 2 건. Phase 4 §9.5 추가 split (ISA-540 등) 중 3-level 필요 시나리오 발생 가능.

**옵션 β-1** (권고): 2-level 유지 + `docs/json_schema.md §9.4` 에 "max 2-level" 명문 제약 + chunk_splitter assert
**옵션 β-2**: `(#\d+){0,3}` 로 3-level 확장 (future-proof)
**옵션 β-3** (기각): `(#[0-9a-f]+)*` unbounded — 책임 전가 과다

### 1a.5 Domain Reviewer 추가 제안 수용

- **Draft A 채택** — Critic 지지 (36/36 + 8590/8590)
- **Draft B 거부** — false-positive (`ASSR` / `ISQM` 단독) 유발 위험
- **FRMK-only 원칙** — 지지 (IAASB 공식 준용)
- **ISQM 2 Phase 5 이월** — 지지 (Draft A + α 가 flex 유지)
- **PK-4 classify_kind 확장** (Reviewer §2.2.2) — 지지 + §3 v1.2 atomicity 5-6번째 편입 + SUB_ITEM ilvl=0 회귀 검증 요청

### 1a.6 3자 합의 종결 (2026-04-22, Task #2 completed)

**최종 regex** (Domain Reviewer prep §1.3.4, 3자 합의 완료):
```regex
standard.standard_id : ^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)$
standard.standard_no : ^\d{1,4}$  (relax — ISQM-1 의 standard_no=1 수용)
```

| 주체 | 최종 상태 |
|---|---|
| Domain Reviewer | ✅ Draft A 채택 + α 수용 + β 조건부 수용, §1.7 3축 리스크 반영 |
| Parser Implementer | ✅ Part A.2 α 독립 제안 (수렴) + Part B re-design (Issue 1-3 해소) |
| Critic (나) | ✅ Draft A 원안 전면 승인 — α 는 parser-implementer + team-lead 수용으로 잔존, β 는 chunk_splitter assert guard 로 수렴 (§9.4 boilerplate optional) |

**α (`ISQM-\d{1,2}`) 철회 처리**:
- Critic 원 철회 판단 유지하되, parser-implementer Part A.2 독립 제안 + team-lead 승인으로 **최종안에 잔존**. non-blocking.
- 구현 시점 parser-implementer 재량 — 현재 실측 영향 0 (ISA 36 + ISQM-1 만 있음).

**β (suffix chain 2-level 제약) 조건부 수용**:
- `json_schema §9.4` boilerplate 추가는 **optional** (parser-implementer 재량)
- `chunk_splitter.py` 2-level assertion guard 는 **v1.2 atomicity #5 필수**

**FRMK 규약 변경 (harmonization)**:
- Draft A 원안: 바리 `FRMK` (no digit)
- 최종 합의: `FRMK-\d` (요구 digit)
- 의미: FRMK document standard_id = **`FRMK-1`** (바리 `FRMK` 아님)
- 근거: 4 spec 간 prefix-digit pattern 균일화 (ISA-200 / ISQM-1 / ASSR-3000 / FRMK-1)
- 영향: 현재 적재 data 0 (FRMK document 는 Phase 4c 에서 신규 생성)

v1.2 atomicity 는 **6-file (PROLOGUE_SECTION 삭제, chunk_splitter guard 추가)** 으로 재구성. §3 최신 구성 참조. 실측 수치:
- 36/36 `standard_id` + `standard_no` backward compat (final regex 포함 재검증 PASS)
- 8,590/8,590 `chunk_id` backward compat
- `#` suffix depth 0: 48.9% / 1: 50.9% / 2: 0.02% (2건) / 3: 0

---

## 1b. Phase 4a Scout cross-check 합의 종결 (2026-04-22)

Domain Reviewer 7-area pushback 전수 수용 + 2 MED / 1 HIGH 재협의 완료. 종합 합의표:

| 영역 | Critic 판정 | 최종 합의 |
|---|---|---|
| 1. ISQM-1 `ISQMTableBodyParser` | 설계 PASS + 예산 **HIGH** | **4b 분할 지지** (Reviewer 동조, team-lead 판정 대기) |
| 1.4 ISQM chunk_id stability | LOW | CP4 drift 측정 시 **ISQM 분리 집계** 수용 |
| 2. ASSR state machine | 승인 | "품질관리" marker 아님 §2.3 주석 추가 예정 |
| 3. FRMK heading_range_strip | 조건부 승인 | `^([^0-9]+?)(\d+(?:-\d+)?)\s*$` 강화 + `.strip().startswith("보론")` + 연도 suffix Phase 5 재검토 플래그 |
| 4. Un-numbered 보론 | 반대 | **대안 B-v2 확정 채택** (§11 참조) |
| 5. Mini Golden F 카테고리 | MED scope creep | **F 폐기** + B 재배치 7건 + Critic B8 추가 + single-author bias slot 3건 (§4.3 참조) |
| 6. fallback_extension | 승인 | 변경 없음 |
| 7. 24 backward_compat test cases | PASS | 변경 없음 |

### 1b.1 Phase 4b 분할 방향 (team-lead 판정 대기)

Reviewer 가 Critic 옵션 (c) 에 동조:
- **Phase 4b-1 (30-40k)**: StandardSpec + 4 spec dataclass + ISA shim + ISQM spec + **ISQMTableBodyParser**
- **Phase 4b-2 (20-30k)**: ASSR/FRMK spec 구현 + recursive descent + v1.2 atomicity commit

옵션 (a) 예산 상향 50-70k 는 team-lead 결정 대기. 옵션 (b) fallback 은 (c) 채택 시 불필요.

### 1b.2 rework budget 사용 내역

- Critic 측 pushback 중 (x) premise 오인 1건 철회 (§12.5 기록) — rework budget 0/2 사용
- 대안 B-v2 제안 수용으로 Reviewer 대안 C 철회 — Reviewer 측 rework budget 1/2 사용
- Critic 잔여 rework budget 2/2 보존 (CP4 최종 판정 시 사용 가능)

---

## 2. 비판 #1 (R2-a) — StandardSpec OCP + Phase 4b 분할 승인 (MED → RESOLVED scope)

**영역**: (design) StandardSpec 추상화 비용 폭증

### 2.0 Phase 4b 옵션 D 최종 승인 (2026-04-22)

team-lead 공식 승인 — **Critic 옵션 (c) 분할 제안 = 옵션 D 로 재명명 후 채택**. 3자 수렴 (Critic + Reviewer + parser-implementer) empirical 근거 기반:

| 항목 | 확정 |
|---|---|
| Phase 4 총 예산 | **150-200k** (Plan v1 허용 범위 회귀) |
| Phase 4b-1 (Task #6) | **25-30k** — StandardSpec foundation + ISA spec + v1.2 7-file atomicity |
| Phase 4b-2 (Task #11) | **25-35k** — 3 spec (ISQM/ASSR/FRMK) + TwoColumnTableBodyParser + docx_reader dispatcher |
| 합계 4b-1+4b-2 | **50-65k** — Critic 추정 65-96k midpoint 대비 하한 수렴 (parser-implementer 자가 재견적 55-70k 와 중첩) |
| Task 의존성 | Task #7 (Phase 4c) `blockedBy: [#6, #11]` 로 갱신 |

### 2.1 OCP 위배 우려 처리

Plan v2 §6.2 원안 4 spec 동시 구현 → 분할 승인으로 **4b-1 ISA spec 단독 foundation + 4b-2 3 spec 추가** 구조. OCP "Open for extension" 은 dispatch registry 패턴으로 흡수 가능 — 4b-1 foundation 에서 `StandardSpec.register(prefix)` 데코레이터 + `SPEC_REGISTRY: dict[str, StandardSpec]` 구조 적용 권고 (parser-implementer 재량). 

**Phase 5+ 확장 시 (ISSAI/ISRE 등)**: 신규 spec 파일 추가 + registry 등록 1줄 → dispatch 코드 수정 없음. OCP 준수.

### 2.2 4b-1 4-커밋 incremental 모니터링 (team-lead plan approval 2026-04-22)

team-lead 가 parser-implementer 4 커밋 incremental 구현 승인. Critic 커밋별 pre-emptive 모니터링 대상:

#### 커밋 1: Spec foundation (`standard_spec.py` + `isa_spec.py` + `SPEC_REGISTRY`)
- `StandardSpec.appendix_extractor` callable signature — 4b-2 3 spec 재사용 가능 여부 static check
- ISA default wrapper 가 기존 `_APPENDIX_RE` 로직과 **byte-level 동등** (structural diff)
- `register_spec` 데코레이터 idempotency (중복 등록 시 behavior)
- `SPEC_REGISTRY` race condition 대비 — import time vs runtime 등록 경계

#### 커밋 2: Types + schema bump + 36 JSON in-place replace
- 36 ISA JSON in-place replace 원자성 — 중간 실패 시 partial state 발생 시나리오
- `scripts/migrate_schema_v1_2.py --dry-run` 사전 검증 작동 확인
- **Domain Reviewer §7.2.1a pull-in 합류 시점** 정합성 (4-party timing)
- `schema_version` heterogeneous 검출 gate (`validate_json.py` drift check)
- `ChunkRecord.special_appendix_name: str | None = None` default 동작 — 기존 8,590 chunk 에 `null` 자동 주입 시 type 정합

#### 커밋 3: `md_parser.py` / `md_renderer.py` StandardSpec 주입형 리팩터
- `parse_markdown(..., spec=ISA_SPEC)` default kwarg — **기존 call sites 회귀 0** (test_md_parser.py 전수 통과)
- `test_isa_reparse_semantic_equivalence` 제외 필드 (`embedding`, `embedded_at`, `embedding_model`) 적정성 — 이 3 필드는 Phase 3 embedder 산출이지 md_parser scope 아님 → 제외 정당
- semantic equivalence assertion 에서 **chunk_id + paragraph_id + kind + heading_trail + content_text + heading_trail_hash** 6 필드 비교 권고
- Domain Reviewer prep §1.8 `test_standard_spec.py::test_standard_id_backward_compat` 24 test cases ingest 완료 여부

#### 커밋 4: `chunk_splitter.py` β-1 guard + `qdrant_writer.py` verify stub
- **β-1 2-level assertion guard** 가 기존 chunk_splitter 분할 로직 (§9.4 ISA-1200 66×2 등) 에 **영향 없음** 검증
- `verify=True` default 동작이 기존 테스트 깨지 않는지 (4b-1 은 재적재 없으므로 mock Qdrant count 만 트리거)
- `IngestIncompleteError` raise 경로 unit test 존재 여부
- depth 2 시도 시 AssertionError 발생 (positive test) + depth 0/1 시 silent pass (negative test)

### 2.3 4b-1 Exit gate 후 Critic 독립 cross-check (5-item)

parser-implementer Exit gate 검증 완료 DM 수신 시 즉각 실행:

| # | anchor / 수단 | 검증 대상 |
|---|---|---|
| 1 | **anchor 3건 (jq) 재실행** | parser-implementer 가 실행한 jq expression 을 Critic 환경에서 독립 재실행 — same-result 확인 |
| 2 | **`test_isa_chunk_id_bit_equal` 논리 검증** | set equality 의 충분성 — **순서 무관 bit-level 동등** 검증 방식이 CP2 §C-P2-1 drift detection 과 정합인지 |
| 3 | **`mypy --strict` + `ruff` 재확인** | clean / error 0 재측정 — Phase 3 baseline 유지 |
| 4 | **예산 실측 vs commit 기록 비교** | parser-implementer 3 중간 usage 보고 gate + 4-커밋 final 실소모 vs team-lead 25-30k 예산 |
| 5 | **7-file atomicity git 검증** | `git log -1 --stat` 으로 7 files (MODified 6 + NEW 1 + script) + 36 ISA JSON in-place replace 포함 확인 — 단일 commit 여부 (3-중간 커밋 후 squash or 단일 commit 인지 parser-implementer 규약 확인) |

**Critic 실행 방식**: Python 독립 script (jq 2차 검증용). Task #10 진입 이전 준비 완료.

### 2.4 4b-2 pre-emptive 모니터링 (team-lead 지시 재확인)

Phase 4b-2 진입 시:

- **TwoColumnTableBodyParser edge case 전수** (row 50~236): col[0] 빈 section heading row, 한글 paragraph_id (`한4-1`) 50+ 건, multi-paragraph cell sub-item, empty layout row 4종 edge case pytest 커버
- **docx_reader recursive descent 무한 재귀 방어**: `MAX_DESCENT_DEPTH = 10` 권고 (styles.py `_MAX_BASED_ON_DEPTH=10` 과 동일 보수 policy). 3 DOCX 실측 depth ≤ 3 확인 필요.
- **StandardSpec interface 재사용** — 4b-1 foundation 의 메서드가 4b-2 3 spec 에서 재정의 없이 사용 가능한지 static check (`SPEC_REGISTRY` 등록 순서 ISA > ISQM > ASSR > FRMK)

**Phase 4b-2 plan approval 수신 시 cross-check**.

### 2.3 4b-2 pre-emptive 리스크 모니터링 commitment (team-lead 지시)

- **TwoColumnTableBodyParser edge case 전수** (row 50~236): col[0] 빈 section heading row, 한글 paragraph_id (`한4-1`) 50+ 건, multi-paragraph cell sub-item, empty layout row
- **docx_reader recursive descent 무한 재귀 방어**: `MAX_DESCENT_DEPTH = 10` 권고 (styles.py `_MAX_BASED_ON_DEPTH=10` 과 동일 보수 policy). 3 DOCX 실측 depth ≤ 3 확인 필요.
- **StandardSpec interface 재사용 가능성** — 4b-2 3 spec 이 4b-1 foundation 의 공통 메서드를 재정의 없이 상속 가능한지 static check

**Phase 4b-2 plan approval 수신 시 cross-check**.

---

## 3. 비판 #2 (R3 심화) — v1.2 MINOR bump atomicity (MED, 6-file 재구성)

**영역**: (b) schema versioning + (j) 파이프라인 무결성

**관찰** (Reviewer prep §1.8 최종안 + Part B re-design, 2026-04-22):

### 3.0 v1.2 bump atomicity 최종 **7-file** (2026-04-22 team-lead 옵션 D 승인 반영)

team-lead 2026-04-22 확정: **6-file → 7-file** 확장 + **Phase 4b 분할 (4b-1 vs 4b-2)** 적용.

Domain Reviewer Part B re-design + Phase 4a Scout 합의 + Phase 4b 분할 반영. **PROLOGUE_SECTION enum 철회** + **chunk_splitter guard** (β-1) + **`special_appendix_name` 신규 필드** (대안 B-v2) + **`scripts/migrate_schema_v1_2.py` 신규** (Critic §3.2 완화안 공식 채택):

| # | 파일 | 변경 내용 | 종류 | Phase |
|---|---|---|---|---|
| 1 | `docs/json_schema.md` | §6.1 regex / §7.2.1a FRMK spec 주석 / §9.4 (optional β-1 docs) / §12 `special_appendix_name` 신규 필드 + `minimum:1` 유지 / §15a.1.2 / §16 Changelog | 필수 (§9.4 optional) | **4b-1** |
| 2 | `tests/fixtures/json_schema_v1_1.schema.json` → **`json_schema_v1_2.schema.json`** | rename + const 1.1.2 → 1.2.0 + regex pattern 확장 + `special_appendix_name: ["string","null"]` 추가 | 필수 | **4b-1** |
| 3 | `src/audit_parser/ingest/types.py` | `JSON_SCHEMA_VERSION = "1.2.0"` + `ChunkRecord.special_appendix_name: str \| None = None` | 필수 | **4b-1** |
| 4 | 36 ISA JSON in-place replace | `schema_version` 1.1.2 → 1.2.0 + **`special_appendix_name: null`** 추가 (bit-level diff 는 신규 key 추가만, chunk_id/embedding 불변) | 필수 | **4b-1** |
| 5 | `src/audit_parser/ingest/chunk_splitter.py` | 2-level assertion guard (β-1) — 3-level 시도 시 raise | 필수 | **4b-1** |
| 6 | `src/audit_parser/spec/standard_spec.py` **신규** + `isa_spec.py` (ISA spec 단독) | StandardSpec dataclass + `SPEC_REGISTRY` + `register_spec` 데코레이터 + ISA spec foundation | 필수 | **4b-1** (ISA 단독) |
| **7** | **`scripts/migrate_schema_v1_2.py` (신규)** | **Atomic all-or-nothing bump helper + dry-run + git status 사전 검증** (Critic §3.2 완화안 공식 채택 — 7-file atomicity rollback 위험 해소) | 필수 | **4b-1** |
| — | `src/audit_parser/spec/{isqm,assr,frmk}_spec.py` + `ir/two_column_table_body_parser.py` + `docx_reader.py` 확장 | 3 spec (ISQM/ASSR/FRMK) + TwoColumnTableBodyParser + dispatcher (v1.2 atomicity 외 — Phase 4b-2 scope) | — | **4b-2** |

### 3.0.0 7-file 의 원자성 trade-off

7-file 모두 **4b-1 단일 commit** 으로 bump. 성공 시:
- Phase 3 → Phase 4b-1 byte diff 는 `schema_version` + `special_appendix_name: null` 추가 (36 ISA JSON) + 신규 7개 파일만
- `embed_cache.sqlite` hit 100% 보장 (chunk_id unchanged)
- pytest Phase 1-3 전수 green 유지 + 신규 7-file 단위 테스트 green

실패 시 (Ctrl-C / shell crash):
- `scripts/migrate_schema_v1_2.py --dry-run` 으로 사전 검증 → 부분 commit 차단
- fallback: `git reset --hard HEAD` + `output/json/` 은 gitignore 이므로 **36 ISA JSON 수동 재생성 필요** (cache 100% hit 으로 재임베딩 비용 $0, 재파싱만 ~수초)

### 3.0.1 중요 변경 (2026-04-22 sync pass)

- **~~PROLOGUE_SECTION enum 신설~~**: **철회** (parser-implementer Part B Issue 2) — ASSR 개정개요 (I/II/III/IV upperRoman) 는 `meta/prelude` 로 **도메인 판단 skip** 처리. enum 확장 불필요.
- **~~SUB_ITEM ilvl=0 확장~~**: **철회** (Part B Issue 1) — `(%1)` at ilvl=0 은 `PARAGRAPH_BODY` + `paragraph_id="(1)"` 보존 (대안 c). ISA `(%1)` at ilvl=0 실측 0건 → 회귀 리스크 LOW 에서 해소.
- **β-1 chunk_splitter assertion guard**: **채택** (v1.2 atomicity #5 필수). §9.4 boilerplate 는 optional (중복 차단).
- **FRMK-\d harmonization**: Draft A 바리 `FRMK` → 최종 `FRMK-\d` (FRMK-1 으로 harmonized). standard_no 도 `\d{1,4}` relax.

**Plan v2 Exit gate**: "36 ISA re-parse 바이트 동등 (cache 100% hit, 재임베딩 불필요)" — PROLOGUE_SECTION / SUB_ITEM ilvl=0 철회로 리스크 크게 감소. 단 **StandardSpec 주입형 refactor 가 기존 dispatch 경로를 byte-equal 로 유지** 하는지는 Phase 4b 구현 시 실측 필수.

**공격 벡터** (6-file atomicity):
1. v1.2 bump commit 이 중도 중단 시 (Ctrl-C, shell crash) — 일부 파일만 `"1.2.0"`, 나머지 `"1.1.2"` → **schema_version heterogeneous** → `validate_json.py` drift gate 에서 fail
2. 36 ISA JSON in-place replace 시 `output/json/ISA-<n>.json` 은 `.gitignore` 대상 → git 복구 불가
3. `.embed_cache.sqlite` 와 `schema_version` 간 cache key 디커플링 확인 필요 — 만약 cache key 에 schema_version 포함돼 있으면 re-parse 시 cache miss → 재임베딩 $8.59
4. `standard_spec.py` 신규 + 4 spec 은 **refactor 범위** — 기존 3 file (md_parser / md_renderer / qdrant_writer) dispatch 로직 변경 — byte-equal 보장이 testing 부담 증가

### 3.1 서브-리스크: StandardSpec 주입형 refactor 의 ISA 회귀 (MED)

- 기존 ISA 전용 dispatch (하드코딩 경로) → StandardSpec 주입형으로 전환
- **회귀 가능성**: spec.classify_kind / spec.render_heading / spec.collection_name 등 메서드 호출 경로가 기존 로직과 bit-level 동등한지 검증 필요
- **요구**: Phase 4b 구현 시 "36 ISA re-parse 전수 chunk_id + kind + paragraph_id unchanged + cache 100% hit" 회귀 테스트 의무화

### 3.2 서브-리스크: 6-file commit atomicity 실패 복구 (MED)

- 6 파일 중 일부만 commit 된 상태로 HEAD 가 이동 시 — git checkout 으로 복구 가능하나 `output/json/` 은 gitignore → 수동 재생성 필요
- **완화안**:
  1. `scripts/migrate_schema_v1_2.py` (신규) — atomic all-or-nothing 스크립트 + dry-run + git status 사전 검증
  2. `validate_json.py` drift gate 에 "schema_version heterogeneous → FAIL" 명문화
  3. Phase 4b exit gate 에 "bump 후 `git status` 에 untracked JSON 0 건, MODified 36 건" + **"re-parse 시 cache hit 100%" 양 조건 동시 검증**
  4. CP4 cross-check anchor #4 추가: "36 ISA cache hit rate == 100% (non-zero api_calls → FAIL)"

### 3.3 Scaffold 이전 표기 정정 이력

**2026-04-22 1차 정정** (team-lead §3 정합성 지적):
- PROLOGUE_SECTION 항목 삭제 (Part B Issue 2 prelude skip 해소)
- SUB_ITEM ilvl=0 확장 항목 삭제 (Part B Issue 1 PARAGRAPH_BODY 보존)
- chunk_splitter guard 추가 (β-1)
- standard_spec.py 신규 (refactor 항목)

**2026-04-22 2차 확장** (team-lead 옵션 D 승인):
- 6-file → **7-file** — `scripts/migrate_schema_v1_2.py` 신규 추가 (Critic §3.2 완화안 공식 채택)
- standard_spec.py + 4 spec 을 **4b-1 ISA spec 단독** + **4b-2 3 spec** 으로 분할
- TwoColumnTableBodyParser + docx_reader dispatcher 를 **4b-2 scope 로 이월** (v1.2 atomicity 외)
- 7-file atomicity 는 **모두 4b-1 단일 commit 에 포함** — 4b-2 는 spec 확장만

**2026-04-23 Naming 통일** (team-lead 지침):
- Critic 원 제안 `scripts/bump_schema_version.py` → parser-implementer plan `scripts/migrate_schema_v1_2.py` 로 확정 통일
- parser-implementer plan approval 이 먼저 수신됨 + `--old-version` default `"1.1.2"` 유지 + 4b-2 에서 ISQM/ASSR/FRMK JSON 생성 후 동일 스크립트 재실행 가능한 구조
- Scaffold 전 섹션 (§3.0 / §3.0.0 / §3.2 / §3.3 / §3.4 / §14) rename 완료 (8 occurrences)

정정 근거: team-lead 옵션 D 승인 DM 2026-04-22 + Naming 통일 지침 2026-04-23 + `docs/checkpoint_4_prep.md §1.3.4` + §1.8 + §2.2.2 (Phase 4b 참조용 초안 배너) + parser-implementer 자가 재견적 (1,965 LOC / 55-70k) + plan §1.1 script naming.

### 3.4 Phase 4b-1 완료 시점 Critic 독립 재측정 (team-lead 지시)

§2.2 약속 재확인. 7-file atomicity commit 성공 조건 Critic cross-check (`audit-parser-phase4` Task #10 준비):
- [ ] ISA 36 파일 `chunk_id` 전수 unchanged (Python 독립 script 로 bit-level 비교 — jq 대안)
- [ ] `embed_cache.sqlite` hit 100% (api_calls=0, cached_hits=8,626)
- [ ] 36 ISA JSON 전수 `schema_version="1.2.0"` + `special_appendix_name: null`
- [ ] pytest 223 + N 신규 → green
- [ ] git status: MODified 6 (#1-5, #7 script) + NEW 2 (standard_spec.py, isa_spec.py)
- [ ] `scripts/migrate_schema_v1_2.py --dry-run` 으로 사전 검증 가능 (re-entrant)

---

## 4. 비판 #3 (R5 심화) — Mini Golden 10 seed 통계적 유의성 (HIGH)

**영역**: (eval) Mini Golden 임계치 통계

**관찰** (Clopper-Pearson 95% exact lower bound 실측):

| n | k (성공) | 관측 p | 95% LB | 임계 0.6 통과? |
|--:|--:|--:|--:|---|
| 5 | 5 | 1.00 | 0.478 | ✗ |
| 10 | 10 | 1.00 | **0.692** | ✓ (턱걸이) |
| 10 | 9 | 0.90 | 0.555 | ✗ |
| 10 | 8 | 0.80 | 0.444 | ✗ |
| 15 | 14 | 0.93 | 0.681 | ✓ |
| 20 | 18 | 0.90 | 0.683 | ✓ |
| 30 | 24 | 0.80 | 0.614 | ✓ |

- **최소 n for k=n perfect → 95% LB ≥ 0.6**: **n=8** (LB=0.631)
- 현 Plan v2 §7.3 임계: Recall@5 ≥ 0.6 or MRR ≥ 0.5, 카테고리 E 가 하위 임계 0.4
- **n=10 에서 단 1건 failure 시 (k=9) 통계적 95% 확증 실패** (LB=0.555 < 0.6)

**영향**: HIGH. "측정 기반 판정" 이 **brittle pass** 구조:
1. Recall@5 우연히 10/10 → GO (LB 턱걸이 0.692)
2. Recall@5 9/10 → **판정 불가** (점추정은 0.9 로 PASS 처럼 보이나 95% 확신 구간 붕괴)
3. Mini Golden "PASS" 판정이 점추정 의존 시 statistical p-hacking 위험

**완화안** (Pre-Kickoff 합의 완료, 2026-04-22):

### 4.1 Domain Reviewer 최종 수용안 (prep §3 신설)

- **안 C 채택** (n=10 + 이중 조건 판정): Pass = 점추정 Recall@5 ≥ 0.7 AND Wilson LB ≥ 0.5. 분리 권고 = 점추정 < 0.6 OR Wilson LB < 0.4. 중간 = CONDITIONAL → seed 추가 10건 (총 n=20) 재측정
- **카테고리 E 최소 n ≥ 3 고정** (Critic 원 제안 "n=1~2 통계 무의미" 를 n=3 으로 구체화). 분리 발동 = **2회 연속 Recall@5 < 0.4** (단일 failure 비가역 결정 차단)
- **Seed pool pre-draft 20~30건** (Phase 4a Scout 단계). n=15/20 확장 시 재발굴 부담 최소화
- **최종 판정 Task #10 진입 시점 team-lead + 사용자 결정** 으로 이월. Pre-Kickoff 기록만

### 4.2 Phase 4f 실측 의무 (Critic cross-check)

- Bootstrap CI + Wilson score interval 동반 보고 의무화
- 카테고리 E n=3 별도 집계
- CONDITIONAL 진입 시 Phase 4f 내 추가 10 seed 집행 vs Phase 5 이월 결정 — team-lead 판정 필요

**Reviewer prep §3 cross-ref 완료**. 본 scaffold 는 prep §3 과 동기화 유지.

### 4.3 F 카테고리 scope creep 처리 (2026-04-22 합의)

**Critic §5 pushback 수용 → Reviewer 전면 수용**:

| Category | Scout 초안 | 수정 후 |
|---|---:|---:|
| A 거버넌스 | 5 | 5 |
| B 위험평가 + 용어 이해 | 5 | **7** (기존 5 + F1/F2 재배치 2 + Critic B8 추가 1 = 8, cat B8 포함) |
| C 모니터링 | 4 | 4 |
| D 참여감사인 | 4 | 4 |
| E 한/영 혼재 (필수 ≥ 3) | 5 | 5 |
| ~~F 예비~~ | ~~2~~ | **폐기** |
| 합계 | 25 | **25** (구성 변경, 총량 유지) |

**Plan v2 §7.1 5-category 체계 준수**. ISQM-1 "용어의 정의" 는 품질관리 용어 이해 → B 자연 포함.

### 4.4 Critic 추가 제안 seed B8 편입

- **ISQM-MG-B8**: "감사인의 독립성 위반 (self-review threat) 이 발견되었을 때 품질관리시스템상 후속 절차"
- lang_mix=ko-en, expected_paragraph_id_hints=["21","22","23","24"]
- 카테고리 B 8번째 seed — single-author bias 대응 1st step
- Reviewer isqm_structure_profile.md §9.2 에 inline 등재 완료

### 4.5 single-author bias 대응 (Plan v2 §7.4 cross-check 의무)

- 25 seed 전부 Reviewer 1인 작성 → 구조적 bias 인정
- **Phase 4f Task #10 진입 시점 team-lead + user 에 "1-3건 추가 주입 요청" DM 의무화**
- Critic B8 seed 추가는 first step, team-lead/user slot 3건 별도 보존
- CP4 final 판정 시 single-author bias slot 사용 여부 실측 기록

---

## 5. 비판 #4 (§7.3 카테고리 E 분리 비가역성) (MED)

**영역**: (design) Phase 5 의사결정 비가역성

**관찰**:
- Plan v2 §7.3: "카테고리 E Recall@5 < 0.4 → **즉시 분리 권고**"
- "분리" 정의: 한/영 혼재 collection 을 `audit_standards_품질관리기준서_2018_ko` + `audit_standards_품질관리기준서_2018_en` 2개로 split
- 한 번 split 후 Phase 5+ 에서 **재통합** 은 embedding 재생성 + 기준서 간 re-chunking + collection drop/recreate 필요 → **비가역적**

**영향**: MED.
- 분리 결정이 측정 기반 (Critic 가 옹호) 이라 단발 낮은 값으로 비가역 결정 → 재측정 기회 없음
- 카테고리 E n=1~2 seed 에서 Recall@5=0/1 만으로 "분리" 확정 시 실제 collection 품질 판단 오판 가능

**완화안**:
1. Plan v2 §7.3 "**즉시 분리**" 를 "**Phase 5 분리 후보 기록 + 재측정 1회 후 분리 확정**" 으로 격상
2. 재측정 조건: Phase 5 에서 seed 10건 추가 (총 n≥3 한/영 혼재) 재실행, 2회 연속 Recall@5 < 0.4 시 분리
3. 또는 "분리" 대신 "**payload field `lang_mix` 추가 + payload filter 적용**" 를 선행 검토 (collection 분리 없는 mitigation)

---

## 6. 비판 #5 (R4 심화) — 4 collection Qdrant 메모리 실측 (MED)

**영역**: (g) Qdrant 성능 + (ops) 16GB 랩톱 운영

**관찰** (실측 기반 추정):

| points | named vectors | raw (MB) | w/ HNSW (MB) |
|--:|--:|--:|--:|
| 8,626 (현재 ISA) | 2 | 269.6 | 350.4 |
| 15,000 (예상 4 collection 합) | 2 | 468.8 | 609.4 |
| 18,000 (상한 예상) | 2 | 562.5 | 731.2 |
| 20,000 (Phase 5+ 여유) | 2 | 625.0 | 812.5 |

**16GB 랩톱 환경**:
- Qdrant: ~750 MB
- Docker + OS + WSL (or Linux): ~2-3 GB
- Python / pytest / embedder cache: ~500 MB
- Browser + IDE + Claude Code: ~3-4 GB
- 여유: 7-8 GB → **즉시 OOM 위험 없음**. 단 16GB 미만 장비 (8GB laptop 저가 개발 PC) 에서는 OOM 가능.

**영향**: MED. Phase 4e 적재 시 실측 필수. Plan v2 §8 R4 "필요 시 scalar quantization 준비" 는 반응적 — **pre-fix 실측 없이 사후 튜닝 의존**.

**완화안**:
1. Phase 4e 적재 직전 및 직후 `docker stats qdrant` 측정 기록 → `docs/PHASE_4_REPORT.md`
2. 18k points 도달 시 자동 alert (PLAN.md §5 리스크 매트릭스 업데이트)
3. 8GB 이하 장비 지원 명시 여부 결정 (Phase 5 scalar quantization 트리거)

---

## 7. 비판 #6 — Phase 4e rollback (MED → **RESOLVED via invariant assertion**) + 파생 3건

**영역**: (j) C-P2-9 원자성 재발

### 7.0 합의 경위 (2026-04-22)

Critic 원 제안 (state JSON 기반 progressive resume) → parser-implementer 반대 제안 (Qdrant invariant assertion pattern) → Critic 수용 (철회) → 추가 3 서브-리스크 제기.

**합의된 설계** (state JSON 도입 없음):
- `chunk_id → uuid5 deterministic + upsert idempotency` 로 자연 resume
- `count(exact=True)` 로 post-ingest 완전성 assertion
- `drop 금지 + partial 유지 + fail-fast` — 실패한 collection 은 그대로, next run 이 자연 보완
- CLI: `--only-collection`, `--force`, `--continue-on-error=False` default
- EMBED_METRICS.json `collections` 필드 확장

**원 (a) state JSON / (c) drop-on-fail 설계 철회 근거**: parser-implementer 의 "Qdrant = single source of truth, state JSON = TOCTOU drift" 논거 정당.

### 7.1 파생 리스크 (x) — `--prune-stale` 상존성 (MED)

**관찰**: invariant assertion 에서 `actual > expected` 시 orphan points 경고 제시 예정.
**공격**: `--prune-stale` 플래그가 **미구현 상태로 경고만 존재** 시 "aspirational documentation". 사용자 실행 시 `No such option` 불통.
**요구**: (i) Phase 4e 구현 scope 의무 편입, 또는 (ii) 경고 메시지에서 옵션 언급 제거 + 수동 절차 안내로 약화. 택일 회신 대기.

### 7.2 파생 리스크 (y) — Phase 4b `verify=True` signature 예약의 test 간섭 (LOW → RESOLVED)

**관찰**: Phase 4b exit gate "36 ISA re-parse 바이트 동등" 실행 시 verify kwarg 의 실 구현 없음 → NotImplementedError 또는 silent no-op 양극단.
**요구**: Phase 4b 에서 **stub 구현** (ISA 8,626 points exact count assert 만) — $0 비용 + 4b 내 regression guard. 4e 에서 expected/actual 계산 확장.

**team-lead 확정** (2026-04-22): 
- **4b-1 ISA baseline stub: 10-15 LOC** — count assertion 만 (8,626 points)
- **4b-2 3 spec 확장** — spec.qdrant_config() 기반 schema assertion
- **4e spec-driven 본격 구현** — invariant assertion pattern full (3-stage 구조)

커밋 4 에 포함. 커밋 4 시점 Critic cross-check (§2.2 commit 4 monitoring): `verify=True` default 가 기존 테스트 무영향 + `IngestIncompleteError` unit test 존재 확인.

### 7.3 파생 리스크 (z) — Collection schema pre-assertion 누락 (MED)

**관찰**: §2 pattern 은 point count 만 검증. Phase 4b 개발 중 test HNSW params (m=8 등) 로 생성된 collection 이 4e 정식 적재 시 silent 재사용 가능 — `create_collection` idempotent 이라 재설정 없음.
**공격**: actual count == expected → assertion PASS, 그러나 HNSW params 는 Plan v2 §6.4 원안 m=16 이 아님 → silent misconfig.
**요구**: `ingest_collection_with_verification` STEP 0 로 schema pre-assertion 추가 — named vectors, dim, distance, HNSW params, (optional) payload indexes. mismatch 시 `SchemaDriftError` raise + 수동 drop+recreate 안내. 수용 여부 회신 대기.

### 7.4 team-lead 확정 (2026-04-22)

parser-implementer 회신 + team-lead 승인 — parser-implementer §8 권고 전수 채택:

| 결정 사항 | 내용 |
|---|---|
| State JSON | **미도입** — Qdrant = single source of truth, invariant assertion 으로 대체 |
| Phase 4b→4e scope | verify kwarg API 경계만 4b 예약, 실 구현 4e |
| fail-fast default | `--continue-on-error` 는 off. collection #2 실패 시 #3 자동 skip + exit 1 |
| drop 금지 | 파괴적 drop 대신 partial 유지 + 재실행 자연 복원 |
| EMBED_METRICS 필드명 | `collections_ingested: list[...]` (top-level 충돌 방지) — Optional v1.1.2 하위 호환 |
| CLI 플래그 (Phase 4e) | `--force` / `--only-collection` / `--continue-on-error` / `--dry-run`. `--all` 제외 (idempotency natural resume 대체) |

**Critic scaffold §7.1-7.3 추가 3 서브-리스크 처리 상태**:

| 서브-리스크 | 원 심각도 | Phase 4e 최종안 반영 | Critic 판정 |
|---|---|---|---|
| (x) `--prune-stale` 상존성 | MED | **해소 by omission** — 최종 CLI 플래그 표에 `--prune-stale` 부재 → 경고 메시지 문구에서 해당 옵션 언급 제거 필요 (Phase 4e 구현 시 확인) | ⚠ **parser-implementer 에 경고 문구 조정 요청 1건만 남음** |
| (y) `verify=True` 4b stub | LOW | parser-implementer 원안 "verify kwarg API 경계만 4b 예약, 실 구현 4e" — 4b 에서 구현 없음 — 4b exit gate "36 ISA cache 100% hit" 은 별도 메커니즘 | ⚠ 4b test 에서 verify 호출 시 NotImplementedError/no-op 거동 확인 필요 |
| (z) Collection schema pre-assertion | MED | **명시적 채택 여부 불명** — `--force` 플래그는 "스키마 변경 시 recreate" 용도로 존재하나 실 assertion 은 미언급. CP4 실측 cross-check 대상. | ⏳ Phase 4e 구현 결과 확인 후 판정 |

### 7.5 CP4 교차검증 예정 anchor (parser-implementer 요청 수용 + B-v2 확장)

Phase 4e 구현 완료 후 Critic Task #10 에서 다음 invariant anchor **4건** 독립 재측정:
1. 3 collection 각각 `actual_points == expected_points` (from `output/json/` pre-count)
2. 3 collection 누적 RSS 메모리 (16GB 환경 실측, Plan v2 §8 R4)
3. `--continue-on-error` 미사용 상태 artificial 실패 injection 시 #3 collection skip 확인 (선택)
4. **(신규, §11 B-v2)** `special_appendix_name` 필드 payload 검증:
   - FRMK 컬렉션 `보론: 역할과 책임` chunk payload 에 `special_appendix_name="역할과 책임"` + `appendix_index=null`
   - ISA 36 JSON 전수 `special_appendix_name=null` + `appendix_index` 기존 값 불변 + cache hit 100% (re-embed=0)

### 7.6 최종 수렴 상태

| 항목 | 심각도 | 최종 상태 |
|---|---|---|
| 원 #6 rollback 설계 공백 | MED → **RESOLVED** | invariant assertion 패턴 채택, team-lead 승인, 2026-04-22 |
| (x) `--prune-stale` 상존성 | MED → **해소 by omission** | 경고 메시지 조정만 Phase 4e 구현 시 확인 |
| (y) verify stub 4b 구현 | LOW → **조건부 해소** | 4b test 에서 verify no-op 거동 검증 (Task #10 anchor) |
| (z) schema pre-assertion | MED → **명시 없음** | Phase 4e 구현 결과 CP4 cross-check 대기 |

**본 영역 Phase 4b plan approval 흐름에 충분히 수렴**. Phase 4e 실 구현 결과에 따라 (z) 재평가만 유예.

---

## 8. 비판 #7 — PK-4 unknown_numbering 5% 임계 근거 (MED)

**영역**: (b) numbering fallback 임계 설정

**관찰**:
- Plan v2 §4 PK-4: "3 DOCX pre-scan (unknown_numbering ≥ 5% 발견 시 fallback 확장 선행)"
- Phase 1 ISA 실측: **0.053%** (6 unknown / 11,267 blocks) — 90/90 pytest green
- 5% 임계 = **94.3× Phase 1 baseline**

**영향**: MED.
- 5% 는 "catastrophic failure only" 수준. Phase 1 의 10× (0.53%) 만 돼도 numbering 품질 유의미 저하 — 임계 내부라 silent pass
- 3 DOCX 는 ISA 대비 작음 (88KB / 347KB / 383KB vs 1626KB). 블록 수 비례 추정 600~2500 블록 → 5% = 30~125 unknown. 대량 silent fallback 위험

**완화안 — 합의 완료 (Domain Reviewer prep §0.2.2 3-tier gate 채택, 2026-04-22)**:

### 8.1 3-tier gate (prep §0.2.2 확정)

| tier | 조건 | 처리 |
|---|---|---|
| **ABORT** | unknown_numbering ≥ 5% | Phase 4a Exit gate 실패 → classify_kind 확장 선행 필수 |
| **WARNING** | 0.5% < unknown ≤ 5% OR 절대값 > 20건 | **수동 검수 + profile_md 에 "Unknown audit" 섹션 의무** (silent pass 차단) |
| **PASS** | unknown ≤ 0.5% AND 절대값 ≤ 20건 | Phase 4a Exit gate 통과 |

- Critic 원 제안 "이중 gate" 를 3-tier 로 격상 채택
- 3 DOCX 독립 적용 — ISQM-1 / ASSR / FRMK 각각 개별 판정
- `numbering_strategy.md §5.2` 에도 동일 규칙 적용 권고

### 8.2 현 Phase 4 pre-scan 실측 (prep §2.1) 대조

| DOCX | direct unknown % | tier (수정안) | classify_kind 확장 후 예상 |
|---|---:|---|---|
| ISQM-1 | 0.00% | PASS | PASS 유지 |
| ASSR | 37.57% | **ABORT** | classify_kind 확장 (PROLOGUE_SECTION + SUB_ITEM ilvl=0) 후 ≤ 5% 예상 → WARNING/PASS 전환 |
| FRMK | 43.14% | **ABORT** | 동일 확장 후 ≤ 5% 예상 |

ABORT 2건은 Plan v2 §4 PK-4 "fallback 확장 선행" 조항 발동. 단 **처리 방식 변경 (2026-04-22 team-lead 지시)**:

- **prep §2.2.2 격하**: "Phase 4b 참조용 초안 (즉시 구현 금지)" 배너 추가됨 — Pre-Kickoff 에서 classify_kind 전역 수정 배제 확정
- **Phase 4a Scout 이후 도메인 판단 반영 하여 확정 명세로 승격**
- parser-implementer Part B re-design 에서 제안된 **prelude skip** (ASSR 개정개요 I/II/III/IV 를 meta 로 분류) 이 classify_kind 전역 확장 없이 해소 경로
- v1.2 atomicity 는 **PROLOGUE_SECTION enum 철회** (§3.0.1 참조) + chunk_splitter guard 추가로 재구성 — ABORT 해소는 **Scout 결과에 따라** 경로 결정 (prelude skip 단독 vs classify_kind 일부 확장)

---

## 9. 비판 #8 — C-P2-1 drift "연환산 200%" 계산 protocol 공백 (MED)

**영역**: (h) C-P2-1 CP4 mandatory drift section

**관찰**:
- Plan v2 §5 Prep 6-item §1-§3 + §8 R6: "realized_annual_cache_invalidation > 200% → v1.2 auto-trigger"
- "연환산" 계산 방식 미정의:
  - Option A: **1회 재파싱 측정치 × 12 개월** (monthly 재파싱 가정)
  - Option B: **실측 빈도 누적 / 관측 기간** (N일 내 M회 재파싱 → M/N × 365)
  - Option C: **N-DOCX 누적 drift 비율 평균**
- Phase 4 단일 CHECKPOINT 에서 1회 측정 → Option A 가 암묵적 default?

**영향**: MED.
- 200% 임계 자체가 **Critic 권고값 + 실측 0 건 heuristic** (CP3 §2.2-ii)
- 계산 방식 미정의 시 "trigger 여부" 자의적 해석 가능
- Phase 4f "C-P2-1 재평가 결과" 섹션 작성 시 calculation protocol 가 없으면 Reviewer/Critic 간 해석 불일치 재발

**완화안 — 합의 완료 (Domain Reviewer prep §0.2.1 채택, 2026-04-22)**:

### 9.1 Option B 공식 (채택)

```
realized_annual_cache_invalidation
  = (Σ per-reparse chunk_affected_ratio / observation_window_days) × 365

분자: Σ per-reparse chunk_affected_ratio (각 재파싱 event 당 영향받은 chunk 비율)
분모: observation_window_days (Phase 4 측정 기간)
스케일: × (365 / window_days) — 연환산
```

### 9.2 인정 사항

- Phase 4 단일 관측 bias 인정 — 측정치 자체가 point estimate 에 불과
- CP4 실측 후 **200% 임계 자체 재조정 가능성 개방** (Critic 원 제안 (iii) 수용)
- 200% 초과 시 v1.2 MINOR bump 후보 고정, bump 실 집행은 Phase 5 이월 (Plan v2 §2 OUT)

### 9.3 측정 의무 (Prep #1/#2/#3)

- Phase 4 DOCX revision history + 재파싱 실측 1건 이상 (prep Prep #1)
- `realized_annual_cache_invalidation` 계산 → `checkpoint_4_review.md §N` 에 기록 (prep Prep #2/#3)
- miss 시 rework 자동 처리

---

## 10. 비판 #9 — ISQM 2 "Scout 확정" 검증 (LOW)

**영역**: (d) Scope 정당성

**관찰**:
- Plan v2 §8: "~~R1 ISQM 2 sub-standard~~ — Scout 확정 (IAASB 공식 ISQM 1 / 2 / ISA 220 Revised 3개 독립)"
- 현 Phase 4 대상 DOCX:
  1. `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` → ISQM **1**
  2. `raw/역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문...docx`
  3. `raw/인증업무개념체계(2022년 개정)_전문.docx`
- ISQM **2** 는 raw/ 에 없음. Phase 4 out-of-scope

**영향**: LOW.
- ISQM 2 가 Phase 5 에서 추가될 예정인지 명시 없음
- "Scout 확정" 이 **단순 구글 검색** 이 아닌 **IAASB 2022 Handbook 공식 매핑** 근거 인용 여부 검증 미흡 — Plan v2 §8 단순 주석 "Scout 확정"

**완화안 — 합의 완료 (Domain Reviewer prep §0.3.3 반영, 2026-04-22)**:

### 10.1 prep §0.3.3 확장 (확정)

- ISQM 2 / ISA 220 Revised KICPA 한국어 번역본 미제공 명기 완료
- IAASB 2022 Handbook URL 인라인 인용: `https://www.iaasb.org/publications/2022-handbook-international-quality-management-auditing-review-other-assurance-and-related-services-pronouncements`
- "IAASB 공식 3개 (ISQM 1 / ISQM 2 / ISA 220 Revised) 중 ISQM 1 만 2018년 번역본 수록" 명시
- "Phase 4 scope 에 추가 수록 없음" 규약 고정

### 10.2 Phase 5 이월 scope

- "IAASB 공식 3개 미수록 2건 통합 검토" 가 Phase 5 scope 에 선기재 (Critic 원 제안 수용)
- regex α 철회로 Draft A 그대로 유지 → Phase 5 ISQM 3+ 발표 시 v1.3 MINOR bump 로 처리 (scope 축소 원칙)
- "Scout 확정" 근거가 session 요약 → IAASB 공식 URL 로 전환 완료 (stale-claim 차단)

---

## 11. 비판 #10 — StandardSpec 단위 테스트 coverage (LOW)

**영역**: (a) test coverage + (b) regression guard

**관찰**:
- Plan v2 §6.2 Phase 4b 산출물: `tests/test_standard_spec.py` **단일 파일**
- 4 spec × 3 단계 (parse / render / ingest) × edge case (unknown_numbering / appendix / table split / heading_trail / section enum) = **최소 12~60 테스트 조합**
- 단일 테스트 파일로 커버 시 **테스트 당 단언 수 과도** 또는 **skip 누락** 위험

**영향**: LOW.
- Plan v2 exit gate "36 ISA re-parse 바이트 동등" 은 regression guard 로 유효하나 **신규 3 spec 의 first-order coverage** 만 검증
- ISQM-specific edge cases (e.g. 한/영 혼재 heading, appendix 없음 구조) 가 ISA-shim spec 으로 silent 통과 가능

**완화안**:
1. `tests/test_standard_spec_{isa,isqm,frmk,assr}.py` 4파일 split
2. 공통 abstract test harness (`tests/test_standard_spec_base.py`) — parametrize 로 4 spec 반복 적용
3. Phase 4b parser-implementer 에 "spec 별 parametrized fixture + 단일 abstract test case 5종" 설계 권고

---

## 11. 비판 #11 — Un-numbered 보론 `appendix_index` 규약 (MED → RESOLVED)

**영역**: (h) JSON Schema §7.2.1 + (b) spec-aware validation consistency

**합의일**: 2026-04-22 (Critic 제안 대안 B-v2 채택)

### 11.1 배경

Phase 4a Scout 결과 FRMK-1 에 `보론: 역할과 책임` (un-numbered) + `보론 1/2/3` (numbered) **공존** 발견. ISA 9 un-numbered 보론은 `json_schema §7.2.1` 에 따라 모두 `appendix_index=1` 매핑. FRMK 에서 동일 규약 적용 시 `보론 1` (=1) 과 충돌.

### 11.2 3 대안 비교

| 대안 | 처리 | 장점 | 단점 | 판정 |
|---|---|---|---|---|
| A (Reviewer 초안) | FRMK un-numbered 만 `appendix_index=0` | 최소 변경 | ISA §7.2.1 파편 분기 (spec-aware validation 필요) | **Reviewer 철회** |
| B-v1 (nullable 전체) | ISA + FRMK 공통 `appendix_index: int \| null` (un-numbered = null) | 규약 통일 | ISA 9 JSON bit-level diff 발생 — backward-compat breaking | Critic 철회 |
| **B-v2** (Critic 제안 → 합의 채택) | FRMK un-numbered 는 `appendix_index=null` + 신규 필드 `special_appendix_name` 에 title 보존, numbered 는 `appendix_index=1/2/3 + null` | ISA 36 JSON bit-level 불변 (`special_appendix_name: null` 추가 외 불변) + FRMK isolate + RAG UX 개선 (title 검색 가능) | JSON Schema 확장 1필드 (v1.2 MINOR 범위) | **✅ 확정 채택** |
| C (Reviewer 원안) | `appendix_index=0` for FRMK un-numbered | 최소 변경 | §7.2.1 "모두 1" 규약과 분기 → spec-aware validation | **Reviewer 철회** |

### 11.3 B-v2 확정 내용

- `chunks[].appendix_index`: `int | null` — un-numbered 는 **null**, numbered 는 기존 정수 (`minimum: 1` 유지, relax 불필요)
- `chunks[].special_appendix_name`: **`str | null`** (v1.2 MINOR bump 신규 optional 필드)
  - FRMK un-numbered `보론: 역할과 책임` → `(appendix_index=null, special_appendix_name="역할과 책임")`
  - FRMK numbered `보론 1/2/3` → `(appendix_index=1/2/3, special_appendix_name=null)`
  - ISA 9 un-numbered 보론 → Phase 4 **불변** (기존 `appendix_index=1` 유지, `special_appendix_name=null`). Phase 5+ 에 선택적 채움

### 11.4 v1.2 atomicity 6-file 영향

§3.0 6-file 표 업데이트 완료:
- #1 `docs/json_schema.md §12` 에 `special_appendix_name` 필드 추가 (§7.2.1a FRMK spec 주석 포함)
- #2 fixture `json_schema_v1_2.schema.json` 에 `special_appendix_name: ["string","null"]` 추가
- #3 `types.py` `ChunkRecord.special_appendix_name: str | None = None`
- #4 36 ISA JSON in-place replace — `schema_version` + `special_appendix_name: null` 추가 (bit-level diff 는 신규 key 추가만, chunk_id/embedding 불변 → cache hit 100%)
- #6 `standard_spec.py` + FRMK spec `_frmk_appendix_mapper` 에서 설정

### 11.5 CP4 교차검증 anchor 확장

§7.5 CP4 anchor 에 #4 신설:
- "FRMK-1 `보론: 역할과 책임` chunk 의 payload 에 `special_appendix_name="역할과 책임"` 존재 확인 (+ `appendix_index=null`)"
- "ISA 36 JSON 전수 `special_appendix_name=null` 존재 + chunk_id 불변 + cache hit 100%"

### 11.6 B-v2 공동 credit

- Critic (§4.2 alternative B-v2 제안) + Reviewer (초기 scope 식별 + 대안 C 철회 수용)
- RAG UX 개선 부가 효과는 Critic 제안 시점 발견, Reviewer 가 "§7.2.1 파편 분기 최소화" 근거로 합의 수용

---

## 12. Self-Audit (Phase 0-3 교훈 계승)

CP3 §6 Self-audit 원칙 계승. 본 scaffold 단계에서의 자체 검증:

### 12.1 stale claim 회피
- (e) 메모리 추정은 **Phase 3 실측 8,626 point 기반** → Plan v2 §8 R4 의 "15-18k points" 상한 추정 + **자체 계산** (4096d × 2 named × 4 byte × 1.3 HNSW overhead)
- (c) Mini Golden 통계는 Clopper-Pearson **실측 계산** (session 요약 의존 금지)
- (g) 0.053% baseline 은 `docs/devils_advocate_checkpoint_1.md` 직접 인용

### 12.2 예측치 사전 공표 (Phase 2 Critic 교훈)
- 본 scaffold §6: Qdrant 메모리 350 → 731 MB 증가 예측 → Phase 4e 실측 대비
- 본 scaffold §4: Mini Golden n=10, k=9 (점추정 0.9) 시 95% LB=0.555 예측 → Phase 4f 실측 검증 대상
- 본 scaffold §8: 5% 임계 → Phase 1 baseline × 10 (0.53%) 제안 → Phase 4a pre-scan 실측 대비

### 12.3 Plan v2 수용 사항 재반박 금지 준수
- §1 명시적 enumeration 완료. §2~§11 의 비판은 **v2 에서 해소되지 않은 gap** 에 한정.

### 12.4 Phase 3 pre-emptive DM 교훈 적용 실적
- §4 (Mini Golden seed 수), §7 (Phase 4e rollback), §8 (unknown 임계), §9 (drift protocol) 4건 — Pre-Kickoff 단계 Domain Reviewer + parser-implementer 에 선제 DM **완료 (2026-04-22)**. 수용률:
  - §4 안 C 채택 (3안 비교 제안 형식, team-lead 프로토콜 준수) ✅
  - §7 invariant assertion 대안 수용 (3 서브-리스크 x/y/z 추가, 2건 합의 + 1건 premise 철회) ✅
  - §8 3-tier gate 격상 채택 ✅
  - §9 Option B 공식 채택 ✅

### 12.5 Critic 자체 실수 1건 기록 (CP3 §6.4 원칙 위반)

**영역**: §7.1 (x) `--prune-stale` aspirational documentation 리스크 제기

**실수 내용**:
- 나는 Pre-emptive DM 에서 "`--prune-stale` 가 미구현 상태에서 경고만 존재하면 aspirational" 이라는 리스크 제기
- parser-implementer 팩트 체크 grep 결과: **`--prune-stale` 은 Phase 3 Task #2 산출물로 이미 완전 구현** (cli.py 8회 occurrence + qdrant_writer `_prune_stale` 메서드)

**근본 원인**:
- Pre-emptive DM 작성 시 session summary 의 "cli.py Phase 3 10 flags" 를 **실존 flag 목록으로 reify 하지 않음**
- `grep --prune-stale src/` 1회 실행으로 방지 가능했음
- **CP3 §6.4 원칙 #1 "Session 압축본 수치는 반드시 원본 파일 재조회 후 재인용" 자체 위반**

**처리**:
- §7.1 (x) premise 철회 (parser-implementer DM 회신 2026-04-22)
- 본 §12.5 에 실수 인정 기록

**재발 방지 원칙 (CP5 이월)**:
- 원칙 #5 (CP4 신설): "pre-emptive DM 의 **`missing feature`** 주장은 반드시 **실측 grep / ls / cat 1회** 선행 — 미선행 시 해당 리스크 제기 자체 철회"
- 원칙 #6 (CP4 신설, team-lead 권장 2026-04-22): "**cross-check 대상 문서의 버전 타임스탬프를 scaffold 업데이트 시점과 대조**. Domain Reviewer / parser-implementer DM 이 최신 문서 반영 전 작성되었을 가능성을 always 체크. scaffold §3 의 PROLOGUE_SECTION 철회 미반영 사례 (2026-04-22 team-lead §3 정합성 지적) 가 본 원칙 계기."
- 원칙 #1 (CP3 계승): Session 압축본 수치는 원본 파일 재조회
- 원칙 #2 (CP3 계승): 용어 정의 합의 후 인용
- 원칙 #3 (CP3 계승): 근거 파일 line number 명시
- 원칙 #4 (CP3 계승): Critic ↔ Reviewer 쌍방 cross-ref 동시 기록

### 12.6 Critic 자체 실수 2건째 기록 (원칙 #6 trigger 사례)

**영역**: §3 v1.2 atomicity 6-file 구성

**실수 내용**:
- 2026-04-22 일자 첫 scaffold 업데이트 시 Domain Reviewer prep §2.2.2 "PROLOGUE_SECTION 신설 + SUB_ITEM ilvl=0 확장" 을 전제로 §3 에 "6-file atomicity" 기록
- 이후 parser-implementer Part B re-design (Issue 1/2/3 해소) 로 PROLOGUE_SECTION 철회 + SUB_ITEM ilvl=0 철회 + prelude skip 채택 → scaffold §3 는 **재설계 이전 snapshot 으로 고착**
- team-lead 2026-04-22 후속 DM 에서 본 정합성 disparity 지적

**근본 원인**:
- Reviewer ↔ parser-implementer DM exchange 이 **scaffold update 사이에 다중 턴 전개** → Critic 은 **최신 prep §1.3.4 + §1.8 버전** 을 scaffold §3 에 즉시 반영하지 못함
- Domain Reviewer / parser-implementer DM 수신 시 prep 문서 최신본을 항상 re-read 하지 않음

**처리**:
- 본 sync pass (2026-04-22) 에서 §3 전수 재작성 — PROLOGUE_SECTION 삭제 + SUB_ITEM ilvl=0 삭제 + chunk_splitter guard 추가 + standard_spec.py 추가 — 최종 6-file 으로 재구성
- §3.3 "Scaffold 이전 표기 정정 이력" 블록 신설하여 투명성 확보
- 원칙 #6 신설 → CP5 이월

**재발 방지**:
- scaffold update 전 **관련 prep 문서 modified-at 확인 의무**
- 다자간 DM exchange 중 (3-way Reviewer / Implementer / Critic) scaffold §3/§7 등 설계 요약 섹션은 **최종 확정 DM 수신 후 단일 sync pass** 로만 업데이트

---

## 13. Phase 5 진입 Go/No-Go (Final, 2026-04-28)

**최종 판정**: **GO**. 판정 조건:

1. Phase 4b~4f 완료.
2. Mini Golden Recall@5 `1.0`, MRR@10 `0.677083`.
3. CP4 mandatory drift 섹션 완료 — realized annual invalidation `0.0%`.
4. 4 collection Qdrant invariant PASS — total `10,387` points.
5. HIGH blocker 0.

**잔여 MED**: ISQM/ASSR `section=null` metadata precision, compose 소유가 아닌 Qdrant
컨테이너 운영 정리. 둘 다 Phase 5 개선 후보이며 Phase 4 release blocker 는 아니다.

---

## 14. 근거 Cross-Reference 인덱스 (scaffold v0, Pre-Kickoff 단계 종결 시점)

| 근거 주제 | 근거 파일 · 섹션 |
|---|---|
| Plan v2 §8 리스크 5건 | `docs/phase_4_plan.md §8` |
| Plan v2 §11 이월 재분류 | `docs/phase_4_plan.md §11` |
| Mini Golden 임계 + 안 C 합의 | `docs/phase_4_plan.md §7.3` + `docs/checkpoint_4_prep.md §3` |
| unknown 3-tier gate | `docs/checkpoint_4_prep.md §0.2.2` |
| realized_annual Option B 공식 | `docs/checkpoint_4_prep.md §0.2.1` |
| ISQM 2 Phase 5 이월 + IAASB URL | `docs/checkpoint_4_prep.md §0.3.3` |
| PK-2 Draft A 확정 | `docs/checkpoint_4_prep.md §1 + §1.7` |
| Phase 1 unknown 0.053% baseline | `docs/devils_advocate_checkpoint_1.md C7` |
| CP2 C-P2-1 drift | `docs/devils_advocate_checkpoint_2.md §C-P2-1` + `docs/checkpoint_3_review.md §4.1` |
| CP3 C-P3-D4 regex 이월 | `docs/devils_advocate_checkpoint_3.md §4.4` |
| Qdrant 8,626 point 기반 | `docs/PHASE_3_REPORT.md` + `EMBED_METRICS.json` |
| StandardSpec 4 spec 계획 | `docs/phase_4_plan.md §6.2` |
| PK-4 pre-scan 실측 | `docs/checkpoint_4_prep.md §2` + `tmp/phase4_prescan.json` |
| Phase 4a Scout 산출물 | `docs/{framework,assurance_other,isqm}_structure_profile.md` + `tests/fixtures/phase4_profile_samples.json` (Task #5 completed 2026-04-22) |
| ISQM-1 table body parser 설계 | `docs/isqm_structure_profile.md §2.2 / §2.3 / §5` — 신규 `ISQMTableBodyParser` 필요 (budget impact) |
| FRMK-1 un-numbered 보론 충돌 | `docs/framework_structure_profile.md §6.2` — Domain Reviewer appendix_index=0 제안 vs ISA §7.2.1 =1 규약 |
| ASSR-3000 section state machine | `docs/assurance_other_structure_profile.md §2.3` — "요구사항"→"목적" 재등장 transition |
| FRMK heading_range_strip | `docs/framework_structure_profile.md §2.3` — regex `(\d+(?:-\d+)?)\s*$` + 보론 prefix exception |
| Mini Golden seed pool 25건 | `docs/isqm_structure_profile.md §9` — A/B/C/D/E/F 분포 (F=2 scope creep 식별) |
| Phase 4b budget 에스컬레이션 | team-lead DM 2026-04-22 — 35-45k → 50-70k 권고 (3 옵션 비교) |
| Phase 4e invariant assertion 합의 | parser-implementer DM (2026-04-22) + team-lead 승인 |
| `--prune-stale` Phase 3 기 구현 | `src/audit_parser/cli.py:151` + `qdrant_writer.py:561` |
| v1.2 atomicity 6-file 최종안 | `docs/checkpoint_4_prep.md §1.8` ↔ scaffold §3 (Part B re-design 반영) |
| PK-4 §2.2.2 격하 배너 | `docs/checkpoint_4_prep.md §2.2.2` 상단 "Phase 4b 참조용 초안" — team-lead 지시 (2026-04-22) |
| PROLOGUE_SECTION 철회 | Reviewer prep §2.2.2 + parser-implementer Part B Issue 2 (prelude skip 채택) |
| FRMK-\d harmonization | Reviewer prep §1.3.4 최종안 — FRMK document standard_id = `FRMK-1` |
| Self-audit 원칙 #6 (버전 타임스탬프 대조) | team-lead DM 2026-04-22 + scaffold §12.6 |
| Phase 4b 옵션 D 승인 (분할) | team-lead DM 2026-04-22 — Critic 옵션 (c) 채택, Task #6 (4b-1 25-30k) + Task #11 (4b-2 25-35k), Task #7 blockedBy [#6, #11] |
| v1.2 7-file atomicity (6→7 확장) | scaffold §3.0 — `scripts/migrate_schema_v1_2.py` 공식 채택 (Critic §3.2 완화안 → team-lead 확정) |
| 4b-1 ISA parity 독립 재측정 | scaffold §2.2 + §3.4 — Task #10 준비 6-point checklist |
| 4b-2 pre-emptive 모니터링 | scaffold §2.4 — TwoColumnTableBodyParser edge case + recursive descent MAX_DESCENT_DEPTH=10 |
| 4b-1 plan approval (4 커밋 incremental) | team-lead DM 2026-04-22 — 커밋 1 spec foundation / 커밋 2 types+schema+36 JSON / 커밋 3 md_parser refactor / 커밋 4 β guard+verify stub, 3 중간 usage 보고 gate 의무 |
| 4b-1 Exit gate cross-check 5-item | scaffold §2.3 — jq anchor / set equality / mypy ruff / 예산 실측 / 7-file atomicity git log |
| verify stub (y) 3-stage 확정 | scaffold §7.2 — 4b-1 10-15 LOC ISA baseline / 4b-2 spec.qdrant_config() / 4e invariant assertion full |
| Script naming 통일 (bump_schema_version → migrate_schema_v1_2) | team-lead DM 2026-04-23 — parser-implementer plan §1.1 approved naming 우선, Critic scaffold 8 occurrences rename |

---

*End of `docs/devils_advocate_checkpoint_4.md` scaffold (v0). Phase 4b~4f 완료 후 v1 최종화. Task #10 에서 Phase 5 Go/No-Go 최종 판정.*
