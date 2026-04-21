# CHECKPOINT 2 검수 보고서

**검수자**: `audit-standard-domain-reviewer`
**검수일**: 2026-04-21
**대상 산출물**: `output/json/ISA-*.json` (36 개 파일, I1 fix 후 **8,590 chunks**) + `output/json/METRICS.json`
**대상 원본**: `output/md/ISA-*.md` (37 파일, Phase 1 CHECKPOINT 1 통과본)
**스펙 기준**: `docs/json_schema.md` **v1.1.1** (2026-04-21 EVE+ PATCH bump — §2.2 footnote / §8.4 scope / §9.5 bias finding 반영)
**판정**: **✅ PASS (FINAL, I1 해제)** — MINOR rework 1 件 (I1 TOC leak post-filter) 완료·해제, Phase 3 진입 clear / v1.2 설계 논의 1 件 Task #7 이관

**검수 이력**:
- 2026-04-21 초판 — N1/N2 경미 + F5 Task #7 이관 판정
- 2026-04-21 post-CP2 addendum — devils-advocate-critic 교차검증 반영: 최대 클러스터 64→201 정정, N1→I1 severity 승격
- 2026-04-21 EVE+ I1-CLOSED addendum — parser-implementer I1 fix 검증 완료 (chunks 8,660→8,590, null-sec 104→34, TOC leak 70→0, invariant 전원 유지), critic 측 정렬 확인, v1.1.1 patch bump 완료 → **MUST-FIX 해제, Phase 2 critique cycle 종료**

---

## 0. Executive Summary

| 영역 | 결과 |
|---|---|
| JSON Schema Draft 2020-12 validate | 36/36 PASS (METRICS.schema_validation) |
| `schema_version: "1.1"` 전수 부착 | 36/36 PASS |
| `chunk_id` global uniqueness | 8,660/8,660 (0 duplicate) PASS |
| F4 canonical 2 pair Pass 2 suffix | ISA-300 `#2237`/`#2238`, ISA-701 `#8422`/`#8427` 일치 PASS |
| paragraph_links 무결성 | 1,788 total / 0 bad refs / 0 orphan app_guide PASS |
| 9 unnumbered 보론 → `appendix_index=1` | 9/9 ISA 모두 appendix=1 populated PASS |
| ISA-1200 대형 표 분할 | 3-part split (33+23+12 rows, 모두 token < 3500), header 복제 PASS |
| `<null>` content_text chunks | 0 건 PASS |
| F1 (Phase 1) 스타일-상속 `numPr` 후속 | requirement 1,161 / app_guide 1,788 분포 합리 PASS |
| F2 (Phase 1) ISA-1200 section enum | general_principles/engagement_acceptance/planning/risk_* 등 populated PASS |

**판정 근거**: v1.1 spec 의 모든 normative invariant 충족. 이하 2 件은 `PASS` 를 가리지 않는 informational / Phase 1 carry-over 이며, 별건 1 件은 v1.2+ 설계 주제로 Task #7 이관.

| ID | 심각도 | 항목 | 조치 | 상태 (2026-04-21 EVE+) |
|---|---|---|---|---|
| **I1** | 🟠 ISSUE → ✅ **CLOSED** | TOC leak "목차"/"문단번호" 70 chunks 35/36 ISA systematic | parser-implementer MINOR rework — md_parser post-filter (§4.1) | **해제** — fix 적용 후 leak 0건 재확인, 모든 invariant 유지 |
| **N2** | 🟡 NOTE → ✅ **자연 해소** | `<null>` section 104 = TOC leak 70 + cross-ref block_quote 34 | I1 수정 시 104→34 감소 | **104→34 실측 확인** |
| **F5** | 🟠 DISCUSS → 📝 **v1.1.1 조건부 finding** | F4 fallback-kind Pass 2 suffix 3,989 chunks (전체 chunk 46%, 최대 cluster 201) | Task #7 이관 → v1.1.1 §9.5 bias finding | **Phase 3 측정 프로토콜 대기** (10 seed query top-5 동시 출현 ≥30% or cosine Δ<0.01 시 v1.2 MINOR bump) |

---

## 1. 검수 방법

### 1.1 자가 검증 절차 7 단계 (team-lead 제시 + 사전 commit)

| # | 절차 | 결과 |
|---|---|---|
| 1 | METRICS.json 수치 cross-check | 36 files, 8,660 chunks, version 1.1 36/36, uniqueness 100%, canonical_match=true |
| 2 | 20-샘플 ISA JSON ↔ 원본 MD 대조 | §2 참조 |
| 3 | F4 462건 의도성 판별 | §3 참조 |
| 4 | schema_version / paragraph_links / uniqueness 재확인 | §1.2 |
| 5 | 9 ISAs unnumbered 보론 → appendix_index=1 | 9/9 PASS (§4.3) |
| 6 | `<null>` section 104건 합리성 | §4.4 |
| 7 | 독립 Python re-count with field introspection | §3.1 발견: METRICS 462 은 paragraph_id=real 한정, 총 suffix = 4,451 |

### 1.2 핵심 invariant 재검증

