# Devils Advocate — CHECKPOINT 0 설계 반박 보고서

**작성일**: 2026-04-20  
**작성자**: devils-advocate-critic  
**검토 대상**: Phase 0 산출물 전체 (PLAN.md, ifrs_reference_map.md, 루트 설정파일 일체)  
**참조 산출물**:
- `PLAN.md` (원본 계획)
- `docs/ifrs_reference_map.md` (ifrs-convention-scout 산출)
- `docs/isa_structure_profile.md` (audit-standard-domain-reviewer 산출)
- `pyproject.toml`, `docker-compose.yml`, `.gitignore`, `.env.example`, `src/`, `README.md` (parser-implementer 산출)

---

## 비판 1 (필수 a): pgvector → Qdrant 변경 — 정당성 검증

### 관찰

PLAN.md §1은 "차이 1: pgvector → Qdrant"를 3대 차별화 중 하나로 명시하지만, **변경 이유를 단 한 줄도 서술하지 않는다**. ifrs_reference_map.md §4.2는 "db_writer.py는 완전 재작성"이라는 비용을 명확히 인정하면서도 그 비용을 지불할 만한 근거를 제시하지 않는다.

schema.sql을 보면 IFRS 파이프라인은 이미 4096차원 벡터를 pgvector로 적재하고 있다(`vector(4096)`). 단, pgvector 0.6의 HNSW 인덱스 2000차원 상한 때문에 IVFFlat으로 우회하고 있으며, 현재 인덱스조차 주석 처리된 상태(Exact Search)다. 이 점이 Qdrant 전환의 핵심 동기일 가능성이 높다. 하지만 PLAN.md 어디에도 이 내용이 명시되어 있지 않다.

**운영 일관성 손실 항목 구체화**:

| 항목 | pgvector 유지 시 | Qdrant 추가 시 |
|------|----------------|--------------|
| DB 인프라 | PostgreSQL 1개 (IFRS DB 동일 인스턴스 또는 분리) | PostgreSQL + Qdrant 별도 운영 |
| 백업 | pg_dump 단일 절차 | pg_dump + Qdrant snapshot 두 절차 |
| 모니터링 | PostgreSQL 메트릭 단일 계기판 | 이종 DB 각각 모니터링 |
| 코드 재사용 | `db_writer.py` 거의 그대로 포팅 가능 | `qdrant_writer.py` 완전 재작성 |
| 팀 학습 비용 | 없음 (IFRS에서 이미 숙련) | Qdrant API 러닝커브 추가 |

**Qdrant의 실제 이점 검토**:

1. **HNSW 4096차원 지원**: pgvector 0.6 HNSW는 2000차원 상한. Qdrant는 제한 없음. 이것이 가장 구체적인 이점이다. 단, pgvector 0.7(2024년 말 릴리스)에서 이 제한이 완화되었을 수 있으므로 버전 확인 필요.
2. **Named Vectors**: 청크(`passage`) + 요약(`summary`)을 동일 포인트에 결합. pgvector는 컬럼 2개(`embedding`, `summary_embedding`)로 동등 구현 가능 — 이점이 아니라 선호 차이.
3. **Payload 인덱싱 및 filter 성능**: Qdrant는 벡터+필터 복합 검색을 HNSW 내부에서 처리. pgvector는 WHERE 절 + 벡터 검색을 분리 처리. 이 프로젝트의 쿼리 복잡도(standard_id, section 필터 정도)에서 성능 차이가 유의미한지 실증 미확인.
4. **REST/gRPC API**: 마이크로서비스 배포 시 이점. 현재 파이프라인은 로컬 스크립트 — 현재 단계에서 해당 없음.

**대안: pgvector 유지 + 분리 DB 전략**:
- `kifrs` DB와 별도로 `audit_standards` DB 생성 (동일 PostgreSQL 인스턴스)
- pgvector 버전 업그레이드 후 HNSW 4096d 지원 여부 확인 (pgvector `>=0.7.0`)
- trade-off: 인프라 단순화, 코드 재사용 극대화. 단, pgvector 0.7 이전이면 IVFFlat 우회 필요.

### 영향

결정 근거 없이 Qdrant를 도입하면, 6개월 후 운영 과정에서 다음 문제가 발생한다:
- Qdrant 컨테이너 장애 → 별도 복구 절차, IFRS pgvector 장애와 다른 대응 필요
- 새 팀원 온보딩 시 두 가지 벡터 DB API를 모두 학습해야 함
- `db_writer.py` 재사용 불가로 IFRS 파이프라인에서 가져온 공통 패턴(upsert idempotency, ON CONFLICT 등)이 Qdrant 방식으로 재구현되면서 두 코드베이스 간 diverge 심화

