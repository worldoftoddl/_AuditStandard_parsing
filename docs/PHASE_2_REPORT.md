# Phase 2 완료 보고서 — MD → JSON

**기간**: 2026-04-21
**판정**: ✅ CHECKPOINT 2 PASS (FINAL, I1 해제) + Devil's Advocate GO
**팀**: `audit-parser-phase2` (Agent Teams, in-process)
**Schema**: `docs/json_schema.md v1.1.1`

---

## 1. 개요

Phase 1 산출물 `output/md/ISA-*.md` 37 파일을 Qdrant 적재 가능한 구조화 JSON (`output/json/ISA-*.json` 36 파일) 으로 변환. 임베딩은 Phase 3 담당, Phase 2 는 파싱·청킹·스키마 확정에 집중.

- `docs/json_schema.md` v1.0 → v1.1 → v1.1.1 3-step SemVer 진화
- F4 chunk_id 충돌 2-Pass 알고리즘으로 구조적 해결
- Phase 1 carry-over TOC leak (I1) 후속 fix
- MD ↔ JSON schema_version 독립 카운터 정책 수립

---

## 2. 팀 구성 및 협업 방식

| 역할 | 이름 | 소유 범위 | 권한 모드 |
|---|---|---|---|
| Leader | team-lead (main session) | 전체 조율 | default |
| Implementer | parser-implementer | `src/audit_parser/ingest/**`, `cli.py`, `pyproject.toml`, `tests/test_*.py`, `scripts/` | **bypassPermissions** |
| Domain Reviewer | audit-standard-domain-reviewer | `docs/**` | default |
| Critic | devils-advocate-critic | `docs/devils_advocate_checkpoint_2.md` | read-only |

Phase 1 에서 확립한 4인 구성 그대로. Implementer 는 초기부터 bypassPermissions 로 소환 (Phase 1 재소환 마찰 방지).

### 협업 실적

- **Critic 예비 증거 공유 방식** 도입 — Task #7 대기 중에도 설계 단계 결함(composite-key collision 2쌍 HIGH, 9 ISA 보론 패턴, sha1 충돌 확률 등)을 parser-implementer·Domain Reviewer 에 선제 DM 하여 스키마 확정 전에 반영
- Phase 1 F4 "3건 vs 6쌍" stale-claim 교훈을 전원이 자가 검증 절차로 체화 (Critic 의 "재읽기 재확인" 메타 교훈 → Phase 3 정착)
- 모든 팀원이 실측 증거(`grep`, 실행 수치) 중심 보고 유지

---

## 3. 구현 산출물

### 3.1 코드 (신규·수정 합계 ~2,000 LOC)

| 파일 | LOC | 역할 |
|---|---:|---|
| `src/audit_parser/ingest/types.py` | 130 | `StandardRecord`·`StandardSummary`·`ChunkRecord`·`ParagraphLink`·`ParsedStandard` frozen dataclass 5종 + `JSON_SCHEMA_VERSION` |
| `src/audit_parser/ingest/md_parser.py` | 937 | MD → `ParsedStandard` 역파싱 + 2-Pass chunk_id + Pass 3 splitter 통합 + TOC post-filter + MD schema fail-fast |
| `src/audit_parser/ingest/chunk_splitter.py` | 366 | 4000 토큰 초과 분할 (§9.4 ISA-1200 66×2 table row-wise + header 복제) |
| `src/audit_parser/cli.py` | — (+80) | `convert` C7 UNKNOWN exit-1, `ingest` / `ingest --single` 실구현 |
| `src/audit_parser/ingest/__init__.py` | 60 | public re-export |
| `scripts/validate_json.py` | 283 | 메트릭 수집 + `METRICS.json` 생성 |
| **합계** | ~1,856 | — |

### 3.2 문서

| 파일 | LOC | 작성자 |
|---|---:|---|
| `docs/json_schema.md` v1.1.1 | 1,113 | Domain Reviewer — 17 섹션 공식 스펙 |
| `docs/checkpoint_2_review.md` | 665 | Domain Reviewer — CP2 검수 + R6 addendum (I1-CLOSED) |
| `docs/devils_advocate_checkpoint_2.md` | 560 | Critic — 비판 10건 (HIGH 2 / MED 5 / LOW 3) + self-audit |
| `docs/f4_known_duplicates.md` | 191 | Domain Reviewer — F4 6쌍 (Phase 1 기 작성) + §4.2 RESOLVED |

### 3.3 테스트

