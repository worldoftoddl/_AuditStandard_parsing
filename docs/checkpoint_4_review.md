# CHECKPOINT 4 Review

**작성일**: 2026-04-28  
**기준 commit**: `f667641` (`feat(ingest): Phase 4e Qdrant collections`)  
**평가 명령**:

```bash
.venv/bin/python scripts/phase4f_eval.py \
  --cache-path .embed_cache.sqlite \
  --qdrant-url http://localhost:6333
```

## 1. 결론

Phase 4는 **GO**로 판정한다. ISA 기존 컬렉션과 Phase 4e 신규 3개 컬렉션 모두
point count, named vector schema, payload index 기준선을 통과했다. ISQM Mini
Golden은 `Recall@5=1.0`, `MRR@10=0.677083`으로 Phase 4 Plan의 기준
(`Recall@5 >= 0.6` 또는 `MRR@10 >= 0.5`)을 충족했다.

## 2. Qdrant Collection 검증

`scripts/phase4f_eval.py`가 기존 ISA 컬렉션에 Phase 4e에서 추가된
`special_appendix_name` payload index를 idempotent하게 보강한 뒤 검증했다. point는
재작성하지 않았다.

| Collection | Expected | Actual | Status | Payload indexes |
|---|---:|---:|---|---:|
| `audit_standards_회계감사기준_2025` | 8,626 | 8,626 | green / ok | 12 |
| `audit_standards_품질관리기준서_2018` | 400 | 400 | green / ok | 12 |
| `audit_standards_기타인증업무기준_2022` | 1,240 | 1,240 | green / ok | 12 |
| `audit_standards_인증업무개념체계_2022` | 121 | 121 | green / ok | 12 |

총 points는 `10,387`이다. 모든 컬렉션은 named vectors `passage` / `summary`,
`4096d`, `Cosine`, HNSW `m=16`, `ef_construct=200` 기준선을 유지한다.

운영 상태: Docker 컨테이너 `audit_standards_qdrant`는 실행 중이며
`docker stats --no-stream` 기준 메모리 사용량은 `96.63MiB / 7.623GiB`였다. 단,
현재 컨테이너는 compose 소유가 아니어서 `docker compose ps`에는 표시되지 않는다.

## 3. ISQM Mini Golden

Dataset: `tests/fixtures/isqm_mini_golden_dataset.jsonl`  
Output: `output/phase4_mini_golden_results.json` (gitignored)

| Metric | Result | Threshold | 판정 |
|---|---:|---:|---|
| Seed count | 8 | 5-10 | PASS |
| Recall@5 | 1.000000 | 0.600000 | PASS |
| MRR@10 | 0.677083 | 0.500000 | PASS |
| `ko_en` Recall@5 | 1.000000 | 0.400000 | PASS |

카테고리별 Recall@5도 모두 `1.0`이다:
`A.leadership`, `B.system_design`, `B.acceptance`, `C.monitoring`,
`D.engagement_review`, `E.lang_mix`.

4개 collection smoke query도 summary top-k에서 대상 standard를 잡고 passage top-k로
전개됐다. 예: ISA query는 `ISA-540`, ISQM query는 `ISQM-1`, ASSR query는
`ASSR-3000`, FRMK query는 `FRMK-1`로 stage 1이 수렴했다.

## 4. C-P2-1 재평가 결과

CP3에서 C-P2-1은 theoretical upper bound 기준 `trimmed mean 42.64%`로 보고됐지만,
Phase 4의 의무 판정은 실현 빈도 기준이다.

공식:

```text
realized_annual_cache_invalidation
  = (Σ per-reparse chunk_affected_ratio) × (365 / observation_window_days)
```

Phase 4 관측값:

| 항목 | 값 |
|---|---:|
| Observation window | 2026-04-22 ~ 2026-04-28, 6 days |
| Source DOCX revision events | 0 |
| Reparse events with source insertion drift | 0 |
| 4e `payload_drift_count` total | 0 |
| `chunks_with_id_change / total_chunks` | 0 / 10,387 |
| Realized annual cache invalidation | 0.0% |

판정: **v1.2 auto-trigger 미발동**. `{kind}#sha1-content` fallback 전환은 Phase 5
필수 작업이 아니다. 다만 외부 원본 DOCX 개정이 반복될 경우 같은 공식을 다시 적용한다.

## 5. §9.5 추가 Split Census

Phase 4 Plan은 ISA-540 등 ISA-1200 외 split 사례 1건 이상 재측정을 요구했다. 최종
JSON 43개를 전수 조사한 결과 `chunk_of > 1` 또는 `part_of != null`인 chunk는 3건뿐이며,
모두 기존 CP3 대상인 `ISA-1200:appendix:d3ec59bd:table#11079` 계열이다.

| Standard | Split chunks |
|---|---:|
| `ISA-1200` | 3 |
| `ISA-540` | 0 |
| Other ISA / ISQM / ASSR / FRMK | 0 |

따라서 ISA-540 추가 header-bias 실험은 적용 대상이 없고, CP3의 §9.5 PASS 판정을
확장 유지한다. Header suppression v1.2 bump는 필요 없다.

## 6. 잔여 리스크

- ISQM/ASSR JSON은 `section=null` 비율이 100%다. 검색 품질은 통과했지만 section 기반
  필터링 품질은 Phase 5에서 개선 후보로 남긴다.
- Qdrant 컨테이너가 compose 소유가 아니므로 Snapshot/Backup 작업 전 운영 정리가 필요하다.
- `output/phase4_*.json`은 gitignored 산출물이다. 재현은 `scripts/phase4f_eval.py`로 수행한다.

