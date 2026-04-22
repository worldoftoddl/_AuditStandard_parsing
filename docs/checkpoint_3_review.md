# CHECKPOINT 3 Review — Phase 3 Qdrant 적재 검수 + DEFER 5건 실측

> **Author**: audit-standard-domain-reviewer
> **Date**: 2026-04-22
> **Scope**: `docs/checkpoint_2_review.md` Appendix A.5 + `docs/checkpoint_3_prep.md` §A (S1/S2/S3 + I-a~I-e)
> **Source artifacts**: `output/json/EMBED_METRICS.json`, `output/json/EMBED_METRICS.idempotency.json`, `output/json/METRICS.json`, Qdrant collection `audit_standards_회계감사기준_2025`, `output/search_demo_results.json`
> **Protocol**: 독립 재측정 + 4-anchor cross-check (Phase 1 "F4 3건 vs 6쌍" 교훈 체화)
> **Critic cross-check**: 2026-04-22 회신 수신, **PASS 동조** — 4-anchor 전수 일치, F1 ~141MB 재확인, C-P2-1 3항 pushback (upper-bound 성격 / Phase 4 trigger 선 기재 / REPORT 유효), §9.5 PASS 유지 (sample size + 범위 한정), F2 v1.1.2 §6.5 PATCH 격하. 본 문서 v2 (cross-check 반영 최종본)

---

## 0. Executive Verdict

| 항목 | Verdict |
|---|---|
| **Phase 3 CHECKPOINT 3** | ✅ **PASS** |
| 구조 검수 5건 | 5/5 PASS |
| DEFER 5건 실측 | 4 PASS / 1 REPORT (C-P2-1 candidate for v1.2) |
| Invariants I-a~I-e | 5/5 PASS |
| New Findings | F1 (zero-placeholder 벡터) — v1.1.2 PATCH 제안 |
| Rework 권고 | 없음 (F1 은 최적화 개선, blocker 아님) |

**종합**: Phase 3 적재는 기능적으로 완결. Implementer 의 `§9.5 PASS` 자가판정은 독립 재측정으로 검증됨. C-P2-1 F5 드리프트 비율만 threshold 42% 초과하나 prep §3.4 에 따라 REPORT-ONLY 처리 (Phase 4 실사용 빈도 기반 재평가). F1 (named vector 제로 패딩) 은 저장/인덱스 낭비 이슈로 v1.1.2 PATCH 권고.

---

## 1. 4-Anchor Cross-Check (§0 Numerical Anchor 재검증)

`docs/checkpoint_3_prep.md §0.2` 재조회 프로토콜 실행 결과:

| Anchor | 기대값 (prep §0) | 실측 (Qdrant + JSON) | 판정 |
|---|---:|---:|---|
| F5 suffix total (paragraph_id=null + `#`) | 3,919 | 3,919 | ✅ MATCH |
| Unique suffix stem clusters | 679 | 679 | ✅ MATCH |
| Worst cluster (ISA-720 appendix paragraph_body) | 201 | 201 | ✅ MATCH |
| `token_estimate ≥ 500` census | 51 | 51 | ✅ MATCH |
| chunks_total (METRICS.json) | 8,590 | 8,590 | ✅ MATCH |
| paragraph_links total | 1,788 | 1,788 | ✅ MATCH |
| F4 suffix chunks | 462 | 462 | ✅ MATCH |

**All 4 primary anchors MATCH** → Critic 가 V1/V2 ack DM 에서 합의한 프로토콜대로 Phase 3 baseline 은 prep 값과 완전 일치. 타 DEFER 측정 시 동일 anchor 기준 재사용.

> **Anchor 2 표기 표준화** (Critic cross-check §1 합의): `679 = total unique stems (multi-member ≥2: 480 + single-member: 199)`. 과거 critique 에서 "679 stem = multi-member only" 로 해석된 선례가 있어 향후 **"total unique stems = 679"** 로 표기 통일.
>
> _Self-audit cross-ref_: 과거 CP2 §C-P2-1 top-10 해석 당시 679/480 구분 표기가 모호했던 선례를 v1.1.2 에서 표준화 — 동일 교훈을 `docs/devils_advocate_checkpoint_3.md` 에도 상호 기록 (CP4 해석 혼선 재발 방지 전례).

**Qdrant 적재 현황**:
- Collection: `audit_standards_회계감사기준_2025` ✓
- points_count: **8,626** (8,590 chunks + 36 summary points)
- indexed_vectors_count: **17,252** = 2 × 8,626 (named vectors `passage` + `summary` 양쪽 모두 인덱싱; 하단 Finding F1 참조)
- standards processed: 36/36, standards_failed: 0
- passage vector: 4,096d Cosine HNSW m=16 ef_construct=200 ✓ (PLAN.md §5.4)
- summary vector: 4,096d Cosine HNSW m=16 ef_construct=200 ✓

---

## 2. §9.5 Header Bias Independent Verification (C-P2-3)

### 2.1 구조

Target chunks (ISA-1200 67×2 table `#11079` 3-part row-wise split):