### 완화안

1. **pgvector 버전 확인 선행**: `pgvector/pgvector:pg17` 이미지의 버전이 0.7+ 이면 4096d HNSW 지원 여부 확인. 지원된다면 pgvector 유지가 합리적.
2. **Qdrant 유지 조건 명시**: "pgvector HNSW 4096d 미지원"이 유일한 전환 근거라면 PLAN.md에 명시. "Qdrant의 추가 기능(named vectors, payload filter ANN)을 미래에 활용할 계획"이 있다면 그것도 명시.
3. **IFRS DB 통합 옵션 검토**: Qdrant 단일 인스턴스에서 `kifrs_*` collection과 `audit_standards_*` collection을 공존시키는 안. 백업·모니터링 단일화 가능.

### 권고: **Serious (Phase 1 전 해결)**

Qdrant 채택 결정이 "pgvector HNSW 4096d 상한 우회"를 근거로 한다면 PLAN.md에 이 사실을 명기하고, pgvector 최신 버전 확인 후 여전히 제한이 있을 때만 Qdrant를 확정한다. 근거 없는 기술 선택은 추후 유지보수 부채가 된다.

---

## 비판 2 (필수 b): 파일별 별도 collection vs 단일 collection + source_file filter

### 관찰

PLAN.md §2 결정 3번: "파일별 별도 collection"이 사용자 결정으로 확정되어 있다. 이 결정을 뒤집을 수 없더라도, 설계의 trade-off가 충분히 분석되어 있는지 검토한다.

**실제 검색 시나리오 3가지**:

**시나리오 A — 교차 문서 개념 통합 검색**  
> "독립성 요구사항과 관련된 내용을 감사기준서 전체(회계감사기준+품질관리기준서)에서 찾아줘."

- **별도 collection 구조**: 각 collection에 개별 검색 후 결과 병합 필요. `audit_standards_회계감사기준_2025`와 `audit_standards_품질관리기준서_2018`에 각각 쿼리 → 결과 수동 re-ranking. `top_k=10`이면 실제로 각 collection에서 10개씩 가져와 20개를 re-rank해야 함.
- **단일 collection 구조**: `source_file` payload filter 없이 단일 쿼리 → Qdrant가 전체 공간에서 nearest-neighbor 자동 처리. 교차 문서 유사도 기반 정렬 자동 달성.

**시나리오 B — 동일 개념의 기준서 간 차이 비교**  
> "회계감사기준서 220의 품질관리 요구사항과 품질관리기준서1의 같은 주제 문단을 함께 검색하고 싶다."

- 별도 collection: 두 collection에서 검색 후 cosine score 기반 병합. score 분포가 collection마다 다를 수 있어 공정한 병합 어려움.
- 단일 collection: 동일 cosine space에서 비교 가능 — 의미적으로 정확.

**시나리오 C — 단일 기준서 문서 내 검색 (격리 필요 케이스)**  
> "감사기준서 315의 리스크 평가 절차 요구사항만 검색하고, 다른 기준서는 노이즈가 되지 않게 해줘."

- 별도 collection: 해당 collection만 쿼리 → 자연스러운 격리. 단, `standard_id`가 payload에 있으므로 단일 collection에서도 `must: standard_id = "ISA-315"` filter로 동일 효과 달성 가능.

**결론**: 시나리오 A, B는 단일 collection이 우월. 시나리오 C는 별도 collection의 유일한 이점이지만, payload filter로 대체 가능.

**Qdrant HNSW 인덱스 비용 분석**:

- 4개 collection 각각 별도 HNSW 인덱스: 각 collection의 `m`, `ef_construct` 파라미터가 독립적으로 작동. 총 메모리: collection별 합산.
- 추정 벡터 수: 회계감사기준 ~5,400, 품질관리기준서 ~400, 기타인증업무기준 ~500, 인증업무개념체계 ~300. Named vectors 2개(passage+summary)라면 총 ~12,800 벡터.
- 4096 × 4 bytes × 12,800 vectors × 1.3(HNSW overhead) ≈ **272 MB** — 현재 규모에서는 메모리 압박 없음.
- 그러나 collection이 적으면 HNSW 그래프가 더 조밀 → **단일 large collection이 검색 품질 면에서 더 유리**. small collection(400 벡터)에서 HNSW m=16은 과적합에 가깝고 graph quality 저하.

**재적재 비용 비교**:

| 상황 | 별도 collection | 단일 collection + partition |
|------|----------------|---------------------------|
| 특정 문서 재임베딩 | 해당 collection drop → recreate → 재적재 | source_file filter로 해당 포인트만 delete → upsert |
| 전체 재임베딩 | 4개 collection 순차 drop/recreate | 단일 collection drop → recreate |
| 신규 문서 추가 | 신규 collection 생성 | 기존 collection에 upsert |

단일 collection + source_file filter가 재적재 유연성에서도 우월하다.

### 영향

4개의 소규모 collection으로 분리하면, 교차 문서 검색이 필요한 RAG 파이프라인에서 **Application Layer 복잡도**가 집중된다. 특히 품질관리기준서(~400벡터)는 HNSW 인덱스를 구성하기에 너무 작다 — nearest-neighbor 품질이 떨어질 수 있다.

6개월 후 추가 문서(인증업무기준 등)가 늘어날수록 collection 관리 목록이 선형 증가하고, 교차 검색 코드가 복잡해진다.

### 완화안

1. **단일 collection 전환**: `audit_standards` 단일 collection + payload `source_file`, `collection_tag` 필드. 교차 검색 단순화, HNSW 품질 향상.
2. **계층적 구조**: `audit_standards_isa` (감사기준서 계열), `audit_standards_other` (품질관리+인증업무). 2개 collection으로 절충.
3. **현행 유지 + 교차 검색 헬퍼**: 별도 collection 유지하되, `search_across_collections()` 헬퍼 함수를 `qdrant_writer.py`에 추가해 교차 검색 re-ranking 추상화. 코드 복잡도를 단일 위치에 격리.

### 권고: **Serious (Phase 1 전 해결)**

사용자가 명시적으로 "별도 collection"을 결정했으나, 이 결정이 교차 문서 검색 시나리오를 고려한 것인지 불명확하다. Phase 1 착수 전에 "교차 문서 검색이 요구사항인가?"를 사용자에게 확인하고, Yes라면 단일 collection 또는 헬퍼 레이어 설계를 추가해야 한다.

---

## 비판 3 (필수 c): Solar 4096 차원 HNSW 최적성

### 관찰

**메모리 추정**:

| 구성 | 벡터 수 | 메모리(raw) | HNSW 오버헤드(1.3x) | 합계 |
|------|---------|------------|-------------------|------|
| 4096 float32, 단일 collection | 6,600 | 103 MB | 134 MB | ~134 MB |
| 4096 float32, named vectors (×2) | 13,200 | 206 MB | 268 MB | ~268 MB |
| 4096 int8 scalar quantization | 13,200 | 52 MB | 68 MB | ~68 MB |
| 1024 float32 (BGE-M3) | 13,200 | 52 MB | 68 MB | ~68 MB |

현재 규모(~6,600 청크)에서는 268 MB로 로컬 운영 가능. **메모리 자체는 Blocker가 아니다.**

**그러나 핵심 문제는 메모리가 아니다**: pgvector의 HNSW는 2000차원 상한이라 4096차원에 IVFFlat(또는 Exact Search)을 써야 했다. Qdrant는 HNSW로 4096차원을 지원한다 — 이것이 정당한 이점이다.

**pgvector schema.sql의 주석이 결정적 단서다**:
```sql
-- pgvector 0.6은 HNSW 최대 2000차원, 4096차원은 IVFFlat 사용
-- CREATE INDEX idx_chunks_embedding ON chunks
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```
현재 IFRS 파이프라인은 Exact Search 상태(인덱스 없음). IVFFlat으로 전환해도 recall 손실이 발생. Qdrant HNSW는 이 문제를 해결한다.

**대안 비교**:

| 옵션 | 차원 | 한국어 성능 | 비용 | 비고 |
|------|------|-----------|------|------|
| Upstage Solar (현행) | 4096 | 우수 (한국어 특화 MTEB 상위) | 유료 API | IFRS에서 이미 사용 중 |
| BGE-M3 | 1024 | 좋음 (multilingual MTEB 상위) | 로컬 실행 가능 (무료) | 자체 서버 GPU 필요 |
| Upstage Solar Matryoshka | 미확인 | - | - | Matryoshka 지원 여부 미확인 |
| Scalar Quantization (int8) | 4096 → 1024 bytes | Solar 동일 | 추가 비용 없음 | 검색 recall ~0.5-1% 감소 |
| Product Quantization | 4096 → 압축 | Solar 동일 | 추가 비용 없음 | 높은 압축률, recall 감소 큼 |

**Upstage Solar Matryoshka 지원 여부**: 공식 문서에서 Matryoshka/Truncatable Dimensions 지원이 명시되어 있지 않다. 확인 없이 차원 축소 계획을 세우면 안 된다.