| 파일 | 케이스 수 |
|---|---:|
| `tests/test_md_parser.py` | 49 (v1.1 MINOR 반영 + C-P2-5 4 + TOC filter 추가) |
| `tests/test_chunk_splitter.py` | 16 |
| `tests/test_cli.py` | 9 (C7 3 + ingest 5 + schema 1) |
| `tests/test_json_schema_compliance.py` | 7 (schema 6 + TOC leak regression 1) |
| `tests/fixtures/json_schema_v1_1.schema.json` | — (Draft 2020-12) |
| Phase 1 기존 | 101 |
| **합계** | **182 cases green** |

---

## 4. CHECKPOINT 2 검수 경과

### 4.1 Task #1 — json_schema.md v1.0 확정

17 섹션 881줄. MED 5건 (C4/C5/C7/C8/C11) 전수 반영. parser-implementer consultation 5건 (table_cells / chunk_id fallback / pipe escape / 00_전문 skip / part_of) 수용.

### 4.2 v1.0 → v1.1 MINOR bump — F4 composite key 실측 충돌 발견

Critic 예비 증거로 composite key `(standard_no, section, heading_trail_hash[:8], paragraph_id)` 가 F4 6쌍 중 **2쌍에서 실제 충돌** 확정 (ISA-300 `7.` idx 2237/2238, ISA-701 `4.` idx 8422/8427 — 둘 다 intervening heading 없이 heading_trail 동일).

**해결**: 2-Pass 알고리즘 채택.
- Pass 1: 기존 4-case 규칙으로 candidate chunk_id 생성 (99.96%)
- Pass 2: `Counter` 기반 중복 감지 → 전원 `#{source_idx}` suffix (first-only 금지, 결정론)
- `assert_chunk_id_uniqueness` runtime invariant (§6.2.1) 도입
- 부수 개선: `.strip()` canonical form (§6.2), 9 ISAs unnumbered 보론 (§7.2.1), ISA-1200 66×2 table 정책 (§9.4)

### 4.3 CHECKPOINT 2 검수 — CONDITIONAL PASS + I1 발견

Domain Reviewer 20-샘플 + F4 462건 의도성 판별 + null-section 104 합리성 검수.

| invariant | 결과 |
|---|---|
| schema_version "1.1" × 36 | PASS |
| chunk_id uniqueness 8,660 / 0-dup | PASS |
| F4 canonical 2 pair 4건 | PASS (MD 직접 확인) |
| paragraph_links 1,788 / 0 bad refs | PASS |
| 9 ISAs unnumbered 보론 appendix_index=1 | PASS |
| ISA-1200 3-part split (3340/3423/1807 tokens) | PASS |
| Phase 1 F1 회복 (requirement 1,161 / app_guide 1,788) | PASS |

**핵심 발견 — F4 suffix 실측 4,451** (METRICS 462 는 real-paragraph_id 한정 집계):
- 462 real-paragraph_id: 의도된 Pass 2 collision 해소 (sub_item 458 `(a)(b)(c)` + requirement canonical 4)
- 3,989 null-paragraph_id: §6.3 kind fallback + §6.4 Pass 2 side effect. spec 위반 없음이나 content drift risk
- worst cluster **201 members** (ISA-720 감사보고서 사례 paragraph_body)

**I1 ISSUE 발견** — "목차"/"문단번호" TOC leak 70 chunks, **35/36 ISA systematic** (Phase 1 md_renderer TOC 표 2×N 헤더 cell carry-over). N1 → I1 severity 승격, MINOR rework 요청.

### 4.4 I1 rework (parser-implementer, 1/2 rework budget)

`src/audit_parser/ingest/md_parser.py` 에 `_TOC_NOISE = {"목차", "문단번호"}` post-filter (kind=paragraph_body + section=None + content ∈ stopwords → drop).

**실측 delta 예측 8/8 정확 일치**:

| 지표 | 수정 전 | 수정 후 |
|---|---:|---:|
| chunks_total | 8,660 | 8,590 |
| section.&lt;null&gt; | 104 | 34 |
| kind.paragraph_body | 1,382 | 1,312 |
| F4 canonical pair | 4 | 4 (불변) |
| paragraph_links | 1,788 | 1,788 (불변) |
| chunk_id unique | 100% | 100% (불변) |
| schema validation | 36/36 | 36/36 (불변) |

**CP2 최종 판정: PASS (FINAL, I1 해제)**.

---

## 5. Devil's Advocate Task #7 — 비판 10건

영역 (a)-(j) 10/10 커버. **CONDITIONAL GO → GO** (MUST-FIX 해제 후).

