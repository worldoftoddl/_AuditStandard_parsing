# Devil's Advocate — CHECKPOINT 2 비판 보고서

> **작성자**: `devils-advocate-critic` (read-only role on `audit-parser-phase2`)
> **작성일**: 2026-04-21
> **대상 산출물**: Phase 2 (Structured Markdown → JSON `ParsedStandard` 파이프라인) 설계·구현·검수
> **참조 산출물**:
> - `docs/json_schema.md` v1.1 (Task #1, 1076 lines, 17 sections)
> - `docs/f4_known_duplicates.md` v1.1 (Task #1 부속, 191 lines, §4.2 RESOLVED)
> - `src/audit_parser/ingest/{md_parser,chunk_splitter}.py` (Task #2, #3)
> - `src/audit_parser/cli.py` (Task #4, `ingest` + `convert` UNKNOWN fail)
> - `output/json/` 36 파일 + `METRICS.json` (Task #5 실측, 8,660 chunks)
> - `docs/checkpoint_2_review.md` (Task #6, domain-reviewer CONDITIONAL PASS)
>
> **검증 대상이 "CHECKPOINT 2 PASS (CONDITIONAL)" 라는 사실을 알고도 미검증된 가정을 의도적으로 공격하기 위해 작성됨.** 동일 양식·심각도 라벨링은 `docs/devils_advocate_checkpoint_1.md` 와 통일 (영역·관찰·영향·완화안·왜 reviewer 가 놓쳤나).

---

## 비판 10건 요약

| # | 영역 | 표제 | 심각도 |
|---|------|------|--------|
| C-P2-1 | (a)(d) chunk_id 안정성 | F5 fallback chunk_id 의 46% 가 `#{source_idx}` 의존 — DOCX 재파싱 시 대량 drift | **HIGH** |
| C-P2-2 | (f) Phase 1 carry-over | TOC leak `"목차"`/`"문단번호"` 70 chunk (36 ISA 전부) — PRE_TOC 상태머신 systematic defect | **HIGH** |
| C-P2-3 | (c) §9.4 bias | 대형 appendix 클러스터 (최대 201 member) header-heavy payload 가 embedding 편향 가능성 — 실측 근거 부재 | MED |
| C-P2-4 | (b) §2.2 SemVer | v1.0 → v1.1 chunk_id 산출 함수 behavior 변경은 **semantic MAJOR** 이나 **practical MINOR** 로 판정 — 조건부 해석이 §2.2 각주로 명문화되지 않음 | MED |
| C-P2-5 | (h) §2.3 schema_version drift | MD 36/36 파일이 `schema_version=1.0`, JSON 36/36 파일이 `schema_version=1.1` — §2.3 "MD ↔ JSON 동기화 규칙" 이 운영 단계에서 침묵 drift 로 이미 깨짐 | MED |
| C-P2-6 | (i) tokenizer 오차 | tiktoken `cl100k_base` vs Upstage Solar 실토크나이저 gap 미측정. 실측 max 3,423 → soft_limit 3,500 margin 77 tokens (2.2%) — 토크나이저 오차 1건이라도 hard_limit 초과 위험 | MED |
| C-P2-7 | (g) Qdrant 성능 | 201-member worst cluster `ISA-720:appendix:3d4ed148:paragraph_body` 등 대형 그룹의 payload filter latency 미실측 — HNSW 필터링 단계 병목 가능성 | MED |
| C-P2-8 | (e) sha1[:8] 32-bit | 실측 충돌 0 건이지만 Phase 4 ISQM 1 등 타 문서 통합 시 chunk 8,660 → 2x 예상. birthday 재평가 없이 [:8] 고정 | LOW |
| C-P2-9 | (j) Phase 3 원자성 | per-ISA collection upsert 원자성 정책 (all-or-nothing vs per-collection vs per-point) 이 `qdrant_writer` 설계 전 미정. 36 collection 중 1 실패 시 rollback 규약 공백 | LOW |
| C-P2-10 | (j) named vector | `docs/json_schema.md` 에 `summary` named vector 참조 0 회. CLAUDE.md §4 는 "Named vectors (passage + summary)" 라 기술했으나 schema 가 이를 구체화하지 않음 — Phase 3 진입 시 design drift 위험 | LOW |

누적 HIGH 2, MED 5, LOW 3. `docs/devils_advocate_checkpoint_1.md` 의 HIGH 2 대비 동급 — 단, C-P2-1 은 spec-compliant 이므로 Phase 2 implementation 결함은 아님.

---

## C-P2-1 — F5 fallback chunk_id 의 46% 가 `#{source_idx}` 의존 (HIGH)

**영역**: (a) chunk 식별자 안정성, (d) idempotency vs Pass 2 충돌

**관찰**:

`output/json/METRICS.json` 실측:

```
chunks_total      = 8660
f4_suffix_chunks  = 462 (canonical_match=true, F4 2쌍 + ISA-300/1200 sub_item 등)
```

그러나 전수 스캔 결과 **chunk_id 에 `#` suffix 가 붙은 chunk 는 4,451 개 (51.4 %)** 이다. 462 는 `paragraph_id != ""` 한정 count. 나머지 3,989 개는 `paragraph_id in {"", None}` 이며 `{kind}#{source_idx}` fallback (§6.3) + §6.4 Pass 2 전원 suffix 규칙이 결합된 결과.

내 독립 스캔:

```
total_suffix = 4451 (51.4%)
  by_pid: null=3989, real=462
  by_kind: bullet=2525, paragraph_body=1382, sub_item=458,
           block_quote=58, table=18, unknown_numbering=6, requirement=4
```

top-10 cluster (suffix 그룹 크기 기준):

| rank | members | cluster stem |
|---|---|---|
| 1 | **201** | `ISA-720:appendix:3d4ed148:paragraph_body` |
| 2 | 107 | `ISA-705:appendix:7a5caf6e:paragraph_body` |
| 3 | 87 | `ISA-700:appendix:26ee3d6a:paragraph_body` |
| 4 | 75 | `ISA-710:appendix:b52890a3:paragraph_body` |
| 5 | 70 | `ISA-720:appendix:3d4ed148:bullet` |
| 6 | 69 | `ISA-570:appendix:9fe35f53:paragraph_body` |
| 7 | 64 | `ISA-1200:appendix:51e42baa:paragraph_body` |

즉 ISA-720 의 **감사보고서 사례 1 개 문단** 이 원본 DOCX 에서 삽입/삭제/순서 변경만 되어도 **201 chunk_id 가 일제히 재할당** 된다. §6.1 이 주장하는 "stable chunk_id" 는 4,009 chunk (46 %) 에 대해서는 실질적으로 "source_idx 순번 ID" 에 수렴한다.

**영향**:

HIGH. 세 가지 구체 피해 시나리오:

1. **Qdrant 재임베딩 비용 폭증**. §8.2 "동일 content_text + 동일 chunk_id → 재임베딩 생략" 의 upsert idempotency 가, 관련 블록 1개 삽입만으로 이후 `source_idx` 전부 shift → **수백~수천 chunk 재임베딩**. Upstage Solar API 호출 비용 (chunk ~100 tokens × 4000건 = 40만 tokens = $ 수준) 로 실제 발생.
2. **Qdrant payload 안정성**. Phase 4 RAG 쿼리 응답에서 반환되는 `chunk_id` 를 UI/log 에 노출하는 경우, 재파싱 사이 동일 문장이 다른 ID 로 표시 → 디버깅·재현 혼란.
3. **Audit trail 왜곡**. §8.1 이 "content drift detection 기능" 으로 positive spin 했으나, 실제로는 **수정 안한 chunk 까지 전부 drift 로 표시** (false positive). 예: ISA-720 appendix 맨 앞 문단 하나 교정 → 200 건 drift 보고 → 노이즈.

**완화안** (Phase 2 가 닫지 못하는 경우 v1.2 에서 닫아야 할 대안):

1. **`{kind}:content_sha1[:6]` fallback** (권장)
   - `paragraph_id in {"", None}` 일 때 chunk_id 꼬리를 `{kind}#{source_idx}` → `{kind}#{sha1(content_text)[:6]}` 로 전환.
   - Content-stable: 동일 텍스트는 DOCX 위치가 바뀌어도 동일 ID.
   - trade-off: 오탈자 수정 = chunk_id 변경 (§8.1 "content_text 변경 시 chunk_id 불변" 원칙과 충돌 — v1.2 에서 정책 재논의 필요).
   - 충돌 가능성: sha1[:6] = 24-bit → 4,451 chunks 에서 birthday 2^24 ≈ 1.3 % 충돌. [:8] 로 가면 practical 0.
2. **`content_text` 또는 `paragraph_links` 기반 보강 키** — sub_item 의 parent `paragraph_id` 를 chunk_id 에 섞어 많은 bullet 을 parent scope 로 disambiguate. 현재 parent 는 `paragraph_links` 필드에만 존재하고 chunk_id 구성에는 미반영.
3. **Phase 1 HTML 주석 확장** — `abstractNumId` 또는 `style` 을 추가 emit 하여 chunk_id 에 포함. MD 재생성 필요 → v1.2 MAJOR 후보.

**왜 reviewer 가 놓쳤나**:

domain-reviewer 의 CP2 판정은 "v1.1 spec 준수 + `canonical_match=true` + `duplicate_count=0`" 의 **spec-level invariant** 에 근거했다. 정당한 판정이다. 그러나 **spec 의 설계 의도 대비 현실의 scale** 은 별개 축 — 스펙상 462 chunk "F4 해소" 를 기대했는데 실제로는 4,451 chunk 가 같은 메커니즘으로 id 를 얻고 있다. 이는 spec bug 가 아니라 **spec 이 규모를 예측하지 못한** 사례. `source_idx scope` 조항 (내 Task #7 재검토 #1) 이 §8 에 명시화되어야 할 이유.

---

## C-P2-2 — TOC leak `"목차"`/`"문단번호"` 70 chunk, 36 ISA 전부 (HIGH)

**영역**: (f) Phase 1 carry-over defect

**관찰**:

전 36 ISA JSON 전수 스캔 결과 `content_text ∈ {"목차", "문단번호"}` 인 paragraph_body chunk 가 **70 건** 존재:

```
ISA-1100: 2, ISA-1200: 2, ISA-200: 2, ISA-210: 2, ISA-220: 2, ISA-230: 2,
ISA-240: 2, ISA-250: 2, ISA-260: 2, ISA-265: 2, ISA-300: 2, ISA-315: 1,
ISA-320: 2, ISA-330: 2, ISA-402: 2, ISA-450: 2, ISA-500: 2, ISA-501: 2,
ISA-505: 2, ISA-510: 2, ISA-520: 2, ISA-530: 2, ISA-540: 1, ISA-550: 2,
ISA-560: 2, ISA-570: 2, ISA-580: 2, ISA-600: 2, ISA-610: 2, ISA-620: 2,
ISA-700: 2, ISA-701: 2, ISA-705: 2, ISA-706: 2, ISA-710: 2, ISA-720: 2
```

ISA 36 개 중 **35 개** 에서 정확히 "목차" + "문단번호" 쌍이 동일 순서로 leak. ISA-315/540 는 1 건만 leak (부분 수정 추정). 원인은 Phase 1 `ir/structure.py` 의 `PRE_TOC → TOC → STANDARD_BODY` 상태머신이 각 ISA 의 목차 헤더 직전 블록을 완전히 필터링하지 못함.

domain-reviewer 가 CP2 보고서에서 ISA-300 `idx=2191/2192` 1 사례를 flag 했으나, 전수 재현 패턴이라는 사실은 본 보고서가 처음 정식화.

**영향**:

HIGH. 세 축:

1. **Embedding 오염**. 8,660 chunk 중 70 (0.81 %) 가 단일 단어 noise 텍스트 ("목차", "문단번호"). 각 chunk 는 token_estimate 3-4 → 개별 임베딩 호출 대상. passage 검색에서 "목차" 라는 query 에 상위 다수가 이 noise 에 매치될 가능성.
2. **RAG 답변 품질**. Phase 4 retrieval 에서 top-k 에 noise chunk 하나만 들어가도 LLM 컨텍스트 오염. 36 ISA 전수 재현 = 어떤 쿼리든 걸릴 위험.
3. **Phase 1 CHECKPOINT 1 회귀 신뢰도**. `docs/checkpoint_1_review.md` 가 PASS 로 종결했음에도 실제로는 전 파일 defect. Phase 1 의 `is_toc` 메트릭 (761 count) 은 정확했지만, **필터링은 된 것이 아니라 "마킹만 된" 블록이 체이닝 과정에서 paragraph_body 로 재분류됨**. 단위 테스트 gap.

**완화안** (우선순위 순):

1. **Phase 2 md_parser post-filter** (권장, 즉시 가능):
   ```python
   # md_parser.py 의 chunk 조립 루프 끝부분
   _TOC_NOISE = {"목차", "문단번호"}
   chunks = [c for c in chunks if (c.content_text or "").strip() not in _TOC_NOISE]
   ```
   - 효과: 70 건 즉시 제거, spec 변경 없음, parser_version MINOR bump 로 가능.
   - 위험: 정당한 "목차" 텍스트를 필터링할 우려 → 실측상 ISA 본문에서 단일 단어 "목차" 가 의미 있는 케이스 0 건 확인.
2. **Phase 1 `structure.py` 근본 수정** (MED cost):
   - `PRE_TOC` 에서 `TOC` 로의 전환 조건을 특정 heading style 등장 시로 강화.
   - `TOC` 에서 `STANDARD_BODY` 로의 전환 조건을 `kind=body` heading 첫 등장 시로 강화.
   - CP1 retrospective 필요 — 본 보고서 범위 초과.
3. **Phase 3 embedding 전 cleanup hook** — 품질 낮음, 기각.

**왜 reviewer 가 놓쳤나**:

CP1 reviewer 는 `is_toc` 메트릭을 "마킹된 블록 수" 로 해석하여 761 을 정상 범위로 판정했다. 그러나 본 Phase 2 JSON 에는 `is_toc=False` 로 분류된 chunk 가 70 건 섞여 있다 — 즉 **마킹 실패** 가 아니라 **마킹되지 않은 채 body 로 분류된 블록**. Phase 1 이 이 "false negative" 경로를 측정하지 않았다. 또한 CP2 reviewer 가 ISA-300 1 사례만 확인하고 전수 패턴으로 확장하지 않은 것은 sample-based 검수의 본질적 한계.

---

## C-P2-3 — 대형 appendix 클러스터의 header-heavy payload embedding 편향 가능성 (MED)

**영역**: (c) `§9.4` row-wise split + 대형 단일-heading 클러스터

**관찰**:

- `§9.4` 는 ISA-1200 66×2 table 에 대해 row-wise split 시 **header row 를 각 chunk 에 복제** (self-contained 원칙) 규정.
- 본 CP2 실측: ISA-1200 66×2 table 은 실제로 3-part split 됨 (token: 3,340 / 3,423 / 1,807), max token 3,423 ≤ soft_limit 3,500 → atomic 처리 회피 가능 구간에 있었음.
- 그러나 **§9.4 와 별개로, `paragraph_body` 중심의 대형 heading-scope 클러스터** 가 별도 bias 위험을 가진다:
  - `ISA-1200:appendix:51e42baa:paragraph_body` 64 member, 합산 token 4,493
  - `ISA-720:appendix:3d4ed148:paragraph_body` 201 member
  - 모두 동일 `heading_trail_hash` 공유 → Qdrant 검색 결과에서 이 heading 하위 chunk 가 함께 등장 시 동일 payload 반복.

heading text 자체는 chunk content_text 에 포함되지 않지만, **embedding 과 payload 필터 모두에서 "단일 heading scope" 과포화** 현상 예상.

**영향**:

MED. 정량적 근거 부재 — Phase 3 실제 embedding 수행 전에는 가정 수준.

- **passage vector 편향**: 64 chunk 가 동일 heading_trail (예: "부록 A — 감사보고서 사례") 하위라면, embedding 공간에서 가깝게 군집 → cosine 검색이 "부록 A 문서 전체" 를 반환하는 경향.
- **payload filter**: Qdrant `section=appendix AND heading_trail_hash=51e42baa` 필터로 동 64 건 일괄 반환 시 top-k pagination 필요.

**완화안**:

1. **Phase 3 실측**: ISA-1200 appendix 를 embed 후 "재무제표 감사보고서" query 로 검색 → top-k 에 heading-similar chunk 가 편향되는지 측정. 측정값 없으면 본 finding 종결 불가.
2. **`summary` named vector 분리** (§10 참조): passage vector + summary vector (heading_trail + paragraph_id 요약) 이원화. 현재 `json_schema.md` 는 summary 필드는 있으나 (`summary` 레코드 §4) **named vector 설계 공백** (C-P2-10 참조).
3. **Conditional finding**: 측정 전에는 설계 변경 불가. v1.2+ 보류.

**왜 reviewer 가 놓쳤나**:

§9.4 는 table row-wise split header 복제 한정 규정. `paragraph_body` heading-scope 클러스터는 §9.4 범위 외. reviewer 가 "§9.4 는 table 에만 적용" 으로 스코프 한정했고 paragraph_body 클러스터는 별도 축으로 인식.

---

## C-P2-4 — §2.2 SemVer 판정 — v1.0→v1.1 semantic MAJOR 가 practical MINOR 로 분류 (MED)

**영역**: (b) SemVer 경계

**관찰**:

`docs/json_schema.md` v1.1 bump 경위:

- v1.0 spec: chunk_id = `{standard_id}:{section}:{heading_trail_hash}:{paragraph_id}` (suffix 없음)
- v1.1 spec: 충돌 시 `#{source_idx}` suffix 부착 (§6.4 Pass 2)
- 동일 DOCX 입력에 대해 v1.0 consumer 는 `ISA-300:requirements:94b679bc:7.` 를 조회 → v1.1 데이터셋에서 **not found** (v1.1 은 `#2237` suffix 포함)

즉 chunk_id 산출 함수가 입력은 동일하되 출력이 다름 → **forward-compat: v1.1 parser 가 v1.0 MD 읽을 수 있음** 은 성립하나 **backward-compat: v1.0 consumer 가 v1.1 ID 조회 불가**. SemVer 엄격 해석상 MAJOR.

domain-reviewer 는 이를 MINOR 로 bump — 근거는 "(a) v1.0 JSON 데이터 미생성 + v1.0 consumer 부재 → 실질 파급 0". 이는 **practical MINOR** (배포 상황에 의존) 이지 **semantic MINOR** (spec 의미상 호환) 는 아니다.

**영향**:

MED. 직접 피해 0 (v1.0 소비자 부재) 이지만 두 가지 파생 위험:

1. **v1.2+ 판정 선례 오염**. 본 "practical MINOR" 판정이 문서화되지 않으면 차후 SemVer bump 시 (예: ISQM 1 통합 시 충돌 해소 규칙 추가) 같은 패턴이 MINOR 로 반복. v1.0 consumer 가 그 시점에 존재하면 silent breakage.
2. **외부 문서화 책무**. `docs/json_schema.md` §0 "청중" 에 "외부 integrator" 가 포함되어 있다. v1.1 footnote 부재는 외부 integrator 가 SemVer 표준 해석으로 "MINOR → backward-compat 보장" 기대 시 괴리.

**완화안** (v1.1.1 patch bump 에 포함 권고 — Task #7 일괄 권고 일부):

§2.2 에 각주 추가:

> **v1.1 조건부 MINOR 판정 (각주)**: chunk_id 산출 함수의 출력이 동일 입력에 대해 변경되었음에도 MINOR 로 판정한 근거는 **(i) 배포된 v1.0 JSON 데이터 0 건**, **(ii) v1.0 chunk_id 를 조회하는 외부 consumer 부재** 두 조건 충족. 향후 유사 변경 시 이 두 조건이 성립하지 않으면 **MAJOR bump 필수**. 특히 Phase 4 RAG 서비스 deploy 후에는 chunk_id format 확장이 MAJOR.

**왜 reviewer 가 놓쳤나**:

domain-reviewer 는 SemVer "super-set extension" 논거로 MINOR 를 방어했고, 내 반박을 수용하면서도 "v1.1.1 batch 로 footnote 삽입" 일정으로 지연 동의. 본 보고서는 해당 footnote 의 **구체 문구** 를 고정하여 지연 축소.

---

## C-P2-5 — MD@1.0 + JSON@1.1 schema_version drift 36/36 (MED)

**영역**: (h) §2.3 MD ↔ JSON 동기화 정책 실운영 실패

**관찰**:

실측 grep:

```
output/md/ISA-*.md    → schema_version: 1.0   (36/36 파일)
output/json/ISA-*.json → schema_version: 1.1  (36/36 파일)
src/audit_parser/convert/md_renderer.py:28 → SCHEMA_VERSION: Final = "1.0"
src/audit_parser/ingest/md_parser.py      → SCHEMA_VERSION 상수 없음
```

`docs/json_schema.md` §2.3 "MD ↔ JSON 동기화 규칙" 은 "MD schema 변경 없이 JSON 만 bump 하는 경우 허용" 으로 기술 (내 기억). 즉 현재 drift 는 스펙 위반이 아니라 의도된 상황.

문제는 세 가지:

1. **`md_parser.py` 가 `SCHEMA_VERSION` 상수를 정의하지 않음** → MD v1.0 / v1.1 분기 로직 부재. 향후 MD schema 가 v1.1 로 bump 될 때 parser 가 두 버전을 구분할 메커니즘 없음.
2. **YAML frontmatter 의 `schema_version` 필드가 MD 의 것인지 JSON 의 것인지 ambiguous**. MD 저장 시 md_renderer 가 1.0 을 넣음 → parser 는 이를 MD schema version 으로 해석. 그러나 CLI 사용자 입장에서는 "ParsedStandard JSON 생성기준" 으로 오독 가능.
3. **§2.3 정책 자체의 침묵 drift 증거**. 36/36 모든 파일에서 발생 → 정책 적용 사례 0 (v1.1 bump 가 JSON 단독이었으므로). 정책의 trigger 조건이 실측으로 검증된 적 없음.

**영향**:

MED. 현재 직접 피해 0, 미래 2 건:

1. **MD v1.1 bump 시 breakage 위험**. 예: Phase 1 renderer 가 block_quote 구분자를 변경하면 MD schema 1.1 bump → parser 가 상수 부재로 분기 실패.
2. **외부 MD 생성기 호환**. Phase 5 에서 사용자가 자체 MD 파이프라인으로 생성한 파일을 ingest 하는 시나리오 (CLAUDE.md §4 "docx → md → json → Qdrant 4단계 명시화" 가 그 여지를 남김) → schema_version 매칭 책무.

**완화안**:

1. **`md_parser.py` 에 `MD_SCHEMA_SUPPORTED = {"1.0"}` 상수 도입**, frontmatter 읽은 후 not in 시 fail-fast. 간단 patch.
2. `docs/json_schema.md` §2.3 재작성:
   - MD 와 JSON 의 `schema_version` 필드를 **별도 네임스페이스** 로 분리:
     - `md_schema_version` (YAML frontmatter)
     - `json_schema_version` (ParsedStandard `schema_version`)
   - 동기화 규칙을 "동일 값 강제 없음, 각자 SemVer 독립" 으로 명문.
3. Phase 3 `qdrant_writer` payload 에 양쪽 버전 기록 → 트레이서빌리티.

**왜 reviewer 가 놓쳤나**:

CP2 reviewer 는 `schema_version_distribution: {"1.1": 36}` 메트릭만 보고 "JSON 전수 v1.1 정상" 로 판정. 검증 범위가 JSON 단독이라 MD 파일의 `schema_version` 필드와의 상호작용은 검사 대상에서 제외. 교차 검증 gap.

---

## C-P2-6 — tiktoken `cl100k_base` vs Upstage Solar tokenizer 오차 미측정 (MED)

**영역**: (i) token_estimate 정확성

**관찰**:

- `docs/json_schema.md` §9.1 은 token_estimate 계산에 `tiktoken.get_encoding("cl100k_base")` 사용 규정.
- §9.3 은 soft_limit = 3,500 tokens, hard_limit = 4,000 tokens.
- Upstage Solar Embedding API 는 **4,000 token 한도** (Solar 공식 문서 기준) 이며 자체 BPE tokenizer 사용 — `cl100k_base` 와는 다름.

실측 분포 (8,660 chunks):

```
<500        : 8,609 (99.4%)
500-1000    :    41
1000-2000   :     6
2000-3000   :     1
3000-3500   :     3 (ISA-1200 table × 2 + ISA-540 table × 1)
3500-4000   :     0
>= 4000     :     0
max         : 3,423 (soft_limit 3,500 대비 margin 77 tokens = 2.2%)
```

margin 의 원천:
- tiktoken `cl100k_base` 는 OpenAI GPT 계열 tokenizer. Korean 텍스트에 대해 일반적으로 **Solar tokenizer 보다 token 을 더 사용** 하거나 **더 적게 사용** 할 수 있으며 (언어·vocabulary 차이), 어느 방향인지 **측정값이 존재하지 않는다**.
- 방향이 "tiktoken > Solar" 이면 보수적 (실제 Solar 한도에 여유), "tiktoken < Solar" 이면 위험 (Solar 가 4,000 초과할 수 있음).

**영향**:

MED. 현재 hard_limit 초과 chunk 0 건이라 Phase 3 단일 실패는 없을 것. 그러나:

1. **토크나이저 오차가 체계적으로 tiktoken 편향** 이면, 3,423 token chunk 가 실제 Solar 에서 4,100+ → **Solar API 가 truncate 하거나 에러**. chunk_splitter 의 안전 가정 파괴.
2. **산출물 재현성**. 다른 한국어 ISA 문서 (ISQM 1 등) 를 통합 시 토크나이저 오차의 편향이 반대일 수 있음. chunk_splitter 안전 margin 의 일반화 부재.

**완화안**:

1. **실측 calibration**:
   ```python
   # 샘플 100 chunk 를 tiktoken 과 Solar 실측 비교
   solar_count = upstage_tokenize_count(text)  # Solar API 공식 엔드포인트 사용
   tiktoken_count = encoding.encode(text).__len__()
   ratio = solar_count / tiktoken_count
   ```
   `ratio` 가 1.0 ± ε 범위면 OK. > 1.0 이면 soft_limit 을 `3500 / ratio` 로 축소.
2. **§9 에 calibration 주기 명시**: Phase 3 진입 전 calibration + 연 1회 재측정.
3. **hard_limit 보수화**: 3,900 → 3,800 으로 조정하는 것도 대안 (현재 0 건이라 영향 없음).

**왜 reviewer 가 놓쳤나**:

CP2 reviewer 의 `token_estimate` 메트릭은 tiktoken 기준 **자기 일관성** 만 검증 (`chunk_splitter` 가 soft_limit 초과시 분할했는가? → YES). 외부 tokenizer 와의 ground truth 대조는 수행되지 않음. 이는 Phase 2 범위 벗어난 논점 — Phase 3 embedding 실측에서 비로소 드러날 수 있음.

---

## C-P2-7 — 201-member worst cluster Qdrant payload filter 성능 미실측 (MED)

**영역**: (g) Phase 3 운영 성능

**관찰**:

C-P2-1 에서 확인한 top-10 cluster 는 Qdrant payload index 관점에서도 중요. 가장 큰 201-member `ISA-720:appendix:3d4ed148:paragraph_body` 는:

- 동일 `heading_trail_hash = 3d4ed148`
- 동일 `section = appendix`
- 동일 `standard_id = ISA-720`
- 동일 `kind = paragraph_body`

Phase 3 `qdrant_writer` 가 이 필드들을 payload index 로 설정하면, "ISA-720 감사보고서 사례 내부 검색" 쿼리 시 **201 vectors 를 HNSW 에서 후-선별** 하는 방식이 된다 (Qdrant filter + vector search 결합). HNSW 의 `ef` 파라미터가 filter-compatible 값을 유지해야 하는데, 클러스터 크기가 201 이면 `ef=64` 설정 (기본값) 과 비교하여 많은 재탐색 발생 가능.

**영향**:

MED. 실측 없이는 가정.

1. **단일 standard 내 RAG 응답 지연**. HNSW + payload filter 조합에서 cluster 가 크면 latency 증가.
2. **Qdrant 메모리**. payload index 의 inverted list 길이가 증가 → Qdrant 메모리 사용 프로파일 변화.

**완화안**:

1. **Phase 3 benchmark**: 36 collection × 평균 240 chunks × `paragraph_body` filter 쿼리 → p50/p99 latency 측정. 실측 없이 설계 변경 불가.
2. **payload index 설계 조정**:
   - `(section, heading_trail_hash, kind)` 복합 index → 201 → 1 번 lookup 으로 빠름
   - 단 insertion 비용 증가
3. **HNSW 파라미터 튜닝**: 대형 cluster 의 cohesiveness 가 높으면 `ef_construct=400` 으로 상향.

**왜 reviewer 가 놓쳤나**:

CP2 범위 = Phase 2 JSON 검수. Qdrant 성능은 Phase 3 단계. reviewer 가 적절히 스코프 격리. 본 보고서는 "Phase 3 진입 전 조건" 관점에서 flag.

---

## C-P2-8 — sha1[:8] 32-bit 확률, ISQM 1 통합 시 재평가 필요 (LOW)

**영역**: (e) hash 충돌 마진

**관찰**:

- `§6.2.1 assert_chunk_id_uniqueness` 가 runtime invariant 로 정착.
- 현재 8,660 chunk, `duplicate_count=0` 실측 확인.
- sha1[:8] = 32-bit, birthday bound ~ 65,536 entries 에서 50% 충돌.
- ISQM 1 (품질관리기준서, `raw/3. 품질관리기준서1...`) 통합 시 추가 ~2,000 chunk 예상 → 총 ~10,660.
- 인증업무개념체계 + 기타 인증업무기준까지 합치면 ~15,000 chunk. birthday 50% bound 는 여전히 멀지만 **기댓값 0.026 → 0.076 선형 증가** (15,000 × 14,999 / 2 × 2^-32 ≈ 0.026).

**영향**:

LOW. 현재 수치로는 무시 가능. 그러나 Phase 5+ 에서 ISA 개정판 누적·국제 ISA 표준 추가 등으로 chunk 가 50,000 근접하면 기댓값 0.29 → 실제 1회 이상 발생 가능성 존재.

**완화안**:

1. **v1.2 에서 `heading_trail_hash` 를 sha1[:10] 또는 [:12] 로 확장** (40-bit → 48-bit). MAJOR bump 필요. 배포된 데이터 존재 시 migration 복잡.
2. **`assert_chunk_id_uniqueness` 가 raise 하는 경우의 알람·re-key 워크플로** 를 §6.2.1 에 명시. 현재는 raise 까지만.
3. **chunk 총 수 모니터링** (운영 지표): METRICS.json `chunks_total` 을 매 ingest 시 기록하고 10,000 돌파 시 재평가 알림.

**왜 reviewer 가 놓쳤나**:

reviewer 도 §6.2.1 에서 birthday 수치 (~0.0034) 를 직접 기술했고 "v2.0 MAJOR 후보" 로 명시. 본 비판은 reviewer 의 인식을 확장하여 **정량 trigger** 를 고정하는 목적.

---

## C-P2-9 — Phase 3 per-collection upsert 원자성 정책 공백 (LOW)

**영역**: (j) Phase 3 진입 조건

**관찰**:

CLAUDE.md §5 "Collection 네이밍 규칙" 은 **파일별 별도 collection** 설계. 36 ISA = 36 collection.

`qdrant_writer.py` (Phase 3, 미구현) 가 전수 ingest 수행 시 원자성 정책이 `docs/json_schema.md` / `PLAN.md` 어디에도 명시되지 않음. 시나리오:

- 36 collection upsert 중 17 번째 (ISA-330) 에서 네트워크 에러 → 이미 완료된 16 개는 커밋됨, 17-36 은 미처리.
- 재실행 시 1-16 도 동일 재업서트 → content_text 동일하면 §8.2 idempotency 로 skip, 아니면 재embedding.

정책 공백 영역:

1. **Batch-level rollback** 여부 (권장: 불필요, per-collection 단위로 충분)
2. **Per-collection atomicity** — collection 단위 all-or-nothing? 부분 업서트 상태 허용?
3. **Retry policy** — 실패한 ISA 만 재실행? 전체 재실행?

**영향**:

LOW. 실제 운영 시 manual 해결 가능. 그러나 정책 공백 자체가 Phase 3 reviewer 의 bikeshedding 대상이 될 위험.

**완화안**:

1. **PLAN.md 또는 `docs/json_schema.md` §11 (신설) 에 운영 원자성 규약** 추가. 권장 설계:
   - 각 ISA 는 독립 collection → per-collection 단위 원자성 자연적 보장
   - CLI `audit-parser ingest` 에 `--resume` 플래그: 이미 존재하는 collection 건너뛰기
   - `--force` 플래그: 기존 collection drop 후 재생성
2. Phase 3 tests/E2E 에서 partial-failure 재현 케이스 1건 추가.

**왜 reviewer 가 놓쳤나**:

Phase 2 범위 밖. domain-reviewer 가 DM 에서 명시적으로 "Phase 3 범위 이관" 동의. 본 비판은 그 이관이 실제 **Phase 3 진입 차단 조건** 으로 승격되지 않도록 사전 flag.

---

## C-P2-10 — Named vector (`passage` + `summary`) 설계 공백 (LOW)

**영역**: (j) Phase 3 진입 조건

**관찰**:

- `CLAUDE.md §4`: "Named vectors (passage + summary), HNSW: m=16, ef_construct=200"
- `docs/json_schema.md` 전수 검색 → `summary vector`, `named vector` 0 회 매치.
- `§4 summary 레코드` 는 **ParsedStandard JSON 의 standard-level 요약 필드** 을 정의, chunk-level named vector 와는 별개.
- 즉 Phase 3 에서 "passage vector" 와 "summary vector" 를 어떤 텍스트로부터 생성할지, dimension 은 동일한지, HNSW 를 둘 다 같은 파라미터로 구성할지 **spec 공백**.

**영향**:

LOW. Phase 3 설계 단계에서 결정하면 된다. 그러나 CLAUDE.md 가 "제품 스펙" 수준에서 명시한 항목이 `json_schema.md` (외부 integrator 대상) 에 없는 건 문서 정합성 이슈.

**완화안**:

1. **Phase 3 설계 착수 전 `docs/json_schema.md` §11 (신설) 또는 `qdrant_writer_spec.md` 신설** 에서:
   - `passage` vector: chunk `content_text` 임베딩 (Upstage passage encoder)
   - `summary` vector: `heading_trail` 조합 또는 `summary` 레코드 임베딩 (query encoder)
   - 각 named vector 의 distance metric (cosine/dot/euclidean)
   - HNSW 파라미터 동일 or 차별화
2. CLAUDE.md §4 와 json_schema.md 의 cross-reference.

**왜 reviewer 가 놓쳤나**:

reviewer 는 `docs/json_schema.md` = "Phase 2 JSON 스펙" 으로 스코프 한정. named vector 는 Phase 3 Qdrant 관심사이므로 json_schema.md 에 없는 게 스코프상 맞다. 그러나 **외부 integrator 시점** 에서는 "Qdrant 에 어떤 벡터가 들어가나?" 가 첫 질문이고 json_schema.md 가 답을 주지 못함.

---

## Self-audit — 내 advisory 오기재 정정

Phase 2 진행 중 parser-implementer 에 보낸 DM (C-P2 직전 단계) 에서 **"무인덱스 보론 보유 9 ISA"** 로 `ISA-230, 240, 260, 265, 450, 540, 550, 560, 580` 을 나열했으나 이는 **stale claim** 이었다.

실측 검증 (domain-reviewer 의 `grep ^### 보론` + 내 JSON `appendix_index=[1]` 교차 확인):

- **정확한 9 ISA**: `ISA-230, 300, 510, 570, 620, 700, 705, 710, 1100`
- 내 리스트와의 overlap: `ISA-230` 1 개만 정확
- 내 리스트 오류 예: ISA-240 은 `appendix_index=[1,2,3]` (번호 있음), ISA-450 은 0 appendix chunk, ISA-540 은 `[2]` 만.

이는 Phase 1 "F4 3건 vs 6쌍" stale-claim 교훈을 스스로 반복한 사례. Task #7 이후 작업에서는 DM 발송 전 해당 scope JSON 을 실측으로 재확인하는 프로토콜 강화 필요.

---

## v1.1.1 patch bump 권고 (domain-reviewer 에 batch 전달)

사전 합의대로 Task #7 산출에 다음 3 건 일괄 권고. parser 동작 무영향 docs-only patch.

### (i) §2.2 SemVer footnote (C-P2-4)

```
v1.1 조건부 MINOR 판정 (각주): chunk_id 산출 함수의 출력이 동일 입력에
대해 변경되었음에도 MINOR 로 판정한 근거는 (a) 배포된 v1.0 JSON 데이터 0 건,
(b) v1.0 chunk_id 를 조회하는 외부 consumer 부재 두 조건 충족.
향후 유사 변경 시 이 두 조건이 성립하지 않으면 MAJOR bump 필수.
특히 Phase 4 RAG 서비스 deploy 후에는 chunk_id format 확장이 MAJOR.
```

### (ii) §8 source_idx idempotency scope (C-P2-1 + domain-reviewer 제안)

```
source_idx 기반 chunk_id 는 동일 DOCX 입력 + 동일 md_renderer/md_parser
버전 조합에 대해서만 idempotent. DOCX author 의 block 삽입/삭제 시 해당
block 이후의 모든 source_idx 재할당 → 영향받은 chunk_id 재계산 필요.
이는 content drift detection 기능으로 활용 가능 (bug 아님).

운영 참고: 단일 block 삽입이 200+ chunk_id 를 재할당할 수 있음
(실측 예: ISA-720 appendix 클러스터 201 member).
```

### (iii) §9.4 conditional bias finding (C-P2-3)

```
row-wise split 시 header row 복제는 passage embedding 편향 가능성
(heading 키워드 과포화) 이 논리적으로 존재하나 Phase 2 시점 실측 근거
부재. Phase 3 embedding 수행 후 top-k 회귀 테스트로 재평가.
대안 설계: summary named vector 에만 header 반영 + passage vector 에서
header 제거 (Phase 3 §11 신설 시 논의).
```

---

## Go/No-Go

### 최종 판정: **CONDITIONAL GO**

**GO 근거**:
- v1.1 spec invariant 3 건 전수 PASS (F4 canonical match, `.strip()` 0 위반, 9 ISA appendix_index=1)
- `chunk_id_uniqueness.global_unique=true`, `duplicate_count=0`
- schema validation 36/36 passed
- HIGH 2 건 모두 **spec 결함이 아닌 "spec-compliant 이되 scale/carry-over 에서 드러난 잠재 리스크"**

**CONDITIONAL 조건**:

**MUST-FIX (Phase 3 진입 전)**:
1. **C-P2-2**: TOC leak 70 chunk post-filter (md_parser 에 `_TOC_NOISE` set 적용). parser-implementer 단일 커밋으로 가능. Phase 3 embedding 오염 방지 필수.

**SHOULD-FIX (Phase 3 진행 중 병렬)**:
2. **v1.1.1 patch bump** — §2.2 각주 + §8 scope + §9.4 conditional finding 3 건 docs-only. domain-reviewer batch 적용 (사전 합의됨).
3. **C-P2-5**: `md_parser.py` 에 `MD_SCHEMA_SUPPORTED` 상수 + fail-fast. 1 liner.

**DEFER (Phase 3 결과 기반 재평가)**:
4. **C-P2-1**: content-sha1 fallback 전환은 v1.2 MAJOR 후보. 현 규모에서는 운영 가능. Phase 4 RAG 실사용 후 재파싱 빈도 실측 후 결정.
5. **C-P2-3/C-P2-6/C-P2-7**: Phase 3 benchmark 후 정량 근거 확보 후 재평가.
6. **C-P2-8**: chunks_total 10,000 도달 시 재평가 트리거.

**NO-GO 미충족 조건 (HIGH 3 건 이상 or F5 근본 재설계 필요)** 에 해당하지 않음 — C-P2-1 은 spec-compliant, C-P2-2 는 단일 커밋 fix 가능.

---

## 부록 A — 비판 영역 (a-j) 커버리지

team-lead 브리핑의 10 영역과 본 10 비판의 매핑:

| 영역 | 핵심 질문 | 커버 비판 |
|---|---|---|
| (a) chunk_id 안정성 | `{kind}#{source_idx}` fallback 장기 안정성? | C-P2-1 |
| (b) SemVer 경계 | v1.0→v1.1 behavior change 판정? | C-P2-4 |
| (c) §9.4 bias | header 복제 embedding 편향? | C-P2-3 |
| (d) §8.1 vs §6.4 | idempotency vs Pass 2 정합성? | C-P2-1 (동일 축) |
| (e) sha1[:8] | 32-bit 충돌 확장 재평가? | C-P2-8 |
| (f) TOC leak | Phase 1 carry-over noise? | C-P2-2 |
| (g) Qdrant 성능 | 대형 cluster filter latency? | C-P2-7 |
| (h) schema_version drift | MD/JSON 독립 카운터 운영? | C-P2-5 |
| (i) tokenizer 오차 | tiktoken ↔ Solar gap? | C-P2-6 |
| (j) 운영·Phase 3 | 원자성·named vector 설계? | C-P2-9, C-P2-10 |

10/10 영역 커버. 최소 6 건 요건 (HIGH+MED+LOW) 대비 10 건 (HIGH 2 + MED 5 + LOW 3) 으로 초과 달성.

---

## 부록 B — 참조

- `docs/json_schema.md` v1.1 §2.2, §2.3, §6.1, §6.2, §6.2.1, §6.4, §7.2, §7.2.1, §8.1, §8.2, §9.1, §9.3, §9.4
- `docs/f4_known_duplicates.md` v1.1 §2-§4.2 RESOLVED
- `docs/checkpoint_2_review.md` (domain-reviewer CONDITIONAL PASS)
- `docs/devils_advocate_checkpoint_1.md` (C1-C11 양식 참조)
- `output/json/METRICS.json`, `output/json/ISA-*.json` 36 파일
- `src/audit_parser/convert/md_renderer.py:28` (SCHEMA_VERSION 상수)
- `src/audit_parser/ingest/md_parser.py` (SCHEMA_VERSION 상수 부재)
- `CLAUDE.md §4` (Named vectors 언급)
- `PLAN.md §4` (Phase 2 요구사항)
