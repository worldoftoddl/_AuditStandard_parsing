# Phase 4 Report

**기간**: 2026-04-22 ~ 2026-04-28  
**상태**: 완료  
**기준 commit**: `f667641`

## 1. Scope

Phase 4의 목표는 Phase 0-3 ISA 파이프라인을 ISA 외 3개 기준서로 확장하는 것이었다.

| Standard | JSON chunks | Qdrant collection | Points |
|---|---:|---|---:|
| ISA 36종 | 8,590 | `audit_standards_회계감사기준_2025` | 8,626 |
| `ISQM-1` | 399 | `audit_standards_품질관리기준서_2018` | 400 |
| `ASSR-3000` | 1,239 | `audit_standards_기타인증업무기준_2022` | 1,240 |
| `FRMK-1` | 120 | `audit_standards_인증업무개념체계_2022` | 121 |

총 Qdrant points는 `10,387`이다.

## 2. 구현 결과

완료된 주요 변경:

- StandardSpec 기반으로 `ISA`, `ISQM`, `ASSR`, `FRMK` standard id와 parser dispatch를 확장했다.
- schema `1.2.0`에서 `ISQM-\d{1,2}`, `ASSR-\d{3,4}`, `FRMK-\d` 패턴과
  `special_appendix_name`을 반영했다.
- 3개 non-ISA DOCX를 Markdown과 JSON으로 변환하고 Qdrant 3개 collection에 적재했다.
- FRMK table row parser를 보강해 `FRMK-1`을 120 chunks + summary 1 point로 안정화했다.
- Phase 4f 평가 스크립트 `scripts/phase4f_eval.py`와
  `tests/fixtures/isqm_mini_golden_dataset.jsonl`을 추가했다.

## 3. 검증 결과

Phase 4e 적재:

```text
ISQM-1: expected=400, upserted=400, verified=True
ASSR-3000: expected=1240, upserted=1240, verified=True
FRMK-1: expected=121, upserted=121, verified=True
```

Phase 4f 검색 평가:

```text
Phase 4f Mini Golden: recall_at_5=1.0 mrr_at_10=0.677083 seeds=8
```

4개 collection 모두 `4096d Cosine` named vectors와 12개 payload index 기준선을 통과했다.
2-stage smoke query도 각 collection에서 summary → passage 경로로 동작했다.

## 4. Go / No-Go

판정: **GO to Phase 5**.

Phase 5 우선순위:

1. Snapshot/Backup/DR 자동화와 compose 소유 컨테이너 정리.
2. HNSW 설정 외부화 및 운영 설정 문서화.
3. ISQM/ASSR `section` metadata 개선.
4. 원본 DOCX revision이 발생할 때 C-P2-1 realized drift 공식을 재적용.