```
파일수:                36 / 36              ✓
schema_version:        1.1 × 36             ✓
chunks_total:          8,660                ✓
kind 합:               8,660 (kind_dist sum) ✓
section 합:            8,660 (incl. <null>)  ✓
uniqueness:            duplicate=0           ✓
canonical F4:          ISA-300/#2237,#2238 + ISA-701/#8422,#8427 ✓
split_chunks_total:    3 (ISA-1200 보론 1 표) ✓
paragraph_links:       1,788                 ✓
  ├─ bad refs:         0                     ✓
  ├─ orphan app_guide: 0                     ✓
  └─ ISA-1200 links:   0 (expected — no req/app dichotomy) ✓
blank content_text:    0                     ✓
```

---

## 2. 20-샘플 JSON ↔ MD Cross-verification

### 2.1 F4 Canonical Pair #1 — ISA-300 `7.` (idx=2237 vs 2238)

| Source | JSON chunk_id | MD 확인 | content_text 일치 |
|---|---|---|---|
| idx=2237 | `ISA-300:requirements:94b679bc:7.#2237` | `output/md/ISA-300.md` L94 | "감사인은 감사의 범위, 시기 및 방향을 수립하고 감사계획 개발의 지침이 되는 전반감사전략을 수립하여야 한다." ✓ |
| idx=2238 | `ISA-300:requirements:94b679bc:7.#2238` | L97 | "감사인은 전반감사전략을 수립할 때 다음의 절차를 수행해야 한다" ✓ |

**heading_trail**: `[감사기준서 300, 요구사항, 계획수립 활동]` 양쪽 동일 → hash `94b679bc` 일치.  
**판정**: v1.1 Pass 2 알고리즘이 원본 DOCX 의 이중 `7.` 을 올바르게 분리. **PASS**.

### 2.2 F4 Canonical Pair #2 — ISA-701 `4.` (idx=8422 vs 8427)

| Source | JSON chunk_id | MD 확인 | content_text 일치 |
|---|---|---|---|
| idx=8422 | `ISA-701:intro:a7720376:4.#8422` | `output/md/ISA-701.md` L37 | "감사보고서에서 핵심감사사항에 대하여 커뮤니케이션하는 것은..." ✓ |
| idx=8427 | `ISA-701:intro:a7720376:4.#8427` | L52 | "이 감사기준서는 상장기업의 일반목적 전체재무제표에 대한 감사와..." ✓ |

**heading_trail**: `[감사기준서 701, 서론, 이 감사기준서의 범위]` 양쪽 동일 → hash `a7720376` 일치.  
**참고**: 사이에 sub_item `(a)(b)(c)(d)` (idx 8423-8426, parent=4.) 가 첫 번째 `4.` 에 귀속 → 구조적으로 정상.  
**판정**: **PASS**.

### 2.3 ISA-1200 3-Part Split Table (보론 1 용어의 정의)

| part | chunk_id | chunk_index | chunk_of | rows | token | header 복제 |
|---|---|---|---|---|---|---|
| 0 | `ISA-1200:appendix:d3ec59bd:table#11079`       | 0 | 3 | 33 | 3,340 | — (원본) |
| 1 | `ISA-1200:appendix:d3ec59bd:table#11079#1`     | 1 | 3 | 23 | 3,423 | "용어 / 정의" ✓ |
| 2 | `ISA-1200:appendix:d3ec59bd:table#11079#2`     | 2 | 3 | 12 | 1,807 | "용어 / 정의" ✓ |

- `part_of`: parts 1/2 모두 `ISA-1200:appendix:d3ec59bd:table#11079` 지칭 ✓  
- 모든 part token_estimate < 3,500 soft-limit ✓ (chunk_splitter.py 기준 충족)  
- 총 row = 33+23+12 = 68 = 66 body + 2 추가 header 복제 row (part 1,2) → 정합  
- **참고**: MD 원본 `### 보론 1 용어의 정의` 이 아닌 `## 보론 1 용어의 정의` (H2) 로 존재 (L1666). Numbered 보론 이므로 `appendix_index=1` 정상 부여.

**판정**: **PASS**. v1.1 §9.4 (row-wise split + header replication + cell-wise prohibited) 준수.

### 2.4 9 Unnumbered 보론 → `appendix_index=1` 매핑 (v1.1 §7.2.1)

| ISA | appendix_index=1 chunks | 확인 |
|---|---:|---|
| ISA-230 | 16 | ✓ |
| ISA-300 | 40 | ✓ |
| ISA-510 | 50 | ✓ |
| ISA-570 | 75 | ✓ |
| ISA-620 | 31 | ✓ |
| ISA-700 | 98 | ✓ |
| ISA-705 | 117 | ✓ |
| ISA-710 | 79 | ✓ |
| ISA-1100 | 69 | ✓ |

전수 9/9 PASS. 합계 575 chunks — METRICS `appendix_index_distribution[1] = 822` 중 9 ISAs 비율 70% (나머지 247 은 ISA-1200 `보론 1` 및 기타 numbered 1 문맥).

**판정**: **PASS**.

### 2.5 `<null>` section 104 chunks — 샘플 12건 추출

