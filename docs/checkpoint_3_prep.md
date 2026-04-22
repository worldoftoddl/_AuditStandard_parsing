# CHECKPOINT 3 검수 사전 준비 (Idle-Mode Prep)

> **작성자**: `audit-standard-domain-reviewer` (team `audit-parser-phase3`)
> **작성일**: 2026-04-21
> **상태**: IDLE 대기 중 사전 준비본 (parser-implementer Task #5 완료 DM 수신 시 착수)
> **대상**: Phase 3 CHECKPOINT 3 검수 + DEFER 5건 실측
> **산출 예정**: `docs/checkpoint_3_review.md`
> **Scope 근거**: `docs/checkpoint_2_review.md` Appendix A.5 + `docs/devils_advocate_checkpoint_2.md` C-P2-1/3/6/7/8/9

본 문서는 본격 검수 착수 전에 다음을 **확정**하여 재실행 가능한 측정 프로토콜로 남기기 위한 것. Phase 3 `qdrant_writer` · `embedder` 준비 완료 후 즉시 실측 phase 로 이동.

---

## 0. 검수 이력 · 수치 닻 (Numerical Anchor)

CP3 실측 및 향후 Critic critique 에서 동일 수치를 사용하기 위한 공식 닻. **본 prep 문서의 수치가 기준**, CP2 문서의 stale 수치 (I1 fix 전 집계) 와 충돌 시 본 문서 우선.

### 0.1 I1 fix 영향 (2026-04-21 EVE+)

| 지표 | CP2 pre-I1 | CP2 post-I1 (= CP3 baseline) | Δ | 주석 |
|---|---:|---:|---:|---|
| `chunks_total` | 8,660 | **8,590** | −70 | TOC leak ("목차"/"문단번호") 제거 |
| `section = <null>` | 104 | **34** | −70 | cross-ref block_quote 만 잔존 |
| F5 null-pid `#` suffix | 3,989 | **3,919** | −70 | 제거된 70건이 모두 F5 suffix 였음 (paragraph_body + null section) |
| F5 stem cluster 수 | — | **679** | — | cluster 구성에는 변화 없음 (TOC stem 은 독립 stem 이었으므로 cluster count 변동 확인 필요 — post-fix 679 측정값 기준) |
| F5 worst cluster | **201** | **201** | 0 | ISA-720 `appendix:3d4ed148:paragraph_body` 불변 (TOC 와 무관) |
| F4 canonical paired suffix | 4 (2 pair) | **4** | 0 | ISA-300 7.#2237/#2238, ISA-701 4.#8422/#8427 불변 |
| paragraph_links | 1,788 | **1,788** | 0 | app_guide 1:1 매칭 불변 |
| `f4_suffix_chunks.total` (METRICS) | 462 | **462** | 0 | paragraph_id=real 한정 집계, I1 무관 |

**근거**: `output/json/METRICS.json` 실측 2026-04-21 EVE+, I1 fix 적용 후.

**Critic critique 연속성**: devils_advocate_checkpoint_2 §C-P2-1 표 (top-10 cluster) 는 CP2 pre-I1 기준이었으나 재검증 결과 **top-10 cluster 수치는 TOC fix 와 무관** (TOC leak 은 독립 stem `ISA-XXX:null:HASH:paragraph_body#IDX` 로 별도 존재, top-10 내에 포함되지 않음). 따라서 critic 의 top-10 표는 CP3 에서도 그대로 유효.

### 0.2 CP3 baseline 스냅샷 (실측 작업 시작 시점 재확인 대상)

다음 값들은 **Task #5 (Qdrant 전수 적재) 완료 시점에 재조회 후 고정**:
- `METRICS.json` 의 chunks_total / kind_dist / section_dist
- Qdrant collection point count == 8,590
- `.embed_cache.sqlite` 의 passage 캐시 entry 수 == 8,590 (+ summary 36)

재조회 결과가 위 수치와 불일치 시 CP3 착수 전 team-lead 에스컬레이션.

---

## 1. §9.5 ISA-1200 header 복제 bias — 10 seed query 설계

### 1.1 측정 목적

`docs/json_schema.md v1.1.1 §9.5` 정의대로 ISA-1200 66×2 "용어의 정의" 표의 3-part split 시 **header row("용어 정의") 가 part 0/1/2 에 모두 복제**되었음. 실측 확인 (2026-04-21):

| chunk_id | token | 첫 30자 |
|---|---:|---|
| `ISA-1200:appendix:d3ec59bd:table#11079` | 3340 | `용어 정의\n(감사증거의) 적합성 감사증거의 질적 척도.` |
| `ISA-1200:appendix:d3ec59bd:table#11079#1` | 3423 | `용어 정의\n숙련된 감사인 감사실무의 경험이 있으며 다음` |
| `ISA-1200:appendix:d3ec59bd:table#11079#2` | 1807 | `용어 정의\n특수관계자 해당 재무보고체계에서 정의하고 있` |

Upstage Solar passage embedding 에서 동일 header 가 임베딩 공간 거리 단축으로 "definitions 쿼리 시 3 조각이 항상 함께 top-k" 효과를 유발하는지 판정.

### 1.2 판정 임계 (§9.5)

**v1.2 MINOR bump trigger** (header-suppression 규칙 도입):
- **조건 A**: 10 seed query 의 top-5 retrieval 에서 `{#11079, #11079#1, #11079#2}` 중 **≥2 조각이 동시 출현** 하는 query 비율 **≥30%** (즉 ≥3/10 query)
- **조건 B (대안)**: 3 조각 상호간 cosine similarity 평균 Δ **< 0.01** (i.e. 임베딩이 거의 구분 불가 수준으로 수렴)

둘 중 하나 충족 시 `docs/json_schema.md v1.2` MINOR bump 로 header-suppression 기록. 둘 다 미충족 시 "header 복제 OK" 로 §9.5 finding 종결.

### 1.3 10 seed query 확정

Query 는 **4 카테고리 × 2-3건** 로 분류, 각 카테고리는 header bias 의 영향 방향이 다름:

| # | 카테고리 | Query (Korean) | 기대 hit chunk (bias 가 **없을** 때) | 기대 hit chunk (bias 가 **있을** 때) |
|---|---|---|---|---|
| 1 | **A. 직접 표제어 match** (header token 과포화 최고 민감) | `"용어의 정의"` | 36 ISA 전반 definitions section 분산 | {#11079, #11079#1, #11079#2} 중 2+ 동시 |
| 2 | A | `"감사기준서 용어 정의 전체 목록"` | ISA-1200 보론 1 중 top-scoring 1 조각 | 3 조각 동시 |
| 3 | A | `"용어 정의 사전"` | 일반 definition scope | 3 조각 동시 |
| 4 | **B. Part 0 내부 전용 용어** (if no bias, only part 0 should hit) | `"감사증거의 적합성과 충분성"` | #11079 (part 0) 만 | #11079 + (#11079#1 또는 #11079#2) |
| 5 | B | `"경영진주장이란 무엇인가"` | #11079 | #11079 + 타 part |
| 6 | **C. Part 1 내부 전용 용어** | `"숙련된 감사인의 요건"` | #11079#1 (part 1) 만 | #11079#1 + 타 part |
| 7 | C | `"실증절차의 정의"` | #11079#1 만 | #11079#1 + 타 part |
| 8 | **D. Part 2 내부 전용 용어** | `"특수관계자의 정의"` | #11079#2 (part 2) 만 | #11079#2 + 타 part |
| 9 | D | `"표본감사와 표본단위"` | #11079#2 만 | #11099#2 + 타 part |
| 10 | **E. Control** (irrelevant to definitions) | `"감사위원회와 지배기구의 커뮤니케이션"` | ISA-260 요구사항 계열 | 동일 (ISA-260 scope 유지) |

**설계 근거**:
- **A 카테고리 (3건)**: header 문자열 "용어 정의" 와 직접 매칭되는 쿼리. bias 가 있다면 3 조각 동시 top-5 확률 최대. 없다면 36 ISA definition section 전반에 분산.
- **B/C/D 카테고리 (2건씩)**: 각 part 고유 용어로 쿼리. bias 가 없다면 해당 part **단독** top-1. 있다면 header 유사성 때문에 다른 part 까지 top-5 에 끌려 들어옴.
- **E 컨트롤 (1건)**: ISA-1200 용어정의 표와 무관한 topic. bias 유무와 상관없이 11079 계열 3 조각이 top-5 에 없어야 함. 만약 있으면 **embedder configuration error** 경보.

### 1.4 측정 실시 프로토콜

**Embedding 비용 최소화 전략** (team-lead 제안 반영):
- Task #5 완료 시점에 `.embed_cache.sqlite` 는 passage 8,590건 + summary 36건 warm-up 완료 상태.
- §9.5 측정은 **query 10건 + 3 target chunk 의 passage vector 재사용 (cache hit)** 으로 처리 → **추가 API 호출 10건 (query embedding only)**. Upstage passage 10건 × 평균 30 token × $0.00000010/token ≈ 거의 0원.
- `embedder.embed_query()` 는 query encoder 사용 (passage 와 다른 모델). 캐시 키는 `(model, text)` 이므로 query 10건은 새로 embed.

Phase 3 parser-implementer Task #6 (search demo) 가 제공하는 search harness 또는 `embedder.embed_query()` 를 직접 호출:

```python
# 의사코드 — Task #7 실측 단계 실제 구현
from audit_parser.ingest.embedder import embed_query
from qdrant_client import QdrantClient

queries = [
    "용어의 정의", "감사기준서 용어 정의 전체 목록", "용어 정의 사전",
    "감사증거의 적합성과 충분성", "경영진주장이란 무엇인가",
    "숙련된 감사인의 요건", "실증절차의 정의",
    "특수관계자의 정의", "표본감사와 표본단위",
    "감사위원회와 지배기구의 커뮤니케이션",
]
TARGETS = {
    "ISA-1200:appendix:d3ec59bd:table#11079",
    "ISA-1200:appendix:d3ec59bd:table#11079#1",
    "ISA-1200:appendix:d3ec59bd:table#11079#2",
}

client = QdrantClient(url="http://localhost:6333")
results = []
co_occur_count = 0
for q in queries:
    qvec = embed_query(q)
    top5 = client.search(
        collection_name="audit_standards_회계감사기준_2025",
        query_vector=("passage", qvec),
        limit=5,
    )
    hit_ids = [hit.payload["chunk_id"] for hit in top5]
    hits_in_target = [cid for cid in hit_ids if cid in TARGETS]
    co_occur = len(hits_in_target) >= 2
    if co_occur:
        co_occur_count += 1
    results.append({"query": q, "top5": hit_ids, "target_hits": hits_in_target, "co_occur": co_occur})

ratio = co_occur_count / len(queries)
print(f"Co-occurrence ratio: {ratio:.0%} (threshold 30%)")

# 대안 지표: 3 조각 상호 cosine similarity
target_vectors = [client.retrieve(collection_name="...", ids=[id_for(cid)], with_vectors=True)[0].vector["passage"] for cid in TARGETS]
from itertools import combinations
cosines = []
for a, b in combinations(target_vectors, 2):
    dot = sum(x*y for x, y in zip(a, b))
    # (vectors assumed unit-normalized by Solar)
    cosines.append(dot)
avg_cos = sum(cosines) / len(cosines)
delta = 1.0 - avg_cos  # cosine distance
print(f"3-part cosine distance avg: {delta:.4f} (threshold <0.01)")
```

### 1.5 판정 매트릭스

| 조건 A (co-occurrence ≥30%) | 조건 B (cosine Δ <0.01) | 판정 |
|---|---|---|
| ✗ | ✗ | PASS — §9.5 finding 종결, v1.2 bump 불필요 |
| ✓ | ✗ | **TRIGGER** — v1.2 MINOR bump (header-suppression rule) |
| ✗ | ✓ | **TRIGGER** — 동일 |
| ✓ | ✓ | **STRONG TRIGGER** — v1.2 bump + Phase 4 RAG deploy 이전 반드시 해소 |

---

## 2. C-P2-7 — 201-member cluster Qdrant payload filter 성능 실측

### 2.1 측정 목적

`ISA-720:appendix:3d4ed148:paragraph_body` stem 이 201 member 로 최다 클러스터 (devils_advocate_checkpoint_2 §C-P2-7). Qdrant `heading_trail_hash = "3d4ed148"` + `standard_id = "ISA-720"` filter 시 HNSW + payload index 조합이 latency 병목인지 실측.

### 2.2 10 stratified sample (201 중)

cluster 전체를 4 구간으로 나눠 0%/10%/20%/30%/40%/50%/60%/70%/85%/100% 위치 sample:

| idx (in cluster) | chunk_id | content[:50] |
|---:|---|---|
| 0 | `ISA-720:appendix:3d4ed148:paragraph_body#9529` | `사례 1: 상장 여부와 관계없이 감사인이 감사보고서일 전에 모든 기타정보를 입수하였으며 기` |
| 20 | `...paragraph_body#9559` | `기타 법규의 요구사항에 대한 보고` |
| 40 | `...paragraph_body#9590` | `경영진은 기타정보에 대한 책임이 있습니다. 기타정보는 [감사보고서일 전에 입수한 X보고서` |
| 60 | `...paragraph_body#9620` | `우리는 ABC 주식회사(이하 "회사")의 재무제표를 감사하였습니다. 해당 재무제표는 20X` |
| 80 | `...paragraph_body#9651` | `독립된 감사인의 감사보고서` |
| 100 | `...paragraph_body#9671` | `[감사기준서 700에 따른 보고 – 감사기준서 700의 사례 1 참고]` |
| 120 | `...paragraph_body#9702` | `[기타정보의 중요한 왜곡표시에 대한 기술]` |
| 140 | `...paragraph_body#9732` | `우리의 의견으로는 이 감사보고서의 한정의견근거 단락에서 언급하고 있는 사항이 미칠 수 있는` |
| 170 | `...paragraph_body#9762` | `입수한 감사증거에 근거하여, 감사인은 감사기준서 570에 따라 계속기업으로서의 존속능력에` |
| 200 | `...paragraph_body#9792` | `[감사보고서일]` |

### 2.3 측정 프로토콜

```python
import time, statistics
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

# Scenario 1: 단일 stem filter (전수 조회)
filter_stem = models.Filter(
    must=[
        models.FieldCondition(key="standard_id", match=models.MatchValue(value="ISA-720")),
        models.FieldCondition(key="heading_trail_hash", match=models.MatchValue(value="3d4ed148")),
        models.FieldCondition(key="kind", match=models.MatchValue(value="paragraph_body")),
    ]
)

# 30회 warm + 100회 측정
for _ in range(30):
    _ = client.scroll(collection_name="audit_standards_회계감사기준_2025", scroll_filter=filter_stem, limit=201)

latencies = []
for _ in range(100):
    t0 = time.perf_counter()
    _ = client.scroll(collection_name="audit_standards_회계감사기준_2025", scroll_filter=filter_stem, limit=201)
    latencies.append((time.perf_counter() - t0) * 1000)

p50 = statistics.median(latencies)
p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
print(f"Scenario 1 (payload filter only, 201 fetch): p50={p50:.1f}ms, p95={p95:.1f}ms")

# Scenario 2: semantic search + filter (HNSW + payload)
query_text = "감사보고서 사례 중 한정의견 상황"
qvec = embed_query(query_text)
latencies2 = []
for _ in range(100):
    t0 = time.perf_counter()
    _ = client.search(
        collection_name="...",
        query_vector=("passage", qvec),
        query_filter=filter_stem,
        limit=10,
    )
    latencies2.append((time.perf_counter() - t0) * 1000)
p50_2 = statistics.median(latencies2)
p95_2 = statistics.quantiles(latencies2, n=20)[18]
print(f"Scenario 2 (HNSW + payload filter, top-10): p50={p50_2:.1f}ms, p95={p95_2:.1f}ms")
```

### 2.4 판정 기준

**Baseline calibration rationale** (team-lead 제안 반영):
- Qdrant 공식 벤치 (`qdrant-benchmarks` 2024): 1M points × 384d HNSW 기준 payload-filter + search p95 ~10-30ms (c5.xlarge 기준).
- 본 프로젝트 규모는 **36 collection × avg 240 chunks = 8,590 points / 4096d** — Qdrant 공식 벤치 대비 points 1/100, dim 10× 크기. p95 계수 추정 **<100ms** (로컬 docker-compose, 8코어/16GB 기준).
- 따라서 로컬 실측 p95 <200ms 는 **보수적 PASS threshold**, <50ms 는 payload filter only scenario 기준.

- **PASS**: Scenario 1 p95 < 50ms, Scenario 2 p95 < 200ms (로컬 docker-compose 기준)
- **WARN**: p95 50-200ms (Scenario 1) / 200-500ms (Scenario 2) → 운영 가능하되 payload index 튜닝 권고
- **FAIL**: p95 > 500ms → HNSW `ef_construct` 또는 composite payload index 설계 재검토 (v1.2)

**Hardware baseline 기록 의무**: CP3 verdict 작성 시 측정 HW (`/proc/cpuinfo` model, RAM, docker resource limit) 를 `docs/checkpoint_3_review.md §2` 에 명기하여 재현성 확보. 향후 HW 변경 시 재측정 필요.

---

## 3. C-P2-1 — F5 fallback suffix 재임베딩 드리프트 측정

### 3.1 현 상태 (I1 fix 반영)

| 지표 | 값 | 비고 |
|---|---:|---|
| chunks_total | 8,590 | CP2 post-I1 |
| F5 suffix (paragraph_id=null + #) | **3,919** | 8,590 의 **45.6%** — critic의 3,989 에서 I1 TOC leak 70 제거 반영 |
| 고유 stem cluster 수 | 679 | |
| 최대 cluster | 201 (ISA-720 appendix) | |
| 상위 10 cluster 합 | 832 (전체 F5 의 21%) | |

### 3.2 드리프트 측정 시뮬레이션 (Phase 3 Qdrant 적재 후)

parser-implementer 의 Task #5 전수 적재 후 **artificial block insertion** 으로 source_idx shift 영향 측정:

1. **Baseline embed**: 8,590 chunk 전수 Upstage Solar 호출 → Qdrant 적재 완료 상태
2. **Mutation 1**: ISA-720 MD 재생성 시 임의 paragraph_body 1 개 삽입 (예: idx 9535 뒤) → 201 chunk 중 ~**195개 chunk_id 변경** 추정 (삽입 위치 이후)
3. **Mutation 2**: ISA-1200 MD 에서 동일 시뮬레이션 → 64 + 49 + 32 = **145 chunk_id 변경** 추정
4. **전수 실행**: 36 ISA 파일에 대해 "맨 앞 블록 하나 삽입" 시뮬레이션 → 영향받는 chunk_id 집계

### 3.3 측정 스크립트 (준비본)

```python
# 의사코드 — Phase 3 DB 완성 후 시뮬레이션
import subprocess, json
from copy import deepcopy

# Baseline: 8,590 chunk_ids snapshot
baseline_ids = set()
for p in sorted(Path("output/json").glob("ISA-*.json")):
    with open(p) as f:
        data = json.load(f)
    baseline_ids.update(c["chunk_id"] for c in data["chunks"])

# Mutation: ISA-720 MD 에 dummy block 삽입 후 재파싱
# (실제 시뮬레이션은 DOCX → MD pipeline 재실행 필요 — Phase 3 scope 외)
# 대신 정적 분석:
from collections import Counter

drift_stats = {}
for p in sorted(Path("output/json").glob("ISA-*.json")):
    with open(p) as f:
        data = json.load(f)
    # suffix chunks = 이 파일에서 source_idx 의존하는 chunk 수
    suffix = [c for c in data["chunks"] if c["paragraph_id"] is None and "#" in c["chunk_id"]]
    drift_stats[data["standard"]["standard_id"]] = {
        "total": len(data["chunks"]),
        "suffix_dependent": len(suffix),
        "ratio": len(suffix) / len(data["chunks"]),
    }

# Report: "which ISA has largest drift footprint per single-block edit"
import operator
ranked = sorted(drift_stats.items(), key=lambda kv: kv[1]["suffix_dependent"], reverse=True)
for isa, s in ranked[:10]:
    print(f"{isa}: total={s['total']}, suffix_dep={s['suffix_dependent']} ({s['ratio']:.1%})")
```

### 3.4 판정 기준

- **REPORT-ONLY (현 v1.1.1 합의)**: 드리프트 비율을 기록. v1.2 개선 판정은 Phase 4 RAG 실사용 후 재파싱 빈도 실측 기반으로 재평가.
- `docs/checkpoint_3_review.md` 에 숫자만 확정 (절대 지표 + ISA 별 분포).

---

## 4. C-P2-6 — tiktoken vs Solar tokenizer 오차 측정

### 4.1 측정 목적

`token_estimate` 는 `tiktoken.cl100k_base` 기준. Upstage Solar 실 tokenizer 와 gap 이 클 경우 `soft_limit = 3500` 의 77 token margin (`max=3423`) 이 실제 Solar 기준으로 초과할 위험.

### 4.2 Calibration 프로토콜

parser-implementer 의 `embedder.py` 가 Upstage Solar API 를 호출할 때 response 의 `usage.prompt_tokens` (또는 유사 필드) 를 수집:

```python
# embedder.py 에서 로그 수집
def embed_passage(text: str) -> tuple[list[float], int]:
    resp = solar_client.embeddings.create(model="solar-embedding-1-large-passage", input=text)
    return resp.data[0].embedding, resp.usage.prompt_tokens  # Solar 실측 토큰
```

100+ chunk 샘플 (다양한 token_estimate 구간) 수집 후:

```python
import json, statistics
from pathlib import Path

samples = []  # [(tiktoken_estimate, solar_actual), ...]
# Phase 3 embedder 가 기록한 로그를 파싱

ratios = [solar / tiktoken for tiktoken, solar in samples if tiktoken > 0]
median_ratio = statistics.median(ratios)
p95_ratio = statistics.quantiles(ratios, n=20)[18]
max_ratio = max(ratios)

print(f"Solar/tiktoken ratio — median={median_ratio:.3f}, p95={p95_ratio:.3f}, max={max_ratio:.3f}")

# 재평가:
# soft_limit_safe = int(3500 / max_ratio) — worst-case Solar 측 4000 초과 방지
# e.g. if max_ratio = 1.15, safe_soft_limit = 3043 → chunk_splitter soft_limit 재튜닝 필요
```

### 4.3 판정 기준

| ratio | 판정 | 조치 |
|---|---|---|
| 0.90 ≤ ratio ≤ 1.05 (±5%) | PASS | soft_limit 3500 유지 |
| 1.05 < ratio ≤ 1.15 | WARN | `docs/json_schema.md §9.3` 주석에 ratio 기록, v1.1.2 PATCH bump |
| ratio > 1.15 or max_ratio > 1.20 | **FAIL** | soft_limit `3500 / max_ratio` 로 축소, chunk_splitter 재실행 필요 (v1.2 MINOR bump) |
| ratio < 0.90 | WARN (보수적 오버측정) | 현재 margin 충분, v1.2 에서 soft_limit 확장 검토 |

### 4.4 Sample 구간 전략

8,590 chunk 중 token_estimate 분포:

| 구간 | chunks |
|---|---:|
| <500 | 8,539 |
| 500-1000 | 41 |
| 1000-2000 | 6 |
| 2000-3000 | 1 |
| 3000-3500 | 3 (ISA-1200 3-part split part0/part1, ISA-540 table × 1) |
| ≥3500 | 0 |

**V2 정정 (critic cross-check 2026-04-21)**: 전수 census **51 chunks** (token_estimate ≥ 500 전 구간 합 41+6+1+3+0 = 51; sampling 불필요). ISA-1200 3-part split 3 chunks 는 이미 [3000,3500) 2건 + [1000,2000) 1건 (part2 token=1,807) 에 포함되어 있어 별도 가산하지 않음. Upstage API 호출 비용 <1원 (passage cache 활용 시 0원, fresh 호출 시 ~51× embedding 1회).

---

## 5. C-P2-8 — chunks_total 10,000 trigger 미도달 확인

### 5.1 현 상태

- chunks_total = **8,590** (post-I1)
- v1.1 birthday trigger 기준 10,000 미도달
- Phase 4 (ISQM 1, 인증업무개념체계, 기타 인증업무기준) 통합 시 **~15,000 예상** → 10,000 돌파 예정

### 5.2 검수 항목 (단순)

- METRICS.json `chunks_total` 값 재확인: 8,590
- 10,000 돌파 예정 시점: **Phase 4 CHECKPOINT 4**
- `docs/checkpoint_3_review.md` 에 `현 8,590 < 10,000 trigger — PASS` 1 줄 확정

---

## 6. CP3 구조 검수 항목 (§9.5 외 4항목)

### 6.1 Qdrant collection naming

`CLAUDE.md §5` 패턴 `audit_standards_{문서종류}_{연도}` 일치 검증.

- 기대값: `audit_standards_회계감사기준_2025`
- 확인 방법: `qdrant_client.get_collections().collections` → name 전수 비교

### 6.2 Payload 매핑 전수 검증

`docs/json_schema.md §13` 의 19 필드가 Qdrant payload 에 모두 존재하는지:

| # | 필드 | indexed 여부 | 타입 |
|---:|---|---|---|
| 1 | standard_id | ✓ keyword | str |
| 2 | standard_no | ✓ keyword | str |
| 3 | source_file | ✗ | str |
| 4 | authority_base | ✗ | int |
| 5 | chunk_id | ✓ keyword | str |
| 6 | paragraph_id | ✓ keyword | str\|null |
| 7 | kind | ✓ keyword | str |
| 8 | section | ✓ keyword | str\|null |
| 9 | appendix_index | ✓ integer | int\|null |
| 10 | heading_trail | ✗ | List[str] |
| 11 | heading_trail_hash | ✓ keyword | str |
| 12 | parent_paragraph_id | ✓ keyword | str\|null |
| 13 | is_application_guidance | ✓ bool | bool |
| 14 | authority | ✗ | int |
| 15 | token_estimate | ✗ | int |
| 16 | chunk_index | ✗ | int |
| 17 | chunk_of | ✗ | int |
| 18 | source_idx | ✗ | int |
| 19 | part_of | ✓ keyword | str\|null |
| 20 | content_text | ✗ | str |
| 21 | content_markdown | ✗ | str |
| 22 | table_cells | ✗ | List[List[str]]\|null |
| 23 | embedded_at | ✗ | str\|null |
| 24 | embedding_model | ✗ | str\|null |

**검증**: 2-3 point 랜덤 추출 → `payload.keys()` 전수 비교.

**Named vectors 검증**:
- `passage` vector 4096d (Upstage Solar passage encoder)
- `summary` vector 4096d (standard-level summary embedding)

### 6.3 §8.4 incremental idempotency

parser-implementer Task #4 (`ingest --upsert` CLI) 의 idempotency 검증:

```bash
# 첫 적재 — 전수 upsert
audit-parser ingest output/json/ --collection audit_standards_회계감사기준_2025

# 두번째 실행 — 동일 collection, 동일 파일 → no-op (skip) 또는 재upsert (payload 동일)
audit-parser ingest output/json/ --collection audit_standards_회계감사기준_2025

# Solar API 호출 횟수 비교:
#   - 1회차: 8590 호출 (baseline embedding)
#   - 2회차: 0 호출 (embed_cache.sqlite 에서 재사용)
```

**stale suffix 시나리오**: 삽입 후 cluster 재편 시 stale chunk 를 삭제해야 하나?

- `docs/json_schema.md §8.4` — "**stale suffix 제거 보장 필요**"
- 검증: mock scenario 로 chunk_id 변경된 경우 Qdrant 에 동시에 new + stale 두 point 가 존재하지 않는지

### 6.4 C-P2-9 per-collection atomicity

중간 실패 시 부분 적재 상태:

- 단일 ISA ingest 중 network error → 해당 collection 은 "partial" 상태
- `--resume` 또는 재실행 시 기존 부분 chunk 를 **drop and rebuild** 또는 **upsert-from-where-left-off**?

검증: ISA-720 (474 chunk) 적재 중 강제 중단 → 재실행 → 중복 없이 전수 474 chunk 도달 확인.

---

## 7. Phase 2 stale-claim 교훈 체화 (검수 원칙)

`docs/checkpoint_2_review.md` Appendix A.4 Critic 협업 교훈 + `docs/devils_advocate_checkpoint_2.md` Self-audit 기반:

1. **전수 스캔 재확인**: METRICS 집계 수치를 fraction 지표로만 수용하지 말고, 독립 스크립트로 raw count 재산출.
2. **timing-dependent 상태는 "재읽기 재확인"**: Qdrant collection 상태는 parser 실행 시점 스냅샷. 검수 시 재조회 후 판정.
3. **DM 발송 전 scope 재검증**: C-P2 self-audit 의 "9 ISA 보론 리스트" 오기재 사례 재발 방지. scope 공표 후 실측 diff 교차 확인.
4. **Predictive delta 사전 공표**: I1 fix 시 8/8 예측치 공표 → 실측 매치 → 검증 신뢰성 강화. Phase 3 fix 요청 시 동일 패턴 적용.

---

## 8. 예상 검수 스케줄 (DM 수신 후)

| 단계 | 소요 | 블로커 |
|---|---|---|
| 0. Task #5 완료 DM 수신 + TaskUpdate → in_progress | 즉시 | — |
| 1. §9.5 10 seed query 실측 (Qdrant 적재 + embed_query) | 30-60 min | parser-implementer 의 Task #6 search demo 제공 여부 |
| 2. 201-member cluster latency 측정 | 20 min | Qdrant 적재 완료 |
| 3. tiktoken vs Solar calibration (51 chunk 전수) | 20 min | embedder.py 에 usage.prompt_tokens 기록 추가 필요 |
| 4. F5 드리프트 정적 분석 | 10 min | — (정적 분석만) |
| 5. 구조 검수 4항목 (payload, collection, idempotency, atomicity) | 40 min | parser-implementer Task #4 완료 |
| 6. `docs/checkpoint_3_review.md` 작성 | 60 min | 위 1-5 결과 |

**총 약 3-4시간 실측 작업**. rework 1건 발생 시 추가 60min.

---

## 9. TODO on Task #5 완료 시 실행 (self-checklist)

- [ ] parser-implementer DM "Task #5 complete" 수신
- [ ] TaskList → TaskUpdate #7 status `pending → in_progress`, owner `audit-standard-domain-reviewer`
- [ ] METRICS.json + Qdrant collection 현 상태 재조회 (timing-dependent)
- [ ] §9.5 10 seed query 중 3 개를 먼저 실행 → pipeline sanity check
- [ ] 5 구조 검수 + 5 DEFER 실측 병렬 진행
- [ ] `docs/checkpoint_3_review.md` 초안 작성 → self-audit → critic cross-check DM → 최종 verdict

---

**관련 문서**:
- `docs/checkpoint_2_review.md` (Appendix A.5 CP3 scope)
- `docs/devils_advocate_checkpoint_2.md` (C-P2-1/3/6/7/8/9 DEFER)
- `docs/json_schema.md v1.1.1 §8.4 / §9.4 / §9.5 / §13` (검수 기준)
- `PLAN.md §4 Phase 3` (CLI 및 collection 네이밍)
- `output/json/METRICS.json` (8,590 chunks baseline)

---

## Addendum A — Critic S1/S2/S3 scope 확장 반영 (2026-04-21 receipt)

devils-advocate-critic 의 사전 증거 DM 수신 (CP2 에 준하는 pre-CP3 advisory). CP3 scope 에 다음 3 축 추가.

### A.1 S1 — `summary` named vector 구체 정의 (invariant 추가)

`docs/json_schema.md §13` 의 `"summary": standard_summary_embedding` 은 **source text / model / metric 모두 미확정**. CP3 검수 시 다음 4 항목을 parser-implementer Task #3 (qdrant_writer) 산출에 대해 실측 확인:

| # | 항목 | 기대값 (CP3 검증) |
|---|---|---|
| S1-1 | **source text 구성** | `StandardSummary.scope_markdown + "\\n\\n" + StandardSummary.definitions_markdown` (null 시 빈 문자열) — 둘 다 null 인 기준서는 `summary.embedding = null` 허용 |
| S1-2 | **Upstage model** | `solar-embedding-1-large-passage` (passage encoder) — `summary` vector 도 passage model 로 통일 (query encoder 사용 금지) |
| S1-3 | **distance metric** | `Cosine` (passage 와 동일). named vector 두 개 `passage` / `summary` 가 같은 collection 안에서 동일 metric 보장. |
| S1-4 | **dimension** | 4096 (Solar 4096d) — `passage` 와 동일 |

**검수 방법**: `client.get_collection("audit_standards_회계감사기준_2025")` 로 `config.params.vectors` dict 전수 조회 → 두 named vector 의 size/distance 확인.

**판정**: S1-1~4 모두 충족 시 PASS. 단 하나라도 불일치 → parser-implementer 에 rework 요청 (CP3 rework 예산 2 중 1 할당).

### A.2 S2 — DEFER 5건 4-axis 정량 경계 (Phase 4 유예 재연장 방지)

각 DEFER 항목마다 **threshold / metric / test procedure / bump target** 4축 명기. Critic 지적: "§9.5 만 정량화 됨, 나머지 4건 재연장 risk."

| ID | threshold | metric | test procedure | bump target |
|---|---|---|---|---|
| **C-P2-1** (F5 드리프트) | ISA 단일 block 삽입 시 재할당 chunk 비율 **≥ 20% (per-ISA avg)** | `drift_ratio = affected_chunks / total_chunks` | **§3.2 정적 분석 (theoretical upper bound)**: `suffix_dependent / total` per-ISA 36 전수 + 10% trimmed mean. **§3.3 synthetic perturbation 의사코드**: ISA-720 appendix 201-cluster idx 9535 뒤 dummy paragraph 삽입 simulation → chunk_id shift 비율 계산 (V1 critic 권고 2026-04-21, 실제 DOCX 재생성은 Phase 4 scope). 실행 스크립트 경로 (CP3 본실행 시): `docs/checkpoint_3_review.md` §3 에 inline 기재 (src/ 수정 불필요 — JSON 전수 static scan) | 초과 시 v1.2 MINOR — `{kind}#sha1(content_text)[:6]` fallback 옵션 제공 (선택적) |
| **C-P2-3** (header bias) | §9.5 기준: **≥ 30% co-occur OR cosine Δ < 0.01** | top-5 co-occur ratio + pairwise cosine Δ | §1.4 10 seed query 프로토콜 | 초과 시 v1.2 MINOR — header-suppression rule (첫 조각 유지, 2nd+ 는 "용어의 정의 (이어서)" 대체) |
| **C-P2-6** (tokenizer gap) | Solar/tiktoken ratio **median ≥ 1.05 OR max ≥ 1.15** | ratio distribution over **51 chunks** (`token_estimate ≥ 500` 전수 census, V2 정정 2026-04-21) | §4.2 calibration, embedder.py usage.prompt_tokens 수집 | median >1.05 → v1.1.2 PATCH (주석 기록), max >1.15 → v1.2 MINOR (soft_limit 축소) |
| **C-P2-7** (cluster latency) | p95 **> 500ms** (Scenario 2 HNSW+filter) | 100회 측정 median + 95th percentile | §2.3 protocol, warm 30 + measure 100 | 초과 시 v1.2 MINOR — composite payload index `(section, heading_trail_hash, kind)` 도입 검토 |
| **C-P2-8** (10k trigger) | chunks_total **≥ 10,000** | METRICS.json 실측 | Phase 4 통합 후 재산출 | 도달 시 `§6.2.1` v2.0 MAJOR 기획 착수 (sha1[:12] or standard_no 포함) |

**CP3 산출**: `docs/checkpoint_3_review.md` 에 위 표 그대로 + 각 실측 결과 컬럼 추가하여 **Phase 4 재연장 되지 않도록 측정값 고정**.

### A.3 S3 — v1.2 MINOR bump candidates 표 신설 권고

Critic 지적: "v1.2 후보가 §8.4, §9.5, Phase 4 prefix 확장 3곳에 산재 — 일괄 가시화 필요."

CP3 verdict 확정 후 **domain-reviewer 권한으로 `docs/json_schema.md §16 Changelog 직전에 `§15a v1.2 MINOR bump Candidates` 표 1개 신설** 합의 제안:

| 후보 | 근거 섹션 | trigger 조건 | 현 CP3 상태 |
|---|---|---|---|
| Header-suppression (§9.5) | §9.5, C-P2-3 | co-occur ≥30% OR cosine Δ <0.01 | CP3 §1.4 실측 결과 |
| Stale suffix cleanup (§8.4) | §8.4, C-P2-9 | incremental ingest 실측상 stale chunk 실효 | CP3 §6.3 실측 결과 |
| `{kind}#sha1-content` fallback (§6.4) | §6.4, C-P2-1 | F5 드리프트 ≥20% per-ISA | CP3 §3.4 실측 결과 |
| Phase 4 standard_id prefix 확장 | §3 standard, §5.2 | ISQM 1 / 인증개념 / 기타인증 통합 시점 | Phase 4 necessity |
| soft_limit 축소 (§9.3) | §9.3, C-P2-6 | Solar/tiktoken ratio max >1.15 | CP3 §4.4 실측 결과 |

**처리**: CP3 verdict 작성 시 domain-reviewer 가 본 표 초안을 `docs/checkpoint_3_review.md` 에 포함하여 team-lead 승인 후 `docs/json_schema.md` §15a 신설 반영 (쓰기 권한 있음).

### A.4 추가 invariant 5건 (CP3 §6 구조검수에 병합)

Critic 제안 5 invariant 를 §6 구조 검수에 흡수:

| # | Invariant | 검증 스크립트 (의사코드) |
|---|---|---|
| I-a | `len(passage_embedding) == 4096` 전수 (8,590 건) | `all(len(pt.vector["passage"]) == 4096 for pt in client.scroll(...))` |
| I-b | `StandardSummary.embedding` 36 기준서 non-null + dim 4096 | `len(standard_summary_vectors) == 36 and all(len(v) == 4096 for v in vectors)` |
| I-c | `chunk_id → uuid5(chunk_id)` 충돌 0 | 8,590 chunk_id → uuid5 list 중 `len(set) == 8590` |
| I-d | Qdrant payload index 5 종 생성 확인 | `collection.payload_schema.keys() ⊇ {"standard_no", "kind", "section", "appendix_index", "heading_trail_hash"}` |
| I-e | I1 회귀: `content_text.strip() ∉ {"목차","문단번호"}` 전수 (Qdrant 적재 후 재확인) | `client.scroll(filter=must_match("content_text", "목차")).points == []` |

**추가 항목**:
- payload index 5종에 `chunk_id`, `paragraph_id`, `parent_paragraph_id`, `part_of`, `is_application_guidance` 포함 여부 별도 확인 (json_schema §13 총 8종 indexed).

### A.5 CP3 Task #7 실행 시 반영 지침

- 본 Addendum A 를 `docs/checkpoint_3_review.md` 실측 시 **§5 Issues 표 이전 section** 으로 통합 (S1/S2/S3 → 별도 "Critic pre-advisory 반영" 장).
- Critic 의 최종 비판 보고서 (`docs/devils_advocate_checkpoint_3.md`) 수령 전 CP3 초안 작성 → critic cross-check 후 verdict 확정 (CP2 와 동일 protocol).
- rework 예산: 현 2/2 중 **S1 S1-1~4 실측 결과 미정합 시 1 할당** — parser-implementer Task #3 (qdrant_writer) 재설계가 필요할 수 있음.

---

*End of CP3 prep. 본 문서는 Task #5 완료 전 idle-mode prep 산출. 실측 완료 후 `docs/checkpoint_3_review.md` 에 통합하며 본 prep 은 보존 (재현성 기록). Addendum A 는 critic 사전 증거 수령 후 2026-04-21 추가.*