| # | 영역 | 심각도 | 표제 | 조치 |
|---|---|---|---|---|
| C-P2-1 | (a)(d) | HIGH | F5 fallback chunk_id 46% `#{source_idx}` 의존 (4,451 suffix, 201-member cluster) | DEFER → Phase 3 v1.2 MAJOR 후보 |
| C-P2-2 | (f) | HIGH | TOC leak 35/36 ISA systematic | **= I1** 해결 완료 |
| C-P2-3 | (c) | MED | ISA-1200 header row 복제 bias | DEFER Phase 3 benchmark |
| C-P2-4 | (b) | MED | §2.2 SemVer semantic MAJOR vs practical MINOR | v1.1.1 §2.2 footnote |
| C-P2-5 | (h) | MED | MD@1.0 / JSON@1.1 schema_version drift | `MD_SCHEMA_SUPPORTED` fail-fast |
| C-P2-6 | (i) | MED | tiktoken vs Upstage tokenizer gap | DEFER Phase 3 |
| C-P2-7 | (g) | MED | 201-member cluster Qdrant filter | DEFER Phase 3 |
| C-P2-8 | (e) | LOW | sha1[:8] ISQM 1 통합 재평가 | DEFER (>10k trigger) |
| C-P2-9 | (j) | LOW | per-collection atomicity | DEFER Phase 3 |
| C-P2-10 | (j) | LOW | Named vector 설계 공백 | DEFER Phase 3 |

Critic self-audit: "9 ISA unnumbered 보론 리스트 1/9 정확 → reviewer 9 리스트가 정확" 공개 정정 포함. Phase 1 F4 stale-claim 재발 방지.

---

## 6. v1.1.1 PATCH bump

Critic Task #7 batch 3건 + 파생 2건 반영. docs + data 동시 bump.

| 변경 | 위치 |
|---|---|
| §2.2 SemVer footnote (chunk_id format 확장은 항상 MAJOR, Phase 4 deploy 후) | json_schema.md |
| §8.4 Idempotency 범위 한정 (ISA-720 201-member 실측 stem) | json_schema.md |
| §9.5 ISA-1200 header 중복 bias finding (Phase 3 측정 프로토콜 조건부 이월) | json_schema.md |
| §2.3 MD/JSON schema_version 독립 카운터 (`MD_SCHEMA_SUPPORTED`) | json_schema.md |
| `schema_version` in-place `"1.1" → "1.1.1"` (payload 바이트 동등) | 36 JSON |
| §12 JSON Schema const `"1.1.1"` | json_schema.md |
| `JSON_SCHEMA_VERSION = "1.1.1"` | types.py |
| 하드코딩 `"1.1"` 교체 (6 파일 8곳) | fixture / validate_json / tests |

**docs-only → data paragraph_version 동기화로 확장**. 재임베딩 불필요 (PATCH 정의 — payload 바이트 동등). Critic 검증 8/8 PASS.

---

## 7. 최종 품질 지표

### 7.1 실측 (METRICS.json 2026-04-21)

```json
{
  "files_total": 36,
  "schema_validation": {"total": 36, "passed": 36, "failed": 0},
  "schema_version_distribution": {"1.1.1": 36},
  "chunks_total": 8590,
  "kind_distribution": {
    "bullet": 2525, "application_guidance": 1788, "sub_item": 1722,
    "paragraph_body": 1312, "requirement": 1161,
    "block_quote": 58, "table": 18, "unknown_numbering": 6
  },
  "section_distribution": {
    "application": 4082, "appendix": 1861, "requirements": 1473,
    "intro": 323, "definitions": 263,
    "risk_response": 149, "conclusion_reporting": 113,
    "purpose": 100, "general_principles": 76, "risk_assessment": 63,
    "<null>": 34, "planning": 28, "engagement_acceptance": 21,
    "overall_objective": 4
  },
  "appendix_index_distribution": {
    "<null>": 6767, "1": 822, "2": 639, "3": 164, "4": 66, "5": 84, "6": 48
  },
  "token_estimate": {
    "count": 8590, "min": 2, "max": 3423, "mean": 97,
    "p50": 64, "p95": 285, "p99": 443
  },
  "paragraph_links_total": 1788,
  "chunk_id_uniqueness": {"global_unique": true, "duplicate_count": 0}
}
```

### 7.2 게이트

- pytest **182 / 182 green** (Phase 1 101 + Phase 2 81)
- ruff check (`src/` `tests/` `scripts/`) clean
- mypy --strict clean (15 source files, `Any` 0건)
- JSON Schema Draft 2020-12 전수 통과 (36/36, 0 errors)
- token_max **3,423 < soft_limit 3,500** (Solar 4000 토큰 상한 여유)

---

## 8. Phase 3 로 이월되는 이슈

### 8.1 Devil's Advocate DEFER 5건