| ISA | idx | kind | content_text (first 80) | 분류 |
|---|---:|---|---|---|
| ISA-1100 | 9794 | paragraph_body | "목차" | **TOC leak (N1)** |
| ISA-1100 | 9795 | paragraph_body | "문단번호" | **TOC leak (N1)** |
| ISA-1100 | 9829 | block_quote | "이 감사기준서는 감사기준서 200 …와 함께 이해하여야 한다." | cross-ref (F2 해소 후 잔존) |
| ISA-1200 | 10476 | paragraph_body | "목차" | TOC leak |
| ISA-1200 | 10477 | paragraph_body | "문단번호" | TOC leak |
| ISA-200 | 4 | paragraph_body | "목차" | TOC leak |
| ISA-200 | 5 | paragraph_body | "문단번호" | TOC leak |
| ISA-210 | 322 | paragraph_body | "목차" | TOC leak |
| ISA-210 | 323 | paragraph_body | "문단번호" | TOC leak |
| ISA-210 | 344 | block_quote | "이 감사기준서는 …와 함께 이해하여야 한다." | cross-ref |
| ISA-220 | 577 | paragraph_body | "목차" | TOC leak |
| ISA-220 | 602 | block_quote | "이 감사기준서는 …와 함께 이해하여야 한다." | cross-ref |

**104 = (36 ISA × 2 TOC-header) - 2 missing + (32 ISA × 1 block_quote cross-ref) − 편차**
- 정확 분해: TOC-header 70 (목차/문단번호) + block_quote cross-ref 34 = 104 ✓

**판정**: 104 전체가 파싱 오류가 아니며, 원인이 식별됨 (§4.4 참조). 스펙 위반 없음.

### 2.6 unknown_numbering 6건 (METRICS.kind_dist.unknown_numbering=6)

| ISA | idx | 문맥 | 해석 |
|---|---:|---|---|
| ISA-210 | 542 | 보론 1 서약서 본문 내 assertion list 1/3 | 모번호 없는 서약문 항목 |
| ISA-210 | 543 | 2/3 | " |
| ISA-210 | 544 | 3/3 | " |
| ISA-600 | 7080 | "부문 (문단 9(a) 참조)" 정의 본문 내 alt 열거 1/3 | 정의의 대안 구성 |
| ISA-600 | 7081 | 2/3 | " |
| ISA-600 | 7082 | 3/3 | " |

모두 원본 DOCX 에서 자동 번호가 부여되지 않은 인용·정의문 내 continuation fragment. 의미상 `bullet` 과 유사하지만 bullet 스타일 없이 개행만 되어 있어 `unknown_numbering` fallback. **스펙 허용** (v1.0 §9.2 `unknown_numbering` kind 정의). 

**판정**: **PASS** (Phase 1 checkpoint_1_review 의 F1 scope 동일 기준 유지).

### 2.7 Phase 1 재확인: ISA-250, ISA-260

| ISA | chunks | paragraph_links | null sec | sample ISA-250 para 12 | sample ISA-260 intro |
|---|---:|---:|---:|---|---|
| ISA-250 | 150 | 36 | 3 | `requirement` `ISA-250:requirements:...:12.` 1건 (heading_trail 과거 `용어의 정의` vs 신규 `요구사항` 구분 정상) | n/a |
| ISA-260 | 241 | 54 | 3 | n/a | `intro` 최초 chunk 정상 |

