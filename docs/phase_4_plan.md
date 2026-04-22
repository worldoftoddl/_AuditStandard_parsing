# Phase 4 Plan v2 — 승인 대기

**작성일**: 2026-04-22
**Freeze point**: Phase 3 commit `e1f2b90` (schema v1.1.2, Qdrant 8,626 points, pytest 223 green)
**상태**: 승인 대기 (사용자 4조건 반영 완료)

---

## 1. 목표

Phase 0~3 에서 완성된 파이프라인을 **ISA 외 3 DOCX** 에 일반화 적용. 회계감사 도메인 전체 커버리지.

### 대상 3 DOCX → Collection

| 원본 | Collection |
|---|---|
| `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` | `audit_standards_품질관리기준서_2018` |
| `raw/역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문(개정개요 포함).docx` | `audit_standards_기타인증업무기준_2022` |
| `raw/인증업무개념체계(2022년 개정)_전문.docx` | `audit_standards_인증업무개념체계_2022` |

---

## 2. Scope (IN / OUT)

### IN
- 3 DOCX → 3 신규 Qdrant collection 적재
- StandardSpec 추상화 (ISA / ISQM / FRMK / ASSR prefix 4종 통합)
- **v1.2 MINOR bump** (chunk_id regex + standard_id pattern 확장)
- 회귀 테스트 fixture (Phase 1~3 regression guard)
- §9.5 drift 추가 split 측정 (ISA-540 등 1건 이상)
- ISQM Mini Golden Dataset 5–10 seed (Recall@5 / MRR) 측정
- CHECKPOINT 4 mandatory drift 섹션 (C-P2-1 의무)

### OUT (Phase 5 이월)
- HNSW externalize (C-P3-D2) — env/config 설정화
- Snapshot CLI + Backup/DR 자동화 (C-P3-D3)
- 언어별 파이프라인 분리 (Mini Golden 임계치 미달 시)
- sha1[:12] 확장 — 운영 모니터링 트리거로만

### OUT (별도 프로젝트)
- `_IFRS_parsing` Golden Dataset / pgvector / AutoRAG 벤치 — 별도 세션

---

## 3. 팀 구성

| 역할 | 이름 | 소유 | 권한 |
|---|---|---|---|
| Leader | team-lead | 전체 조율 | default |
| Implementer | parser-implementer | `src/**`, `cli.py`, `tests/test_*.py`, `scripts/`, `notebooks/`, `docker-compose.yml`, `.env.example` | **bypassPermissions** |
| Domain Reviewer | audit-standard-domain-reviewer | `docs/**`, `tests/fixtures/**` | default |
| Critic | devils-advocate-critic | `docs/devils_advocate_checkpoint_4.md` | read-only |

Phase 3 팀(`audit-parser-phase3`) shutdown + `TeamDelete` → 신규 `audit-parser-phase4` 소환.

---

## 4. Pre-Kickoff (4-item, Phase 4a 진입 전 필수)

| # | Item | 책임 | 출력 |
|---|---|---|---|
| PK-1 | **§0.3 Freeze Point 문서화** | Domain Reviewer | `docs/checkpoint_4_prep.md §0.3` |
| PK-2 | **C-P3-D4 chunk_id regex 3자 합의** | Domain Reviewer + Implementer + Critic | `docs/checkpoint_4_prep.md §1` |
| PK-3 | **Prep 6-item 선기재** (v1 의 7-item 중 C-P2-8 제거) | Domain Reviewer | `docs/checkpoint_4_prep.md §0` |
| PK-4 | **3 DOCX pre-scan** (unknown_numbering ≥5% 발견 시 fallback 확장 선행) | Domain Reviewer | `docs/checkpoint_4_prep.md §2` |

### §0.3 Freeze Point 양식 (PK-1 산출)