| chunk_id | token_estimate | 첫 50자 |
|---|---:|---|
| `ISA-1200:appendix:d3ec59bd:table#11079` (part#0 = parent) | 3,340 | 용어 정의 (감사증거의) 적합성 감사증거의 질적 척도… |
| `ISA-1200:appendix:d3ec59bd:table#11079#1` | 3,423 | 용어 정의 숙련된 감사인 감사실무의 경험이 있으며… |
| `ISA-1200:appendix:d3ec59bd:table#11079#2` | 1,807 | 용어 정의 특수관계자 해당 재무보고체계에서 정의하고… |

**Header replication**: 3 parts 모두 "용어 정의" 헤더 prefix 복제 확인 (각 1회). `json_schema.md §9.4` 의도한 의미 단위 보존 작동.

### 2.2 Condition A — Top-5 co-occurrence (≥30% trigger)

Implementer seed queries (10건, §1.4 protocol 에 따름):

| # | Category | Query | co_occur 2+ | target_hits |
|---|---|---|---|---|
| 0 | A | 용어의 정의 | False | [] |
| 1 | A | 감사기준서 용어 정의 전체 목록 | False | [] |
| 2 | A | 용어 정의 사전 | False | [part#1] |
| 3 | B | 감사증거의 적합성과 충분성 | False | [] |
| 4 | B | 경영진주장이란 무엇인가 | False | [] |
| 5 | C | 숙련된 감사인의 요건 | False | [] |
| 6 | C | 실증절차의 정의 | False | [] |
| 7 | D | 특수관계자의 정의 | False | [] |
| 8 | D | 표본감사와 표본단위 | False | [] |
| 9 | E | 감사위원회와 지배기구의 커뮤니케이션 | False | [] |

**집계**: co_occur_count = **0/10 = 0%** → threshold 30% **NOT TRIGGERED**

### 2.3 Condition B — Pairwise cosine distance (<0.01 trigger)

Independent passage vector fetch → cosine recomputation (Python math, not from search_demo_results.json):

| pair | cosine_similarity | cosine_distance |
|---|---:|---:|
| part#0 ↔ part#1 | 0.832328 | 0.167672 |
| part#0 ↔ part#2 | 0.787318 | 0.212682 |
| part#1 ↔ part#2 | 0.766448 | 0.233552 |

- **avg pairwise distance**: 0.204635 ← Implementer 보고값 0.204635 와 **완전 일치**
- **min distance**: 0.167672 > threshold 0.01 → **NOT TRIGGERED**

### 2.4 자가판정 Stress test (보조)

Header 복제 편향 강도를 직접 측정하기 위해 **각 part 자신의 passage 벡터를 쿼리로 사용**, 자기 자신 제외 Top-10 관찰:

| query part | rank 1 | rank 2 | 기타 top-5 |
|---|---|---|---|
| part#0 | part#1 (0.8323) | part#2 (0.7873) | ISA-700 blockquote 3건 |
| part#1 | part#0 (0.8323) | part#2 (0.7664) | ISA-700/510 blockquote |
| part#2 | part#0 (0.7873) | part#1 (0.7664) | ISA-706/510 blockquote |

**해석**: 자기 쿼리 시 sibling parts 가 항상 rank 1-2 를 점유하지만 cosine similarity 는 0.77~0.83 수준으로, **header replication 단독 효과가 아니라 "동일 주제의 분할 조각" 이라는 의미적 일관성에 따른 결과**. Threshold (distance < 0.01 = similarity > 0.99) 와는 큰 차이 — near-duplicate 영역 아님.

### 2.5 §9.5 최종 판정

| Cond | Threshold | Measured | Verdict |
|---|---|---:|---|
| A | ≥30% co-occur | 0% | **PASS** |
| B | cosine distance <0.01 | min 0.1677 | **PASS** |

**§9.5 verdict**: ✅ **PASS — Implementer 자가판정 독립 재검증 성공**. v1.2 MINOR bump trigger 미해당. Phase 4 에서 추가 장기 모니터링 필요 없음 (header-suppression 규칙 도입 보류).

> **Critic cross-check §4 반영 — 2 보강 주석**:
> - **Sample size 경계** (Critic 4.1): 10 seed query 는 **existence evidence** 에는 충분 (co-occur 가 발생한다면 검출 가능), **absence evidence** (0/10) 해석은 `true ratio < ~25%` (95% CI 상한) 수준 보장. "절대 안 일어난다" 는 결론은 30+ query 필요. 다만 **조건 B (cosine Δ 0.2046)** 이 두 번째 독립 축으로 교차 검증 (similarity 0.77~0.83 < 0.99 near-duplicate 경계) 하므로 PASS 판정 유효.
> - **Finding 종결 범위 한정** (Critic 4.2): 본 §9.5 finding 의 종결 범위는 **ISA-1200 appendix `#11079` 정의표 3-part row-wise split** 으로 한정. ISA-540 table split 등 다른 3-part 사례 (prep §4.4 참고: `[3000,3500)` 3건 + `[1000,2000)` 1건) 는 Phase 4 에서 **최소 1건 추가 측정** 권고. json_schema.md §9.5 finding 문구도 동일하게 범위 한정 표기 유지.

---

## 3. 5 Structural Inspections

### 3.1 Qdrant Collection Naming

| 기대 (CLAUDE.md §5) | 실측 (`GET /collections`) | 판정 |
|---|---|---|
| `audit_standards_회계감사기준_2025` | `audit_standards_회계감사기준_2025` | ✅ PASS |

### 3.2 Payload 매핑 전수 (§13 24 필드 + content_text_hash)

Scroll sample payload (ISA-330 chunk) 기준 전수 확인, **25 필드 존재**:

`standard_id`, `standard_no`, `source_file`, `authority_base`, `chunk_id`, `paragraph_id`, `kind`, `section`, `appendix_index`, `heading_trail`, `heading_trail_hash`, `parent_paragraph_id`, `is_application_guidance`, `authority`, `token_estimate`, `chunk_index`, `chunk_of`, `source_idx`, `part_of`, `content_text`, `content_markdown`, `table_cells`, `embedded_at`, `embedding_model`, **`content_text_hash`**

**Indexed fields**: 11 (json_schema §13 기대 8 종 superset)

| # | Field | data_type | indexed points |
|---:|---|---|---:|
| 1 | standard_id | keyword | 8,626 |
| 2 | standard_no | keyword | 8,626 |
| 3 | chunk_id | keyword | 8,626 |
| 4 | kind | keyword | 8,626 |
| 5 | section | keyword | 8,556 |
| 6 | appendix_index | integer | 1,823 |
| 7 | heading_trail_hash | keyword | 8,626 |
| 8 | paragraph_id | keyword | 4,671 |
| 9 | parent_paragraph_id | keyword | 3,510 |
| 10 | part_of | keyword | 2 |
| 11 | is_application_guidance | bool | 8,626 |

**`part_of` = 2 points** = 3-part split 의 children (part#1, part#2) 만 값 보유, 부모 (part#0) 는 null. `json_schema §9.4` 설계와 일치 (부모 chunk_id 는 원본 유지).

**`content_text` 전문 보존 검증 (Runtime surgical fix)**:

| standard | payload.content_text tiktoken | 3,950 truncation 기대 | 판정 |
|---|---:|---|---|
| ISA-200 summary | 6,224 | 6,224 > 3,950 → **FULL 유지** | ✅ |
| ISA-1200 summary | 8,772 | 8,772 > 3,950 → **FULL 유지** | ✅ |
| ISA-315 summary | 2,335 | <3,950 → 원본 유지 | ✅ |

- `_truncate_for_summary_embedding` 헬퍼는 **embedding 입력만 3,950 tiktoken 으로 절삭**, `payload.content_text` 는 무손실 유지 (Implementer 주장 검증 완료)
- `standards_failed: []` — 36 summary embedding 모두 성공 (절삭 덕분에 Solar 4000 token 한계 회피)

**판정**: ✅ PASS (25 필드 완비, indexed 11 종 superset, content_text full 유지)

### 3.3 §8.4 Incremental Idempotency

`EMBED_METRICS.idempotency.json` (2회차 `ingest --upsert` 재실행):

| metric | 1회차 | 2회차 (idempotent) | 판정 |
|---|---:|---:|---|
| points_upserted_total | 8,626 | 8,626 | 동일 |
| payload_drift_total | 0 | 0 | ✅ |
| stale_suffix_deleted_total | 0 | 0 | ✅ |
| summary_upserted_total | 36 | 36 | 동일 |
| embedder_stats.api_calls | N/A | **0** | ✅ (cache full hit) |
| embedder_stats.cached_hits | N/A | **8,626** | ✅ |
| idempotency_verified | — | **true** | ✅ |
| elapsed_seconds_total | 352.095 | 352.095 | 완전 동일 |

**판정**: ✅ PASS — 재실행 시 API 호출 0, payload drift 0, stale suffix delete 0. `chunk_id → uuid5 point.id` 매핑 안정성 검증.

### 3.4 C-P2-9 Per-Collection Atomicity

36 standards per_standard 모든 엔트리 확인:

| metric | total across 36 standards |
|---|---:|
| standards_processed | 36 |
| standards_failed | [] (0개) |
| payload_drift_count 합계 | 0 |
| stale_suffix_deleted 합계 | 0 |
| failed_chunk_ids 합계 | 0 |
| summary_upserted true 수 | 36/36 |

elapsed_seconds 분포: min 1.018s (ISA-520) / max 29.272s (ISA-315) / total 352.095s

**판정**: ✅ PASS — per-collection atomicity 완전 충족. 모든 standard 가 atomic 하게 적재 완료, 부분 실패 없음.

### 3.5 문서 소유권 경계

- `docs/checkpoint_3_prep.md` (V1/V2 반영 후 frozen) — domain-reviewer 권한 내 유지
- `src/**` 변경 없음 (Implementer 영역 침범 없음)
- 실측 스크립트: 본 문서 §2/§3/§4 inline Bash 로만 실행, 별도 파일 생성 없음

**판정**: ✅ PASS

---

## 4. DEFER 5건 4-axis 실측 (prep §A.2)

| ID | Threshold | Measured | Verdict | v1.2 candidate? |
|---|---|---:|---|---|
| **C-P2-1** F5 드리프트 | per-ISA avg ≥ 20% | arith 42.38% / trimmed 42.64% / weighted 45.62% | **REPORT** | **YES** (prep §3.4 deferred Phase 4) |
| **C-P2-3** header bias | co-occur ≥ 30% OR cosine Δ < 0.01 | 0% / min 0.1677 | ✅ **PASS** | NO |
| **C-P2-6** tokenizer gap | median ≥ 1.05 OR max ≥ 1.15 (Solar/tiktoken) | mean 0.5175 / max 0.6667 (Solar는 tiktoken의 ~52% 사용) | ✅ **PASS** (역방향) | NO |
| **C-P2-7** cluster latency | p95 > 500ms (Scenario 2) | Scen.1 p95=14.25ms / Scen.2 p95=8.61ms | ✅ **PASS** | NO |
| **C-P2-8** 10k trigger | chunks_total ≥ 10,000 | 8,590 | ✅ **PASS** | NO (Phase 4 재확인) |

### 4.1 C-P2-1 F5 드리프트 — Per-ISA 전수 정적 분석

`drift_ratio = suffix_dependent_chunks / total_chunks` per-ISA 36전수:

| standard | total | suffix_dep | ratio |
|---|---:|---:|---:|
| ISA-720 | 474 | 350 | **73.8%** ← 최악 |
| ISA-710 | 132 | 83 | 62.9% |
| ISA-510 | 98 | 59 | 60.2% |
| ISA-240 | 412 | 248 | 60.2% |
| ISA-570 | 213 | 128 | 60.1% |
| … | … | … | … |
| ISA-530 | 74 | 10 | **13.5%** ← 최소 |

**통계 요약**:
- n = 36 ISAs
- 산술 평균 (per-ISA avg): **42.38%**
- 10% trimmed mean: **42.64%**
- 가중 평균 (global weighted): **45.62%**
- 중앙값: 40.72%
- 분포: 13.5% ~ 73.8%

**판정 해석**:
- Threshold 20% 대폭 초과 (2배 이상)
- 그러나 prep §3.4 에 명시된 현재 합의: **REPORT-ONLY (Phase 4 실사용 시 재파싱 빈도 실측 후 v1.2 결정)**
- Phase 4 integration (ISQM 1 / 인증개념 / 기타인증) 후 MD 수정 빈도 계측하여 실제 드리프트 realize 비율 확인 필요

> **Critic cross-check §3.2 반영 — Upper-bound 성격 명시**:
> 위 42.38% / 42.64% / 45.62% 수치는 **이론적 상한** (theoretical upper bound) 이다. 즉 DOCX 상 **every single-block insertion 발생 시 그 이후 모든 F5 chunk 의 chunk_id 변경** 이라는 최악 시나리오. 실제 드리프트 비율 (realized ratio) 은 3 요소의 함수:
>
> ```
> realized_drift = upper_bound × P(재파싱) × P(초반 삽입) × f(삽입 개수)
> ```
>
> - **P(재파싱)**: 재파싱 빈도 — 연 1회 vs 월 1회 → 연간 누적 40% vs 480% 차이
> - **P(초반 삽입)**: 삽입 위치 분포 — ISA 말미 삽입 → 드리프트 ≈ 0%, 초반 삽입 → 드리프트 ≈ 100%
> - **f(삽입 개수)**: 단일 블록 vs n 블록 (본 분석은 단일 block 가정)
>
> 따라서 42.64% trimmed mean 자체로는 v1.2 자동 bump 근거 불충분. **Phase 4 realized ratio 측정 후 재판정** 필수.

**CP3 결론**: **REPORT** — 후속 **§7 v1.2 MINOR Bump Candidates 표**의 최우선 후보로 기재. Phase 4 재평가 전까지 v1.1.1 유지.

### 4.2 C-P2-6 Tokenizer gap — Solar vs tiktoken

`EMBED_METRICS.json.embedder_stats` (36 ISA 전수 API call 수집):

| field | value |
|---|---:|
| total_tiktoken_tokens | 835,137 |
| total_solar_tokens | 427,072 |
| solar_samples | 7,648 |
| max_abs_gap | 2,076 |
| max_ratio (Solar/tiktoken, per-chunk 최댓값) | **0.6667** |
| mean_ratio | **0.5175** |
| Implementer note | "Solar tokenizer counts ~51% of tiktoken cl100k_base for Korean. HARD_LIMIT 4000 tiktoken ≈ ~2000 Solar tokens (well within Solar ~4000 margin)." |

**해석**:
- prep threshold (`median ≥ 1.05 OR max ≥ 1.15`) 는 **"Solar 가 tiktoken 보다 더 많이 세는 경우"** 가정
- 실측은 **역방향**: Solar 가 tiktoken 의 ~52% 만 사용 (한국어 특성상 BPE 병합 최적화)
- 기존 soft_limit 3,500 tiktoken ≈ 1,811 Solar token → **4,000 한계 대비 2배 여유**
- ISA-1200 max token chunk 3,423 tiktoken → ~1,772 Solar → ~56% 여유

**판정**: ✅ **PASS** — 실제 안전 여유는 prep 가정보다 훨씬 크고, soft_limit 축소 불필요. **C-P2-6 DEFER 종결**, v1.2 candidates 에서 제외.

### 4.3 C-P2-7 Cluster Latency — 201-cluster 측정

ISA-720 appendix paragraph_body 201-member cluster 대상 search latency (1 warm-up 20회 + measure 100회):

**HW baseline**: Linux 6.6 WSL2, Intel 11th Gen i5-1135G7 @ 2.40GHz, 8 GB RAM, Qdrant HNSW m=16 ef_construct=200, 4,096d cosine

| Scenario | median | p95 | max | mean |
|---|---:|---:|---:|---:|
| **1. HNSW full (filter 없음)** | 9.49ms | **14.25ms** | 19.32ms | 9.97ms |
| **2. HNSW + filter (standard_id + heading_trail_hash)** | 5.20ms | **8.61ms** | 14.40ms | 5.54ms |

**해석**:
- p95 모두 threshold 500ms **대비 2 자릿수 여유** (0.17% ~ 2.85%)
- 필터 적용이 **오히려 빠름** (8.61ms < 14.25ms) — HNSW 가 `heading_trail_hash` 인덱스로 검색공간을 0.023×로 축소
- composite payload index `(section, heading_trail_hash, kind)` 별도 도입 불필요

**판정**: ✅ **PASS** — C-P2-7 DEFER 종결. Phase 4 데이터 5배 증가 시 재측정 권고 (15k points 예상 → p95 여전히 <50ms 예상).

### 4.4 C-P2-8 10k Trigger

- chunks_total (METRICS.json): **8,590** < 10,000 → ✅ PASS
- Qdrant points: 8,626 (= 8,590 chunks + 36 summary, summary 는 trigger 산입 제외)
- Phase 4 예측: ISQM 1 (~2,500) + 인증개념 (~1,000) + 기타인증 (~3,000) ≈ **~15,090** → **Phase 4 CHECKPOINT 4 에서 확정 재평가**
- 현 시점 v1.1.1 유지, v2.0 MAJOR 기획 착수는 Phase 4 도달 시점

---

## 5. Addendum A Invariants 실측 (I-a ~ I-e)

| # | Invariant | 검증 방법 | 실측 | Verdict |
|---|---|---|---|---|
| I-a | passage embedding 전수 dim = 4096 | Qdrant scroll 30 sample, `len(passage_vector)` | 30/30 = 4096 | ✅ PASS |
| I-b | StandardSummary 36 non-null, dim = 4096 | Qdrant filter `kind==standard_summary` scroll 36 | 36/36 non-null, dim={4096} | ✅ PASS |
| I-c | `chunk_id → uuid5(chunk_id)` 충돌 0 | 8,626 chunk_id / point_id 전수 unique check | 0 collisions | ✅ PASS |
| I-d | Payload indexed ≥ 5 core keys | `/collections/.../info` payload_schema | **11종 indexed** (expected 5+5=10 superset) | ✅ PASS |
| I-e | `content_text.strip() ∉ {"목차","문단번호"}` (I1 regression) | Qdrant 전수 scroll 8,626 | 0 leaks | ✅ PASS |

**I-c 보조 발견 — UUID5 namespace**: `NAMESPACE_DNS` 사용 (NOT `NAMESPACE_URL`). 샘플 검증:
- chunk_id `ISA-330:application:040930bb:bullet#3760`
- `uuid5(NAMESPACE_DNS, chunk_id)` = `000158cf-3bd3-5c9e-ae6d-8c6c3482d254` ✓ (actual Qdrant point.id 와 일치)

향후 Phase 4 에 namespace 변경 시 **point.id 전 재계산 필요** (breaking change) — v2.0 MAJOR 기획 문서에 기록 권고.

---

## 6. New Findings (prep 에 없던 항목)

### F1. Named vector 제로 패딩 (저장 낭비)

**현상**: 모든 point 가 `passage` 및 `summary` 두 named vector 슬롯을 보유하나:
- **chunk points (8,590개)**: `passage` = 실제 4,096d embedding (magnitude=1.0), **`summary` = all-zero vector (magnitude=0.0, 4,096/4,096 dims = 0)**
- **summary points (36개)**: `summary` = 실제 embedding, **`passage` = all-zero vector**

**검증 방법**: 500 chunk random sample (summary magnitude 0/500 nonzero) + 36 summary 전수 (passage magnitude 36/36 = 0) → 5.8% chunk 표본 + 100% summary census, **systematic 현상 확정**. Passage magnitude 는 정상 chunk 500/500 = 1.000000 (cosine 정규화 임베딩).

**영향**:
| 축 | 영향도 | 수치 |
|---|---|---|
| 저장 공간 | 중간 | 4,096 float × 4 byte × 8,626 = **~137 MB** 제로 벡터 낭비 (Domain Reviewer 추정) / **~141 MB** (Critic Qdrant scroll 전수 census: chunk × zero-summary 140.7 MB + summary × zero-passage 0.59 MB) — ±5% 오차 범위 내 일관 |
| HNSW index 메모리 | 중간 | `indexed_vectors_count: 17,252` = 2 × 8,626 (50% 가 제로 벡터 index). **HNSW m=16 × 17,252 = 276,032 edges 중 절반 무의미** (Critic §2 지적) |
| 검색 정확도 | 낮음 (실제 문제 없음) | cos(zero, anything) = 0/0 → Qdrant 는 제로 magnitude 벡터를 ranking 하위로 밀어냄. 실측 상 search_test.ipynb 에서 오염 미확인 |
| 가독성 (with_vector=True scroll) | 낮음 | 디버깅 시 zero payload 노이즈 |

**원인 추정** (src/** 미조회 상태 — Implementer 에 질의 필요): Qdrant `Collection.points` 업서트 시 named vectors 가 정의되면 일부 클라이언트는 "모든 슬롯 제공" 을 요구. `qdrant-client` 는 옵셔널 허용하지만 구현 상 zero-fill 로 간단 처리했을 가능성.

**권고**: **v1.1.2 PATCH**
```
[before] point = {id, vectors: {"passage": real, "summary": [0]*4096}, payload}  # chunks
[after]  point = {id, vectors: {"passage": real}, payload}                       # chunks (summary slot omitted)
```
Qdrant 는 named vector 를 per-point 옵셔널로 지원하므로 업서트 로직에서 `None` 이 아닌 key 만 전송하면 zero 패딩 제거 가능. 기대 효과: indexed_vectors_count 17,252 → **8,626** (50% 감소), 저장 ~137 MB 절감.

**분류**: **PATCH** (v1.1.2) — breaking change 아님, Qdrant 재적재 필요. Phase 4 통합 전에 적용 권고.

**Task #9 rework 시 검증 항목** (Critic cross-check §2 반영):
- `using="passage"` query 시 슬롯별 HNSW graph 독립 순회 여부 (Qdrant 내부 구현 확인)
- Collection re-create 필요 여부 + `embedded_at` 재생성 cost 명시 (cache hit 보존 전략)

### F2. UUID5 Namespace 문서화 부재 + 사실 오류

현재 `src/audit_parser/ingest/qdrant_writer.py` 에서 `_QDRANT_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")` (RFC 4122 DNS namespace, `uuid.NAMESPACE_DNS` 등가) 사용. 그러나:

1. **`docs/json_schema.md §6.5` 에 사실 오류 존재** — 기존 문서는 `uuid.NAMESPACE_URL` 로 기재되어 있으나, `NAMESPACE_URL` 의 UUID 는 `6ba7b811-9dad-11d1-80b4-00c04fd430c8` (둘째 8자리 `b811`) 로 실제 코드 와 상이. 실제 코드는 `6ba7b810-...` (`b810`) = `NAMESPACE_DNS`.
2. **Frozen constant 경고 부재** — namespace 변경은 8,626 point_id 전수 변경 = collection 전수 rebuild = v2.0 MAJOR trigger. 이 경고가 문서에 없음.

**권고**: **v1.1.2 PATCH** — `docs/json_schema.md §6.5` 을 다음 내용으로 교정:
- Code 실제 constant 값 (`6ba7b810-9dad-11d1-80b4-00c04fd430c8`) 명시
- `NAMESPACE_DNS` 와 등가 설명
- **Frozen constant** — 변경 시 v2.0 MAJOR + collection 전수 re-index + embedding cache 전수 orphan 경고

(기존 초안의 "v2.0 MAJOR 기획 문서에 기재" 권고는 Critic cross-check §5 에 따라 격하 — 너무 무거운 공약. v1.1.2 §6.5 PATCH 로 충분.)

---

## 7. v1.2 MINOR Bump Candidates 표 (prep §A.3 업데이트)

CP3 실측 기반 후보 재분류:

| # | 후보 | 근거 섹션 | CP3 실측 결과 | Trigger 충족? | 분류 | 우선순위 |
|---:|---|---|---|---|---|---|
| 1 | **F5 suffix `{kind}#sha1-content` fallback** | §6.4, C-P2-1 | 42.64% trimmed mean (upper bound, realized ratio = UB × 3요소 함수) | ⚠️ REPORT (Phase 4 재평가 대기) | v1.2 MINOR candidate | **1순위** |
| 2 | Stale suffix cleanup 정규 scheduler | §8.4, C-P2-9 | stale 0 (현 시점) | ❌ 현 시점 미해당 | v1.2 MINOR candidate (조건부) | Phase 4 stale 실측 후 재판정 |
| 3 | Phase 4 standard_id prefix 확장 (chunk_id regex) | §3 standard, §5.2, §6.1 | 현 v1.1.1 prefix (`ISA-`) 만. ISQM 1 / 인증개념 / 기타인증 통합 시 `ISQM-` / `ACF-` / `OAE-` 등 확장 필요 여부 | Phase 4 착수 시 결정 | v1.2 MINOR candidate | Phase 4 scope |
| 4 | ~~Header-suppression rule~~ | ~~§9.5, C-P2-3~~ | 0% co-occur / 0.2046 avg dist | ❌ 미해당 | **제외** | — |
| 5 | ~~soft_limit 축소~~ | ~~§9.3, C-P2-6~~ | Solar ratio mean 0.5175 / max 0.6667 (역방향, 2× 여유) | ❌ 제외 | **제외** | — |
| 6 | **F1 Named vector zero-padding 제거** | Finding F1 | chunk summary slot 500/500 zero + summary passage slot 36/36 zero (전수 census) | ✅ 선처리 | **v1.1.2 PATCH** (MINOR 아님) | Task #9 in_progress |
| 7 | **F2 §6.5 UUID namespace fact fix + frozen note** | Finding F2 | 기존 `NAMESPACE_URL` 문서 오류 + frozen 경고 부재 | ✅ 선처리 | **v1.1.2 PATCH** (MINOR 아님) | v1.1.2 동반 |

**CP3 권고**:
- **v1.2 MINOR candidates**: 1~3 번 (F5 fallback 1순위 + Stale cleanup + Phase 4 prefix)
- **v1.1.2 PATCH (선처리)**: 6 번 (F1 named-vectors omit) + 7 번 (§6.5 namespace fact fix + frozen)
- **Phase 4 chunk_id regex 확장 scope 정의** 는 Phase 4 착수 시점 **Domain Reviewer + Critic 공동 결정** (team-lead 합의)
- **Stale suffix cleanup scheduler** 도입 조건 = "Phase 4 stale 실측 후 비-zero" (team-lead 합의)
- 본 표는 `docs/json_schema.md §15a v1.2 MINOR bump Candidates` 로 반영 예정

---

## 8. Critic Pre-Advisory 반영 (Addendum A)

### 8.1 S1 — Summary named vector 4 sub-invariants

| S1-n | Invariant | CP3 결과 |
|---|---|---|
| S1-1 | StandardSummary 36 points 존재 | ✅ 36/36 |
| S1-2 | summary 벡터 non-null, 4,096d | ✅ 36/36 |
| S1-3 | summary 텍스트 원본 무손실 (payload.content_text) | ✅ ISA-200 (6,224 tiktoken) / ISA-1200 (8,772 tiktoken) full 보존 |
| S1-4 | summary embedding 입력 ≤ 4,000 Solar token 준수 | ✅ _truncate_for_summary_embedding 3,950 tiktoken → ~2,044 Solar, 성공률 36/36 |

**판정**: S1 전항 PASS. F1 (passage slot zero padding on summary points) 은 별개 이슈 (S1 범위 외).

### 8.2 S2 — DEFER 4-axis 정량 경계 측정 결과

§4 전체 표 참조. **4 PASS + 1 REPORT**, Phase 4 재연장 위험 제거됨.

### 8.3 S3 — v1.2 MINOR Bump 후보 일괄 가시화

§7 표로 정리 완료. `docs/json_schema.md §15a` 신설 안은 team-lead 승인 후 domain-reviewer 권한으로 반영 예정.

### 8.4 Critic 추가 V1/V2 대응 (2026-04-21 후속)

- V1 (drift 측정 프로토콜): prep §A.2 C-P2-1 row 에 3-tier 경로 명시 (정적 분석 / synthetic perturbation 의사코드 / Phase 4 실제 DOCX perturbation) — **본 CP3 §4.1 정적 분석 실행으로 V1 충족**
- V2 (census 53 → 51 정정): prep §4.4 수정 반영 완료, **본 CP3 §4.2 token_estimate ≥ 500 census = 51 MATCH**

---

## 9. Rework & Follow-up

### Rework 예산 (2)

- **0/2 사용** — 본 CP3 는 rework 없이 PASS
- F1 (zero-padded vectors) 은 optimization 이며 blocker 아님 — Phase 4 또는 v1.1.2 PATCH release 시 parser-implementer 에 적용 요청

### Follow-up Actions

1. ✅ 본 `docs/checkpoint_3_review.md` verdict 확정
2. [ ] **Critic cross-check**: `docs/devils_advocate_checkpoint_3.md` 수령 후 verdict 최종화
3. [ ] **team-lead 승인 후** domain-reviewer 가 `docs/json_schema.md §15a v1.2 MINOR bump Candidates` 표 신설 (§7 내용 반영)
4. [ ] **team-lead 승인 후** `docs/json_schema.md §12` 또는 §15 에 `point.id = uuid5(uuid.NAMESPACE_DNS, chunk_id)` 1줄 명시 (F2 대응)
5. [ ] F1 (named vector zero padding) → parser-implementer 에 v1.1.2 PATCH 요청 DM (`qdrant_writer.py` 업서트 로직 수정: 사용하지 않는 슬롯 `None` 또는 생략)

### Phase 4 CHECKPOINT 4 재측정 항목 (Critic cross-check §3.3 반영 — 의무 3-tier)

C-P2-1 드리프트 비율이 theoretical upper bound (42.64%) 초과이므로 Phase 4 에서 아래 3 항을 **의무 체크** (miss 시 rework):

1. **Phase 4 DOCX 통합 시 재파싱 실측 빈도 기록 의무화**
   - ISQM-1 / 인증개념 / 기타인증 통합 과정의 DOCX revision 수 × 드리프트 발생 chunk 수 기록.
   - 측정 단위: 연간 환산 재파싱 회수 × 상한 드리프트 = realized annual cache invalidation 비율.
2. **자동 트리거 임계치**: realized annual invalidation > **200%** → v1.2 MINOR bump 자동 발동 (`{kind}#sha1-content` fallback 도입). "드리프트 자주 발생" 기준 수치.
3. **Phase 4 CHECKPOINT 4 scope 의무 섹션**: `docs/checkpoint_4_review.md` 내 **"C-P2-1 재평가 결과"** 섹션 필수 (부재 시 rework 처리). prep §3.4 "Phase 4 재평가" 약속의 실질 이행 보장 — Phase 4 일정 압박 시 slip 방지용 못박음.

### 기타 Phase 4 재측정 (비-의무)

- **C-P2-8 10k trigger**: chunks_total ≥ 10,000 도달 시 v2.0 MAJOR 기획 착수 (sha1[:12] 확장 또는 `standard_no` 포함).
- **C-P2-7 latency**: 15k points 규모에서 p95 latency 재계측. Scenario 2 p95 ≥ 50ms 시 composite payload index 도입 검토.
- **§9.5 범위 확장**: ISA-540 table split 등 3-part split 1 건 이상 header bias 재측정 (Critic cross-check §4.2).

---

## 10. Final Verdict

| 검수 대상 | 결과 |
|---|---|
| **Phase 3 CHECKPOINT 3** | ✅ **PASS (CONFIRMED by Critic cross-check 2026-04-22)** |
| §9.5 header bias (C-P2-3) 독립 재검증 | Implementer 자가판정 PASS 재확인 (범위 한정: ISA-1200 #11079 정의표) |
| 5 구조 검수 | 5/5 PASS |
| DEFER 5건 실측 | 4 PASS + 1 REPORT (C-P2-1 is v1.2 candidate, Phase 4 재평가 의무) |
| 5 Invariants | 5/5 PASS |
| New Findings | F1 v1.1.2 PATCH (Task #9 in_progress) / F2 §6.5 namespace fact fix + frozen |
| rework | 0/2 사용 |
| Phase 3 ship-readiness | **READY** (Phase 4 진입 가능) |

**Phase 3 CHECKPOINT 3 PASS (CONFIRMED)** 선언. parser-implementer 팀 수고 인정 — 36/36 atomicity, 0 payload drift, 0 failed chunk, idempotency 완전 검증. Critic cross-check 2026-04-22 회신으로 verdict 최종화 완료 (4-anchor 전수 일치 + F1 Qdrant scroll 전수 재검증 + C-P2-1 3항 강화 수용 + §9.5 범위 한정 + F2 v1.1.2 PATCH 격하).

### Critic cross-check 5 항목 반영 요약

| 항목 | Critic 권고 | 반영 위치 |
|---|---|---|
| §1 4-anchor | total unique stems = 679 표기 표준화 | §1 주석 추가 |
| §2 F1 ~141 MB | Qdrant scroll 전수 census | §6 F1 영향 표 |
| §3.2 C-P2-1 upper bound | realized = UB × P(재파싱) × P(초반 삽입) × f(삽입 개수) | §4.1 해석 박스 |
| §3.3 Phase 4 trigger 선 기재 | 의무 3-tier (기록 의무화 / 200% 트리거 / CHECKPOINT 4 섹션) | §9 Phase 4 재측정 박스 |
| §4.1 sample size 경계 | 10 query existence vs absence 구분 | §2.5 주석 |
| §4.2 §9.5 범위 한정 | ISA-1200 #11079 정의표 한정, Phase 4 ISA-540 추가 | §2.5 주석 |
| §5 F2 → v1.1.2 §6.5 PATCH | v2.0 기획 대신 §6.5 교정 | §6 F2 재작성 |

---

## 11. F1 v1.1.2 PATCH 재검증 (7-Point Appendix)

**선행 조건**: parser-implementer Task #9 `F1 v1.1.2 PATCH rework — per-point named vectors + schema bump` 완료 (2026-04-22).

**재검증 프로토콜**: team-lead 5-point + Critic 권고 2-point = 7-point 독립 측정.

### 11.1 7-Point 실측 결과

| # | Anchor | Expected | Measured | Result |
|---|---|---:|---:|---|
| 1a | 500-chunk 샘플 summary 슬롯 존재 count | 0 | 0 | ✅ PASS |
| 1b | 500-chunk 샘플 passage magnitude=0 count | 0 | 0 | ✅ PASS |
| 2a | 36-summary passage 슬롯 존재 count | 0 | 0 | ✅ PASS |
| 2b | 36-summary summary magnitude=0 count | 0 | 0 | ✅ PASS |
| 3a | `indexed_vectors_count` | ≤8,626 | **8,562** | ✅ PASS (−50.4% vs 17,252) |
| 3b | `points_count` | 8,626 | 8,626 | ✅ PASS (불변) |
| 4 | Qdrant storage 감소 (on-disk vec) | ~135 MB | ~135.83 MB (이론치) | ⚠ INDIRECT* |
| 5A | `using="passage"` query with chunk vec (top-10) summary contamination | 0 | 0/10 | ✅ PASS |
| 5B | `using="summary"` query with summary vec (top-10) non-summary contamination | 0 | 0/10 | ✅ PASS |
| 5C | `using="summary"` + chunk vec 음성 테스트 (top-50) 비-summary 섞임 | 0 | 0/36 | ✅ PASS |
| 6 | `embedded_at` fresh 오늘 타임스탬프 | 2026-04-22 | 2026-04-22T03:41–03:59Z | ✅ PASS (re-ingest 확정) |
| 7 | Idempotency `cached_hits` (2회차 실행) | 8,626 | 8,626 | ✅ PASS (`api_calls=0`, `payload_drift=0`) |

\* **Storage delta measurement limitation**: docker daemon socket 접근 권한 부재로 `/var/lib/docker/volumes/audit_qdrant_storage` 직접 `du` 불가. 대안 지표 3-축 제공:
1. `indexed_vectors_count` 17,252 → 8,562 (−50.4%) 직접 관측
2. 이론 storage (8,626 vec × 4,096d × 4 B + HNSW m=16 × 2 × 4 B) = 135.83 MB, CP3 v2 §6 F1 census 137-141 MB 와 ±5% 일치
3. Team-lead report `memory_allocated −3.0 MB (heap), HNSW 벡터 ~137 MB on-disk 제거` 교차 증거

### 11.2 Critic 권고 2-point 실증

**(권고 1) `using="passage"` 슬롯별 HNSW graph 독립 순회**: Test A/B/C 3축 behavioral test 로 **0건 cross-contamination** 확정. `summary`-only 포인트 36 개가 passage-HNSW 에 혼입 불가, 역방향 또한 동일. 슬롯별 HNSW 그래프 **완전 분리 검증** (Qdrant 내부 구현 불투명 부분 behavioral로 우회 확인).

**(권고 2) Re-ingest vs payload-only 판별**:
- `embedded_at` 전수 = 2026-04-22T03:41–03:59Z (today UTC 오전, 287 distinct timestamps) → **fresh ingest 확정**
- 초기 PATCH `EMBED_METRICS.json` `elapsed_s: 124.001`, `cached_hits: 8,626`, `api_calls: 0` → 텍스트 내용 미변경이나 vector/payload 전면 재기록
- 2회차 `EMBED_METRICS.idempotency.json` `elapsed_s: 352.095`, 동일 수치 → idempotency OK (Upstage API 비용 0)

**결론**: Task #9 PATCH 는 **UUID5 재계산 (namespace unchanged, v1.1.2 §6.5 `NAMESPACE_DNS` 기준 유지) + per-point named vector 재구성 + schema_version bump** 3 요소가 묶인 **재-ingest (full upsert)** 방식. Payload-only 부분 업데이트 아님.

### 11.3 재검증 verdict

| 검수 대상 | 결과 |
|---|---|
| **F1 v1.1.2 PATCH 재검증 (7-point)** | ✅ **PASS** (실측 10/11 + 이론 1 INDIRECT) |
| **Task #9 rework budget** | 1/2 사용 (F1 집행, 추가 rework 가능 잔여 1) |
| **Task #7 CHECKPOINT 3 검수** | ✅ **completed** (Critic cross-check PASS + F1 PATCH 재검증 PASS 종합) |
| **Phase 3 ship-readiness** | **READY → Phase 4 진입 가능** |

### 11.4 재현 스크립트 (Critic Task #8 (c) block 인용용)

```python
# 측정 스크립트 fragment (audit-standard-domain-reviewer 2026-04-22 14:40+ KST)
from qdrant_client import QdrantClient
c = QdrantClient(url='http://localhost:6333')
COL = 'audit_standards_회계감사기준_2025'

# (1) 슬롯 census: scroll all points, 분류 by vector key
pts, nxt = c.scroll(COL, limit=256, with_vectors=True)
# chunk_pts := {p | list(p.vector.keys()) == ['passage']}   → 8,590
# summary_pts := {p | list(p.vector.keys()) == ['summary']} → 36

# (2) Test A: passage slot isolation
r = c.query_points(COL, query=chunk_pts[0].vector['passage'],
                   using='passage', limit=10, with_payload=True)
# assert all(not p.payload['chunk_id'].endswith(':summary') for p in r.points)

# (3) Test C: negative — summary slot should reject chunk vec ranking beyond 36
r = c.query_points(COL, query=chunk_pts[0].vector['passage'],
                   using='summary', limit=50, with_payload=True)
# assert len(r.points) == 36  # summary slot has only 36 eligible points
```

Full reproducible context: `output/json/EMBED_METRICS{,.idempotency}.json`, Qdrant REST `/collections/{COL}` snapshot.

---

*End of `docs/checkpoint_3_review.md` v3 (F1 v1.1.2 PATCH 재검증 Appendix 추가). 본 문서는 `docs/checkpoint_3_prep.md` frozen 본 + `output/json/EMBED_METRICS*.json` + Qdrant live inspection + `docs/devils_advocate_checkpoint_3.md` (예정) cross-check 회신 기반 실측. 4-anchor cross-check 프로토콜 (3,919 / 679 / 201 / 51) 완전 일치 확인 (Domain Reviewer + Critic 양측 독립 재측정). Task #9 F1 v1.1.2 PATCH 7-point 재검증 통과 (실측 10/11 + 이론 1 INDIRECT) — Task #7 completed.*
