# Phase 4 Pre-Kickoff Prep

> **작성자**: `audit-standard-domain-reviewer` (team `audit-parser-phase4`)
> **작성일**: 2026-04-22
> **대상 산출물**: Phase 4 CHECKPOINT 4 (3 DOCX → 3 신규 Qdrant collection) 착수 전 Freeze / Prep / regex / pre-scan 의무 4건.
> **참조 문서**:
> - [`docs/phase_4_plan.md`](./phase_4_plan.md) — Phase 4 Plan v2 (PK 4건 정의)
> - [`docs/PHASE_3_REPORT.md`](./PHASE_3_REPORT.md) §8 — 이월 이슈
> - [`docs/devils_advocate_checkpoint_3.md`](./devils_advocate_checkpoint_3.md) §2.3, §4.4 — Prep 7-item 근거
> - [`docs/json_schema.md`](./json_schema.md) v1.1.2 §6.1, §6.4, §12, §15a — chunk_id 현행
> - [`docs/numbering_strategy.md`](./numbering_strategy.md) §3, §5 — classify_kind / fallback 현행
> - [`docs/isa_structure_profile.md`](./isa_structure_profile.md) — ISA 비교 baseline
> - `tmp/phase4_prescan.py` + `tmp/phase4_prescan.json` — PK-4 실측 원본

본 문서는 **5개 section** 으로 구성된다:

- **§0 Prep 6-item** (PK-3) — Phase 4 CHECKPOINT 에서 반드시 이행할 의무 조항 (+ §0.2 Critic 선행 리스크 반영: realized_annual 공식 / unknown 이중 gate / Mini Golden pre-draft)
- **§0.3 Freeze Point** (PK-1) — Phase 4 착수 시점 스냅샷 (컨텍스트 오염 방지 + ISQM 2 / ISA 220 Revised Scope 외 근거 URL)
- **§1 chunk_id regex v1.2.0 합의** (PK-2) — Domain Reviewer 초안 + Critic 3축 리스크 반영 (§1.7) + parser-implementer / devils-advocate-critic 3자 DM 합의
- **§2 3 DOCX pre-scan** (PK-4) — 실측 요약 + unknown_numbering ≥5% fallback 확장 필요성 판정
- **§3 Mini Golden seed size 3안 비교** (Critic c 반영, Task #10 최종 결정 이월)

---

## 0. Prep 6-item (PK-3)

> **근거**: `docs/phase_4_plan.md` §5 (v1 7-item 중 C-P2-8 제거 → 6-item 축소).
> **준수 의무**: 아래 6개 조항은 CHECKPOINT 4 검수 시 **miss → rework** 자동 처리.
> Critic cross-check §2.3 에서 Phase 4 entry 조건으로 확정된 바 있음.

CHECKPOINT 4 mandatory drift 섹션 (`docs/checkpoint_4_review.md`) 필수 항목:

| # | 항목 | 근거 | 측정 / 판정 기준 |
|---|---|---|---|
| 1 | **C-P2-1 drift 연환산 빈도 기록 의무** | CP3 §9 / json_schema §15a.1 / Critic §2.3 (i) | Phase 4 3 DOCX revision history + 재파싱 실측 1건 이상. 측정치 (trimmed mean / per-standard max·min) `docs/checkpoint_4_review.md §N` 로 기록. |
| 2 | **`realized_annual > 200%` → v1.2 auto-trigger** (측정만, bump 은 Phase 5 이월) | json_schema §15a.1 후보 #1 / Phase 4 Plan v2 §5 row 2 / Critic DM (b-2) | `realized_annual_cache_invalidation` 공식 (**§0.2.1 에서 확정**) 로 계산 → 200% 초과 시 `docs/checkpoint_4_review.md` 에 "v1.2 bump candidate 고정" 기록 (Phase 5 이월). Critic pushback 반영 — 분자/분모 정의 본 문서 §0.2.1 참조. |
| 3 | **CHECKPOINT 4 mandatory drift 섹션** | Critic §2.3 Phase 4 prep §0 / Phase 4 Plan v2 §5 row 3 | `docs/checkpoint_4_review.md` 내 "§N C-P2-1 재평가 결과" 섹션 존재 필수. 부재 시 rework. |
| 4 | **chunk_id regex v1.2.0 3자 합의** | CP3 §4.4 C-P3-D4 / Phase 4 Plan v2 §5 row 6 / 본 문서 §1 | Phase 4a 진입 전 Domain Reviewer + Parser Implementer + Critic 3자 DM 합의. `docs/json_schema.md §6.1 / §12 pattern / §15a.1.2` 동기 bump. v1.2 MINOR (backward-compat prefix 확장). |
| 5 | **§6.5 NAMESPACE frozen 재확인** | CP3 §6.5 / v1.1.2 PATCH / Phase 4 Plan v2 §5 row 7 | 신규 3 DOCX collection 생성 시 `_QDRANT_POINT_NAMESPACE = 6ba7b810-9dad-11d1-80b4-00c04fd430c8` (NAMESPACE_DNS) 불변 확인. 변경 = v2.0 MAJOR trigger. |
| 6 | **§9.5 drift 추가 split 측정 (ISA-540 등 1건 이상)** | json_schema §9.5 / Phase 4 Plan v2 §6 4f / Critic §2.3 | ISA-1200 header bias 측정 프로토콜 (10 seed query × cond A/B) 을 ISA 외 타 기준서 1건 이상 (ISA-540 권장) 에 **동일 절차로 재적용**. CHECKPOINT 4 에 수치 기록. |

**제거된 v1 조항 (컨텍스트 오염 방지)**:

| 원 # | 원 항목 | 제거 사유 |
|---|---|---|
| ~~4~~ | ~~HNSW externalize~~ | **Phase 5 이월** (`phase_4_plan.md` §2 OUT §11 C-P3-D2) |
| ~~5~~ | ~~Backup/DR 루틴~~ | **Phase 5 이월** (§11 C-P3-D3) |
| ~~8~~ | ~~sha1[:12] 확장~~ | **폐기** (충돌 기댓값 1.8×10⁻⁷, premature optimization). json_schema §15a 운영 모니터링 트리거로만. |

### 0.1 v1 8-item → v2 6-item 전환 매트릭스

Plan v2 의 결정을 Prep 테이블 형태로 고정 (추후 Critic cross-check 참조용):

| v1 slot | v1 항목 | v2 분류 | 소속 | 비고 |
|---|---|---|---|---|
| 1 | C-P2-1 drift frequency | **Prep #1** | Phase 4 | 이행 |
| 2 | 200% auto-trigger | **Prep #2** | Phase 4 측정 / Phase 5 bump | 이행 |
| 3 | Mandatory drift 섹션 | **Prep #3** | Phase 4 CP4 review | 이행 |
| 4 | HNSW externalize | **이월** | Phase 5 | C-P3-D2 |
| 5 | Backup/DR 루틴 | **이월** | Phase 5 | C-P3-D3 |
| 6 | chunk_id regex 3자 합의 | **Prep #4** | Phase 4 pre-kickoff | 이행 (§1) |
| 7 | §6.5 NAMESPACE frozen 재확인 | **Prep #5** | Phase 4 이행 | 이행 |
| 8 | sha1[:12] 확장 | **폐기** | — | 재개 조건 = 운영 모니터링 트리거 |
| — | §9.5 추가 split 측정 | **Prep #6** | Phase 4 CP4 | Plan v2 §2 IN 에서 편입 |

### 0.2 Critic 선행 리스크 반영 (2026-04-22 DM pushback)

devils-advocate-critic 선제 리스크 제기 4건 ((a) PK-2 regex 3축 / (b-1) unknown 5% 임계 / (b-2) realized_annual 공식 / (b-3) ISQM 2 Scope 명시) 본 prep 에 반영. 각 근거 section:

| 리스크 | 근거 | 반영 위치 |
|---|---|---|
| (a) PK-2 regex 3축 | Critic DM "backward-compat / alternation order / separator safety" | §1.5 (3자 합의 절차) 하단 §1.7 Critic a1-a3 반영 |
| (b-1) unknown % 이중 gate | Phase 1 ISA baseline 0.053% vs 5% → 94.3× | §0.2.2 (신설) + §2.1 판정 기준 갱신 |
| (b-2) realized_annual 공식 | Plan v2 §5 row 2 미정의 | §0.2.1 (신설) |
| (b-3) ISQM 2 Scope 재확인 | Plan v2 §8 R1 + Critic "근거 URL 요청" | §0.3.3 Scope 외 + §2.3 확장 |
| (c) Mini Golden seed size 3안 | Critic Clopper-Pearson 분석 | §3 Mini Golden 3안 비교 (신설) |

### 0.2.1 `realized_annual_cache_invalidation` 공식 (Critic b-2 반영)

Critic DM 의 지적 "분자/분모 정의 선기재" 에 대응. **Option B 변형 채택**:

```
realized_annual_cache_invalidation
  = (Σ per-reparse chunk_affected_ratio)  ×  (365 / observation_window_days)

분자:
  per-reparse chunk_affected_ratio
    = (chunks_with_id_change / total_chunks_in_standard)
    per 재파싱 이벤트 별로 실측.  Phase 1 `source_idx` 재매핑 이력 / MD frontmatter diff 로 산출.

분모:
  observation_window_days
    = Phase 4 본체 기간 (4a~4f), 또는 3 DOCX 원본 revision 간격 실측 중 큰 값.

annualization:
  × (365 / window_days)  — 단순 선형 연환산.
  단일 관측만 존재 시 seasonality 보정 없음 → Phase 4f 에서 재조정 가능성 개방.
```

**해석 근거**:
- Phase 4 에서 **실측 재파싱 빈도 = 0~1 회** 예상 (주로 prep / 실적재 각 1회). 단일 관측 기반 threshold 은 불확실 → "200%" 자체도 heuristic 임을 §15a.1 각주 로 확인.
- Critic (b-2) 옵션 제시 중 Option A (monthly 가정 × 12) 는 bias 크고, Option C (N-DOCX 평균) 는 DOCX 간 등질성 가정 강함 → **Option B 단일 공식 선택**.
- Phase 4f 에서 실측 1건 이상 확보 시 200% 임계 자체 **재조정 가능성** 개방 (Critic 단일 관측 sample-size 약점 인정).

**재조정 규약**: CHECKPOINT 4 mandatory drift 섹션 (`docs/checkpoint_4_review.md §N C-P2-1 재평가 결과`) 에 `realized_annual = X%` 실측치 + 공식 적용 내역 필수 기록. 200% 근거가 약하다고 판정되면 **Phase 5 에서 임계 재조정 bump** (MINOR, 본 문서와 함께).

### 0.2.2 unknown_numbering 이중 gate (Critic b-1 반영)

Critic (b-1) 지적: Phase 1 ISA baseline = **0.053%** (6 / 11,267 실측) vs Plan v2 PK-4 gate 5% → **94.3× baseline** — catastrophic-only 수준. Phase 4a Exit gate 완화 위험.

**수정된 이중 gate** (본 prep 로 반영, Plan v2 §6 4a Exit gate 보완):

| Gate | 조건 | 조치 |
|---|---|---|
| **ABORT (HARD)** | 확장 `classify_kind` 후 unknown_numbering **≥ 5%** (기존 Plan v2 기준) | Phase 4a rework — classify_kind 추가 확장 또는 StandardSpec 분리 재검토 |
| **WARNING (SOFT, NEW)** | unknown_numbering **> 0.5% 또는 > 20건 (절대값)** | Phase 4a 진행 가능하나 **Domain Reviewer 수동 검수 의무** — 각 unknown 샘플 inspect, 의도적 unknown 인지 silent fallback 인지 판정 후 `docs/{isqm,assurance_other,framework}_structure_profile.md §N Unknown audit` 섹션에 기록 |
| **PASS** | unknown_numbering ≤ 0.5% **AND** ≤ 20건 | 별도 검수 없이 Phase 4b 진입 허용 |

**실측 계산 기준**:
- Phase 4a Exit gate 측정은 **classify_kind 확장본 기준**. 확장 전 (본 §2.1 표의 37.57% / 43.14%) 은 참고치.
- Phase 1 ISA 실측 baseline `6/11,267 = 0.053%` 은 `src/audit_parser/ir/numbering.py::NumberingEngine.metrics()` 결과 기준 — Phase 4 DOCX 도 동일 함수로 측정.

**적용 범위**: 3 DOCX 각각 독립 적용 (집계 아님). ISQM-1 이 0% 여도 FRMK 가 WARNING 이면 FRMK 만 수동 검수.

### 0.2.3 Mini Golden seed pool pre-draft 권고 (Critic c 반영)

Phase 4f Mini Golden 진입 전 seed 확장 가능성에 대비, **Domain Reviewer 는 Phase 4a Scout 시점에 seed pool 20~30건 pre-draft** 해두고 10건만 우선 사용. 추후 n=15 / n=20 확장 시 재발굴 부담 최소화.

Pre-draft 대상: 주 5 카테고리 (A 거버넌스 / B 위험평가 / C 모니터링 / D 참여감사인 / E 한영 혼재) + 확장 예비분 (F 세부 절차, G 용어 정의 lookup).

Seed final n 결정은 §3 (Mini Golden 3안 비교) + Task #10 진입 시점 team-lead 판정.

---

## 0.3 Freeze Point (Phase 4 착수 시점 스냅샷, PK-1)

**기준 commit**: `e1f2b90` (Phase 3 CHECKPOINT 3, schema v1.1.2)

### 0.3.1 현 프로젝트 상태 (Phase 3 종결 실측)

| 항목 | 값 | 근거 |
|---|---|---|
| Qdrant collection | `audit_standards_회계감사기준_2025` | PHASE_3_REPORT §7.1 |
| Qdrant points_count | **8,626** (chunks 8,590 + standard_summary 36) | PHASE_3_REPORT §7.1 |
| Qdrant indexed_vectors_count | **8,562** (v1.1.2 PATCH 후 17,252 → 8,562, −50.4%) | PHASE_3_REPORT §7.1 |
| Storage delta | ~137 MB 감소 (F1 zero-padding 제거) | PHASE_3_REPORT §5.5 |
| Embedder | Upstage Solar 4096d `.embed_cache.sqlite` 7,661 entries | PHASE_3_REPORT §3.4 |
| HNSW 파라미터 | `m=16, ef_construct=200` (모듈 상수, externalize 는 Phase 5 이월) | CP3 §4.1 |
| Backup/DR 루틴 | **미구현** (Phase 5 이월) | C-P3-D3 |
| JSON Schema 버전 | **v1.1.2** (36 ISA JSON in-place replace 완료) | json_schema §12 / §16 |
| pytest | **223 / 223 green** | PHASE_3_REPORT §7.1 |
| ruff / mypy --strict | clean (17 source files, Any 0건) | PHASE_3_REPORT §7.1 |

### 0.3.2 Phase 4 Scope (IN)

| 대상 DOCX | Collection | Standard ID prefix (§1 초안) |
|---|---|---|
| `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` | `audit_standards_품질관리기준서_2018` | `ISQM-1` (단일 standard) |
| `raw/역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문(개정개요 포함).docx` | `audit_standards_기타인증업무기준_2022` | `ASSR-3000` (ISAE 3000, 단일 standard — §2.2 실측 확정) |
| `raw/인증업무개념체계(2022년 개정)_전문.docx` | `audit_standards_인증업무개념체계_2022` | `FRMK` (단일 document, no number — §2.3 실측 확정) |

추가 작업:
- StandardSpec 추상화 (ISA / ISQM / FRMK / ASSR 4 spec, Phase 4b)
- v1.2 MINOR bump (chunk_id regex + standard_id pattern 확장 — §1)
- 36 ISA JSON `schema_version` in-place replace (1.1.2 → 1.2.0, re-embed 불필요)
- 회귀 fixture + CHECKPOINT 4 mandatory drift 섹션 (§0 Prep 3건)
- ISQM Mini Golden 10 seed × 5 카테고리 (Recall@5 / MRR)

### 0.3.3 Scope 외 (컨텍스트 오염 방지)

| 프로젝트 | 과제 | 상태 |
|---|---|---|
| `_IFRS_parsing` | Golden Dataset 재작성 | pending (별도 세션) |
| `_IFRS_parsing` | pgvector → Qdrant 마이그 | pending |
| `_IFRS_parsing` | AutoRAG 벤치 | pending |
| `_AuditStandard_parsing` | HNSW externalize (C-P3-D2) | **Phase 5 이월** |
| `_AuditStandard_parsing` | Snapshot CLI + Backup/DR (C-P3-D3) | **Phase 5 이월** |
| `_AuditStandard_parsing` | sha1[:12] 확장 | **운영 모니터링 트리거**로 축소 (premature optimization) |
| `_AuditStandard_parsing` | 언어별 파이프라인 분리 | **조건부 Phase 5** (Mini Golden 임계치 미달 시에만) |
| `_AuditStandard_parsing` | ISQM 2 한국어 번역본 | **KICPA 미제공** (2026-04-22 기준). Phase 5+ IAASB 원문 (2022 Handbook) 통합 검토 대상. Critic (b-3) 반영 — 번역본 확보 시점까지 별도 scope. |
| `_AuditStandard_parsing` | ISA 220 Revised | **KICPA 미제공** (2026-04-22 기준). Phase 5+ IAASB 2022 Handbook 통합 검토 대상. |
| `_AuditStandard_parsing` | ISQM 2 / ISA 220 Revised 별도 수록 | **본 Phase 4 대상 아님**. IAASB 공식 3개 독립 (ISQM 1 / ISQM 2 / ISA 220 Revised) 중 **ISQM 1 만** KICPA 2018년 번역본으로 수록 확인. 근거: `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` 단일 파일 실측 (PK-4 §2.2.1). IAASB handbook 공식 reference — `https://www.iaasb.org/publications/2022-handbook-international-quality-management-auditing-review-other-assurance-and-related-services-pronouncements` (Critic 요청 URL). |

### 0.3.4 원칙

**Phase 4 착수 후 위 "Scope 외" 과제는 본 문서에서 재참조 금지**. DM · 검수 발언 중 scope 외 항목 언급 시 Critic 이 "scope drift" 로 플래그.

Freeze point 변동 발생 시 (예: v1.1.3 emergency PATCH):
1. 본 §0.3 먼저 갱신 후 CHECKPOINT 4 로 가산
2. Prep 6-item 은 불변 (스코프 고정)
3. Critic cross-check DM 시 본 §0.3 commit hash 인용

---

## 1. chunk_id regex v1.2.0 합의 (PK-2) — ✅ **3자 합의 확정 (2026-04-22)**

> **Status**: ✅ **CONFIRMED** — Domain Reviewer 초안 (draft A) 에 Critic α 확장 + parser-implementer A3 (FRMK-1) 수정 병합 → 최종안 §1.3.4. Critic empirical cross-check (36/36 + 8,590/8,590) + parser-implementer 구현 가능성 PASS.
> **참조**: `docs/json_schema.md §6.1` (현 chunk_id 정의), `§12` (JSON Schema), `§15a.1.2` (Phase 4 확장 scope).
> **영향 범위**: json_schema §6.1 예문 + §12 `standard.standard_id.pattern` / `standard.standard_no.pattern` / `chunks.chunk_id.minLength`, `tests/fixtures/json_schema_v1_1.schema.json` → `json_schema_v1_2.schema.json`, `scripts/validate_json.py` drift gate, `src/audit_parser/ingest/md_parser.py` (정규식 없음 — standard_id 문자열 수용만 검증), `src/audit_parser/convert/md_renderer.py` (기존 `"ISA-{standard_no}"` 하드코딩 → `spec.format_standard_id(standard_no)`).

### 1.1 현행 v1.1.2 regex

- `standard.standard_id` pattern: `^ISA-\d{3,4}$`
- `chunks.chunk_id` minLength=1 (pattern 없음 — 구조적 검증은 `make_chunk_id` 함수 단위)
- `chunk_id` 문법 (사람 가독): `{standard_id}:{section}:{hash8}:{pid_or_fallback}[#{suffix_chain}]`

### 1.2 Phase 4 요구 — prefix 집합 확장

| Source DOCX | 합의안 `standard_id` | 사람 읽기 | 형식 근거 |
|---|---|---|---|
| `0. 회계감사기준 전문(2025 개정).docx` | `ISA-200` ~ `ISA-1200` | ISA 36 standards | v1.1.x 불변 |
| `3. 품질관리기준서1(2018년 제정)_국어전문.docx` | `ISQM-1` | **단일** | IAASB 공식 표기 (번호 1 단일) |
| `역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문...docx` | `ASSR-3000` | **단일** (ISAE 3000) | IAASB 공식 `ISAE 3000` 준용 + 문서내 9회 언급 실측 (§2.2) |
| `인증업무개념체계(2022년 개정)_전문.docx` | **`FRMK-1`** (최종안, parser-implementer A3 권고 채택) | **단일** (Assurance Framework). IAASB display name = "International Framework for Assurance Engagements" (번호 없음), internal identifier = `FRMK-1` (구조 균일) | 실질 single framework. internal `{PREFIX}-{number}` 균일 구조 준수 — display 는 `standard_title` 에 "인증업무개념체계 (2022)" 로 보존. 개정 시 `FRMK-2` 자연 확장. |

### 1.3 v1.2.0 regex — 최종안 (draft A + α + A3 병합)

> **최종안** (§1.3.4) 은 §1.3.1 draft A 를 baseline 으로 Critic α (`ISQM-\d{1,2}`) + parser-implementer A3 (`FRMK-\d`) 수정 병합한 결과. §1.3.1~§1.3.3 은 draft A 초안 보존 (이력).

#### 1.3.1 draft A — `standard.standard_id` pattern (초안, 이력)

```regex
^(ISA-\d{3,4}|ISQM-\d|ASSR-\d{3,4}|FRMK)$
```

**매칭 사례**:

| 입력 | match? | 비고 |
|---|---|---|
| `ISA-200`, `ISA-1200` | ✅ | v1.1.x 호환 |
| `ISQM-1` | ✅ | IAASB ISQM 1 |
| `ISQM-2` | ✅ (regex 허용) | 본 Phase 4 에는 포함 안 되나 Phase 5 ISQM 2 통합 여지 보존 |
| `ISA-220R` | ❌ | revised suffix 는 scope 외 — 필요 시 v1.3 MINOR bump |
| `ASSR-3000` | ✅ | ISAE 3000 |
| `ASSR-3410` | ✅ (regex 허용) | 향후 ISAE 3410/3420 등 통합 여지 |
| `FRMK` | ✅ | 번호 없는 framework |
| `FRMK-1` | ❌ | framework 는 단일, 번호 금지 (Critic cross-check 권고 예정) |

#### 1.3.2 `chunks.chunk_id` pattern (신설, 검증 목적)

```regex
^(ISA-\d{3,4}|ISQM-\d|ASSR-\d{3,4}|FRMK):[a-z_]+:[0-9a-f]{8}:[^#\s:]+(#\d+(#\d+)?)?$
```

**구성 요소**:
- prefix = `standard_id` (§1.3.1 재사용)
- section = `[a-z_]+` (closed enum §5.3 json_schema — 런타임 validate 는 enum 으로)
- hash8 = `[0-9a-f]{8}` (sha1[:8])
- pid_or_fallback = `[^#\s:]+` (예: `12.`, `A1.`, `bullet#37` 의 `bullet`, `table#1669` 의 `table`)
- optional suffix chain = `#\d+` (source_idx) + optional `#\d+` (chunk_index for split)

**주의**: pid_or_fallback 자체에 `#` 가 포함되는 `{kind}#{source_idx}` fallback (§6.4) 은 별도 alt 로 취급해야 하므로 regex 가 복잡해짐. v1.2.0 에서는 **chunk_id 는 pattern 강제 없이 minLength≥1 유지**, JSON Schema validation 은 prefix enum 으로만 잡는다 → regex 는 structural check (scripts) 전용.

**권고**: json_schema §12 `chunks.chunk_id` 는 minLength=1 유지, 별도 `scripts/validate_json.py` 가 위 regex 로 sanity check.

#### 1.3.3 backward compatibility

- v1.1.x 의 36 ISA JSON 은 모두 `ISA-\d{3,4}` prefix 로 시작 → v1.2.0 regex alt 첫 항목에 매칭.
- JSON Schema `const` / `pattern` 확장 = backward-compat MINOR (§2.2 정책 — "기존 enum 값 확장 = MINOR").
- v1.1.2 → v1.2.0 전이 시 `output/json/ISA-*.json` 재생성 불필요 (chunk_id / embedding 모두 불변).
- **Critic empirical cross-check (2026-04-22)**: draft A regex 를 36 ISA JSON 전수 적용 → `standard_id` **36/36 PASS**, `chunk_id` **8,590/8,590 PASS**, `#` suffix depth 분포 `{0: 4209, 1: 4379, 2: 2, 3: 0}` — byte-level backward compat empirical 확정.

#### 1.3.4 ✅ v1.2.0 최종안 (3자 합의 확정)

**`standard.standard_id` pattern**:

```regex
^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)$
```

**`standard.standard_no` pattern** (relax):

```regex
^\d{1,4}$
```

(이전 `^\d{3,4}$` → ISQM/FRMK 의 1-digit `"1"` 허용. ISA 는 여전히 3~4-digit 이므로 backward-compat 유지.)

**최종 매칭 사례**:

| 입력 | match? | 비고 |
|---|---|---|
| `ISA-200` ~ `ISA-1200` | ✅ | v1.1.x 호환, 36/36 empirical PASS |
| `ISQM-1` | ✅ | IAASB ISQM 1, Phase 4 Target |
| `ISQM-2`, `ISQM-10`~`ISQM-99` | ✅ (Critic α 확장 수용) | Phase 5 이월 ISQM 2 통합 여지 + 향후 확장 여유 — 비용 0 |
| `ISQM-100` (3-digit) | ❌ | v1.3 MINOR bump 시 재확장 |
| `ASSR-3000` | ✅ | ISAE 3000, Phase 4 Target |
| `ASSR-3410`, `ASSR-3400` 등 | ✅ (regex 허용) | 향후 ISAE 3410 통합 여지 |
| `FRMK-1` | ✅ (parser-implementer A3 채택) | Phase 4 Target, internal `{PREFIX}-{number}` 균일 |
| `FRMK` (no number) | ❌ | internal identifier 균일 규약 — display 는 `standard_title` 로 보존 |
| `FRMK-2`, `FRMK-9` | ✅ (regex 허용) | 향후 framework 개정 (2030+) 시 자연 확장 |
| `ISA-1`, `ISA-12345` | ❌ | `\d{3,4}` 경계 유지 — 의도된 거부 |
| `ISA-220R` | ❌ | revised suffix scope 외 — v1.3 MINOR bump 시 재확장 |
| `ISA`, `ISQM`, `ASSR`, `FRMK` (prefix only) | ❌ | prefix-only 입력 false-positive 거부 (Critic (2) pushback 수용) |
| `ASSR-300`, `ASSR-99999` | ❌ | ASSR 3~4 digit 경계 유지 |

**draft A 대비 변경점**:

| 구분 | draft A | ✅ 최종안 | 근거 |
|---|---|---|---|
| ISQM prefix | `ISQM-\d` | **`ISQM-\d{1,2}`** | Critic α — Phase 5 ISQM 3~99 확장 여유 확보, 비용 0 |
| FRMK prefix | `FRMK` (literal) | **`FRMK-\d`** | parser-implementer A3 — internal `{PREFIX}-{number}` 균일, `standard_no` 타입 일관성, 구현 단순화 |
| standard_no | `^\d{3,4}$` (기존) | **`^\d{1,4}$`** | ISQM-1 / FRMK-1 의 1-digit 수용 |

**최종안 채택 근거 요약**:
- 36 ISA + 8,590 chunks **backward compat 실측 PASS** (Critic cross-check)
- implementer: re.compile 1회 + fullmatch O(n), backtracking 리스크 0, 구현 단순 → **PASS**
- FRMK-1 채택으로 `md_renderer.py` / `md_parser.py` / chunk_id parsing 코드 경로 4 prefix 전부 `{PREFIX}-{number}` 단일화
- ISQM-\d{1,2} 로 Phase 5 확장 내성 확보 (IAASB ISQM 추가 발표 대비)
- Critic 의 "prefix-only false-positive 거부" 원칙 (ASSR / FRMK 단독 금지) 유지

### ~~1.4 Alternative draft B~~ (Critic (2) 명확 반대 — 폐기 확정)

draft B `^(ISA|ISQM|ASSR|FRMK)(-\d{1,4})?$` 는 **폐기**. Critic (2) 반대 근거 수용:
- `ISA`, `ISQM`, `ASSR` 등 **prefix-only false-positive** 가 실 payload 에 유입 시 Qdrant 검색 오염 위험 (prefix-only 식별자는 특정 standard 지시 불가)
- Draft A 의 false-negative (예: `ISA-1`) 는 현실 표준에 존재하지 않으므로 해로움 없음
- Critic 논거 수용: false-positive 는 silent bug, false-negative 는 loud failure — 전자가 압도적으로 해롭다

(전원 관련 cross-check 은 §1.5 기록)

### 1.5 3자 합의 절차 (완료)

| 주체 | 역할 | 상태 | 근거 |
|---|---|---|---|
| Domain Reviewer (나) | 초안 draft A 작성, 실측 근거 (§2) 제공, 최종안 §1.3.4 병합 | ✅ **승인** | 본 §1 |
| Parser Implementer | 구현 가능성 PASS (re.compile O(n), backtracking 0), `md_renderer.py` / `md_parser.py` / StandardSpec 영향 확인. **A3 제안 (FRMK-1)** 채택 | ✅ **승인** (2026-04-22 DM) | DM Part A — §A.1~A.7 |
| Devil's Advocate Critic | draft A empirical cross-check PASS (36/36 + 8590/8590). 3축 리스크 (§1.7) + β (§1.8) 합의. **Draft B 명확 반대**. Critic 후속 DM — **α 철회 (non-blocking, Phase 5 v1.3 bump 로 이월)** + **β 조건부 철회 (§9.4 docs 만 optional, chunk_splitter assertion guard 유지 지지)** | ✅ **Draft A 전면 승인** (2026-04-22 후속 DM) | DM §2 — "Draft A 원안 그대로 3자 합의" |

**α / β 철회 처리 (Critic 후속 DM 반영)**:
- **α (ISQM-\d{1,2})** — Critic 측 철회했으나 **parser-implementer (A.2) 도 독립 제안** + **team-lead 최종 승인 (2026-04-22)** 에 포함됨 → **최종안 §1.3.4 유지**. Critic 이 non-blocking 으로 철회해도 구현팀·lead 채택으로 잔존.
- **β (§9.4 docs boilerplate)** — Critic 조건부 철회 수용 → **optional 로 downgrade** (§1.8 반영). chunk_splitter assertion guard 는 Critic 지지 하에 6-file atomicity #5 에 유지.

**Critic scaffold 동기화 (2026-04-22)**: `docs/devils_advocate_checkpoint_4.md` sync pass 2회 완료.

**1차 sync** (PK-2 + PK-3 + PK-4 종결 시점):
- §1a — β 조건부 철회 + α 잔존 사유 + 36/36 / 8590/8590 / suffix depth 실측 증거 + FRMK-\d harmonization
- §3 — v1.2 atomicity 6-file 재구성 (PROLOGUE_SECTION 철회, SUB_ITEM ilvl=0 철회, chunk_splitter guard + standard_spec.py 추가, §3.3 정정 이력)
- §4 — Mini Golden 안 C + 카테고리 E n≥3 + seed pool 20-30
- §8 — PK-4 §2.2.2 격하 배너 반영
- §9 — drift 연환산 Option B 공식 + Phase 4 단일 관측 bias 인정
- §10 — ISQM 2 IAASB URL 인라인
- §12.4-12.6 — 원칙 #5/#6 + Self-audit 실수 2건 공식 기록
- §14 — cross-ref 인덱스 +5 ref (총 20+)

**2차 sync** (Phase 4a Scout 7-area cross-check 합의 종결 시점):
- **§1b 신설** — 7 영역 합의 종결 매트릭스 (1 HIGH + 2 MED + 3 LOW + 1 PASS 전수 수용) + 4b 분할 지지 + rework budget 현황 (Critic 2/2 보존, Reviewer 1/2 사용 — 대안 C 철회)
- **§3.0 갱신** — v1.2 atomicity 6-file 에 `special_appendix_name` 필드 추가 (§12 + §7.2.1a + ChunkRecord + 36 ISA JSON + FRMK spec `_frmk_extract_appendix`)
- **§4.3 신설** — Mini Golden F 카테고리 폐기 + B 재배치 (B6/B7) + Critic B8 편입 (self-review threat, ko-en)
- **§4.4 신설** — B8 편입 근거 (Critic §5.3 single-author bias 완화)
- **§4.5 신설** — Single-author bias 대응 protocol (Plan v2 §7.4 cross-check 의무) + CP4 진입 시 team-lead/user 주입 요청 DM 의무
- **§7.5 갱신** — CP4 anchor 3→4건 확장 (신규 #4: `special_appendix_name` payload 검증)
- **§11 신설** — Un-numbered 보론 대안 A/B-v1/B-v2/C 비교 + **B-v2 확정 채택** + 공동 credit 기록 (RAG UX 개선 부가 효과는 Reviewer cross-check 중 부수 발견 — Critic §11.6)

**Bidirectional 합의 최종 상태**: 7 영역 전수 합의, 대안 B-v2 채택, F 폐기 + B8 편입, 4b 분할 지지. 공통 유휴 복귀, team-lead 예산 판정 대기.

**합의 완료 선언**: 2026-04-22. 본 §1 상단 "✅ CONFIRMED" 표기 완료. 후속 hand-off:
1. `docs/json_schema.md §6.1 / §12 / §15a.1.2` 동기 bump — **Phase 4b parser-implementer 일괄 커밋** (§1.6 / §1.7 / §1.8 atomicity 6-file)
2. `src/audit_parser/convert/md_renderer.py` 하드코딩 `"ISA-{standard_no}"` → `spec.format_standard_id(standard_no)` 변경 — **Phase 4b StandardSpec refactor 범위**
3. `tests/test_standard_spec.py::test_standard_id_backward_compat` 표 (§1.7.1 기반) 구현

### 1.6 잔존 위험 — Phase 4 RAG 배포 후 MAJOR lock

CP2 §2 각주 + json_schema §2.2 footnote 재인용:

> Phase 4 RAG 서비스 deploy 후에는 `chunk_id` format 확장이 **항상 MAJOR**.

→ v1.2.0 regex 확장은 **Phase 4 적재 전** 에 commit 필수 (본 prep 의 원 목적). Phase 4c MD → 4d JSON 파이프라인 **시작 시점** 에 regex 확장본이 merged 되어야 하며, 이미 적재된 ISA 36 JSON 의 chunk_id 는 불변 유지 (backward-compat MINOR).

### 1.7 Critic 선제 3축 리스크 반영 (a1 / a2 / a3)

devils-advocate-critic DM 에서 제기한 regex 레벨 3 리스크 선행 반영.

#### 1.7.1 (a1) Backward-compat explicit test

draft A `^(ISA-\d{3,4}|ISQM-\d|ASSR-\d{3,4}|FRMK)$` 에 대한 36 ISA `standard_id` 전수 매칭 테스트 케이스 표 (Phase 4b 구현 시 `tests/test_standard_spec.py` 추가 대상):

| standard_id | draft A alt | 매칭 | 비고 |
|---|---|---|---|
| `ISA-200` | alt 1 (`ISA-\d{3,4}`) | ✅ | 기존 최소 3-digit |
| `ISA-450`, `ISA-500`, `ISA-720` | alt 1 | ✅ | 3-digit 전형 |
| `ISA-1100`, `ISA-1200` | alt 1 (`\d{3,4}`) | ✅ | 4-digit edge |
| `ISA-99` (가상) | alt 1 | ❌ | `\d{3,4}` 가 최소 3 강제 — 의도된 거부 |
| `ISA-12345` (가상) | alt 1 | ❌ | `\d{3,4}` 가 최대 4 강제 — 의도된 거부 |
| `ISQM-1` | alt 2 (`ISQM-\d`) | ✅ | Phase 4 Target |
| `ISQM-12` (가상) | alt 2 | ❌ | `\d` 단일 — Phase 5 (ISQM 2) 통합 시 ISQM-2 허용, 두자리는 v1.3 MINOR |
| `ASSR-3000` | alt 3 (`ASSR-\d{3,4}`) | ✅ | Phase 4 Target (ISAE 3000) |
| `ASSR-3410` (가상) | alt 3 | ✅ | 향후 ISAE 3410 통합 여지 |
| `FRMK` | alt 4 (`FRMK`) | ✅ | Phase 4 Target (no number) |
| `FRMK-1` (가상) | — | ❌ | alt 4 가 literal 만 매칭 — framework 단일 원칙 보장 |

**판정**: 36 ISA 기존 standard_id 전수 alt 1 매칭 → backward-compat 보장 (v1.1.x 데이터 migration 불필요). Phase 4b 구현 시 본 표를 `tests/test_standard_spec.py::test_standard_id_backward_compat` 로 고정.

#### 1.7.2 (a2) Alternation order (substring greedy 함정)

현 draft A 의 alt 4 종 (`ISA`, `ISQM`, `ASSR`, `FRMK`) 은 서로 **substring 관계 없음** → alternation order 무관. 단 Critic 가정 "향후 ISAE 추가 시 ISA 의 prefix 가 substring" 리스크 대비, **alt 추가 시 longer prefix 를 앞에 배치하는 규약 고정**:

```regex
# Phase 5+ 확장 규약 (예시, 미적용)
^(ISAE-\d{3,4}|ISRE-\d{3,4}|ISA-\d{3,4}|ISQM-\d|ASSR-\d{3,4}|FRMK)$
#  ↑↑↑↑                    ↑↑↑                    ↑↑↑
# ISAE 가 "ISA-" substring 충돌 → ISAE 앞에 배치
```

본 규약을 `docs/json_schema.md §15a.1.2 chunk_id regex 확장 scope 결정 절차` 에 병기 bump (v1.2.0 동반).

**현 상태 (v1.2.0)**: ISAE / ISRE / ISRS prefix 는 **scope 외** — Phase 5+ 통합 시 별도 bump 필요. 본 prep 에서는 규약만 기록.

#### 1.7.3 (a3) Separator safety (`:` / `#` 포함 금지)

`chunk_id` = `{standard_id}:{section}:{hash8}:{pid_or_fallback}[#{suffix_chain}]` 에서 `standard_id` 가 `:` 또는 `#` 를 포함하면 split 파싱 실패.

**draft A 검증**: 4 alt 모두 `[A-Z]` 와 `-\d+` (또는 literal `FRMK`) 로만 구성 → `:` / `#` 부재 보장. **Pass**.

**Phase 5+ 규약 (Critic a3 반영)**: 향후 alt 추가 시 반드시 `^[A-Z]+(-\d+)?$` 형태 유지. `:` / `#` / whitespace 포함 금지. `docs/json_schema.md §15a.1.2` 에 본 규약 명시.

### 1.8 Critic β — chunk_id suffix chain 2-level assertion guard (β-1 부분 채택)

> **Critic 후속 DM (2026-04-22)**: β 조건부 철회 — `json_schema §9.4` boilerplate 는 optional 로 분류 (chunk_splitter assertion 이 있으면 docs 문구는 중복). chunk_splitter runtime guard 는 유지 지지.
> **Domain Reviewer 최종**: assertion guard (#5) 는 v1.2 atomicity 6-file 에 유지, §9.4 docs 추가 (#1 중 §9.4) 는 **선택 사항** 으로 downgrade.

Critic β DM (초기안) 및 조건부 철회 DM 종합 — suffix chain `(#\d+(#\d+)?)?` 최대 2-level **assertion guard 채택**, 문서 boilerplate 은 선택.

**실측 분포** (Critic cross-check, 8,590 chunks):
- depth 0 (no suffix): 4,209 (48.9%)
- depth 1 (single `#<idx>`): 4,379 (50.9%)
- depth 2 (`#<source_idx>#<chunk_index>`): 2 (0.02%)
- depth 3+: 0

**β-1 확정 규약**:
1. `chunk_id` suffix chain **최대 2-level** — `(#\d+(#\d+)?)?` regex 유지 (§1.3.2 chunk_id sanity regex)
2. `chunk_splitter` 가 3-level 시도 시 **assertion fail 강제** (runtime guard) — **v1.2 atomicity #5 에 포함**
3. (optional) `docs/json_schema.md §9.4` 대형 table 분할 정책 에 다음 문구 추가 — **Critic 조건부 철회로 선택 사항. parser-implementer 재량**:
   > "chunk_id suffix chain **최대 2-level** (source_idx + chunk_index). 재분할 대상 chunk 가 이미 2-level suffix 를 가진 경우, **분할 금지 + warning 로그** → Domain Reviewer 수동 개입."

**β-2 (3-level 확장) 기각**: Critic 본인 β-1 선호 명시 + 실측 3-level 필요 0건 → 불필요한 복잡도 도입 회피. Phase 4 §9.5 추가 split 측정 시에도 2-level 내 충분 (`ISA-540:appendix:{h}:table#<idx>#<chunk_idx>`).

**β-3 (unbounded token) 기각**: Critic 본인 기각 ─ `assert_chunk_id_uniqueness` 책임 전가, regex structural check 의미 상실.

**v1.2 atomicity 확장 (Critic §4 scaffold §3 동기, Critic 조건부 철회 반영)**: Phase 4b parser-implementer 일괄 커밋 범위 — **6-file 유지, §9.4 boilerplate 만 optional**:
1. `docs/json_schema.md` §6.1 / §12 / §15a.1.2 (필수) + §9.4 β-1 boilerplate (optional, Critic 조건부 철회)
2. `tests/fixtures/json_schema_v1_1.schema.json` → `json_schema_v1_2.schema.json`
3. `src/audit_parser/ingest/types.py` `JSON_SCHEMA_VERSION = "1.2.0"`
4. 36 ISA JSON `schema_version` in-place replace
5. `src/audit_parser/ingest/chunk_splitter.py` 2-level assertion guard 추가 — **필수, Critic 지지**
6. `src/audit_parser/spec/standard_spec.py` (신규) — 4 spec + prefix format 함수

**※ Phase 4 classify_kind / BlockKind enum 변경은 §2.2.2 로 scope 분리 (parser-implementer Part B 재설계 권고 수용).**

---

## 2. 3 DOCX pre-scan (PK-4)

> **원본 스크립트**: `tmp/phase4_prescan.py` (재현 가능, SHA-bound)
> **상세 JSON 산출**: `tmp/phase4_prescan.json` (54 KB, 전수 abstractNum · style · 샘플 포함)
> **실행 커맨드**: `.venv/bin/python tmp/phase4_prescan.py`

### 2.1 요약 매트릭스 (본 문서 one-liner)

| 지표 | ISQM-1 | ASSR (ISAE 3000) | FRMK | ISA baseline 참고 |
|---|---:|---:|---:|---:|
| DOCX 크기 | 89 KB | 383 KB | 347 KB | 1,600 KB |
| body paragraphs | 3 | 86 | 52 | ~10,500 |
| table-cell paragraphs | **881** | 1,871 | 742 | 소수 |
| total corpus paragraphs | 884 | 1,957 | 794 | ~10,500 |
| tables | 3 | 12 | 14 | 74 |
| 최대 table 크기 | **244×1, 236×2** | 5×3 | 7×2 | 66×2 (ISA-1200) |
| abstractNums | 30 | 115 | 54 | 742 개 numId |
| direct-numPr numbered paragraphs | 130 | 567 | 204 | ~3,700+ (style-inherited 포함 ~5,400 chunk) |
| **direct unknown_numbering** | **0.00%** | **37.57%** | **43.14%** | ~0% (핵심 5 계열 완비) |
| core abstract {15,51,70,98,140} 존재 | 1 개 (15만) | 4 개 (140 없음) | 2 개 (15,51만) | 5 개 전수 |
| 한글 % | 67.83 | 71.58 | 73.28 | ~90 |
| 영문 (Latin) % | 1.18 | 1.74 | 1.61 | < 0.5 |
| bilingual paragraph samples (eye) | 8 | 8 | 8 | 거의 없음 |

### 2.2 파일별 실측 핵심

#### 2.2.1 ISQM-1 `3. 품질관리기준서1(2018년 제정)_국어전문.docx`

- **content locus = 거대 표 안** (244×1 header block + 236×2 body block). body paragraphs 3건은 표지/TOC 성격.
- **단일 standard** (`품질관리기준서1` 단어 2회 등장 — TOC 1 + 본문 heading 1)
- section keyword hits: `서론(2), 요구사항(2), 적용 및 기타 설명자료(2), 목적(1), 용어의 정의(1)` — ISA 와 **동일한 5-section 패턴** 을 따름 (ISQM 의 custom 섹션 아님).
- **direct unknown_numbering = 0%** — 5 계열 일부(`abstractNumId=15`) + 그 외 bullet 패턴만. **classify_kind 확장 불필요** (기존 fallback 내 OK).
- 단, **MD 렌더러는 table-cell paragraph 를 일반 paragraph 처럼 emit 해야 함** → `docx_reader.py` / `structure.py` 가 `inside_table` 플래그로 heading_trail 유지 필요. Phase 4a 산출물 `isqm_structure_profile.md` 에서 상세 명세 예정.
- Style 상위: `'' (760), Numbered Paragraph (69), Contents (26), Numbered paragraph (16), TOC Body (10)`. ISA 에 없는 English style names (`Numbered Paragraph`, `TOC Body`, `Contents`) 존재 → StandardSpec 에서 section-to-style 매핑 재정의 필요.

**판정**: Phase 4a Scout 에서 단일 spec (ISQM_SPEC) 으로 커버 가능, classify_kind 확장 **불필요**.

#### 2.2.2 ASSR `역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문(개정개요 포함).docx`

- **단일 standard = ISAE 3000** (Revised). DOCX 내 `ISAE 3000` 10회 등장, `ISAE3000` 1회 (space 없음). 다른 sub-standard (ISAE 3400, 3410, ISRS) **0건**.
- **개정개요 prelude** 가 문서 상단에 별도 섹션 (`개요 / 개정 배경 / 개정 기준서의 주요 내용 / 주요 개정 이슈` — upperRoman `I. II. III. IV.` 로 번호 부여).
- **direct unknown_numbering = 37.57%** (⚠ >5%) — 주요 원인:
  1. `abstractNumId=109, lvlText='%1.', numFmt=upperRoman` (개정개요 상위 4 항목)
  2. `(%1) decimal / lowerLetter / lowerRoman` 패턴 (`abstractNumId=18, 73, 108` 등) — 현 classify_kind 는 ilvl=0 에서 `(%1) lowerLetter` 를 unknown 처리.
- 핵심 abstractNum 중 **140 missing**, 51/70/98 present → 요구사항/적용지침 구조는 가져옴.
- Style 상위: `'' (1011), 바탕글 (853), List Paragraph (58), MS바탕글 (23)` — 한글 office 스타일 `바탕글` 등장. StandardSpec 에서 paragraph style 화이트리스트 확장 필수.
- 품질관리기준서 1 cross-reference 16건 — Phase 5 inter-collection link 후보.

> ⚠️ **Status: Phase 4b 참조용 초안 (즉시 구현 금지)**. team-lead 결정 (2026-04-22) 에 따라 Pre-Kickoff 에서 `classify_kind` 전역 수정 **배제**. 본 §2.2.2 전체는 **Phase 4b StandardSpec refactor 시점 참조용 초안**. parser-implementer 는 본 설계를 Phase 4a Scout 산출물 (`docs/{isqm,assurance_other,framework}_structure_profile.md`) 반영 후 Phase 4b 에서 일괄 구현. Domain Reviewer 는 Phase 4a Scout 에서 "개정개요 prelude skip 여부" 등 도메인 판단을 확정한 뒤 본 §2.2.2 를 참조용 초안 → 확정 명세로 승격.

**초안 판정** (Domain Reviewer 초안) — **철회**. parser-implementer DM Part B 의 3 이슈 제기 수용하여 **재설계 권고 채택**. 아래는 **Phase 4b 참조용 설계 초안**:

##### 2.2.2.1 parser-implementer 재설계 권고 (3 이슈 수용)

parser-implementer DM Part B.2 지적:

1. **Issue 1 — `(%1)` → `BlockKind.SUB_ITEM` 의미 왜곡**: 현 SUB_ITEM 정의는 "부모 번호 문단의 하위". ASSR `(%1) decimal` at ilvl=0 는 **독립 정의 항목** (heading_trail 상 `용어의 정의` 직접 자식). SUB_ITEM 재활용 시 semantic 왜곡.
   - **대안 (c) 채택**: `paragraph_id = "(1)"` 그대로 보존 + `kind = PARAGRAPH_BODY`. JSON Schema 변경 없이 chunk_id 에 자연 노출 `ISQM-1:definitions:{h}:(1)`.

2. **Issue 2 — `PROLOGUE_SECTION` 신설 전 skip 검토**: ASSR/FRMK 상단 `개요 / 개정 배경 / 주요 개정 내용 / 주요 개정 이슈` (upperRoman `I./II./III./IV.`) 는 **document "개정개요" preface 섹션 헤딩** — meta/prelude 성격, 본문 아님.
   - **parser-implementer 대안 채택**: `PROLOGUE_SECTION` enum 신설 철회 → **"개정개요" prelude skip** 규약 도입. ISA 00_전문.md skip 규약 (md_parser.py L246) 과 동일 패턴. `StandardSpec.prelude_skip_heading = "개정개요"` 주입형.
   - **결정 근거**: 개정개요는 "이 번 개정에서 뭐가 바뀌었는지" 서술 — 사용자가 **감사 실무 질의 시 검색 대상 아님**. meta 성격. skip 이 올바름.

3. **Issue 3 — ISA 회귀 리스크 LOW (실측 확인)**: parser-implementer DM 전수 grep 결과 ISA 36 MD 의 `paragraph_id = "(%1)"` 은 **ilvl ≥ 1 에서만 발생** (기존 SUB_ITEM 브랜치 포섭). **ISA 에 `(%1)` at ilvl=0 는 0건** → Phase 4 확장이 ISA 를 회귀 없이 확장 가능.

##### 2.2.2.2 Spec-aware classify_kind 설계 (Phase 4b 시점 구현)

parser-implementer DM Part B.4 설계 채택:

```python
# src/audit_parser/spec/standard_spec.py
@dataclass(slots=True, frozen=True)
class StandardSpec:
    prefix: Literal["ISA", "ISQM", "FRMK", "ASSR"]
    standard_id_regex: re.Pattern[str]
    section_enum: type[StrEnum]
    classify_kind: Callable[[str, NumFmt, int], BlockKind]  # 주입형
    prelude_skip_heading: str | None  # "개정개요" or None
    ...
```

- **`isa_spec.py`**: `classify_kind` = 현 `numbering.py::classify_kind` 함수 그대로 주입 (회귀 0)
- **`isqm_spec.py`**: 동일 (ISA 와 구조 유사, §2.2.1 실측 unknown 0%)
- **`assr_spec.py` / `frmk_spec.py`**: override —
  - `(%1)` decimal/lowerLetter/lowerRoman at ilvl=0 → `BlockKind.PARAGRAPH_BODY` + `paragraph_id = "(1)"` 보존
  - `upperRoman %1.` at ilvl=0 → prelude_skip_heading 매칭 시 **blocks skip** (md_parser 가 chunk 생성 안 함)
- **회귀 가드**: `tests/test_numbering.py` 에 ISA spec fixture 로 전수 테스트 유지. ASSR/FRMK 는 Phase 4a fixture 로 별도 case 추가.

##### 2.2.2.3 Pre-Kickoff 에서 확장 금지 (시점 수정)

Plan v2 §4 PK-4 "fallback 확장 선행" 조항을 **"Phase 4 진입 전"** 으로 해석 (parser-implementer DM §B.5 권고 수용). 구체 시점:

- **Pre-Kickoff 에서는 설계만** — 본 §2.2.2.1~.2 에 명세 고정 (현 문서)
- **Phase 4a Scout** 에서 `docs/{isqm,assurance_other,framework}_structure_profile.md` 에 classify 확장 + prelude skip 세부 규칙 확정
- **Phase 4b StandardSpec refactor** 시점에 실제 구현 (spec-aware classify_kind)
- **Phase 4c 진입 전** classify 확장본으로 3 DOCX pre-scan 재측정 → §0.2.2 3-tier gate 실측 확인

기존 초안의 "classify_kind 를 Pre-Kickoff 에 하드코딩 확장" 제안은 **철회**. Phase 4a Scout 단계에서 도메인 판단이 선행되어야 spec-aware 로 안전하게 구현 가능.

##### 2.2.2.4 확장 후 예상 unknown % (수정)

parser-implementer 대안 (c) + prelude skip 적용 후:
- ASSR: 37.57% → **≤ 5%** (기대). 주요 unknown `(%1) 각종` 7/10 샘플은 PARAGRAPH_BODY 로 해소, `upperRoman` 4건은 prelude skip 으로 chunk 제외.
- FRMK: 43.14% → **≤ 5%** (기대). 동일 원리.
- ISQM-1: 0.00% 유지 (영향 없음).

**판정**: Phase 4a Scout 완료 후 classify 확장 + prelude skip 적용본으로 **재측정 필수** — 실측 < 5% 확인 전까지 Phase 4c 진입 금지. §0.2.2 3-tier gate (ABORT / WARNING / PASS) 기준 일괄 적용.

#### 2.2.3 FRMK `인증업무개념체계(2022년 개정)_전문.docx`

- **단일 document** (number 없음). IAASB "International Framework for Assurance Engagements" 의 KICPA 번역.
- 품질관리기준서 1 cross-ref 4건, ISAE 3000 cross-ref 1건.
- **direct unknown_numbering = 43.14%** (⚠ >5%) — ASSR 과 동일 원인 (상위: upperRoman `%1.`, (%1) all numFmt).
- core abstract 중 {15, 51} 만 존재 — 적용지침 구조는 가져옴, **요구사항(70/98/140) 전부 missing**. FRMK 는 순수 개념 문서 → 요구사항이 없는 것이 정상.
- Style 상위: `'' (414), 바탕글 (298), List Paragraph (43), heading 2 (21)` — **`heading 2` 21건** → section 구조가 명시적 heading 2 로 표현됨 (ISA 와 유사). Phase 4a profile 에서 `heading 2` → Framework section enum 매핑 초안 필요.
- corpus size 794 paragraphs → ISA-200 규모의 10~20% 수준 (소형 문서).

**판정**: classify_kind 확장 + heading 2 기반 section 분류 로 충분. ASSR 과 동일 fallback 확장 공유.

### 2.3 ISQM 2 / ISA 220 Revised 공식 확정

- **Phase 4 대상 DOCX 3건은 모두 IAASB 기준 "단일 standard 또는 단일 framework"** (복수 sub-standard 없음).
- ISQM 2 (업무 품질관리 검토) 및 ISA 220 Revised 는 **KICPA 본 세트에 미포함** — IAASB 공식 3개 독립 문서 (ISQM 1 / ISQM 2 / ISA 220 Revised) 중 ISQM 1 만 2018년 번역본으로 수록.
- Phase 4 scope 에 ISQM 2 / ISA 220 Revised 추가 수록 **없음**. Plan v2 §8 R1 제거 사항과 일치.
- Phase 5 에서 향후 IAASB 업데이트판 통합 시 StandardSpec (ISQM_SPEC) 을 `^ISQM-\d$` regex (draft A) 로 그대로 수용 가능 — 2, 3 번호 확장 시 별도 bump 없음.

### 2.4 fallback 확장 작업 일정 권고 (parser-implementer DM §B.5 시점 수정 반영)

| 단계 | 작업 | 담당 | 소속 |
|---|---|---|---|
| ~~Phase 4a-pre~~ | ~~classify_kind 전역 하드코딩 확장~~ | — | **철회** (§2.2.2.3 시점 수정) |
| Phase 4a | 3 DOCX Scout & profile md 3건 + 확장 번호 매핑 검증 + **prelude skip heading 확정 (도메인 판단)** + **seed pool 20~30건 pre-draft** (§0.2.3) | Domain Reviewer | `docs/{isqm,assurance_other,framework}_structure_profile.md`, `tests/fixtures/phase4_profile_samples.json`, Mini Golden seed pool draft |
| Phase 4b-1 | StandardSpec dataclass (prefix / section_enum / **classify_kind 주입형** / prelude_skip_heading) + 4 spec (ISA/ISQM/ASSR/FRMK) 구현 | parser-implementer | `src/audit_parser/spec/standard_spec.py` + `{isa,isqm,assr,frmk}_spec.py` |
| Phase 4b-2 | md_parser / md_renderer / qdrant_writer StandardSpec 주입형 리팩터 + v1.2 MINOR bump 6-file atomicity (§1.8) | parser-implementer | Phase 4 Plan v2 §6 4b |
| Phase 4b-3 | ISA 36 re-parse byte 동등 + ASSR/FRMK unknown% 재측정 | parser-implementer | `output/md/ISA-*.md` unchanged assertion + 3 DOCX pre-scan v2 |
| Phase 4c | 3 DOCX → MD (3-tier gate 통과 확인 후) | parser-implementer | `output/md/{ISQM,ASSR,FRMK}*.md` |

**Exit gate (Phase 4b-3)**: classify_kind 확장본 (spec-aware) 기준 unknown_numbering 3-tier gate 판정 (§0.2.2):
- ABORT: ≥ 5% → rework 
- WARNING: > 0.5% 또는 > 20건 → Domain Reviewer 수동 검수 의무
- PASS: ≤ 0.5% AND ≤ 20건

WARNING / PASS 시에만 Phase 4c 진입 허용.

### 2.5 `tests/fixtures/phase4_profile_samples.json` 스키마 초안

Phase 4a 산출물 예정. 본 prep 에서는 예상 스키마만 고정:

```json
{
  "generated_at": "2026-04-22T...Z",
  "source_script": "tmp/phase4_prescan.py",
  "targets": {
    "ISQM-1": {"file": "...", "counts": {...}, "abstract_nums": [...], "style_inheritance": {...}},
    "ASSR":   {"file": "...", "counts": {...}, ...},
    "FRMK":   {"file": "...", "counts": {...}, ...}
  },
  "fallback_extension": {
    "added_patterns": [
      {"lvlText": "(%1)", "numFmts": ["decimal", "lowerLetter", "lowerRoman"], "ilvl": 0, "kind": "sub_item"},
      {"lvlText": "%1.",  "numFmts": ["upperRoman"],                            "ilvl": 0, "kind": "prologue_section"}
    ],
    "expected_unknown_pct_after": {"ISQM-1": 0.0, "ASSR": "<5", "FRMK": "<5"},
    "measured_unknown_pct_after": null
  }
}
```

Phase 4a 본체 작업에서 `measured_unknown_pct_after` 를 실값으로 치환.

---

## 3. Mini Golden seed size — 3안 비교 (Critic c 반영, Task #10 최종 결정 이월)

> **Status**: Pre-Kickoff 기록 목적. 최종 판정은 Task #10 (CP4 + Mini Golden) 진입 시점 team-lead + 사용자 결정으로 이월.
> **근거**: devils-advocate-critic DM "Mini Golden #3 — 3안 비교 제안".
> **동기화**: `docs/phase_4_plan.md §7.1` 의 seed 10 원안 + `docs/devils_advocate_checkpoint_4.md` scaffold §4 (Critic 소관).

### 3.1 통계 배경 (Clopper-Pearson 95% exact LB)

Plan v2 §7.3 임계 `Recall@5 ≥ 0.6` 에 대한 95% confidence lower bound:

| n | 관측 k/n | 점추정 | 95% LB | 임계 0.6 통과 |
|--:|:-:|--:|--:|---|
| 10 | 10/10 | 1.00 | 0.692 | ✓ (턱걸이) |
| 10 | 9/10 | 0.90 | 0.555 | ✗ |
| 10 | 8/10 | 0.80 | 0.444 | ✗ |
| 15 | 15/15 | 1.00 | 0.782 | ✓ |
| 15 | 14/15 | 0.93 | 0.681 | ✓ |
| 20 | 20/20 | 1.00 | 0.832 | ✓ |
| 20 | 18/20 | 0.90 | 0.683 | ✓ |

**핵심**: n=10 에서 단 1건 failure (9/10) 시 95% confidence 로 0.6 확증 실패. 점추정 0.9 는 pass 보이나 통계적으로 brittle.

### 3.2 3안 비교

#### 안 A — n=10 유지 (Plan v2 원안)

| 축 | 내용 |
|---|---|
| seed 수 | 10 (5 카테고리 × 2 평균) |
| 장점 | pre-kickoff 토큰 절약 / seed 작성 비용 최소 / ISQM 도메인 전문성 병목 최소 |
| 단점 | k=9/10 시 판정 모호 (점추정 PASS / 95% LB FAIL). Phase 5 분리 권고의 통계 근거 약화. |
| 적정 영역 | 점추정이 10/10 또는 ≤5/10 극단 — 중간 구간 brittle |

#### 안 B — n=15 상향

| 축 | 내용 |
|---|---|
| seed 수 | 15 (5 카테고리 × 3 평균) |
| 장점 | k=14/15 LB=0.681 → 1건 failure 내성. Phase 5 분리 권고 통계 근거 명확. 카테고리 E (한영 혼재) 가 n=3 확보. |
| 단점 | seed 작성 비용 +50%. Plan v2 §7.1 표 재작성 필요. |
| 적정 영역 | 판정 임계치 ±10% 구간에서 통계 해석 필요 시 |

#### 안 C — n=10 + 이중조건 판정 (Critic 선호)

```
Phase 4 통합 pipeline 유지 조건:
  - 점추정 Recall@5 ≥ 0.7  AND
  - 95% Wilson LB ≥ 0.5

Phase 5 분리 권고 조건:
  - 점추정 Recall@5 < 0.6  OR
  - 95% Wilson LB < 0.4

중간 (점추정 0.6~0.7 OR LB 0.4~0.5):
  - CONDITIONAL — seed 추가 10건 (총 n=20) 재측정
```

| 축 | 내용 |
|---|---|
| seed 수 (초기) | 10 (pool 은 20~30건 pre-draft 보유, §0.2.3) |
| 장점 | seed 비용 초기 동일. 이중조건으로 통계 엄격성 확보. CONDITIONAL 영역 명시 → brittle-pass 투명. |
| 단점 | 판정 flow 복잡. CP4 review 에 flow chart 필요. 카테고리 E n=1~2 는 통계 무의미 (이중조건 적용 불가, 점추정 해석만). |
| 적정 영역 | Phase 4 일정 보수 + Phase 5 분리 엄격성 양립 필요 시 |

### 3.3 Domain Reviewer 입장

- **안 C 동의 (Critic 선호 동조)** — pre-kickoff 부담 최소, 이중조건으로 통계 엄격성 확보. CONDITIONAL 영역 도입으로 brittle-pass 방지. Critic DM 논거 수용.
- **안 B 수용 여지** — Phase 4a Scout 에서 seed pool pre-draft 진행 시 (본 §0.2.3 반영) n=15 확장이 자연스럽게 용이해짐. 최종 결정 시점에 seed 작성 실비용 확인 후 재검토.
- **안 A 기각** — 3 DOCX 단일 Mini Golden 결과가 Phase 5 분리 결정의 sole ground truth 임을 고려할 때 브리틀-pass 위험 용납 불가.

**카테고리 E (한영 혼재) 보완**: 카테고리 E 는 본 Mini Golden 의 **핵심 측정 대상** (Plan v2 §7.1, §7.3 즉시 분리 권고 조건). n=1~2 에서 통계 무의미 → Critic 권고 "2회 연속 Recall@5 < 0.4" 로 격상 수용. 단, 카테고리 E seed 수를 **필수 3건 이상** 으로 고정 (안 C 채택 시에도).

### 3.4 최종 판정 이월

본 §3 은 기록만. 최종 결정 지점:
- **Task #10 (CP4 + Mini Golden)** 진입 시점
- 판정자: team-lead + 사용자
- Domain Reviewer 는 Phase 4a 단계에서 seed pool 20~30건 pre-draft 준비 (§0.2.3)
- Critic 은 `docs/devils_advocate_checkpoint_4.md §4` 에 scaffold 유지, Phase 4f 실측 후 v1 최종화

---

## 4. Cross-check 참조 (Phase 4 후속 작업 hand-off)

| 후속 산출물 | 본 prep 참조 section |
|---|---|
| `docs/isqm_structure_profile.md` (Phase 4a) | §2.2.1 + §0.3.2 ISQM-1 row |
| `docs/assurance_other_structure_profile.md` (4a) | §2.2.2 + classify_kind 확장 |
| `docs/framework_structure_profile.md` (4a) | §2.2.3 + heading 2 기반 section 초안 |
| `tests/fixtures/phase4_profile_samples.json` (4a) | §2.5 스키마 |
| Phase 4b v1.2 bump | §1 regex + json_schema §6.1/§12/§15a.1.2 동기화 |
| Phase 4f CHECKPOINT 4 mandatory drift 섹션 | §0 Prep #1, #2, #3, #6 |
| Phase 4f ISQM Mini Golden dataset | Plan v2 §7 + 본 §0.3.2 ISQM-1 collection row |
| Critic cross-check (Phase 4 pre-kickoff) | 본 문서 전수 (Critic DM pushback 결과 §1.5 에 반영) |

---

## 5. 검수 원칙 재확인 (Phase 1/2/3 교훈)

- **전수 스캔 재확인** — 본 §2 는 직접 python-docx 구동 실측 (session cache 재인용 금지). 재측정 시 `tmp/phase4_prescan.py` 단일 명령으로 완전 재현 가능.
- **timing-dependent 상태 재읽기** — Phase 4a/4b 진행 중 `tmp/phase4_prescan.json` 이 stale 이 될 수 있음. 4b 후 DOCX 원본 변경이 없다는 전제 하에 재실행 불필요, 단 변경이 의심되면 스크립트 재구동.
- **2 rework budget** — Phase 4 전체 기준. Pre-kickoff 내에서의 합의 실패 (§1 PK-2) 는 1 rework 소비.
- **파일 소유권 엄수** — 본 문서는 `audit-standard-domain-reviewer` 전용 (`docs/**`, `tests/fixtures/**`). `src/**`, `PLAN.md`, `CLAUDE.md` 는 쓰기 금지.

---

*End of `docs/checkpoint_4_prep.md` v1 draft. §1 PK-2 3자 합의 완료 시 상단 "확정" 표기 + commit. Phase 4a Scout 진입 조건: PK 4건 전부 완료 (§0, §0.3, §1 확정, §2 완료).*