```markdown
## 0.3 Freeze Point (Phase 4 착수 시점 스냅샷)

**기준 commit**: `e1f2b90` (Phase 3 CHECKPOINT 3, schema v1.1.2)

### 0.3.1 현 프로젝트 상태
- Qdrant collection: `audit_standards_회계감사기준_2025` (points 8,626 / indexed 8,562)
- Embedder: Solar 4096d, `.embed_cache.sqlite` 7,661 entries
- HNSW: `m=16, ef_construct=200` (Phase 5 이월)
- Backup/DR: **미구현** (Phase 5 이월)

### 0.3.2 Phase 4 Scope (IN)
- ISQM 1 / 기타인증업무 / 인증개념체계 3 DOCX → 3 collection
- StandardSpec + v1.2 MINOR bump
- ISQM Mini Golden + §9.5 추가 split 측정

### 0.3.3 Scope 외 (컨텍스트 오염 방지)
| 프로젝트 | 과제 | 상태 |
|---|---|---|
| `_IFRS_parsing` | Golden Dataset 재작성 | pending (별도 세션) |
| `_IFRS_parsing` | pgvector → Qdrant 마이그 | pending |
| `_IFRS_parsing` | AutoRAG 벤치 | pending |
| `_AuditStandard_parsing` | HNSW externalize / Snapshot CLI / sha1[:12] | Phase 5 이월 |

### 0.3.4 원칙
Phase 4 착수 후 위 "Scope 외" 과제는 본 문서에서 재참조 금지.
```

---

## 5. Prep 6-item (조건 3 — C-P2-8 제거)

1. C-P2-1 drift 연환산 빈도 기록 의무
2. `realized_annual > 200%` → v1.2 auto-trigger (측정만, bump 은 Phase 5 이월)
3. CHECKPOINT 4 mandatory drift 섹션
4. ~~HNSW externalize~~ — Phase 5 이월
5. ~~Backup/DR 루틴~~ — Phase 5 이월
6. chunk_id regex 3자 합의 (PK-2)
7. §6.5 NAMESPACE frozen 재확인
8. ~~sha1[:12] 확장~~ — **삭제** (충돌 1.8×10⁻⁷, premature optimization)

---

## 6. Implementation Phases

### Phase 4a — Scout & Profile (25–35k)

**목표**: 3 DOCX style_map 차이 프로파일링.

**산출**:
- `docs/isqm_structure_profile.md`
- `docs/assurance_other_structure_profile.md`
- `docs/framework_structure_profile.md`
- `tests/fixtures/phase4_profile_samples.json`

**Exit gate**: 프로파일 3건 + R1/R7 확정 + unknown < 5% (또는 fallback 확장 완료).

### Phase 4b — StandardSpec 추상화 + v1.2 MINOR bump (35–45k, **축소됨**)

**범위 (v1 대비 축소)**:
- ✅ StandardSpec dataclass (prefix / section enum / numbering rule / appendix policy 캡슐화)
- ✅ 4 spec: `ISA_SPEC`, `ISQM_SPEC`, `FRMK_SPEC`, `ASSR_SPEC`
- ✅ `md_parser.py` + `md_renderer.py` + `qdrant_writer.py` StandardSpec 주입형 리팩터
- ✅ schema v1.2 MINOR bump (§3 / §6.1 / §15a / §16)
- ✅ `JSON_SCHEMA_VERSION = "1.2.0"` + fixture const + 36 ISA JSON in-place replace
- ❌ **제외 (Phase 5 이월)**: HNSW externalize, Snapshot CLI

**산출**:
- `src/audit_parser/spec/standard_spec.py` + 4 spec 파일
- `docs/json_schema.md v1.2.0`
- `tests/test_standard_spec.py`

**Exit gate**: 36 ISA re-parse 바이트 동등 (cache 100% hit, 재임베딩 불필요).

### Phase 4c — 3 DOCX → MD (20–30k)

**산출**:
- `output/md/ISQM-<n>.md`
- `output/md/ASSR-<nnnn>.md`
- `output/md/FRMK.md`

**언어**: 한국어 본문 + 영어 용어 병기 그대로 (조건 4 — 분리 금지).

### Phase 4d — MD → JSON (15–25k)

**산출**:
- `output/json/ISQM-*.json`, `ASSR-*.json`, `FRMK.json`
- v1.2 schema validation 통과
- `tests/test_md_parser_phase4.py`

### Phase 4e — Qdrant 적재 (15–25k)