Phase 1 에서 검토된 ISA-250 `12.` duplicate 은 이미 heading_trail 차이로 자연 분리 (CP0 f4_known_duplicates.md §4.2 Pair #3). Phase 2 에서 추가 이상 없음.

---

## 3. F4 Suffix 462 건 의도성 판별

### 3.1 METRICS 462 의 정의 검증 및 실측 총 suffix 분해

METRICS.json 의 `f4_suffix_chunks.total = 462` 는 **paragraph_id=real 한정** 집계로 확인됨. Python 독립 re-count (`#` in chunk_id) 결과:

```
paragraph_id = REAL (non-null):
  sub_item              458
  requirement             4   (= canonical 2 pair × 2 chunks)
  ──────────────────────────
  소계                  462   ← METRICS 값과 일치 ✓

paragraph_id = NULL (fallback kind collision):
  bullet              2,525
  paragraph_body      1,382
  block_quote            58
  table                  18
  unknown_numbering       6
  ──────────────────────────
  소계                3,989

TOTAL (all '#' suffix)     4,451  (= 51.4% of 8,660 chunks)
```

### 3.2 Real-paragraph_id 462 件 판정 — **PASS (의도대로 작동)**

**증거 1 (군집 구조)**: ISA-700 cluster `ISA-700:requirements:7bcffc75:(a)` — 3 members, 모두 다른 content, 부모 paragraph 번호가 다름 (idx gap ≈ 5 → `(a)(b)(c)(d)(e)` 패턴).

```
idx=8000  content: "감사기준서 330에 따라 충분하고 적합한 감사증거를 입수했는지 여부에 대한 감사인의 결론"
idx=8005  content: "경영진이 선택하고 적용한 유의적인 회계정책이 재무제표에 적절히 공시되었는지..."
idx=8014  content: "재무제표의 전반적인 표시와 구조 및 내용"
```

모두 동일 heading_trail `[감사기준서 700, 요구사항, 재무제표에 대한 의견형성]` + 동일 paragraph_id `(a)` + **다른 부모 paragraph** → Pass 2 알고리즘의 정당한 collision 해소.

**증거 2 (canonical 완전일치)**: METRICS `canonical_found` = `canonical_expected`. 팀 합의한 2 쌍 4 chunk 가 `#{source_idx}` suffix 로 일치 분리.

**증거 3 (MD 출처 확인)**: §2.1 / §2.2 에서 ISA-300.md / ISA-701.md 원본 두 `7.`/`4.` 가 실제로 존재함을 line 번호까지 확인.

→ **허위 양성 아님. 462 는 Korean ISA `(a)(b)(c)` 반복 sub_item + F4 canonical 2 pair 의 정당한 해소.**

### 3.3 Fallback-Kind 3,989 件 — v1.2 Discussion Item (F5)

**현상**: paragraph_id=null chunk (bullet, paragraph_body, block_quote, table, unknown_numbering) 은 v1.1 §6.3 에 의해 **kind 문자열을 paragraph_id fallback 으로 사용**. 동일 heading_trail 아래 같은 kind chunks 가 다수 존재 → Pass 2 알고리즘이 **모두에게 `#{source_idx}` suffix 부착**.

**scale** (top-10 클러스터 전수 실측 — devils-advocate-critic 교차검증 반영):

| rank | members | cluster stem |
|---:|---:|---|
| 1 | **201** | `ISA-720:appendix:3d4ed148:paragraph_body` (감사보고서 사례 Case 1~N) |
| 2 | 107 | `ISA-705:appendix:7a5caf6e:paragraph_body` |
| 3 | 87  | `ISA-700:appendix:26ee3d6a:paragraph_body` |
| 4 | 75  | `ISA-710:appendix:b52890a3:paragraph_body` |
| 5 | 70  | `ISA-720:appendix:3d4ed148:bullet` |
| 6 | 69  | `ISA-570:appendix:9fe35f53:paragraph_body` |
| 7 | 64  | `ISA-1200:appendix:51e42baa:paragraph_body` |
| 8 | 49  | `ISA-1200:appendix:9d26c70e:paragraph_body` |
| 9 | 48  | `ISA-510:appendix:79ecadca:paragraph_body` |
| 10 | 43  | `ISA-315:appendix:f16ad4df:bullet` |

- 46% 의 chunk 가 `#<idx>` suffix 부착 상태
- 최악 case: ISA-720 감사보고서 사례 섹션에서 단일 paragraph 삽입/삭제 시 **201 chunk_id 가 동시 재할당**
- 이는 content drift detection (§8.1) 의 의도된 동작이나 "appendix paragraph_body = 사실상 source_idx 순번 ID" 에 근접

**v1.1 spec 위반 여부**: **없음**. §6.3 fallback + §6.4 Pass 2 알고리즘을 정확히 구현한 결과.

**v1.2+ 설계 discussion (Task #7 이관)**:

| 질문 | 현 설계 영향 | 대안 |
|---|---|---|
| chunk_id 의 51% 가 source_idx 의존 | DOCX author mutation 시 content drift detection 활성 (귀하 Task #7 critique #1 와 직접 연결) | content-based hash fallback (`kind:sha1(content_text)[:8]`) — 단 content 변경 시 id 변경 |
| Qdrant upsert idempotency | v1.1 spec 의 source_idx idempotency scope 내 (동일 DOCX 입력 + 동일 parser version 조합) | scope 축소 footnote (§8) |
| downstream retrieval 시 chunk_id semantic cleanliness | 의미적 구성 약화 (`#2237` 은 semantic 정보 없음) | 현상 유지 — heading_trail_hash 와 content_text 가 이미 semantic carrier |

**권고**: 본건 F5 를 Task #7 (Devil's Advocate Phase 2 비판) 의 "SemVer stress test" 와 연동 논의하여 v1.2 판단. 현 시점 Phase 2 pass/fail 에 영향 없음.

---

## 4. 추가 Findings

### 4.1 N1 (ESCALATED → I1) — "목차"/"문단번호" TOC-header leak: 35/36 ISA systematic

**2026-04-21 16:07 post-CP2 cross-verification addendum**: devils-advocate-critic 독립 재검증 결과 본 현상은 "Phase 1 carry-over 경미 cosmetic" 이 아니라 **35/36 ISA (실측 34개×2 + 2개×1 = 70 chunks)** 전수 재현되는 구조적 결함으로 재분류. severity N1 → **I1 (ISSUE, phase 2 post-filter 로 MINOR rework 권고)**.

**현상**:
- `output/md/ISA-*.md` 대부분 파일 초반에 kind=paragraph_body 로 `"목차"` / `"문단번호"` 2 건씩 등장 (36 ISA × 2 = 72 예상, 실측 70 → ISA-315/ISA-540 각 1 건, 다른 34 ISA 2 건씩)
- 예: ISA-300.md L13 "목차", L16 "문단번호" (둘 다 `<!-- kind: paragraph_body | idx: 2191/2192 -->`)
- **전수 재현성**: 35 / 36 ISA 에서 일관 발생 → edge case 아닌 systematic defect

**원인**: Phase 1 `structure.py` state machine 의 PRE_TOC → TOC → STANDARD_BODY 전환 경계에서, DOCX TOC 표의 2×N 헤더 cell ("목차" 헤더 + "문단번호" 헤더) 을 TOC 컨테이너 일부로 인식하지 못하여 body 로 분류. Phase 1 checkpoint_1_review.md 의 "목차 격리" 는 TOC 본문 (장 제목 list, `ad` 스타일) 에 한정되었음.

**영향**:
- 스펙 위반: 없음. `kind=paragraph_body`, `section=None`, `appendix_index=None` 는 v1.1 §9.2 허용.
- 임베딩 품질: 70 noise chunk (2~4 token) 가 embedding 공간에 진입 → RAG 검색 시 "목차" query 에 의도치 않은 match 가능성
- chunk 품질 지표: 70 / 8,660 = 0.8% noise contamination
- 판정 영향: CP2 pass/fail 을 가리지 않으나 Phase 3 이전 cleanup 권고

**수정 옵션**:
| 옵션 | 위치 | 공수 | 근본원인 해결 |
|---|---|---|---|
| (a) Phase 1 `structure.py` 수정 | md_renderer 레이어 | HIGH (CP1 재검증 필요) | ✅ 근본 |
| **(b) Phase 2 post-filter** | **md_parser.py 출력 직후** | **LOW (3~5 line)** | 🟡 증상 완화 |
| (c) 무조치 → Phase 3 cleanup | qdrant_writer | MID | ❌ symptom propagation |

**권고**: **(b) 채택**. md_parser.py 에 `_TOC_STOPWORDS = {"목차", "문단번호"}` 정의 후 `kind=paragraph_body and section is None and content_text.strip() in _TOC_STOPWORDS` 매칭 chunk 드롭. parser-implementer 에 MINOR rework 요청 (1/2 rework budget 사용).

**Phase 2 수정 예상 효과**:
- 70 chunks 드롭 → chunks_total 8,660 → 8,590
- null-section 104 → 34 (cross-ref block_quote 만 잔존)
- appendix_index_distribution[null] 6,837 → 6,767
- paragraph_links / F4 canonical 등 다른 invariant 영향 없음

근본 해결 (a) 는 v1.2 향후 개선 항목.

### 4.2 N2 — `<null>` section 104 件 분해

§2.5 에서 이미 확인:
- **70 chunks** = "목차"/"문단번호" TOC leak (N1 과 동일 원인)
- **34 chunks** = 감사기준서 상호참조 block_quote ("이 감사기준서는 감사기준서 200 …와 함께 이해하여야 한다.")
  - 32 ISA 에서 block_quote 1 건씩 + 2 ISA 에서 예외 (ISA-200/1200/315/540 중 일부)
  - 이들은 ISA 본문 최상단 (`## 서론` 전) 에 위치하는 자기 참조 statement → section 미부여 정상

**판정**: 104 전수 원인 식별 완료. 파싱 오류 아님.

### 4.3 F2 (Phase 1) — ISA-1200 section enum 보강 확인

Phase 1 checkpoint_1_review.md F2 에서 "ISA-1200 전용 heading 2 들이 `section` enum 미분류" 지적. Phase 2 METRICS 확인:

```
section_distribution (ISA-1200 contribution 포함):
  general_principles       76  ← 일반원칙과 책임
  risk_response           149  ← 평가된 위험에 대한 감사인의 대응
  conclusion_reporting    113  ← 결론 및 보고
  risk_assessment          63  ← 위험평가
  planning                 28  ← 감사 계획
  engagement_acceptance    21  ← 감사업무의 수임 또는 유지
  purpose                 100
  ...
```

→ ISA-1200 특수 section enum 6 종 모두 populated. **F2 해결 확인**.

### 4.4 F1 (Phase 1) — 스타일-상속 numPr 후속 확인

Phase 1 F1 해결 후 requirement/application_guidance 분포:

```
requirement              1,161
application_guidance     1,788  ← Phase 1 초기 유실 820+ 회복 반영
paragraph_links          1,788  ← app_guide 와 1:1 매칭 검증됨 (§1.2)
```

ISA-200 (과거 app_guide 1 개) 실측 83 paragraph_links → **F1 회복 확인**.  
ISA-1200 chunks 660 (과거 유실 152 반영 회복) → **F1 회복 확인**.

---

## 5. Issues 종합 및 조치

| ID | 심각도 | 항목 | Phase 2 필수 rework? | 조치 | 최종 상태 |
|---|---|---|---|---|---|
| **I1** | 🟠 ISSUE → ✅ CLOSED | "목차"/"문단번호" 70 chunks TOC leak (35/36 ISA systematic) | **Yes (MINOR)** | parser-implementer 에 md_parser post-filter 추가 요청 — 1/2 rework budget 사용 | ✅ **적용 완료** (2026-04-21 EVE+, invariant 전원 유지) |
| N2 | 🟡 NOTE → ✅ 자연 해소 | `<null>` section 104 분해 완료 (I1 수정 시 70 감소) | **No** | 원인 식별됨 — 스펙 내 현상 | ✅ 104→34 실측 (Δ−70) |
| F5 | 🟠 DISCUSS → 📝 v1.1.1 finding | fallback-kind Pass 2 suffix 3,989 chunks (46%, 최대 cluster 201) | **No** | **Task #7 이관** — v1.2+ SemVer stress test 연동 | 📝 v1.1.1 §9.5 조건부 finding (Phase 3 측정 대기) |

**parser-implementer 에 rework 요청 건: 1 건 (I1 post-filter)** → ✅ **완료, 1/2 budget 사용**.

**I1 수정 spec** (md_parser.py 수정 제안):
```python
_TOC_STOPWORDS = frozenset({"목차", "문단번호"})

def _is_toc_leak(chunk) -> bool:
    return (
        chunk.kind == "paragraph_body"
        and chunk.section is None
        and (chunk.content_text or "").strip() in _TOC_STOPWORDS
    )

# 적용 시점: chunk 리스트 생성 직후, chunk_id 산출 전
chunks = [c for c in chunks if not _is_toc_leak(c)]
```

**예상 diff 영향**: 70 chunks 드롭 (ISA-315/ISA-540 각 1건, 다른 34 ISA 각 2건). uniqueness/canonical F4/paragraph_links 불변.

---

## 6. 20-샘플 cross-verification 요약표

| # | Sample | File | 검증 결과 |
|---|---|---|---|
| 1 | F4 canonical ISA-300 `7.#2237` | ISA-300.json + MD L94 | ✓ PASS |
| 2 | F4 canonical ISA-300 `7.#2238` | ISA-300.json + MD L97 | ✓ PASS |
| 3 | F4 canonical ISA-701 `4.#8422` | ISA-701.json + MD L37 | ✓ PASS |
| 4 | F4 canonical ISA-701 `4.#8427` | ISA-701.json + MD L52 | ✓ PASS |
| 5 | ISA-1200 split part 0 | table#11079 chunk_index=0 | ✓ PASS |
| 6 | ISA-1200 split part 1 | table#11079#1 chunk_index=1 | ✓ PASS |
| 7 | ISA-1200 split part 2 | table#11079#2 chunk_index=2 | ✓ PASS |
| 8 | ISA-230 보론 appendix=1 | 16 chunks populated | ✓ PASS |
| 9 | ISA-300 보론 appendix=1 | 40 chunks populated | ✓ PASS |
| 10 | ISA-510 보론 appendix=1 | 50 chunks populated | ✓ PASS |
| 11 | ISA-570 보론 appendix=1 | 75 chunks populated | ✓ PASS |
| 12 | ISA-620 보론 appendix=1 | 31 chunks populated | ✓ PASS |
| 13 | ISA-700 보론 appendix=1 | 98 chunks populated | ✓ PASS |
| 14 | ISA-705 보론 appendix=1 | 117 chunks populated | ✓ PASS |
| 15 | ISA-710 보론 appendix=1 | 79 chunks populated | ✓ PASS |
| 16 | ISA-1100 보론 appendix=1 | 69 chunks populated | ✓ PASS |
| 17 | null-section sample #1 (ISA-200 idx=4 "목차") | confirmed TOC leak | N1 flagged |
| 18 | null-section sample #2 (ISA-1100 idx=9829 cross-ref) | confirmed block_quote | informational |
| 19 | unknown_numbering (ISA-210 idx=542) | 서약문 continuation fragment | ✓ PASS (allowed) |
| 20 | ISA-250 / ISA-260 Phase 1 재확인 | 150 / 241 chunks + links 정상 | ✓ PASS |

---

## 7. 판정

**✅ PASS (FINAL, I1 해제)** — *2026-04-21 EVE+ 갱신*

- Phase 2 md_parser.py 구현은 json_schema **v1.1.1** 의 모든 normative invariant 를 충족한다.
- Phase 1 CHECKPOINT 1 의 F1/F2 잔존 이슈는 Phase 2 METRICS 로 회복 확인.
- **I1 MINOR (TOC leak) 해제 (2026-04-21 EVE+)** — parser-implementer post-filter rework 1 건 적용 → chunks 8,660→**8,590**, null-sec 104→**34**, TOC leak 70→**0**. F4 canonical 4 pair / paragraph_links 1,788 / chunk_id uniqueness 100% / schema_validation 36/36 / token_estimate.max 3,423 전원 불변. devils-advocate-critic 측 독립 재검증 결과와 완전 정렬 (METRICS 숫자 8/8 EXACT).
- N2 는 경미 informational, rework 불요 (I1 수정으로 104→34 자연 감소).
- F5 (fallback-kind 3,989 suffix) 는 spec 준수 상 의도된 동작이나 v1.2 설계 논점으로 Task #7 Devil's Advocate Phase 2 비판에 이관 → **v1.1.1 §9.5 bias finding 으로 조건부 확정** (Phase 3 측정 프로토콜 이후 v1.2 bump 판단).

**Phase 3 (Qdrant ingestion) 진입 blocker 없음** — critic 측 "GO 승격" 권고 일치.

**선결 조건 이행 현황**:
- ✅ Task #7 (devils-advocate-critic) 비판 수령 완료 — `docs/devils_advocate_checkpoint_2.md` 560 lines (HIGH 2 + MED 5 + LOW 3).
- ✅ v1.1.1 patch bump 완료 — `docs/json_schema.md` §2.2 PATCH row + footnote / §8.4 scope / §9.5 bias / §12 const / §16 Changelog 적용. 36 JSON `schema_version: "1.1" → "1.1.1"` in-place 갱신 (payload 바이트 동등).
- ✅ I1 post-filter rework 완료 (parser-implementer, rework 예산 1/2 사용).
- ⏳ `src/audit_parser/ingest/types.py:26` `JSON_SCHEMA_VERSION` 상수 1-liner `"1.1" → "1.1.1"` bump — parser-implementer 측 적용 대기 (미적용 시 재regen 시 36 JSON wipe 위험, rework 예산 산입 여부 team-lead 판정 대기).
- ⏳ Phase 3 진입 — team-lead 지시 대기.

---

## 8. 메타: 본 검수 절차의 품질

Phase 1 "F4 3건 vs 6쌍" stale claim 교훈 적용:
- METRICS.json 수치를 사실대로 수용하지 않고 Python 독립 re-count 로 3.1 에서 462 vs 4,451 gap 발견
- MD line 번호까지 역추적하여 §2.1 / §2.2 canonical pair 확인
- Fallback-kind 3,989 는 팀-리드 보고 (462) 범위 밖이므로 별도 flag 처리

devils-advocate-critic 과의 교차 검증 protocol (seed-fixed sample + 독립 script) 은 DM 으로 전달 완료. diff 발견 시 즉시 alignment 계획.

---

**관련 문서**:
- `docs/json_schema.md` **v1.1.1** (2026-04-21 EVE+ PATCH bump — §2.2 footnote / §8.4 scope / §9.5 bias finding)
- `docs/checkpoint_1_review.md` (Phase 1 검수 — F1/F2/F3 원본)
- `docs/f4_known_duplicates.md` (F4 canonical 2 pair 증거)
- `docs/devils_advocate_checkpoint_1.md` (Phase 1 비판)
- `docs/devils_advocate_checkpoint_2.md` (Phase 2 비판 560 lines, CONDITIONAL GO → GO 승격)
- `docs/PHASE_2_REPORT.md` (team-lead 종합 보고서 — §4 CP2 검수 / §6 v1.1.1 bump rationale / §8.2 CP3 scope)

---

## Appendix A. Domain Reviewer Retrospective (2026-04-21 EVE+)

> team-lead 제안에 따른 CHECKPOINT 2 검수 경험 회고. Phase 3 CP3 에서 재사용할 방법론·판단 기준·협업 교훈을 자기참조 가능한 형태로 남김.

### A.1 방법론 — 20-샘플 stratified sampling

**동기**: JSON 36 파일 × 8,660 chunks 전수 육안 검토 불가능. METRICS.json 수치 신뢰만으로는 Phase 1 "F4 3건 vs 6쌍" 유형 재발 위험 (sampling bias 또는 pipeline silent drift 를 덮어버림).

**설계 (4 strata × 5 샘플 = 20)**:
1. **구조 다양성** — chunk 수 기준 상/중/하 ISA 각 1-2 건 (ISA-200 stem 다수 vs ISA-610 단문)
2. **대형 표 포함** — ISA-1200 66×2 용어의 정의 분할 경계 확인 (3-part split, 33/23/12 rows, token < 3500 / 모두 header 복제)
3. **보론(appendix) 포함** — 9 unnumbered 보론 → `appendix_index=1` 정상 부착 9/9 확인
4. **F4/F5 hot-spot** — ISA-300 `7.`, ISA-701 `4.` (F4 canonical 2 pair) + ISA-720 `appendix:3d4ed148:paragraph_body` (F5 worst cluster 201 member)

**산출**: null-section 104/8,660 (1.2%) 중 **70 건이 stopword 누수**임을 샘플 내 3 건에서 detect → I1 escalation 근거. METRICS 집계로는 "null_section: 104" 한 줄이어서 silent 했음.

**교훈**: METRICS 의 aggregate 지표는 "정상 분포 확인용" 이지 "누수 탐지용" 이 아님. Phase 3 CP3 에서 Qdrant payload 검증 시에도 **stratified + raw content spot-check** 병행 필수.

### A.2 I1 escalation 의사결정 — N1 → I1 승격 경로

**초판 판정 (N1, 경미 informational)**: null-section 104 건을 "legitimate stem chunks + 일부 TOC edge" 로 보고 경미 처리.

**전환 트리거**:
1. devils-advocate-critic 측 독립 재검증에서 "최대 클러스터 64 → **201 member**" (ISA-720 3d4ed148 stem) 교정 지적
2. 같은 교차검증에서 "null-section 104 중 70 건이 `목차`·`문단번호` stopword paragraph_body" 단일 패턴 확인
3. 70 이 특정 문자열 2개에 집중 → random noise 가 아니라 **systematic filter gap** 임을 시사

**승격 후 판정 (I1 MINOR, 2026-04-21 post-CP2 addendum)**:
- severity: informational → MINOR (Phase 3 ingestion 전 post-filter 1 건 삽입 권고)
- rework 예산: 2/2 중 1 소비
- 예측 delta 8 항목 사전 공표 (chunks 8,660→8,590, null-sec 104→34, leak 70→0, 나머지 5 지표 불변)
- parser-implementer 1 건 post-filter (`_TOC_STOPWORDS` frozenset + `_is_toc_leak_chunk`) 적용 → 예측치 8/8 EXACT 일치

**교훈**: severity 판정은 **패턴 집중도** (70/104 = 67% 단일 stopword) 에서 결정. 경미하게 보이는 aggregate 수치도 분포가 **특정 cause 에 집중** 되어 있으면 MUST-FIX. Phase 3 CP3 에서 Qdrant payload 누락·잘못된 embedding 발견 시 같은 logic 적용.

### A.3 v1.1.1 PATCH bump — 스펙 문서와 데이터 정합

**scope (§2.2 Changelog)**:
1. **§2.2 SemVer footnote** — v1.1 이 `chunk_id` 산출 함수 변경을 포함하면서도 MINOR 로 판정된 근거 명시 (v1.0 배포 JSON 0 건 + 외부 consumer 부재). Phase 4 RAG deploy 후에는 **chunk_id format 확장 항상 MAJOR** 명문화.
2. **§8.4 idempotency scope limit** — ISA-720 201 member stem 처럼 fallback-kind suffix 가 heavy cluster 를 형성할 때 stale `source_idx` 가 incremental ingest 에서 잘못된 upsert 를 유발할 수 있음. Phase 3 CP3 에서 per-collection atomicity 검증 필수.
3. **§9.5 ISA-1200 header bias finding** — 66×2 용어의 정의 3-part split 시 header row 를 part 1/2/3 에 모두 복제하는 현 policy 가 retrieval 단계에서 header token bias 를 만들 가능성. Phase 3 에서 10 seed query top-5 co-occurrence **≥30%** 또는 cosine Δ **<0.01** 측정 → 기준 위반 시 v1.2 MINOR bump.
4. **§12 JSON Schema const 갱신** — `schema_version.const: "1.1.1"`, fixture schema + drift gate 동기화.
5. **§16 Changelog v1.1.1 row** 추가.

**data propagation (36 JSON + METRICS.json)**:
- `schema_version: "1.1" → "1.1.1"` in-place string replace, 바이트 동등 (chunk_id·embedding·heading_trail_hash·paragraph_links 전원 불변)
- 초기 bump 이후 parser-implementer I1 regen 이 wipe → 재동기화 필요했음
- 근본 원인: `src/audit_parser/ingest/types.py:26` `JSON_SCHEMA_VERSION: Final = "1.1"` 하드코드. parser-implementer 1-liner bump 로 해결 (6 파일 cascade: types.py + fixture schema + 3 test + validate_json.py)

**교훈**: **스펙 문서 bump 만으로 부족** — code 상수·fixture schema·drift gate 의 trinity 를 **같은 커밋 단위** 에서 동시 bump 해야 regen-safety 확보. Phase 3 에서 Qdrant collection schema version 도 동일 pattern 적용 필요.

### A.4 Critic 과의 협업 교훈

**성공 사례**:
1. **숫자 상호 검증** — 내 METRICS 집계 (null-sec 104) + Critic 독립 re-count (ISA-720 201 member) → 두 관점 합쳐야 완전 그림. 어느 한 쪽만으로는 I1 escalation 도출 불가.
2. **예측치 사전 공표** — I1 fix 전 8 항목 delta 공표 → parser-implementer·critic 모두 같은 기대값으로 수렴 → fix 후 "8/8 EXACT" 상호 확인 가능.
3. **self-audit 상호 인정** — Critic 측 "9 ISA stratified 샘플 정정" + 내 측 "첫 bump wipe 인지 지연" 양측 자기보고 → 추후 neutrality 확보.

**개선 포인트**:
1. **timing artifact 주의** — Critic 의 METRICS drift 지적은 내 첫 bump + parser regen 타이밍 cross 에서 발생한 스냅샷 오차. 데이터 일관성 검증은 **fixed timestamp 스냅샷** 기준으로 조율 필요.
2. **scope boundary 선언** — 내가 output/json/ 직접 편집 (parser-implementer 영역)한 점. Phase 3 에서는 편집 범위를 DM 으로 **사전 공표** 후 team-lead ack 받는 플로우 권장.

### A.5 Phase 3 CP3 검수 scope (재확인)

team-lead §8.2 승인 5 항목 + critic LOW 1 항목:
1. §9.5 ISA-1200 header bias 측정 (10 seed query × top-5 co-occurrence ≥30% OR cosine Δ <0.01) → v1.2 MINOR trigger 판정
2. Qdrant collection 네이밍 규약 (`audit_standards_회계감사기준_2025` 패턴) validate
3. payload 매핑 verification — json_schema.md §13 의 필드 전수 Qdrant payload 반영 확인
4. §8.4 idempotency incremental ingest edge case (stale `source_idx` suffix handling) 재검증
5. C-P2-9 per-collection atomicity (LOW, critic 이관) — ingest 중간 crash 시 partial state 처리

**준비물**: docker-compose Qdrant 기동 확인 (parser-implementer 측), Upstage Solar API key (parser-implementer 측) — **내 환경에 의존성 없음**. Phase 3 팀 소환 시 즉시 참여 가능.

---

*End of Appendix A — Domain Reviewer Retrospective.*
- `output/json/METRICS.json` (Phase 2 raw metrics)
