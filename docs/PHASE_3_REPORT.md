# Phase 3 완료 보고서 — JSON → Qdrant

**기간**: 2026-04-21 ~ 2026-04-22
**판정**: ✅ CHECKPOINT 3 PASS (CONFIRMED) + Devil's Advocate **GO**
**팀**: `audit-parser-phase3` (Agent Teams, in-process)
**Schema**: `docs/json_schema.md v1.1.2`

---

## 1. 개요

Phase 2 산출물 `output/json/ISA-*.json` 36 파일을 Upstage Solar 4096d 임베딩 후 Qdrant 벡터 DB(`audit_standards_회계감사기준_2025`) 에 적재. 파이프라인 **최종 검색 가능 상태** 완성.

주요 결정사항:
- Per-point named vectors (F1 v1.1.2 PATCH) — zero-vector padding 제거로 indexed_vectors 50.4% 감축
- `_truncate_for_summary_embedding` runtime surgical fix (ISA-200/1200 summary HARD_LIMIT 초과 대응, payload full 유지)
- §6.5 NAMESPACE_URL → NAMESPACE_DNS 사실 교정 (reproducibility hazard 해소)
- Solar/tiktoken cumulative ratio 0.5114 확정 (C-P2-6 soft_limit 축소 불필요)

---

## 2. 팀 구성

| 역할 | 이름 | 소유 범위 | 권한 |
|---|---|---|---|
| Leader | team-lead (main session) | 전체 조율 | default |
| Implementer | parser-implementer | `src/audit_parser/ingest/**`, `cli.py`, `tests/test_*.py`, `scripts/`, `notebooks/`, `docker-compose.yml`, `.env.example` | **bypassPermissions** |
| Domain Reviewer | audit-standard-domain-reviewer | `docs/**`, `tests/fixtures/**` | default |
| Critic | devils-advocate-critic | `docs/devils_advocate_checkpoint_3.md` | read-only |

협업 특이점:
- **Critic 선제 DM 프로토콜** Phase 2 에서 검증된 방식 재사용 — 설계 단계에서 HIGH 이슈(F1 zero-vector, §6.5 fact error) 포착·반영
- **4-anchor cross-check 프로토콜** Domain Reviewer ↔ Critic 간 수치 교차 검증 (3,919 / 679 / 201 / 51)
- **timing-dependent 상태 재읽기 원칙** Phase 2 교훈 체화 — Critic Security HIGH 주장 self-audit 후 LOW 정정

---

## 3. 구현 산출물

### 3.1 코드 (신규·수정 합계 ~1,750 LOC)

| 파일 | LOC | 역할 |
|---|---:|---|
| `src/audit_parser/ingest/embedder.py` | 583 | Upstage Solar 4096d passage/query + SQLite WAL 캐시 + retry 3회 + integrity_check 자동 rebuild |
| `src/audit_parser/ingest/qdrant_writer.py` | ~620 | Per-point named vectors + HNSW `m=16 ef_construct=200` + 25 payload + RFC4122 DNS UUID5 + `_truncate_for_summary_embedding` |
| `src/audit_parser/cli.py` | +146 | `convert --unknown-threshold` C7 exit-1, `ingest --upsert/--collection/--batch-size/--dry-run/--prune-stale` 10 플래그 |
| `src/audit_parser/ingest/__init__.py` | 60 | public API re-export |
| `src/audit_parser/ingest/types.py` | +8 | `JSON_SCHEMA_VERSION = "1.1.2"` |
| `scripts/validate_json.py` | 283 | schema validation + 메트릭 수집 |
| `notebooks/search_test.ipynb` | 21 cells | 2단계 검색 데모 + §9.5 header bias 측정 |

### 3.2 문서 (신규·수정 합계 ~2,700 LOC)