**collection**:
- `audit_standards_품질관리기준서_2018`
- `audit_standards_기타인증업무기준_2022`
- `audit_standards_인증업무개념체계_2022`

**HNSW**: `m=16, ef_construct=200` 하드코딩 유지 (Phase 5 이월).

### Phase 4f — CHECKPOINT 4 + Mini Golden 측정 (25–35k)

**3 trunk**:
1. CHECKPOINT 4 mandatory drift — §6 C-P2-1 재평가 + §9.5 ISA-540 추가 split
2. **ISQM Mini Golden** (조건 4) — 5–10 seed Recall@5 / MRR
3. Devil's Advocate + Go/No-Go Phase 5

**산출**:
- `docs/checkpoint_4_review.md`
- `docs/devils_advocate_checkpoint_4.md`
- `docs/PHASE_4_REPORT.md`
- `tests/fixtures/isqm_mini_golden_dataset.jsonl`
- `notebooks/phase4_retrieval_eval.ipynb`
- `output/phase4_mini_golden_results.json`

**Exit gate**:
- pytest Phase 1–4 전수 green
- 4 collection 독립 2-stage 검색 시연
- Mini Golden Recall@5 ≥ 0.6 **또는** MRR ≥ 0.5 (미달 시 Phase 5 분리 권고 기록)

---

## 7. ISQM Mini Golden Dataset 스펙 (조건 4)

### 7.1 카테고리 분산 (Critic 편향 방지)

| Category | Seed 수 | 예시 |
|---|---|---|
| A. 거버넌스 / 리더십 | 2 | "품질관리시스템 설계 시 최고 감사파트너의 책임 범위" |
| B. 위험평가 요소 | 2 | "ISQM 1 에서 요구하는 품질목적의 설정 절차" |
| C. 모니터링 / 개선 | 1–2 | "연도별 모니터링 활동의 평가 및 보고" |
| D. 참여감사인 | 1–2 | "감사참여팀 품질관리의 핵심요소" |
| E. **한/영 혼재** (핵심 측정) | 1–2 | "engagement quality review 와 EQCR 의 차이" |

### 7.2 스키마

```jsonl
{"query_id": "ISQM-MG-01", "query_text": "...", "category": "A", "expected_chunk_ids": [...], "expected_standard_ids": ["ISQM-1"], "lang_mix": "ko"}
```

### 7.3 Metric / 임계치

| Metric | 임계치 (Phase 5 분리 트리거) |
|---|---|
| Recall@5 | **< 0.6 → Phase 5 분리 권고** |
| MRR@10 | **< 0.5 → Phase 5 분리 권고** |
| 카테고리 E Recall@5 | < 0.4 → 즉시 분리 권고 |

### 7.4 프로토콜

1. 4e 적재 완료 후 `notebooks/phase4_retrieval_eval.ipynb` 실행
2. Stage1 summary top-3 → Stage2 passage top-5
3. 10 seed × Recall@5 / MRR → `output/phase4_mini_golden_results.json`
4. PASS 시: Phase 4 GO, 통합 파이프라인 유지
5. 미달 시: Phase 4 여전히 GO, **Phase 5 Split Recommendation** 섹션 기록

**Critic cross-check 의무**: 독립 재측정 + seed 편향 점검.

---

## 8. Risks (5건, v1 8건에서 축소)

| 심각도 | ID | 리스크 | 완화 |
|---|---|---|---|
| 🔴 HIGH | R2 | 3 DOCX style_map 차이 — StandardSpec 비용 폭증 | 4a pre-scan + 4b dataclass 경계 명확화 |
| 🟡 MED | R3 | v1.2 bump 동기화 실패 (4곳 in-place replace) | 4b 단일 commit + validate_json.py drift gate |
| 🟡 MED | R4 | 4 collection Qdrant 메모리 실측 (8,626 → 예상 15–18k points) | 4e 메모리 측정, 필요 시 scalar quantization 준비 |
| 🟡 MED | R5 | Mini Golden seed 주관 편향 | Critic cross-check + 5 카테고리 분산 |
| 🟢 LOW | R6 | C-P2-1 drift 200% 초과 시 Phase 4 내 재귀적 v1.2 scope 폭증 | 4f 측정만, bump 은 Phase 5 이월 |

