# Devil's Advocate — CHECKPOINT 3 비판 보고서

> **작성자**: `devils-advocate-critic` (read-only on `audit-parser-phase3`; writable file 1건: 본 문서)
> **작성일**: 2026-04-22
> **대상 산출물**: Phase 3 (Stage 2b: JSON → Qdrant 적재) 설계·구현·검수
> **참조 산출물**:
> - `src/audit_parser/ingest/{embedder,qdrant_writer}.py` (Task #2, #3, #9)
> - `src/audit_parser/cli.py` (Task #4, `ingest --upsert`)
> - `output/json/EMBED_METRICS.json` + `.idempotency.json` (Task #5, #9)
> - `output/search_demo_results.json`, `notebooks/search_test.ipynb` (Task #6)
> - `docs/checkpoint_3_prep.md` (Domain Reviewer IDLE prep, frozen)
> - `docs/checkpoint_3_review.md` **v3** (Domain Reviewer `PASS (CONFIRMED by Critic cross-check 2026-04-22)`, 576 lines, §1-§11 Appendix)
> - `docs/json_schema.md` **v1.1.2** (1,174 lines, §6.5+§6.5.1 namespace fact fix, §15a v1.2 candidates, §16 Changelog 7-bullet)
> - `docs/devils_advocate_checkpoint_2.md` (v1.1 CP2 — DEFER 5건 추적 원본)
>
> **검증 전제**: CP3 verdict "PASS (CONFIRMED)" 를 알고도 미검증 가정을 의도적으로 공격하기 위해 작성. 심각도 라벨링은 `docs/devils_advocate_checkpoint_{1,2}.md` 와 통일.

---

## 0. Executive Summary

| 항목 | Verdict |
|---|---|
| **Phase 4 진입 Go/No-Go** | ✅ **GO** (조건부 GO 아님 — pre-fix 블로커 0건) |
| CP3 Domain Reviewer verdict | ✅ PASS (CONFIRMED) 동조 |
| 4-anchor cross-check 독립 재측정 | ✅ 4/4 전수 일치 (3,919 / 679 / 201 / 51) |
| F1 Qdrant scroll 전수 census | ✅ 141 MB 실증 → Task #9 v1.1.2 PATCH 후 17,252→8,562 해소 (−50.4%) |
| F1 PATCH 7-point 재검증 | ✅ 실측 10/11 + 이론 1 INDIRECT (Reviewer §11) |
| §6.5 NAMESPACE spec-bug 교정 | ✅ v1.1.2 반영 (`NAMESPACE_URL` → `NAMESPACE_DNS`) |
| C-P2-1 F5 드리프트 42.64% | ⚠ REPORT (Phase 4 의무 3-tier 편입 확정) |
| v1.1.2 PATCH 3-block (F1/§6.5/C-P2-1 기록) | ✅ 지지 |
| DEFER 5건 실측 | 4 PASS / 1 REPORT (C-P2-1) |
| Critic 잔여 critique 4건 | Security LOW / HNSW F2-bis MED / Backup MED / Phase 4 regex LOW |
| rework budget | 1/2 사용 (F1 집행), 잔여 1 |

**결론**: Phase 3 는 기능·품질 양면에서 ship-ready. Domain Reviewer 와 Critic 2인 독립 검증이 4-anchor / F1 census / NAMESPACE spec-bug / C-P2-1 upper-bound / §9.5 범위 한정 5개 축에서 수렴 일치. Phase 4 진입 전 **추가 pre-fix 요구 없음**. Phase 4 scope 에 **의무 조항 3건** (§3.2 C-P2-1 drift 재측정 / §4.2 HNSW 파라미터화 재검토 / §4.4 chunk_id regex 확장 3자 합의) 만 선기재 요청.

---

## 1. Block (a) — CP3 PASS 동조 (CP2 Critic 역할 연속)

**Domain Reviewer `docs/checkpoint_3_review.md` v3 §10 Final Verdict 를 전수 endorsement**.

| CP3 검수 항목 | Reviewer 판정 | Critic 재검증 | 최종 |
|---|---|---|---|
| 구조 검수 5건 | 5/5 PASS | spot-check 2건 (§6.5.1 / §15a) 일치 | ✅ PASS |
| DEFER 5건 실측 | 4 PASS + 1 REPORT | §3 (C-P2-1) 조건부 pushback 반영 | ✅ PASS |
| Invariants I-a~I-e | 5/5 PASS | 독립 재측정 미수행, Reviewer 증거 신뢰 | ✅ PASS |
| New Finding F1 | v1.1.2 PATCH 권고 | Qdrant scroll 500+36 전수 census 검증 | ✅ PASS → Task #9 집행 완료 |
| New Finding F2 (NAMESPACE) | v1.1.2 §6.5 fact fix | spec-code divergence 심각도 "reproducibility hazard" 재분류 | ✅ PASS |
| Task #9 재검증 7-point | 실측 10/11 + 1 INDIRECT | §11.4 재현 script 재실행 불필요 (Reviewer `embedded_at` 287 distinct timestamps 로 re-ingest 확정) | ✅ PASS |
| rework budget 1/2 사용 | F1 집행, 잔여 1 | 동의 | ✅ 확인 |

**동조 근거 (cross-check 2026-04-22)**: 
- 4-anchor 4/4 일치 (critic 독립 스크립트 `glob("output/json/ISA-*.json") → re.search(r"#\d+$", chunk_id)` 재실행)
- F1 census 141 MB (critic Qdrant scroll) vs 137 MB (Reviewer 추정) ±5% 일관
- §9.5 Δ 0.2046 Reviewer 독립 재측정 = parser-implementer 자가판정 `cosine Δ 0.2046` 완전 일치 (byte-level)
- §6.5 NAMESPACE_DNS vs 구 spec NAMESPACE_URL 한 hex digit 차이 (6ba7b81**0** vs 6ba7b81**1**) 검증 완료

**CP2 Critic 협업 교훈 연속 기록**: CP2 DEFER 5건 (C-P2-1 drift / C-P2-3 bias / C-P2-6 tokenizer / C-P2-7 latency / C-P2-8 10k trigger) 이 CP3 에서 4 PASS + 1 REPORT 로 해소. Reviewer CP3 §1 각주의 "CP4 해석 혼선 재발 방지 전례" 문구 상호 호응.

---

## 2. Block (b) — C-P2-1 Phase 4 Trigger 재공표 (Critic 강경 입장)

### 2.1 수치 재확인 (Reviewer CP3 §4.1 upper-bound 해석 박스 수용)

| 측정 | 값 |
|---:|---:|
| arith mean drift | 42.38% |
| **10% trimmed mean** | **42.64%** |
| weighted mean | 45.62% |
| per-ISA max (ISA-720) | 73.8% |
| per-ISA min (ISA-530) | 13.5% |

**해석**: `realized_drift = UB × P(재파싱) × P(초반 삽입) × f(삽입 개수)` — 42.64% 는 **이론적 상한**. 실측 = 상한 × 3-요소 함수 (Reviewer §4.1).

### 2.2 Critic 강경 입장 — Phase 4 의무 3-tier 은 **최소 조건**

Reviewer `§15a.1` + `checkpoint_3_review.md §9` 2축에 이미 명문화된 의무 3-tier:

1. Phase 4 DOCX 통합 시 **재파싱 실측 빈도 기록 의무화**
2. `realized_annual_cache_invalidation > 200%` → v1.2 MINOR bump **자동 발동**
3. `docs/checkpoint_4_review.md` 내 "C-P2-1 재평가 결과" 섹션 **필수 (miss → rework)**

**Critic 입장 — 본 3-tier 은 "최소 조건" 이지 "충분 조건" 아님**:

- (i) prep §3.4 "REPORT-ONLY" 합의는 현 v1.1.1 한정. Phase 4 ISQM-1 통합 시 chunks_total 15k 돌파 예상 — **C-P2-8 trigger 와 동시 발동 가능**. 동시 발동 시 v1.2 minor 가 아닌 **v2.0 major (sha1[:12] 확장)** 요구됨.
- (ii) "200% threshold" 는 Critic 권고값. Reviewer 가 수용했으나 **실측 데이터 0건 기반의 heuristic**. Phase 4 1차 측정 후 threshold 자체 재조정 여지 존재.
- (iii) **"Phase 4 일정 압박 시 slip 위험"** 은 실제 위험 — Phase 0~3 진행 중 이미 "Phase 4 에서" 로 deferred 된 항목 누적 (C-P2-7 15k latency / C-P2-8 10k trigger / C-P2-1 drift / §9.5 ISA-540 range / HNSW 파라미터화 / chunk_id regex / backup 전략). Phase 4 **단일 CHECKPOINT 가 8+ 검증 항목 일괄 수행** 구조 = 체크리스트 고갈 위험.

### 2.3 Critic 권고 — Phase 4 prep 선기재 요구

Phase 4 kickoff 시 `docs/checkpoint_4_prep.md` (신규) 에 **본 3-tier 을 §0 Executive 최상단 바인딩**:

```markdown
# CHECKPOINT 4 Prep (audit-standard-domain-reviewer, TBD)

## 0. 선기재 의무 조항 (from CP3 §9 + CP3 §15a.1 + devils_advocate_checkpoint_3.md §2.3)

CHECKPOINT 4 miss → rework 자동 처리:
1. [ ] Phase 4 DOCX 통합 후 재파싱 실측 빈도 기록 (분기 1회 이상)
2. [ ] realized_annual_cache_invalidation 계산 → 200% 초과 시 v1.2 MINOR bump 발의
3. [ ] "C-P2-1 재평가 결과" 섹션 (본 prep §N 로 채번)
4. [ ] C-P2-8 chunks_total ≥ 10k 도달 시 v2.0 기획 (동시 발동 주의)
5. [ ] HNSW 파라미터 externalize 재검토 (F2-bis MED, §4.2)
6. [ ] chunk_id regex Phase 4 prefix 확장 3자 합의 (§15a.1.2)
7. [ ] §9.5 ISA-540 table split 등 추가 3-part split 1건 이상 측정
```

이 선기재 없이 Phase 4 착수 시 Critic 은 **Phase 4 entry 에 CONDITIONAL 태그** 부착 권고. 현 Phase 3 Go/No-Go 와 분리된 **Phase 4 entry 조건** 으로 처리 — Phase 3 GO 자체는 불변.

---

## 3. Block (c) — v1.1.2 PATCH 3-block 지지 (개별 평가)

`docs/json_schema.md §16 Changelog v1.1.2 7-bullet` 개별 리뷰:

### 3.1 Bullet #1: F1 — Named vector zero-padding omit

**근거**: `docs/checkpoint_3_review.md §11` 7-point 재검증 PASS.

| 축 | 값 | 판정 |
|---|---|---|
| indexed_vectors_count | 17,252 → **8,562** (−50.4%) | ✅ 실증 |
| chunk summary slot 존재 | 0/500 | ✅ 실증 |
| summary passage slot 존재 | 0/36 | ✅ 실증 |
| HNSW slot 독립 순회 (Critic 권고 1) | `using="passage"` top-10 summary contamination 0건, `using="summary"` top-50 non-summary 섞임 0건 | ✅ behavioral PASS |
| re-ingest vs payload-only (Critic 권고 2) | `embedded_at` 287 distinct timestamps 2026-04-22T03:41–03:59Z, `api_calls=0 / cached_hits=8,626` | ✅ re-ingest 확정 |

**Critic 판정**: ✅ 지지. F1 은 code-only change, schema 개념 변경 없음. Reviewer 재검증 프로토콜 충분.

### 3.2 Bullet #2: §6.5 NAMESPACE spec-bug 교정

**근거 — 나의 §5 cross-check 및 실증**:

```
NAMESPACE_DNS = 6ba7b810-9dad-11d1-80b4-00c04fd430c8   ← code 실제
NAMESPACE_URL = 6ba7b811-9dad-11d1-80b4-00c04fd430c8   ← 구 spec 오기재
```

한 hex digit (6ba7b81**0** vs 6ba7b81**1**) 차이 → UUID5 알고리즘 특성상 결과 UUID 완전 상이 → 외부 컨슈머 spec literal 구현 시 8,626 point_id 전부 mismatch.

**Critic 판정**: ✅ 지지. Reviewer 가 §6.5.1 "⚠ spec-implementation divergence 경고" 박스에 Critic 의 "reproducibility hazard 수준" 강조 문구 + 8,626 DNS-derived 명시 + "외부 컨슈머 본 정정본 기준 구현 필수" 강행 문구 반영 (line 492-505) 확인.

**심각도 분류**: 단순 documentation typo 가 아니라 **reproducibility hazard** — spec 따라 구현한 외부 RAG 팀이 기존 DB 의 point 를 단 하나도 못 찾음, "내가 만든 point 가 기존 DB 에 왜 없지?" 디버깅 몇 시간 소요. v1.1.2 급 교정은 불가피.

### 3.3 Bullet #3: §6.5 Frozen constant 경고

**Critic 판정**: ✅ 지지. Reviewer §6.5 line 483–489 반영 확인. 향후 namespace 변경 = v2.0 MAJOR trigger 명기 — Phase 4+ 신규 DOCX 통합 시에도 동일 namespace 유지 의무화.

### 3.4 Bullet #4: C-P2-1 F5 drift 42.64% trimmed mean 기록

**Critic 판정**: ✅ 지지. §4.1 upper-bound 해석 박스 + per-ISA max/min (ISA-720 73.8% / ISA-530 13.5%) + Phase 4 의무 3-tier 3종 세트 완비. Bullet 분리 권고 (v1.1.2 Changelog 7-bullet) 반영 확인.

### 3.5 Bullet #5-#7: §15a 신설 / §12 const / 근거 링크

- **#5 §15a v1.2 Candidates 표**: F5 fallback (1순위) / stale cleanup 조건부 / Phase 4 prefix 확장 3후보. Critic 제안 `{kind}#sha1-content` fallback 이 1순위로 기재됨 — 판정 **PASS**.
- **#6 §12 `"const": "1.1.2"`**: line 884 실증 확인. `src/` + `tests/fixtures/` + `output/json/` 36 파일 sync 완료 — parser-implementer 동반 집행. 판정 **PASS**.
- **#7 근거 링크**: `docs/checkpoint_3_review.md` 양방향 cross-ref (§1 각주 line 45 + 본 문서 Self-audit §6) 완성. 판정 **PASS**.

### 3.6 v1.1.2 PATCH 종합 평가

7-bullet 전수 PASS. **v1.1.2 는 clean PATCH** — MINOR/MAJOR escalation 불필요, 기존 8,626 point_id 및 재임베딩 payload 바이트 동등성 유지 (F1 은 named vector 구조만 변경, vector 값 불변).

---

## 4. Block (d) — Critic 잔여 Critique (Reviewer 미탐구 영역)

CP3 검수 scope 외 **운영성·Phase 4 선행 조건** 4건. Reviewer CP3 §9 의무 3-tier 와 상보적.

### 4.1 C-P3-D1 — Security (LOW / INFO)

**최초 심각도 HIGH 였으나 Critic 자가 재검증 결과 LOW 로 하향**.

**영역**: (j) Phase 3 원자성/보안 운영

**관찰**:
- `docker-compose.yml` bind: `"127.0.0.1:6333:6333"` + `"127.0.0.1:6334:6334"` ✅ — LAN 노출 차단 완료 (주석 `# 127.0.0.1 바인딩 — 로컬 개발 한정, 외부 노출 차단.` 명시)
- `.env.example`: `QDRANT_API_KEY=` 빈 값 + 설명 주석 `# 로컬 docker-compose 는 인증 불필요 — 빈 값 유지. 원격 Qdrant Cloud 사용 시 실제 API key 주입 (컨테이너 외부 노출이므로 반드시 설정).` — **documented policy** ✅
- `.env` (실키) `.gitignore` 포함 (Phase 0-1 검증 완료)
- git log secret scan (`git log -S "UPSTAGE_API_KEY=up_"` — 0 matches, Phase 0 기 확인)

**영향**: 로컬 개발 한정 보안 가정 기술되어 있고 실제 바인딩 일치. 원격 배포 시나리오 (Qdrant Cloud) 에 대해서도 `.env.example` 이 명시적 경고 제공.

**완화안**: 
- (a) Phase 4 이전 단계에서는 **추가 조치 불필요**.
- (b) Phase 5+ 프로덕션 배포 시점에 `docs/deployment.md` (신규) 로 TLS / API key rotation / network policy 별도 항목화 권고 — Phase 4 scope 아님.

**왜 내가 HIGH 로 오인했나**: Session 요약본 기반으로 "6333:6333 no 127.0.0.1 prefix" 로 기술돼 있었음 — **stale claim**. 실제 `docker-compose.yml` 재조회 시 127.0.0.1 prefix 존재. **CP2 Self-audit §3 의 "재조회 원칙" 위반** — 내가 stale source 재인용. 본 critique §6 Self-audit 에 명기.

**심각도 최종**: LOW/INFO — 기록 목적.

### 4.2 C-P3-D2 — F2-bis HNSW 하드코딩 (MED)

**영역**: (a) HNSW tuning (원 Task #8 critique area a)

**관찰**: 
- `qdrant_writer.py` line 84-85: `HNSW_M: Final = 16` / `HNSW_EF_CONSTRUCT: Final = 200` — 모듈 상수
- line 344, 349: `HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCT)` 호출부에 하드코딩 주입
- `__all__` 에 export 되어 있으나 **환경변수 / CLI flag / config 파일 어느 경로로도 overridable 아님**
- `PLAN.md §5.4` 기준값 일치 — 기능적으로 옳으나 **튜닝 용이성 부족**

**영향**: 
- Phase 4 ISQM-1 등 신규 DOCX 통합 시 chunks_total 15k 예상. Qdrant 공식 벤치 기준 m=16 은 sweet spot 이나 **recall/latency trade-off 재평가 기회 상실**.
- 실험 비용: 코드 수정 + PR + re-ingest (352s). 사소한 튜닝 주기 장애물.
- CP2 §C-P2-7 201-cluster latency 측정 결과 Scen.1 14.25ms / Scen.2 8.61ms — 현 m=16 이면 충분하나, **15k 점 도달 시 재측정 필수**.

**완화안 (v1.2 MINOR 후보)**:
- (a) `QdrantWriter.__init__` 인자에 `hnsw_m: int = 16`, `hnsw_ef_construct: int = 200` 추가
- (b) `.env.example` 에 `QDRANT_HNSW_M=16`, `QDRANT_HNSW_EF_CONSTRUCT=200` 기재
- (c) `CLAUDE.md §3` 환경변수 섹션에 기록

**왜 Reviewer 가 놓쳤나**: CP3 §3.1 collection config 는 `PLAN.md §5.4` 기준값 일치 여부만 확인. **"externalize 여부"** 는 structural 검수 외 운영성 영역이라 scope 초과 판정. Critic 역할 적절.

**심각도**: MED. Phase 4 pre-fix 필수 아님 (blocker 아님), **v1.2 MINOR 후보 추가 편입** 권고.

### 4.3 C-P3-D3 — Backup 전략 부재 (MED)

**영역**: (j) Phase 3 원자성 + 장애 복구

**관찰**:
- `docker-compose.yml`: `audit_qdrant_storage` named volume, `restart: unless-stopped` — **container crash 복구는 가능, 볼륨 corruption 시 복구 경로 부재**
- `docs/` 전반 backup / snapshot / disaster recovery 관련 문서 **0 건**
- 복구 경로 = full re-ingest: `.embed_cache.sqlite` 보존 시 `api_calls=0 / elapsed 352s` (idempotency §11 실증). **cache miss 시나리오 (sqlite 도 동시 손상)** = 8,590 × Upstage Solar passage call = ~$8.59 + summary 36 call = ~$0.04 ≈ **$8.63 + 5-10분 latency**
- SQLite `.embed_cache.sqlite` 자체는 F4 RESOLVED (WAL + integrity_check + `.corrupt.<UTC_ts>` 백업) 로 자체 복구 메커니즘 존재 — **부분적 mitigation**

**영향**: 
- 현재 단일 개발자 로컬 docker 환경 — 치명도 낮음
- Phase 4+ 실 RAG 배포 시 고객 질의 응답 공백 발생 가능
- `qdrant_storage` 볼륨 corruption 원인: disk full / kernel crash / docker daemon bug

**완화안 (Phase 5 운영 진입 시 필수, 현재는 권고)**:
- (a) `docker compose exec qdrant qdrant snapshot create` CLI 기반 snapshot 자동화 스크립트 (cron)
- (b) `qdrant_client.create_snapshot(collection_name=COL)` Python 주기 실행
- (c) snapshot 파일 원격 저장 (S3 / 단일 외부 디스크)

**왜 Reviewer 가 놓쳤나**: idempotency 검증 PASS 를 "복구 가능성" 으로 등치 — 실제로는 **`.embed_cache.sqlite` 생존** 전제. 양측 동시 손상 시 $8.63 재임베딩 비용 발생, Qdrant 볼륨 단독 복구 경로는 없음. Reviewer idempotency 측정은 WIP 모델 (file-based) 한정.

**심각도**: MED. Phase 4 블로커 아님. **Phase 5 운영 진입 시점 재평가** 권고, Phase 4 prep 에 backup 전략 초안 항목 추가.

### 4.4 C-P3-D4 — Phase 4 chunk_id regex MINOR bump (LOW)

**영역**: (b) SemVer + (h) schema_version drift (CP2 C-P2-4, C-P2-5 연속)

**관찰**: 
- `docs/json_schema.md §12 line 890`: `"standard_id": {"type": "string", "pattern": "^ISA-\\d{3,4}$"}`
- ISQM-1 통합 시 `standard_id = "ISQM-1"` → **current regex 불합격**
- 기타 인증업무기준 / 인증업무개념체계도 각각 `ASA-xxxx`, `FRMK-xxxx` 유사 prefix 예상 (확정 아님)

**영향**: 
- Phase 4 DOCX 통합 **시작 시점** 에 MD frontmatter parser (`md_parser.py`) 가 `standard_id` 검증 실패 → **파이프라인 즉시 실패**
- 사전 조치 없이 Phase 4 착수 시 첫 DOCX 파싱에서 crash
- `json_schema.md §15a.1.2` 에 이미 3자 합의 절차 (Domain Reviewer + Critic + Parser Implementer) 기재됨

**완화안 (Phase 4 착수 **전** 필수)**:
- (a) ISQM-1 / 기타 인증업무 / 인증개념 3종 DOCX scan 선행 → 실 prefix 확정 (Domain Reviewer Phase 4 prep §1)
- (b) regex 확장 `^(ISA|ISQM|ASA|FRMK)-\d{1,4}$` (가안) + 3자 합의 승인
- (c) v1.2 MINOR bump — Changelog 신설 row
- (d) 기존 36 ISA 파일 `schema_version` 은 불변 유지 (schema 확장은 backward compatible)

**왜 Reviewer 가 놓쳤나**: CP3 는 현 v1.1.2 체크포인트 scope 에 한정, Phase 4 진입 조건 은 §9 "Phase 4 의무 3-tier" 에 의무화만 기재. **시점 명확화** (regex 확장은 Phase 4 "착수 전" 임을 강조) 는 Critic 추가 기여.

**심각도**: LOW. 절차 기재 완료, 시점 명확화만 필요.

### 4.5 Critic 잔여 critique 종합

| # | 제목 | 심각도 | Phase 4 pre-fix 필수? |
|---|---|---|---|
| C-P3-D1 | Security | **LOW/INFO** | ❌ (127.0.0.1 bind 완료) |
| C-P3-D2 | HNSW 하드코딩 | MED | ❌ (v1.2 MINOR 후보) |
| C-P3-D3 | Backup 전략 부재 | MED | ❌ (Phase 5 운영 진입 시) |
| C-P3-D4 | chunk_id regex 확장 | LOW | ⚠ **Phase 4 착수 전 필수** |

**Phase 3 GO 블로커 0건**. Phase 4 pre-condition 1건 (C-P3-D4).

---

## 5. 10 Critique Area (a)-(j) 전수 Cover

원 Task #8 brief 의 (a)-(j) 10개 critique area 각각에 대한 최종 판정:

| # | 영역 | CP3 처리 | 판정 |
|---|---|---|---|
| a | HNSW tuning | F2-bis MED (C-P3-D2) — v1.2 MINOR 후보 | ⚠ 부분 미해결 |
| b | 4096d cosine memory | F1 PATCH 로 ~137 MB 절감, indexed 17,252→8,562 | ✅ 해소 |
| c | SQLite concurrency | F4 RESOLVED (WAL + integrity_check + corrupt 백업) | ✅ 해소 |
| d | chunk_id→UUID stability | F3 RESOLVED (DNS namespace frozen) + §6.5 fact fix | ✅ 해소 |
| e | Upstage Solar rate limits | embedder.py retry 3×2^attempt + AuthError fast-fail | ✅ 해소 (운영 시 재평가) |
| f | Named vectors trade-off | F1 v1.1.2 PATCH 로 per-point 구조 확정 | ✅ 해소 |
| g | DEFER 5 측정 해석 | CP3 §4 (4 PASS + 1 REPORT), Critic pushback 3항 반영 | ✅ 해소 |
| h | Phase 4 collection naming 충돌 | §15a.1.2 3자 합의 절차 + C-P3-D4 regex 확장 | ⚠ 절차 존재, Phase 4 착수 전 집행 필요 |
| i | Qdrant backup 전략 | C-P3-D3 MED — Phase 5 운영 진입 시 | ⚠ 부분 미해결 |
| j | 보안 | C-P3-D1 LOW — 127.0.0.1 bind + documented policy | ✅ 해소 |

**10개 영역 중 7 해소 / 3 부분 미해결 (a / h / i)**. 부분 미해결 3건은 모두 **non-blocker** — Phase 4 착수 시 순차 집행 가능.

---

## 6. Self-Audit (Phase 0-2 교훈 연속)

Phase 1 `docs/devils_advocate_checkpoint_1.md` §6 + Phase 2 `docs/devils_advocate_checkpoint_2.md` Self-audit 원칙 계승:

### 6.1 본 CP3 critique 에서 내가 실수한 2건

1. **Security 심각도 HIGH 오인 (C-P3-D1)**: Session 압축 요약본의 "6333:6333 no 127.0.0.1 prefix" 기술을 검증 없이 재인용 → 실측 `docker-compose.yml` 에는 127.0.0.1 prefix 존재. 실제로는 LOW/INFO 수준. **CP2 Self-audit §3 "timing-dependent 상태는 재읽기" 원칙 위반** — stale source 재인용. Task #8 작성 중 `Read` 재조회 시 정정.
2. **679 stem 오해석 (CP2 C-P2-1 top-10 표)**: Phase 2 초기 critique 에서 "679 stem = multi-member only" 로 해석, 실제는 **total unique stems 679 (multi 480 + single 199)**. CP3 §1 Anchor 2 표기 표준화 + `checkpoint_3_review.md §1 각주 line 45` 쌍방향 cross-ref 기록 완료. 본 문서의 cross-check 회신 (§1.참고) 에서 정정 공표.

### 6.2 공동 credit 기록

- **§6.5 NAMESPACE spec-bug 발굴**: Domain Reviewer 가 §6.5 교정 착수 중 "구 spec `NAMESPACE_URL` vs 실 code `NAMESPACE_DNS`" 불일치 포착 → Critic (나) 가 "reproducibility hazard 수준" 심각도 재분류 + 외부 컨슈머 경고 문구 강행. **공동 발굴, 공동 credit**. Reviewer `checkpoint_3_review.md §6 F2` + `json_schema.md §6.5.1` 에 대응 기록.

### 6.3 CP2 → CP3 교훈 체화 성과

| CP2 교훈 | CP3 적용 결과 |
|---|---|
| "전수 스캔 재확인" (stale METRICS 금지) | 4-anchor 독립 스크립트 재측정 — 3,919 / 679 / 201 / 51 전수 일치 |
| "timing-dependent 상태 재읽기" | Qdrant scroll 500+36 census 실시간 재조회, METRICS.json 재조회 |
| "DM scope 재검증" | cross-check 회신 5개 섹션 각각 근거 파일·라인 명시 |
| "Predictive delta 사전 공표" | F1 v1.1.2 PATCH 후 `indexed_vectors_count` 17,252→≤8,626 예측 → 실측 8,562 일치 |
| "공동 credit 기록" | §6.5 spec-bug Reviewer/Critic 공동 credit |

### 6.4 다음 Phase (CP4) 에 이월할 Self-audit 원칙

1. Session 압축본 수치는 **반드시 원본 파일 재조회 후 재인용** (C-P3-D1 실수 재발 방지)
2. Stem / cluster / census 등 **수치 용어는 정의부터 합의 후 인용** (679/480/199 혼선 재발 방지)
3. Cross-check 회신 시 **근거 파일 line number 명시** — Phase 2 관행 유지
4. Critic → Reviewer 쌍방 cross-ref 는 양 문서에 **동시 기록** (CP4 해석 혼선 재발 방지 전례)

---

## 7. Go/No-Go Verdict

### 7.1 Phase 4 진입 조건 체크

| 조건 | 상태 |
|---|---|
| CP3 PASS (Reviewer) | ✅ CONFIRMED |
| 4-anchor cross-check 전수 일치 | ✅ 3,919 / 679 / 201 / 51 |
| F1 v1.1.2 PATCH 재검증 PASS | ✅ 실측 10/11 + 이론 1 INDIRECT |
| §6.5 NAMESPACE spec-bug 교정 | ✅ v1.1.2 반영 |
| HIGH 심각도 미해결 | 0건 |
| MED 심각도 미해결 | 2건 (F2-bis HNSW / Backup) — **non-blocker** |
| LOW 심각도 미해결 | 2건 (Security INFO / chunk_id regex) |
| rework budget | 1/2 사용 (여유 있음) |
| Phase 4 착수 전 필수 사전 조치 | 1건 (C-P3-D4: chunk_id regex 확장 3자 합의) |

### 7.2 Go/No-Go 기준 매핑

- **GO**: Phase 4 진입 가능
- **CONDITIONAL GO**: HIGH 1~2건 pre-fix 권고
- **NO-GO**: HIGH 3건 이상

**실측**: HIGH 0 / MED 2 / LOW 2 → **GO** (CONDITIONAL 경계 아님).

### 7.3 최종 Verdict

```
┌────────────────────────────────────────────────────────────┐
│ Phase 3 CHECKPOINT 3 Go/No-Go — ✅ GO                       │
│                                                            │
│ - Phase 3 는 기능·품질·문서 3축 완결                           │
│ - Phase 4 진입 가능                                          │
│ - Phase 4 착수 **전** 1건 집행 필수: C-P3-D4 (chunk_id regex  │
│   확장 3자 합의 + v1.2 MINOR bump)                           │
│ - Phase 4 scope 에 §2.3 의무 3-tier 선기재 요구 (Critic 강경)  │
│ - MED 2건 (HNSW 하드코딩 / Backup) 은 Phase 4-5 순차 처리      │
│                                                            │
│ Critic: devils-advocate-critic @ audit-parser-phase3        │
│ 작성일: 2026-04-22                                          │
└────────────────────────────────────────────────────────────┘
```

### 7.4 Phase 4 진입 Critic 권고 3건 재확인

1. **Phase 4 착수 전 (pre-kickoff)**: C-P3-D4 chunk_id regex 확장 3자 합의 + v1.2 MINOR bump — §15a.1.2 절차 집행
2. **Phase 4 prep 최상단 바인딩 (§2.3)**: C-P2-1 의무 3-tier + C-P2-8 / C-P2-7 / §9.5 ISA-540 / HNSW externalize / backup 전략 초안 — **7-item 선기재**
3. **Phase 4 rework budget**: 2건 full reset (CP4 기준 신규 2건). CP3 의 잔여 1건은 CP3 scope 종결로 소각.

---

## 8. 근거 Cross-Reference 인덱스

| 근거 주제 | 근거 문서 · 라인 |
|---|---|
| CP3 PASS verdict | `docs/checkpoint_3_review.md §10` (line 471–482) |
| 4-anchor 일치 | `docs/checkpoint_3_review.md §1` (line 32–39) + Critic 독립 스크립트 (본 §1) |
| F1 Qdrant census 141 MB | Critic cross-check 2026-04-22 DM §2 (in-scope script) |
| F1 7-point 재검증 | `docs/checkpoint_3_review.md §11.1` (line 508–521) + `§11.4` 재현 script |
| §6.5 NAMESPACE fact fix | `docs/json_schema.md §6.5 + §6.5.1` (line 469–505) |
| §15a.1 Phase 4 의무 3-tier | `docs/json_schema.md §15a.1` (line 1118) + `checkpoint_3_review.md §9` (line 453–461) |
| §16 Changelog 7-bullet | `docs/json_schema.md §16` |
| C-P2-1 upper-bound 해석 | `docs/checkpoint_3_review.md §4.1` (line 255–265) |
| §9.5 범위 한정 | `docs/checkpoint_3_review.md §2.5` |
| Self-audit cross-ref | `docs/checkpoint_3_review.md §1 각주` (line 45) ↔ 본 문서 §6 |

---

*End of `docs/devils_advocate_checkpoint_3.md` v1. Phase 3 공식 종결 준비 완료 — Phase 4 진입 GO.*