| 파일 | LOC | 작성자 |
|---|---:|---|
| `docs/json_schema.md` v1.1.2 | 1,174 | Domain Reviewer — §6.5 NAMESPACE fact fix + §6.5.1 reproducibility hazard 경고 + §15a v1.2 Candidates + §16 Changelog |
| `docs/checkpoint_3_prep.md` | 591 | Domain Reviewer — 10 seed query A/B/C/D/E 카테고리 + 201-member stratified + Appendix A/V1/V2 |
| `docs/checkpoint_3_review.md` v3 | 576 | Domain Reviewer — 7-point F1 PATCH 재검증 + Critic cross-check v2 → v3 |
| `docs/devils_advocate_checkpoint_3.md` | 399 | Critic — 10 critique area + 4-block critique + self-audit 2건 + GO 판정 |

### 3.3 테스트

| 파일 | 케이스 수 |
|---|---:|
| `tests/test_embedder.py` | 18 (cache WAL / integrity / retry / check_same_thread) |
| `tests/test_qdrant_writer.py` | 16 (live Qdrant, per-point vectors, RFC4122 namespace) |
| `tests/test_cli.py` | +7 (Phase 3 ingest 플래그, 총 16) |
| `tests/test_json_schema_compliance.py` | 7 (v1.1.2 schema + TOC leak regression) |
| Phase 1/2 유지 | 182 |
| **합계** | **223 cases green** |

### 3.4 운영 산출물 (gitignore)

- Qdrant collection `audit_standards_회계감사기준_2025` (named volume `audit_qdrant_storage`)
- `.embed_cache.sqlite` (SQLite WAL, 7,661 entries)
- `output/json/EMBED_METRICS.json` + `EMBED_METRICS.idempotency.json`
- `output/search_demo_results.json`

---

## 4. CHECKPOINT 3 검수 경과

### 4.1 Task #1 환경 확인

- Qdrant 기동(qdrant/qdrant:1.17.1), named-vector 4096d smoke test PASS
- `.env` UPSTAGE_API_KEY 실값 확인
- 의존성 전수 importable
- Docker Desktop WSL integration deviation 1건 → named volume 우회 승인

### 4.2 Task #2 embedder.py (parser-implementer plan 승인)

Critic 선제 DM 5건 전수 반영:
- **F1 (summary 중복)** → 별도 kind='standard_summary' point + zero-vector 슬롯 채택 (이후 v1.1.2 PATCH 에서 per-point 로 전환)
- **F2 (HNSW 벤치)** → `HNSW_M=16, HNSW_EF_CONSTRUCT=200` 모듈 상수 유지 (Phase 4 DEFER)
- **F3 (UUID namespace)** → RFC 4122 DNS `6ba7b810-9dad-11d1-80b4-00c04fd430c8` 명시
- **F4 (SQLite WAL)** → `PRAGMA journal_mode=WAL` + `integrity_check` 자동 rebuild + 원본 백업
- **보안 (127.0.0.1 binding)** → `docker-compose.yml` port 제한

### 4.3 Task #5 실적재

- **Collection**: `audit_standards_회계감사기준_2025`
- **Points**: 8,626 (chunks 8,590 + standard_summary 36)
- **Initial ingest**: 789.8s / Idempotency 재실행 352.1s (api_calls=0, cached_hits=8,626, payload_drift=0)
- **Runtime surgical fix**: `_truncate_for_summary_embedding` (ISA-200 6,224 tokens → 3,950, ISA-1200 8,772 → 3,950). 임베딩 입력만 절삭, payload full 유지.

### 4.4 Task #6 search_test.ipynb 실제 실험

사용자 직접 실행 → feedback "왜 이렇게 빨라?" (정상: Qdrant HNSW ms 단위 + query cache hit).

2단계 검색 시연:
- Stage1 `summary` top-3 = `[ISA-550, ISA-1200, ISA-1100]`
- Stage2 ISA-550 `passage` top-1 score 0.5604 "새롭게 식별된 특수관계자 … 실증감사절차"

**§9.5 ISA-1200 header 복제 bias**:
- Cond A co-occurrence: 0/10 = 0% (< 30% 임계)
- Cond B avg cosine Δ: 0.2046 (> 0.01 임계)
- Verdict: **PASS (v1.2 bump 불필요)**