| ID | 내용 | Trigger |
|---|---|---|
| C-P2-1 | content-sha1 fallback (v1.2 MAJOR 후보) | F5 3,989 null-pid suffix 실사용 영향 측정 후 |
| C-P2-3 | ISA-1200 header 복제 embedding bias | §9.5 프로토콜 실측 (10 seed query top-5 동시 출현 ≥30% 또는 cosine Δ<0.01) |
| C-P2-6 | tiktoken cl100k_base vs Upstage Solar 오차 | Phase 3 embedder.py 실측 |
| C-P2-7 | 201-member cluster Qdrant payload filter 성능 | Qdrant 실적재 후 latency 측정 |
| C-P2-8 | sha1[:8] 32bit 확장 | chunks_total 10,000 trigger (ISQM 1 통합 시) |

### 8.2 Phase 3 CP3 검수 scope (Domain Reviewer 제안 승인)

- §9.5 측정 프로토콜 — 10 seed query top-5 동시 출현 ≥30% 또는 cosine Δ<0.01 → v1.2 bump 판단
- Qdrant collection naming 검증 (`audit_standards_회계감사기준_2025` 등)
- payload 매핑 검증 (`json_schema.md` §13)
- §8.4 idempotency 추가 — incremental ingest 시 stale `source_idx` suffix 처리
- C-P2-9 per-collection atomicity

### 8.3 잔여 null-section 34건

I1 후 잔존 34건 = cross-ref block_quote 위주. 스펙 위반 아님. Phase 3 benchmark 시 표본 스캔 권고.

---

## 9. Phase 3 팀 소환 시 브리핑 필수 항목

1. `docs/PHASE_2_REPORT.md` (본 문서)
2. `docs/json_schema.md v1.1.1` §13 Qdrant payload 매핑 + §9.5 측정 프로토콜
3. `docs/checkpoint_2_review.md` §R6 addendum (I1-CLOSED)
4. `docs/devils_advocate_checkpoint_2.md` DEFER 5건 + Go/No-Go 체계
5. `output/json/ISA-*.json` 36 파일 실제 JSON (Phase 3 입력)
6. `output/json/METRICS.json` 수치
7. `docs/f4_known_duplicates.md` — F4 canonical 4 + 462 real-paragraph_id + 3,989 null-pid 분류
8. PLAN.md §4 Phase 3 Qdrant ingest 설계 (Upstage Solar / named vectors passage+summary / HNSW m=16 ef_construct=200)

---

## 10. 커밋 대상 파일

### 신규
- `docs/PHASE_2_REPORT.md` (본 문서)
- `docs/json_schema.md`
- `docs/checkpoint_2_review.md`
- `docs/devils_advocate_checkpoint_2.md`
- `src/audit_parser/ingest/{types,md_parser,chunk_splitter}.py`
- `scripts/validate_json.py`
- `tests/test_{md_parser,chunk_splitter,cli,json_schema_compliance}.py`
- `tests/fixtures/json_schema_v1_1.schema.json`

### 수정
- `docs/f4_known_duplicates.md` — §4.2 RESOLVED 마킹
- `src/audit_parser/cli.py` — convert C7 + ingest 실구현
- `src/audit_parser/ingest/__init__.py` — public re-export
- `pyproject.toml` — `jsonschema>=4.23` dev dep

### 제외 (gitignore 유지)
- `output/json/` — 파이프라인 산출물 (METRICS.json 포함)
- `raw/`, `output/md/`, `.env`, `.claude/`, `tmp/`

---

## 11. 다음 Phase

**Phase 3 — Stage 2b: JSON → Qdrant**. PLAN.md §4 Phase 3 에 정의.

### 준비 필요

- 현 Phase 2 팀 정리 (`TeamDelete` 예정, 본 커밋 후 사용자 승인 시점)
- Phase 3 신규 팀 소환 — parser-implementer(Phase 3 embedder/qdrant_writer), audit-standard-domain-reviewer, devils-advocate-critic
- Phase 3 브리핑에 §9 항목 모두 포함
- `docker compose up -d` 로 Qdrant 로컬 기동
- `.env` 에 `UPSTAGE_API_KEY` 설정 확인

### 주요 작업

- `embedder.py` — Upstage Solar passage/query, `.embed_cache.sqlite`
- `qdrant_writer.py` — Named vectors (passage + summary), HNSW m=16 ef_construct=200, payload 필드 매핑
- `cli.py ingest --upsert` — JSON → Qdrant 적재
- CHECKPOINT 3 검수 — 2단계 검색 데모 + idempotency + §9.5 bias 측정
- Devil's Advocate DEFER 5건 실측 평가