**제거**:
- ~~R1 ISQM 2 sub-standard~~ — Scout 확정 (IAASB 공식 ISQM 1 / 2 / ISA 220 Revised 3개 독립)
- ~~R7 unknown_numbering > 5%~~ — PK-4 pre-scan 의무화
- ~~R8 Solar 한/영 저품질~~ — 측정 기반 (Mini Golden)

---

## 9. 토큰 예산

| Phase | 예산 |
|---|---|
| Pre-Kickoff | 10–15k |
| 4a Scout | 25–35k |
| 4b StandardSpec + v1.2 | **35–45k** (축소 반영) |
| 4c Parse | 20–30k |
| 4d MD→JSON | 15–25k |
| 4e Ingest | 15–25k |
| 4f CP4 + Mini Golden | 25–35k |
| **합계** | **135–175k** (원 예산 150–200k 수렴 ✓) |

**기간**: 5–7일.

**Fallback**:
- 4b StandardSpec 폭증 시 → ISA shim + ISQM spec 우선, ASSR/FRMK 는 4c 합류
- Mini Golden 미달 시 → Phase 4 GO 유지, Phase 5 분리 scope 이월

---

## 10. Open Questions (2건)

| # | Question | 처리 |
|---|---|---|
| Q1 | ISQM 한/영 혼재 — 분리 파이프라인 필요 여부 | **측정 기반** (4f Mini Golden) |
| Q3 | DOCX style_map 변이 — StandardSpec 4종 수렴 가능? | 4a pre-scan → 4b 설계 확정 |
| ~~Q2~~ | ~~sha1[:12] 확장~~ | **폐기** (premature optimization) |
| ~~Q4~~ | ~~ISQM 2 sub-standard~~ | **해소** (Scout 확정) |

---

## 11. Phase 3 이월 이슈 재분류

| ID | 항목 | v1 처리 | **v2 처리** |
|---|---|---|---|
| C-P3-D1 | Security LOW | Phase 4 문서화 | 유지 |
| **C-P3-D2** | HNSW externalize | 4b 편입 | **Phase 5 이월** |
| **C-P3-D3** | Backup/DR | 4b 편입 | **Phase 5 이월** |
| C-P3-D4 | chunk_id regex 확장 | Pre-Kickoff | **유지 (PK-2)** |

---

## 12. Critical Files

구현 대상:
- `src/audit_parser/spec/standard_spec.py` (신규, 4b)
- `src/audit_parser/spec/{isa,isqm,assr,frmk}_spec.py` (신규, 4b)
- `src/audit_parser/ingest/md_parser.py` (4b StandardSpec 주입)
- `src/audit_parser/ingest/qdrant_writer.py` (4b + 4e)
- `src/audit_parser/ingest/types.py` (v1.2.0 bump)
- `docs/json_schema.md` (§3 / §6.1 / §15a / §16 v1.2 동기화)

신규 문서:
- `docs/checkpoint_4_prep.md` (Pre-Kickoff)
- `docs/{isqm,assurance_other,framework}_structure_profile.md` (4a)
- `docs/checkpoint_4_review.md` (4f)
- `docs/devils_advocate_checkpoint_4.md` (4f)
- `docs/PHASE_4_REPORT.md` (4f)
- `tests/fixtures/isqm_mini_golden_dataset.jsonl`
- `notebooks/phase4_retrieval_eval.ipynb`

---

## 13. 승인 후 즉시 착수 순서

1. Phase 3 팀 shutdown 3명 → `TeamDelete`
2. `audit-parser-phase4` 팀 소환 (team-lead + parser-implementer bypass + domain-reviewer + devils-advocate-critic)
3. Pre-Kickoff Task 4 생성 + 의존성 설정
4. Domain Reviewer PK-1 §0.3 Freeze Point 착수 → PK-2 regex 합의 → PK-3 Prep 6-item → PK-4 pre-scan
5. PK 4건 완료 후 4a Scout 진입