### 4.5 CHECKPOINT 3 검수 (Domain Reviewer v3)

| invariant | 결과 |
|---|---|
| 4-Anchor cross-check (3,919 / 679 / 201 / 51) | **ALL MATCH** |
| 구조 검수 5/5 | **PASS** (naming, payload, idempotency, atomicity, §8.4 경계) |
| DEFER 5건 실측 | **4 PASS + 1 REPORT** (C-P2-1 drift 42.64% REPORT-only, Phase 4 재평가) |
| Invariants I-a~I-e | **5/5 PASS** |
| §9.5 header bias (독립 재측정) | **PASS** (소수점 6자리 Implementer 일치) |

**판정**: PASS (CONFIRMED by Critic cross-check)

### 4.6 신규 발견 → v1.1.2 PATCH

1. **F1 Named-vector zero-padding** — 8,590 chunk의 summary slot + 36 summary의 passage slot 모두 zero vector (500 sample all magnitude 0.0). indexed 17,252 중 50% 무의미. ~137MB 저장 낭비
2. **§6.5 NAMESPACE_URL 사실 오류** — 문서에 `uuid.NAMESPACE_URL` 기재, 실 구현 `NAMESPACE_DNS`. 한 hex digit 차이 (`6ba7b810` vs `6ba7b811`) → 외부 컨슈머 spec 기반 구현 시 point.id 전량 mismatch (reproducibility hazard)
3. **C-P2-1 F5 drift 실측** — trimmed mean 42.64% (max ISA-720 73.8%, min ISA-530 13.5%)

---

## 5. v1.1.2 PATCH bump — 3-block 묶음

### 5.1 Block A — F1 per-point named vectors (parser-implementer Task #9)

- `qdrant_writer.py` upsert 로직 변경: `vector={"passage": passage_vec}` or `vector={"summary": summary_vec}` 단일 슬롯
- `_ZERO_VECTOR` 상수 제거
- Qdrant collection 재생성 + 재적재 (cache hit 100%, API 비용 0)

### 5.2 Block B — §6.5 NAMESPACE fact fix (Domain Reviewer)

- `docs/json_schema.md §6.5` `NAMESPACE_URL` → `NAMESPACE_DNS` 교정 + 상수값 `6ba7b810-9dad-11d1-80b4-00c04fd430c8` 명시
- **§6.5.1 신설** — reproducibility hazard 경고, UUID 표, 외부 컨슈머 실사용 시나리오
- Frozen constant 경고 + v2.0 MAJOR trigger

### 5.3 Block C — C-P2-1 drift upper-bound 기록

- `docs/checkpoint_3_review.md §4.1` upper bound + 4요소 realized ratio 함수
- `docs/json_schema.md §15a` F5 row 연환산 > 200% 자동 v1.2 bump trigger 편입

### 5.4 v1.1.2 전파

- `src/audit_parser/ingest/types.py` `JSON_SCHEMA_VERSION = "1.1.2"`
- `tests/fixtures/json_schema_v1_1.schema.json` const `"1.1.2"`
- `scripts/validate_json.py` drift gate
- `output/json/*.json` 36 파일 in-place string replace (payload 바이트 동등)
- `docs/json_schema.md §12` const `"1.1.2"`, §16 Changelog 7-bullet

### 5.5 F1 재검증 (Domain Reviewer 7-point)

| # | Anchor | Expected | Measured | Result |
|---|---|---:|---:|---|
| 1a | 500-chunk summary slot 존재 | 0 | 0 | PASS |
| 1b | 500-chunk passage magnitude=0 | 0 | 0 | PASS |
| 2a | 36-summary passage slot 존재 | 0 | 0 | PASS |
| 2b | 36-summary summary magnitude=0 | 0 | 0 | PASS |
| 3a | `indexed_vectors_count` | ≤8,626 | **8,562** | PASS (-50.4%) |
| 3b | `points_count` | 8,626 | 8,626 | PASS |
| 4 | Storage delta | ~137 MB | ~135.83 MB | INDIRECT (docker socket 권한 부재, 3-축 보강) |
| 5A-C | HNSW slot 독립성 (Critic 권고) | 0 contamination | 0/10/10/50 | PASS |
| 6 | `embedded_at` re-ingest | 2026-04-22 | 03:41-03:59Z | PASS |
| 7 | 2회차 idempotency | drift=0 | drift=0 | PASS |