**Scalar Quantization 권고 조건**: 현재 ~268 MB는 로컬 8GB 이상 RAM에서 문제없음. 청크 수가 50,000을 초과하는 경우(4개 docx 외 대규모 확장 시) 재검토 필요.

**HNSW 파라미터 `m=16, ef_construct=200` 적합성**:
- PLAN.md §3에서 이 파라미터가 명시되어 있으나 근거 없음.
- 일반 권고: `m=16`은 moderate density, recall과 메모리의 균형. 6,600벡터 규모에서는 적절하나, `ef_construct=200`은 index build time 증가 (품질 향상 목적). 현재 규모에서는 오버킬일 수 있으나 harm 없음.
- **실제 문제**: `ef` (search time parameter, 기본 100)가 설정에 빠져있다. `ef >= top_k`여야 정확한 검색이 보장됨.

### 영향

4096차원 HNSW에서 Scalar Quantization 없이 운영하면 현재 규모에서는 문제없다. 하지만 Phase 4 이후 추가 문서를 계속 적재할 경우, 50,000 벡터 초과 시 RAM 4GB+ 상황에서 Docker 컨테이너 OOM이 발생할 수 있다.

Solar 임베딩 모델의 Matryoshka 미지원 확인 없이 "필요 시 차원 축소" 계획을 세우면, 나중에 차원 축소 불가 판정 시 전체 재임베딩 비용이 발생한다.

### 완화안

1. **현행 4096 float32 유지 + ef 파라미터 명시**: `ef=100` (default) → `ef=200` 설정 권고. search quality 향상, latency 소폭 증가.
2. **Scalar Quantization 조건부 적용**: 적재 완료 후 총 벡터 수 × 268 MB/13,200 공식으로 메모리 재추정. 2 GB 초과 예상 시 int8 활성화.
3. **Solar Matryoshka 지원 확인**: Upstage 공식 문서 또는 API response 헤더에서 `dimensions` 파라미터 지원 여부 확인. 지원되면 1024d로 줄여 BGE-M3과 동일 메모리로 Solar 품질 유지 가능.

### 권고: **Nice-to-have (현재 규모에서 비-Blocker)**

현재 ~6,600 청크 규모에서 4096d HNSW는 메모리·성능 모두 적합하다. Qdrant 전환의 핵심 이점(HNSW 4096d 지원)은 실질적이다. 단, `ef` 파라미터 명시와 Scalar Quantization 조건부 계획은 Phase 3 이전에 코드에 반영할 것.

---

## 비판 4: JSON 중간 단계 — 3가지 용도 실제 달성 여부

### 관찰

PLAN.md §2 결정 2번: JSON 중간 단계의 목적을 ① 사람 검수 ② 타 시스템 연계 ③ 재임베딩 캐시 3가지로 명시. 각각을 해부한다.

**(1) 사람 검수**: JSON은 계층구조가 명시적이어서 검수 가능하다. 그러나 JSON 배열의 청크를 눈으로 읽는 것은 Markdown을 읽는 것보다 어렵다. 감사사는 Markdown(`ISA-200.md`)을 열어보는 것이 훨씬 자연스럽다. JSON이 사람 검수용으로 추가 가치를 제공하려면 JSON Viewer 또는 별도 HTML 렌더러가 있어야 한다. **현재 계획에 이런 도구가 없으므로, 사람 검수용은 MD로 충분하다.**

**(2) 타 시스템 연계**: `schema_version` 필드와 `docs/json_schema.md`(Phase 2 산출물)가 연계용 스펙이다. 이 목적은 JSON으로만 달성 가능하며, 정당하다. **단, `docs/json_schema.md`가 Phase 2에 미룰 계획이므로, Phase 1 ~ Phase 2 사이에 외부 시스템이 연계를 시도하면 스펙 없이 사용하는 위험이 있다.**

**(3) 재임베딩 캐시**: `embedding: null` → 재임베딩 후 `embedding: List[float]` 채움. 이 패턴은 유효하다. 그러나 JSON 파일에 4096차원 float 배열을 저장하면, 청크 6,600개 × 4096 float × 4 bytes ≈ **108 MB**의 JSON 파일이 생성된다. 이를 `git` 저장소에 커밋하지 않도록 `output/`이 `.gitignore`에 있는지 확인 필요.

**현재 `.gitignore` 상태 확인**: 현재 `.gitignore`는 `.env`, `raw/`, `CLAUDE.md`, `.claude/` 만 포함. **`output/`이 없다**. 임베딩이 채워진 JSON을 커밋할 위험이 있다.

또한, `.embed_cache.sqlite`(PLAN.md §3에 언급)도 gitignore에 없다.

