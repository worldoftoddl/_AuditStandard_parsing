# Anthropic RAG Pipeline Usage

이 문서는 Qdrant에 적재된 감사기준 데이터베이스를 Anthropic LLM으로 테스트하는 방법을 정리한다. 실행 notebook은 `notebooks/phase4_llm_rag_test.ipynb`이다.

## 1. 전제 조건

- Qdrant가 `http://localhost:6333`에서 실행 중이어야 한다.
- Phase 4e 적재가 완료되어 4개 collection이 존재해야 한다.
- `.env`에 Upstage query embedding key와 Anthropic key가 있어야 한다.

기대 collection:

| Collection | Points |
|---|---:|
| `audit_standards_회계감사기준_2025` | 8,626 |
| `audit_standards_품질관리기준서_2018` | 400 |
| `audit_standards_기타인증업무기준_2022` | 1,240 |
| `audit_standards_인증업무개념체계_2022` | 121 |

## 2. 환경 설정

`.env`에 다음 값을 설정한다.

```env
UPSTAGE_API_KEY=up_...
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

`ANTHROPIC_MODEL`에는 API key가 아니라 모델 ID를 넣어야 한다. API key가 traceback 등에 노출되면 즉시 Anthropic Console에서 폐기하고 재발급한다.

## 3. 실행 순서

1. 가상환경을 활성화한다.

```bash
source .venv/bin/activate
```

2. Qdrant 상태를 확인한다.

```bash
curl http://localhost:6333/healthz
```

3. notebook을 연다.

```bash
jupyter lab notebooks/phase4_llm_rag_test.ipynb
```

4. `Kernel > Restart Kernel and Run All Cells`로 처음부터 실행한다.

이전 버전 notebook을 실행했던 kernel에는 old provider 함수나 잘못된 환경변수가 남아 있을 수 있으므로, 오류 수정 후에는 반드시 kernel을 재시작한다.

## 4. Pipeline 단계

Notebook은 다음 순서로 동작한다.

1. 환경 설정: `.env`, Qdrant client, `Embedder`를 초기화한다.
2. Qdrant Sanity Check: 4개 collection의 point count, summary count, named vectors, payload index를 검증한다.
3. Anthropic Model Check: `/v1/models/{ANTHROPIC_MODEL}`로 모델 접근 가능 여부를 확인한다.
4. 기준서 식별: query를 `embedding-query`로 임베딩하고 각 collection의 `summary` vector를 검색한다.
5. Passage 검색: 후보 `standard_id` 안에서 `passage` vector top-k를 검색한다.
6. Context Builder: 검색 결과를 chunk citation이 포함된 LLM context로 구성한다.
7. Anthropic 답변: Messages API로 답변을 생성하고 근거 chunk_id를 표시한다.
8. Batch Smoke Test: 기본 테스트 쿼리 4개를 검색 중심으로 반복 실행한다.
9. 결과 저장: `output/phase4_llm_rag_results.json`에 실행 결과를 저장한다.

## 5. 기본 테스트 쿼리

Notebook 기본 쿼리:

- `품질관리시스템의 궁극적인 책임은 누구에게 있는가?`
- `회계추정치 감사에서 경영진 추정치를 어떻게 평가해야 하는가?`
- `제한적 확신업무 결론은 어떻게 표현되는가?`
- `인증업무에서 세 당사자의 역할은 무엇인가?`

개별 테스트는 `rag_pipeline("질문")`으로 실행한다.

```python
result = rag_pipeline("감사인이 계속기업 가정을 평가할 때 고려할 사항은?")
```

## 6. 비용 제어

기본 batch smoke test는 `RUN_LLM_BATCH = False`로 설정되어 있어 LLM 호출 없이 검색과 context 구성만 검증한다.

여러 쿼리에 대해 Anthropic 답변까지 생성하려면 notebook의 batch cell에서 명시적으로 변경한다.

```python
RUN_LLM_BATCH = True
```

단일 쿼리의 LLM 호출 여부는 `.env`의 `ANTHROPIC_API_KEY` 존재 여부와 `RUN_LLM` 값으로 결정된다.

## 7. Troubleshooting

`model: sk-ant-...` 오류:

- `ANTHROPIC_MODEL`에 API key를 넣은 상태다.
- `.env`를 `ANTHROPIC_API_KEY=sk-ant-...`, `ANTHROPIC_MODEL=claude-sonnet-4-20250514`로 고친다.
- kernel을 재시작한다.

`404 Not Found`:

- 모델 ID가 잘못됐거나 base URL이 Anthropic API가 아니다.
- `ANTHROPIC_MODEL=claude-sonnet-4-20250514`로 되돌리고 model check cell을 먼저 실행한다.

`ANTHROPIC_API_KEY 미설정`:

- `.env`에 key가 없거나 notebook kernel이 `.env` 수정 전 상태다.
- `.env` 저장 후 kernel을 재시작한다.

Qdrant count assertion 실패:

- Phase 4e 적재가 누락되었거나 다른 Qdrant 인스턴스를 보고 있다.
- `QDRANT_URL`을 확인하고 `audit-parser phase4e --cache-path .embed_cache.sqlite --qdrant-url http://localhost:6333`를 재실행한다.

## 8. 산출물

- Notebook: `notebooks/phase4_llm_rag_test.ipynb`
- 실행 결과: `output/phase4_llm_rag_results.json`
- `output/`은 gitignored이므로 실행 결과는 로컬 검증용으로만 사용한다.