---

## 6. Devil's Advocate Task #8 — 10 critique + GO 판정

| 영역 | 건수 | 심각도 | 상태 |
|---|---:|---|---|
| (a) HNSW 파라미터 튜닝 근거 | 1 | MED | Phase 4 DEFER |
| (b) 4096d cosine 메모리 | 1 | LOW | 실측 완료 |
| (c) SQLite WAL 동시성·손상 | 1 | LOW | 실측 완료 |
| (d) UUID5 stable hash | 1 | LOW | §6.5 fact fix 로 해소 |
| (e) Solar rate limit | 1 | LOW | retry 3회 backoff 확인 |
| (f) Named vector 2종 trade-off | 1 | MED | F1 PATCH 로 해소 |
| (g) DEFER 해석 + v1.2 bump 경계 | 1 | LOW | §15a 7-row 확정 |
| (h) Phase 4 collection 충돌 | 1 | MED | Phase 4 DEFER |
| (i) Qdrant 백업 전략 | 1 | MED | **C-P3-D3** Phase 4 전 정의 |
| (j) `.env`/port 보안 | 1 | **LOW 철회** | docker-compose 127.0.0.1 binding 이미 구현 확인 (Critic self-audit) |

**Severity 집계**:
- HIGH 0건 (blocker 없음)
- MED 2건 — C-P3-D2 HNSW 하드코딩 / C-P3-D3 Backup/DR
- LOW 2건 — C-P3-D1 Security INFO / C-P3-D4 chunk_id regex Phase 4 확장

**Critic self-audit 2건**:
- Security HIGH → LOW 정정 (timing-dependent 재읽기 원칙 위반 교훈)
- 679 stem 오해석 정정 (multi 480 + single 199 = 679 unique total)

**판정**: **GO** (Phase 4 진입 가능).

**Phase 4 Pre-Kickoff 필수 1건**: C-P3-D4 chunk_id regex scheme 3자 합의 (Domain Reviewer + Parser Implementer + Critic).

**Phase 4 Prep 7-item**:
1. C-P2-1 연환산 drift frequency 기록 의무
2. realized_annual > 200% 자동 v1.2 bump trigger
3. CHECKPOINT 4 mandatory drift 섹션
4. HNSW 파라미터 설정화 (env/config)
5. Backup/DR 루틴 정의
6. chunk_id regex 3자 합의
7. §6.5 NAMESPACE frozen 재확인

---

## 7. 최종 품질 지표

### 7.1 수치

| 지표 | 값 |
|---|---|
| pytest | **223 / 223 green** |
| ruff / mypy --strict | clean (17 source files, Any 0건) |
| JSON Schema v1.1.2 validation | 36/36 pass (Draft 2020-12) |
| Qdrant points_count | 8,626 (chunks 8,590 + summary 36) |
| Qdrant indexed_vectors_count | **8,562** (17,252 → 8,562, -50.4%) |
| Storage delta | ~137 MB 감소 (on-disk HNSW vector) |
| Cache hit ratio (재실행) | 100% |
| Upstage API cost (재실행) | 0 (cache warm) |
| Idempotency (3회차) | payload_drift=0, elapsed 352s → 204s → 124s |
| Solar/tiktoken ratio | 0.5114 cumulative |

### 7.2 검색 예시

- Query: `"특수관계자 거래에 대한 감사절차"`
- Stage1 summary top-3: `[ISA-550, ISA-1200, ISA-1100]`
- Stage2 ISA-550 passage top-1: score `0.5604` — "새롭게 식별된 특수관계자 … 실증감사절차" (의미적 완벽 매치)

### 7.3 사용자 feedback