### 영향

- `output/` gitignore 누락: 108 MB의 임베딩 JSON이 실수로 커밋될 경우, git 이력에서 제거하려면 `git filter-repo`가 필요 — 대규모 이력 재작성 작업.
- `docs/json_schema.md` Phase 2 지연: Phase 1 완료 직후 외부 연계 시도 시 스펙 없음 → 파싱 오류 또는 misuse.
- JSON 검수 도구 부재: 사람 검수는 결국 MD로 하게 됨 → JSON 단계가 ①용도에서 실질 가치 없음. 단계가 추가될수록 파이프라인 실패 지점 증가.

### 완화안

1. **`.gitignore` 즉시 수정**: `output/`, `.embed_cache.sqlite`, `qdrant_storage/`를 추가. (pyproject.toml 산출물에 이미 있다면 재확인 필요 — 현재 `.gitignore`는 4줄뿐).
2. **`docs/json_schema.md` Phase 1 중 초안 작성**: Phase 2 완성 전에 필드 목록과 타입을 초안으로라도 작성.
3. **JSON 검수용 렌더러 계획**: `search_test.ipynb`에 JSON → HTML 간단 렌더링 섹션 추가, 또는 `audit-parser validate` CLI 명령으로 JSON → MD diff 출력.

### 권고: **Blocker (즉시 수정)**

`.gitignore`에 `output/`과 `.embed_cache.sqlite` 누락은 즉각적인 데이터 보안 및 저장소 오염 리스크다. Phase 1 착수 전에 수정 필수.

---

## 비판 5: numbering.xml 파싱 실패 시 fallback 전략 부재

### 관찰

PLAN.md §5 리스크 매트릭스에서 "ISA 문단번호가 numbering.xml 자동넘버링 — 단순 텍스트 파싱으로 불가"를 RED 리스크로 정확히 식별하고 있다. 완화책으로 "numbering.py 카운터 replay 필수, Phase 1에서 20개 수동 검증"을 제시한다.

그러나 Phase 1 구현 계획 어디에도 **파싱 실패 시 fallback 전략**이 없다.

**isa_structure_profile.md §3에서 드러난 실제 복잡도 (Domain Reviewer 실측)**:

- 전체 **742개 numId**가 존재. PLAN.md는 `numId=64`, `numId=57` 2개만 예상했으나, 실제로는 수백 개의 numId 인스턴스.
- 핵심 abstractNumId: 요구사항은 `{70, 98, 140}`, 적용지침은 `{15, 51}`. 그 외 `(%1)`, `%1.` lowerRoman, upperLetter 등 9가지 이상의 비표준 패턴 존재.
- **numId='0' 특수 케이스**: 303개 문단이 번호 명시적 제거 표시 — `numId=None`(numPr 없음)과 다르게 처리 필요.
- **lvlOverride** 존재: 일부 numId는 `<w:lvlOverride>` + `<w:startOverride>`로 카운터 재시작.

이는 PLAN.md가 상정한 "2개 numId 패턴"이 **실제 742개 numId의 극히 일부**임을 의미한다. 파서가 알려진 패턴(`abstractNumId ∈ {15, 51, 70, 98, 140}`) 외의 numId를 만날 때 어떻게 동작할지 정의되어 있지 않다.

**구체적 실패 시나리오 (Domain Reviewer EC-1~5 기반)**:
- `numId='0'`을 "numId 없음"으로 처리하면 303개 문단 분류 오류 (EC-1)
- 기준서 경계(`heading 1`) 감지 실패 → 카운터 리셋 시점 오판 → ISA-210 문단 1이 실제로는 ISA-200의 마지막 번호 다음으로 계산되는 오류 (EC-5)
- `abstractNumId` 미등록 패턴의 numId → 분류 불가, 번호 할당 실패

### 영향

numbering.xml 파싱이 실패하면 `paragraph_id`가 잘못 부여되고, MD 파일의 모든 `<!-- para: N -->` 주석이 오염된다. 이 오류는 JSON까지 전파되어, Qdrant payload의 `paragraph_id`도 잘못 적재된다.

6개월 후 감사인이 "ISA-315 문단 17을 찾아줘" 검색 시 실제로는 문단 14의 내용이 반환될 수 있다 — 회계감사 기준 오인 리스크.

### 완화안

1. **정적 테이블 fallback**: `numbering.xml`에서 패턴 인식 실패한 numId는 "UNKNOWN-{numId}-{ilvl}-{seq}" 형식 ID 부여. 파싱은 계속되고, 검수 단계에서 UNKNOWN 비율 리포팅.
2. **`unknown_*` 비율 임계값 설정**: Phase 1 검수 기준(`unknown*` kind 비율 < 5%)이 이미 있다. 동일하게 `unknown_paragraph_id` 비율 < 5% 임계값 추가. 초과 시 Phase 1 CHECKPOINT fail.
3. **numbering.xml 파싱 단위 테스트**: `tests/fixtures/isa_profile_samples.json` (Domain Reviewer 산출 예정)에서 numId 샘플을 추출해 unit test 작성. 파싱 실패 케이스를 사전에 코드화.

### 권고: **Serious (Phase 1 구현 전 반드시 설계)**

fallback 없는 파싱은 Phase 1 전체를 단일 장애점으로 만든다. 구현 전에 fallback 정책을 명시하고, `numbering.py`에 `ParseWarning` 수집 메커니즘을 추가해야 한다.

---

## 비판 6 (추가): 표(Table) 청킹 전략 미정 — ISA-1200 시한폭탄

### 관찰

PLAN.md §5 리스크 매트릭스: "표(Table) 청킹 전략 미정 → Phase 2 전 결정" 으로 MED 리스크로 분류. 그러나 isa_structure_profile.md §4에서 실측된 표 분포를 보면 이 리스크의 심각성이 과소평가되어 있다.

**실측 결과 (Domain Reviewer 산출)**:

| ISA | 표 수 | 최대 크기 | 위험도 |
|-----|:---:|:---|:---|
| ISA-315 | **10개** | 23×4, 20×2 | **높음**: 요구사항 매핑 표가 토큰 초과 확실 |
| ISA-530 | 3개 | 8×3 | 중간 |
| ISA-700~720 | 다수 | 1×1 (박스형) | 낮음 (단순 박스) |
| **ISA-1200** | 1개 | **66×2** | **치명**: 단일 표가 전체 기준서에서 가장 큼 |

특히 ISA-1200의 66행×2열 표는 EC-8에서 명시: "단일 청크로 만들면 4000 토큰 초과 가능성 높음". 4000 토큰 ≈ 16,000자. 66행 × 2열의 요구사항 대조표는 가볍게 이 임계값을 초과한다.

**더 심각한 문제**: 78개 표 중 58개(78%)가 1×1 단일 셀 박스다. 이 박스들은 "경고문, 예시문"으로 **표형태로 저장되어 있지만 의미적으로는 문단**이다. 현재 Phase 1 설계에서 이 1×1 박스를 표로 취급할지, 특수 단락으로 취급할지 결정되어 있지 않다.

1×1 박스를 표로 취급하면: `table_cells` 필드에 내용이 들어가고, 청크 생성 시 별도 처리 필요.  
1×1 박스를 문단으로 취급하면: `content_text`에 직접 병합 가능하지만, 형태를 잃음.

### 영향

ISA-315의 23×4 대형 표에서 "감사기준서 315 내 위험평가 매트릭스"를 검색할 때:
- 단일 청크: 토큰 초과로 임베딩 API 오류 또는 5000자 강제 절단 → 표 후반부 유실
- 행별 분할: "위험 유형 | 평가 절차" 셀이 분리되면 각 행이 독립 의미를 갖지 않음 → 검색 품질 저하

### 완화안

1. **1×1 박스는 "블록 인용구" 처리**: `kind='block_quote'`로 별도 분류. 내용을 단락처럼 임베딩. 표 처리 경로에서 제외.
2. **다열 표는 행 그룹 분할 + 헤더 반복**: 최대 10~15행 단위로 분할, 각 청크 시작에 표 헤더 행 반복 추가. `chunk_id = "ISA-315:table:1:part2"` 형식.
3. **66행×2열 특수 처리**: ISA-1200의 거대 표는 Phase 2에서 별도 처리 경로 설계. 행 의미 단위(요구사항 항목 단위) 분할 검토.

### 권고: **Serious (Phase 2 전 결정 필수)**

1×1 박스 처리 방법은 Phase 1 IR 설계(`types.py`, `docx_reader.py`)에서 결정해야 한다. Phase 1 후에 결정하면 IR 재설계가 필요하다. PLAN.md가 "Phase 2 전 결정"으로 미룬 것은 실수다 — Phase 1 IR 설계 단계로 앞당겨야 한다.

---

## 비판 7: .gitignore — CLAUDE.md 제외와 .env 보안

### 관찰

현재 `.gitignore` (4줄):
```
.env
raw/
CLAUDE.md
.claude/
```

**문제 1: `CLAUDE.md`가 gitignore에 있다**