- `search_test.ipynb` 실제 실행 성공
- "왜 이렇게 빨라?" → Qdrant HNSW + query cache hit 으로 정상
- Docker Desktop WSL integration 일시 꺼짐 → 재기동 가이드 제공

---

## 8. Phase 4 로 이월

### 8.1 MED 이슈

- **C-P3-D2 HNSW 파라미터 하드코딩** — Phase 4 에서 env/config 설정화
- **C-P3-D3 Backup/DR 루틴 미정의** — named volume `audit_qdrant_storage` 백업 자동화 (Qdrant snapshot API 활용)
- **C-P3-D4 chunk_id regex 확장** — ISQM-1 / ASA 등 통합 시 `^(ISA|ISQM|ASA)-\d+` v1.2 MINOR bump

### 8.2 DEFER 유지

- C-P2-1 F5 drift → Phase 4 연환산 >200% 실측 시 자동 v1.2 bump
- C-P2-8 chunks_total 10,000 trigger → ISQM 1 통합 시 재평가 (현 8,626)

### 8.3 Phase 4 CHECKPOINT 4 scope (합의)

- Phase 4 추가 3 docx 파싱 (ISQM 1 / 역사적 재무정보 이외 인증업무 / 인증업무개념체계)
- 파일별 별도 collection 생성 (PLAN §5 4 매핑)
- Style map 차이 프로파일링 + 공용 모듈 일반화
- CHECKPOINT 4 mandatory drift measurement (§9.5 측정 프로토콜 ISA-540 등 타 split 최소 1건 추가)
- Phase 1~3 회귀 가드 유지

---

## 9. 커밋 대상 파일

### 신규
- `docs/PHASE_3_REPORT.md` (본 문서)
- `docs/checkpoint_3_prep.md`, `checkpoint_3_review.md`, `devils_advocate_checkpoint_3.md`
- `src/audit_parser/ingest/{embedder,qdrant_writer}.py`
- `tests/test_{embedder,qdrant_writer}.py`
- `notebooks/search_test.ipynb`
- `uv.lock` (ipykernel/jupyterlab 추가)

### 수정
- `docs/json_schema.md` (v1.1.2)
- `src/audit_parser/ingest/types.py` (`JSON_SCHEMA_VERSION = "1.1.2"`)
- `src/audit_parser/ingest/__init__.py`, `cli.py` (Phase 3 확장)
- `tests/fixtures/json_schema_v1_1.schema.json` (const bump)
- `tests/test_{cli,json_schema_compliance,md_parser}.py` (v1.1.2)
- `scripts/validate_json.py` (drift gate)
- `docker-compose.yml` (named volume + 127.0.0.1 binding)
- `.env.example` (QDRANT_API_KEY 정책 주석)
- `pyproject.toml` (ipykernel + jupyterlab dev dep)

### 제외 (gitignore 유지)
- `output/json/*.json`, `output/search_demo_results.json`, `EMBED_METRICS*.json`
- `raw/`, `output/md/`, `.env`, `.claude/`, `tmp/`
- `.embed_cache.sqlite`, `qdrant_storage/` (named volume)

---

## 10. 다음 Phase

**Phase 4 — 추가 3 docx 일반화**. PLAN.md §4 Phase 4.

### 착수 전 준비

1. 현 Phase 3 팀 정리 (`TeamDelete` 예정, 본 커밋·push 후 사용자 승인)
2. Phase 4 신규 팀 소환
3. **Pre-Kickoff 필수**: C-P3-D4 chunk_id regex scheme 3자 합의
4. Phase 4 브리핑에 §8 이월 이슈 전수 포함

### 주요 작업

- 추가 3 docx 파싱 (style_map 차이 프로파일링)
- 회귀 테스트 fixture 구축 (`tests/fixtures/`)
- 4개 collection 동시 운영 검증
- CHECKPOINT 4 drift 측정 의무 항목 수행
- Devil's Advocate 잔존 MED 2건 (HNSW 설정화 / Backup/DR) 해결