CLAUDE.md는 "개발 컨벤션, 개발 중요 포인트, 실행 커맨드"를 담는 핵심 개발 가이드다. 이 파일이 gitignore에 있으면:
- 저장소 클론 후 CLAUDE.md 없이 개발을 시작하는 팀원이 컨벤션을 모름
- Phase 0 이후 팀 정리(`Clean up the team`) 후 새 팀 소환 시 CLAUDE.md를 다시 수동 배포해야 함
- `README.md`는 커밋되어 있지만 CLAUDE.md는 없는 상황 → 개발자 가이드 부재

반박 가능 이유: "CLAUDE.md에 민감 정보가 있을 수 있다". 하지만 현재 `CLAUDE.md`는 빈 파일이고, PLAN.md 요약 + 컨벤션을 담을 예정이다. 민감 정보는 `.env`에 분리되어 있다.

**문제 2: `output/`, `.embed_cache.sqlite`, `qdrant_storage/` 누락 (비판 4와 중복)**

pyproject.toml 산출물에는 이미 `.gitignore` 업데이트 지시사항이 있었으나 (Task #3 description §5: `.venv, __pycache__, output/, .pytest_cache` 등 추가 지시), 실제 `.gitignore`는 4줄 그대로다. **Implementer가 이 항목을 이행하지 않았다**.

**문제 3: `.env` 단독 보호의 취약성**

`.gitignore`에서 실수로 `.env` 줄을 삭제하면 API 키 노출. pre-commit hook이나 `git secrets` 설정 없이 단독 gitignore 의존은 취약하다. PLAN.md §5 리스크 매트릭스에서도 `.env API 키 노출 → .gitignore 확인됨`으로 LOW 분류했으나, gitignore 자체가 불완전한 상태다.

### 영향

- CLAUDE.md gitignore: Phase 2 이후 팀 재소환 시 컨텍스트 손실. 새 팀원 온보딩 비용 증가.
- `output/` gitignore 누락: 임베딩 JSON 커밋 시 108 MB 저장소 오염 + API 응답 데이터의 무단 배포 리스크.
- `.env` 단독 보호: UPSTAGE_API_KEY 노출 시 API 비용 무단 발생.

### 완화안

1. **CLAUDE.md를 gitignore에서 제거하고 커밋**: 민감 정보를 `.env`에 완전히 분리한 상태에서 CLAUDE.md는 공개 문서로 관리.
2. **`.gitignore` 즉시 보완**: `output/`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.embed_cache.sqlite`, `qdrant_storage/` 추가.
3. **pre-commit 훅 추가**: `detect-secrets` 또는 `git-secrets`를 `[tool.pytest.ini_options]` 옆에 pre-commit 설정으로 추가. 최소한 `.env` 키워드를 staged files에서 검색.

### 권고: **Blocker (즉시 수정)**

`output/` 및 관련 파일의 gitignore 누락과 CLAUDE.md 접근성 문제는 Phase 1 착수 전 수정 필수. Task #3 Implementer의 미이행 항목이므로 리더가 재이행을 요청해야 한다.

---

## 비판 8: Agent Teams 토큰 비용 ROI

### 관찰

PLAN.md §6 복잡도 & 토큰 예산: Phase 0~4 합산 700k~900k 토큰 (4 팀원 × Phase별 비용). 단일 세션 대비 3~5배.

**Phase 0는 명백히 정당**: 병렬 조사(IFRS 스캔 + ISA 프로파일링 + 골격 구축 + 비판) 4개 작업이 상호 독립적이고 전문성이 분리되어 있어 Agent Teams 이점이 명확하다.

**Phase 1은 정당**: `numbering.xml` 파싱 구현(Implementer)과 Domain Reviewer의 20개 샘플 검수가 동시 진행 가능. 단, 구현이 검수보다 먼저 완료되어야 하므로 실제 병렬도는 낮을 수 있다.

**Phase 2~3은 의문**: 
- Phase 2 (MD→JSON): 코드 작업이 단일 Implementer에 집중. 다른 팀원의 역할이 모호.
- Phase 3 (JSON→Qdrant): 역시 Implementer 중심, Reviewer는 검수 역할이나 Phase 1 검수와 유사한 단순 반복.
- 이 두 Phase에서 Agent Teams 오버헤드(컨텍스트 전달, 팀 소환, 팀 정리)가 기여 이익을 초과할 수 있다.

**Phase 4는 정당**: 4개 docx 파일별 style_map 분석이 Scout + Implementer 병렬 작업으로 가속 가능.

### 영향

Phase 2~3에서 Agent Teams를 그대로 사용하면 실질 속도 향상 없이 토큰만 3~5배 소모. 700k~900k 예산에서 Phase 2~3가 불필요하게 200~300k를 소비할 수 있다.

### 완화안

1. **Phase 2~3는 단일 세션**: Implementer 역할만 남기고 단일 세션에서 처리. Domain Reviewer는 CHECKPOINT 시점에만 투입 (전체 팀 구성 불필요).
2. **팀 규모 축소**: Phase 1~4에서 Scout + Implementer + Reviewer 3명 체계로 축소. Devil's Advocate는 각 CHECKPOINT에서만 재투입.
3. **토큰 예산 재추정**: Phase별로 Agent Teams 필요 여부를 명시한 결정표 작성.

### 권고: **Nice-to-have (Phase 2 착수 전 검토)**

현재 Phase 0는 적합하다. Phase 2~3 시작 전에 팀 구성을 재검토해 토큰 비용을 20~30% 절감 가능한지 평가할 것.

---

## Go / No-Go 종합 의견

### Blocker 목록 (Phase 1 착수 전 반드시 수정)

| # | Blocker | 담당 | 난이도 |
|---|---------|------|--------|
| B1 | `.gitignore`에 `output/`, `.embed_cache.sqlite`, `qdrant_storage/` 추가 | parser-implementer | 5분 |
| B2 | CLAUDE.md를 gitignore에서 제거하고 저장소에 커밋 | parser-implementer | 10분 |

### Serious 목록 (Phase 1 착수와 병행하거나 CHECKPOINT 1 전 완료)

| # | Serious | 담당 |
|---|---------|------|
| S1 | pgvector → Qdrant 전환 근거를 PLAN.md에 명시 (pgvector HNSW 4096d 상한 우회가 주 이유인지 확인) | team-lead |
| S2 | 파일별 별도 collection 결정의 교차 문서 검색 trade-off를 사용자에게 재확인 | team-lead |
| S3 | numbering.xml 파싱 실패 시 fallback 정책 설계: numId='0' 처리, UNKNOWN-id 부여, unknown 비율 임계값 | parser-implementer |
| S4 | 1×1 박스 표의 처리 방법(`kind='block_quote'` vs 표 경로)을 Phase 1 IR 설계 단계에서 결정 | parser-implementer |

### Nice-to-have (Phase 2 전 검토)

| # | 항목 |
|---|------|
| N1 | Solar Matryoshka 지원 여부 확인 + Scalar Quantization 조건부 계획 |
| N2 | Phase 2~3 Agent Teams 축소 검토 (토큰 비용 절감) |
| N3 | `docs/json_schema.md` 초안을 Phase 1 완료 시 작성 |
| N4 | pre-commit hook (`detect-secrets`) 설정 |

### 종합 판정

**조건부 Go** — Blocker 2개(B1, B2)를 해결한 후 Phase 1 착수 가능. Serious 4개(S1~S4)는 Phase 1 구현 착수 전 설계 단계에서 처리.

치명적 설계 결함은 없다. PLAN.md의 4단계 파이프라인 구조는 합리적이고, ifrs_reference_map.md가 IFRS→ISA 전환의 핵심 차이(numbering.xml 자동넘버링)를 정확히 식별했다. isa_structure_profile.md는 PLAN.md가 예상한 "numId=64, numId=57" 두 패턴이 실제로는 742개 numId 인스턴스에서 5개 abstractNum 패턴({15, 51, 70, 98, 140})으로 작동함을 실증했다 — 파싱 난이도가 예상보다 높다.

Implementer 산출물(pyproject.toml, docker-compose.yml, src/ 골격)은 구조적으로 양호하나 `.gitignore` 누락이 즉각 수정 필요.

**Phase 1에서 가장 높은 ROI 활동**: `numbering.py` 작성 전에 (1) numId='0' 처리, (2) 알 수 없는 abstractNumId에 대한 UNKNOWN-id fallback, (3) 기준서 경계에서의 카운터 리셋 정책을 명시적으로 문서화한 후 구현을 시작할 것.

---

*작성 완료: 2026-04-20 (isa_structure_profile.md 반영 업데이트)*  
*Blocker 급 비판: 2개 (B1: output/ gitignore 누락, B2: CLAUDE.md gitignore 문제)*  
*Serious 급 비판: 4개 (S1: Qdrant 전환 근거 미명시, S2: collection 분리 교차검색 trade-off, S3: numbering fallback 부재, S4: 1×1 박스 표 처리 방법 미정)*  
*Nice-to-have: 4개*  
*총 비판 수: 8개 (필수 3개 + 추가 5개)*  
*Go/No-Go: 조건부 Go (B1, B2 해결 후)*
