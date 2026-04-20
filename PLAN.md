# PLAN — 회계감사기준 → Qdrant 벡터 DB 파이프라인

**프로젝트**: `/home/shin/Project/_AuditStandard_parsing/`
**작성일**: 2026-04-20
**참조 아키텍처**: `/home/shin/Project/_IFRS_parsing/`
**실행 방식**: Claude Code Agent Teams (실험 기능, v2.1.32+)

---

## 1. 목표

`_IFRS_parsing` 의 2-stage 설계를 계승하되 3가지 차별화된 파이프라인 구축:

- **차이 1**: pgvector → **Qdrant**
- **차이 2**: 중간 산출물을 `docx → md → **json** → Qdrant` 로 명시적 4단계화
- **차이 3**: `raw/` 내 파일별 **별도 Qdrant collection** (임베딩 공간 분리)

### 대상 문서

| 우선순위 | 파일 | 용도 |
|---|---|---|
| 1차 (이번 세션) | `raw/0. 회계감사기준 전문(2025 개정).docx` (1.6MB) | KICPA ISA 전문, 메인 타겟 |
| 2차 | `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` | ISQM 1 |
| 3차 | `raw/역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)_전문(개정개요 포함).docx` | 기타 인증업무 |
| 4차 | `raw/인증업무개념체계(2022년 개정)_전문.docx` | 인증업무 개념체계 |

각 파일 → 별도 collection: `audit_standards_회계감사기준_2025`, `audit_standards_품질관리기준서_2018`, 등

---

## 2. 사용자 결정사항

| # | 항목 | 결정 |
|---|---|---|
| 1 | Agent Teams 전략 | **전면 사용** (Phase 0~4 전부). 각 팀원이 초기 의도·컨텍스트 유지. 토큰 상한 도달 시 해당 Phase 에서 중단 |
| 2 | JSON 중간 단계 용도 | **a+b+c 모두** — ① 사람 검수 ② 타 시스템 연계 (스키마 문서화 필수) ③ 재임베딩 캐시 (embedding 필드 nullable) |
| 3 | Qdrant 구조 | **파일별 별도 collection**. 사유: 문서 간 권위 구조·어휘·문단번호 체계가 달라 임베딩 공간을 격리해야 검색 품질 보장. 교차 문서 검색은 현재 요구사항 아님 (CHECKPOINT 0 재확인, 2026-04-20) |
| 4 | 이번 세션 범위 | Phase 0 + Phase 1 착수. 토큰 제한 도달 시 중단 |
| 5 | 벡터 DB: pgvector → Qdrant | **Qdrant 채택**. 사유: ① Solar 4096d HNSW 지원 (pgvector 0.6 은 IVFFlat 우회 필요, 0.7+ 는 HNSW 확장됐으나 운영 리스크), ② named vectors 로 `passage`·`summary` 분리 내장 지원, ③ payload filter 로 standard_no·section·authority 조합 인덱싱 우수, ④ IFRS 프로젝트와 DB 인프라 분리 (장애 격리). 결정일: 2026-04-20 CHECKPOINT 0 |

### JSON 스키마 요구사항 (결정 2 반영)

- `schema_version` 필드 — 외부 연계 시 호환성 관리
- `embedding: Optional[List[float]]` — null 허용 → 재임베딩 가능
- `embedded_at: Optional[datetime]`, `embedding_model: Optional[str]` — 캐시 유효성 판정용
- `docs/json_schema.md` — 외부 시스템 연계용 공식 스펙 (Phase 2 산출물)

---

## 3. 에이전트 팀 구성

### 팀원 4명

| 역할 | 이름 | 책임 | 권한 |
|---|---|---|---|
| 🧭 Scout | `ifrs-convention-scout` | `_IFRS_parsing` 구조·네이밍·포맷 스캔, 재사용 가능한 모듈 식별, 차이점 문서화 | read-only |
| 📖 Domain Reviewer | `audit-standard-domain-reviewer` | ISA 구조 이해, semantic parsing 품질 검수, 샘플 문단 원본 대조 | read-only + `docs/**`·`tests/fixtures/**` 쓰기 |
| 🛠️ Parser Implementer | `parser-implementer` | docx→md, md→json, json→Qdrant 구현 | `src/audit_parser/**` 쓰기, **구현 전 plan approval 필수** |
| 😈 Devil's Advocate | `devils-advocate-critic` | 각 CHECKPOINT 설계 결함·edge case·운영 리스크 반박 | read-only |

### 조율 규칙

- **리더(main session)**: 사용자와 직접 통신, 작업 분배, 팀 정리 (`Clean up the team`)
- **Shared task list**: `~/.claude/tasks/{team}/` 자동 생성
- **Plan approval 모드**: Parser Implementer 는 구현 전 계획 승인 필요 (`Require plan approval before changes`)
- **파일 충돌 방지**: 각 팀원의 소유 디렉토리 명시 (위 표 참조)
- **팀원당 작업 수**: 5–6개 권장
- **CHECKPOINT 마다 팀 정리** (`Clean up the team`) 후 다음 Phase 에서 신규 팀 생성 — 컨텍스트 과중 방지

---

## 4. Phase 분해

### Phase 0 — 부트스트랩 & 병렬 조사 (CHECKPOINT 0)

**Scout** (병렬):
1. `_IFRS_parsing` 코드 컨벤션 스캔 → `docs/ifrs_reference_map.md`
   - 네이밍 규칙, 모듈 분리, IR→MD 렌더링 패턴
   - 2-stage CLI 구조 (`convert.py`·`ingest.py`)
   - pyproject 의존성 전략
2. 재사용 후보 명시: `FormattedRun` 등 IR 데이터클래스

**Domain Reviewer** (병렬):
1. 대상 docx 프로파일링 → `docs/isa_structure_profile.md`
   - 감사기준서 N 개수, 각 기준서 섹션 패턴
   - 문단번호 체계 (`n.` 요구사항 vs `An.` 적용지침)
   - 표·부록·목차 분포

**Implementer**:
1. `pyproject.toml` (python>=3.12, python-docx, lxml, qdrant-client, openai, typer, python-dotenv, tiktoken)
2. 디렉토리 골격: `src/audit_parser/{ir,convert,ingest}/`, `tests/`, `output/` (gitignore)
3. `.env.example`, `docker-compose.yml` (Qdrant), `CLAUDE.md`

**Devil's Advocate 체크질문**:
- 왜 pgvector → Qdrant 변경? (IFRS 와 일관성 깨짐) — 명시 결정 기록 요구
- 파일별 별도 collection vs 단일 collection + tag 운영 부담
- Solar 4096 차원 HNSW 최적성

→ **CHECKPOINT 0**: 사용자 승인 후 Phase 1

---

### Phase 1 — Stage 1: docx → Structured Markdown (CHECKPOINT 1)

#### IR 레이어 (`src/audit_parser/ir/`)

- `types.py` — `RawBlock`, `Block` 데이터클래스
  - 필드: `idx, kind, text, style, paragraph_id, is_application_guidance, parent_paragraph_id, standard_no, standard_title, section, heading_trail, immediate_heading, is_toc, is_header_footer, table_cells`
- `docx_reader.py` — DOCX body iterate (python-docx + lxml), style→kind 매핑, 표 처리, 빈 문단 skip
- `numbering.py` — `word/numbering.xml` 파싱 + 카운터 replay
  - **실측 복잡도 (CHECKPOINT 0, `docs/isa_structure_profile.md`)**: 742개 numId 인스턴스, abstractNumId 5개 계열 `{15, 51, 70, 98, 140}`, 9종 이상 lvlText 패턴
  - **요구사항 ID**: `abstractNumId ∈ {70, 98, 140}`, ilvl=0 → `%1.` decimal (세 계열 동일 구조)
  - **적용지침 ID**: `abstractNumId ∈ {15, 51}`, ilvl=0 → `A%1.` decimal
  - **`numId='0'` 특수 케이스** (303개 문단): 명시적 번호 제거 마커. `None` 과 반드시 구별 — 상태머신에서 "번호 없음 (의도적)" 으로 표시
  - **동적 fallback 필수**: 미지 `abstractNumId`/`lvlText` 조합을 만나면 (a) 경고 로그 (b) `kind='unknown_numbering'` 태깅 (c) 파싱 계속 — hard-coded 화이트리스트 금지
  - Phase 1 착수 전 `docs/numbering_strategy.md` 로 동적 handling 설계 문서 산출
- `structure.py` — 상태머신 `PRE_TOC → TOC → STANDARD_BODY`
  - `감사기준서 N` 경계 탐지, section 매핑 (`서론/목적/용어의 정의/요구사항/적용 및 기타 설명자료`)
  - **ISA-200 특수처리**: `감사인의 전반적인 목적` 섹션 (유일) — section enum 에 `overall_objective` 추가
  - **ISA-1200 특수처리**: 요구사항·적용지침 섹션 없음, `목적` 3회 반복 — section 카운팅 로직 필요
  - heading stack → `heading_trail`, `An` → 부모 `n` 연결
  - 반복 페이지 헤더 필터 — **실측상 body iteration 자동 제외됨** (헤더는 `word/header*.xml` 에만 존재). `_flag_repeating_headers` 는 보험용으로만 유지
  - **`목차` 스타일 764개가 전역 산재** (단순 PRE_TOC→TOC 상태머신만으론 불충분) — `ad` 스타일 블록을 상태 무관하게 is_toc 플래깅하는 2차 규칙 추가

#### 표(Table) 처리 — 1×1 박스 승격 (CHECKPOINT 0 결정)

실측 74개 표 중 **58개(78%) 가 1×1 단일 셀** — 예시·경고·인용 컨테이너용. Phase 1 IR 레이어에서:
- 1×1 단일 셀 표 → `paragraph_body` 로 승격 (heading_trail 보존)
- 2×N 이상 → `kind='table'` 유지, `table_cells` 보존
- ISA-1200 의 66×2 초대형 표 → Phase 2 청킹 시 행별 분할 예외처리

#### Renderer (`src/audit_parser/convert/md_renderer.py`)

출력 형식 (`_IFRS_parsing` 동형 YAML frontmatter + HTML 주석):

```markdown
---
standard_id: "ISA-200"
standard_no: "200"
standard_title: "독립된 감사인의 전반적인 목적과 감사기준에 따른 감사의 수행"
source_file: "0. 회계감사기준 전문(2025 개정).docx"
schema_version: "1.0"
---

# 감사기준서 200

## 서론
<!-- section: intro | authority: 1 -->

1	본 감사기준서는...
<!-- para: 1 | kind: requirement -->

## 적용 및 기타 설명자료

A1	문단 1의 적용지침...
<!-- para: A1 | kind: application_guidance | parent: 1 -->
```

#### CLI

```bash
audit-parser convert raw/0.\ 회계감사기준\ 전문\(2025\ 개정\).docx --out output/md/
```

**출력**: `output/md/ISA-<nnn>.md` + `output/md/00_전문.md`

#### Domain Reviewer 검수 (CHECKPOINT 1)

- 랜덤 샘플 20개 문단을 DOCX 원본과 대조
- heading_trail 완전성 검증
- `An` → `n` 매핑 정확도
- section enum 매핑 정확도
- `unknown*` kind 비율 < 5%

---

### Phase 2 — Stage 2a: MD → JSON (CHECKPOINT 2)

#### 모듈 (`src/audit_parser/ingest/`)

- `md_parser.py` — MD → `ParsedStandard`
  - `StandardRecord`, `ChunkRecord[]`, `StandardSummary`, `ParagraphLink[]`
- `chunk_splitter.py` — Upstage 4000 토큰 초과 청크 분할 (heading_trail 재사용, 문단 경계 우선)

#### JSON 스키마 (제안)

```json
{
  "schema_version": "1.0",
  "standard": {
    "standard_id": "ISA-200",
    "standard_no": "200",
    "standard_title": "...",
    "source_file": "0. 회계감사기준 전문(2025 개정).docx",
    "authority_base": 1
  },
  "summary": {
    "scope_text": "...",
    "scope_markdown": "...",
    "definitions_text": "...",
    "definitions_markdown": "...",
    "embedding": null,
    "embedded_at": null,
    "embedding_model": null
  },
  "chunks": [
    {
      "chunk_id": "ISA-200:req:1",
      "paragraph_id": "1",
      "kind": "requirement",
      "section": "requirements",
      "heading_trail": ["감사기준서 200", "요구사항"],
      "content_text": "...",
      "content_markdown": "...",
      "authority": 1,
      "parent_paragraph_id": null,
      "token_estimate": 312,
      "embedding": null,
      "embedded_at": null,
      "embedding_model": null
    }
  ],
  "paragraph_links": [
    {"source": "ISA-200:app:A1", "target": "1", "link_type": "guidance_of"}
  ]
}
```

#### 산출물

- `output/json/ISA-<nnn>.json`
- `docs/json_schema.md` — 외부 연계 공식 스펙

**Devil's Advocate**:
- JSON 스키마 버전 전략 (SemVer? MAJOR 변경 시 migration)
- embedding null ↔ non-null 변환 시 idempotency 보장

---

### Phase 3 — Stage 2b: JSON → Qdrant (CHECKPOINT 3)

#### 모듈

- `embedder.py` — Upstage Solar passage/query 분리, `.embed_cache.sqlite` 캐시
- `qdrant_writer.py`
  - Collection 생성/업서트
  - Named vectors: `passage` (본문) + `summary` (기준서 식별)
  - HNSW: `m=16, ef_construct=200`
  - payload: 모든 메타데이터 (standard_no, section, paragraph_id, authority, heading_trail, ...)

#### Collection 네이밍

| 원본 | Collection |
|---|---|
| `0. 회계감사기준 전문(2025 개정).docx` | `audit_standards_회계감사기준_2025` |
| `3. 품질관리기준서1(2018년 제정)_국어전문.docx` | `audit_standards_품질관리기준서_2018` |
| `역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)...` | `audit_standards_기타인증업무기준_2022` |
| `인증업무개념체계(2022년 개정)_전문.docx` | `audit_standards_인증업무개념체계_2022` |

#### CLI

```bash
audit-parser ingest output/json/ --collection audit_standards_회계감사기준_2025
audit-parser ingest --single output/json/ISA-200.json --collection audit_standards_회계감사기준_2025
```

#### 운영

- `docker-compose.yml` Qdrant 로컬 (6333/6334)
- `search_test.ipynb` — 2단계 검색 데모

**Devil's Advocate**:
- 재적재 idempotency (chunk_id upsert → payload 변경 시 주의)
- 4096차원 HNSW 메모리 실측, 필요 시 scalar quantization

---

### Phase 4 — 나머지 3개 docx 일반화 (CHECKPOINT 4)

- Scout 재투입: 파일별 style_map 차이 조사
- 회귀 테스트 fixture 구축 (`tests/fixtures/`)
- `pytest` + `ruff` + `mypy` 통합
- 모든 collection 적재 완료

---

## 5. 리스크 매트릭스

| 심각도 | 리스크 | 완화 |
|---|---|---|
| 🔴 HIGH | ISA 문단번호 `numbering.xml` 복잡도 — 742 numId, 9종+ 패턴, numId=0 특수 케이스 303건 (CHECKPOINT 0 실측) | `numbering.py` 동적 fallback 필수 (미지 패턴 `unknown_numbering` 태깅 후 파싱 계속), Phase 1 착수 전 `docs/numbering_strategy.md` 설계, 20개 수동 검증 |
| 🔴 HIGH | ISA-200·ISA-1200 섹션 구조 예외 | 상태머신에 특수 분기 추가, section enum 확장 (`overall_objective`) |
| 🔴 HIGH | Qdrant 4096차원 HNSW 메모리 부담 | 로컬 실측, 필요 시 scalar quantization |
| 🟡 MED | Upstage 4000 토큰 상한 초과 청크 | `chunk_splitter` — heading_trail 재사용, 문단 경계 우선 |
| 🟡 MED | 4개 docx 간 style_map 상이 | Phase 4 에서 파일별 프로파일링 후 병합 |
| 🟡 MED | 표(Table) 청킹 전략 미정 | Phase 2 전 결정 (단일 청크 vs 행별) |
| 🟡 MED | Agent Teams 토큰 비용 단일 세션 3~5배 | 각 CHECKPOINT 에서 팀 정리, 필요 시 Phase 단위 중단 |
| 🟡 MED | Agent Teams 세션 재개 제약 (`/resume` 미지원) | Phase 단위로 완결, 중간 산출물 파일로 저장 |
| 🟢 LOW | `.env` API 키 노출 | `.gitignore` 확인됨 (`.env` 포함) |

---

## 6. 복잡도 & 토큰 예산

| Phase | 복잡도 | 예상 토큰 (팀 전체) |
|---|---|---|
| Phase 0 | LOW | 4 teammates × 30k ≈ 120k |
| Phase 1 | HIGH (numbering.xml) | 200–300k |
| Phase 2 | MEDIUM | 100–150k |
| Phase 3 | MEDIUM | 100–150k |
| Phase 4 | MED-HIGH | 150–200k |
| **합계** | HIGH | ~700k–900k |

---

## 7. 이번 세션 실행 계획 (세션 재시작 후)

### 7.1 전제조건 상태

- ✅ Claude Code `2.1.114` (≥ 2.1.32)
- ✅ `~/.claude/settings.json` 에 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 추가 완료
- ⏳ Claude Code 재시작 필요

### 7.2 재시작 후 실행 순서

1. 이 저장소(`/home/shin/Project/_AuditStandard_parsing/`) 에서 Claude Code 기동
2. 팀 소환 프롬프트 (아래 §8) 를 리더에게 전달
3. Phase 0 실행 → CHECKPOINT 0 사용자 승인 → 팀 정리 → Phase 1 신규 팀 소환
4. 토큰 한도 도달 또는 Phase 1 완료 시 중단

---

## 8. 팀 소환 프롬프트 (재시작 후 이것을 붙여넣기)

```
PLAN.md 를 읽어 전체 맥락을 파악한 뒤, Phase 0 를 실행할 Agent Team 을
생성해줘. 팀원 4명:

1. ifrs-convention-scout — read-only. `/home/shin/Project/_IFRS_parsing/`
   코드를 스캔해 네이밍 규칙·모듈 분리·IR→MD 렌더링 패턴·2-stage CLI
   구조·pyproject 의존성 전략을 정리해 `docs/ifrs_reference_map.md`
   파일로 산출. 재사용 가능한 IR 데이터클래스(FormattedRun 등)도 명시.

2. audit-standard-domain-reviewer — read-only + docs/·tests/fixtures/
   쓰기 가능. `raw/0. 회계감사기준 전문(2025 개정).docx` 를 프로파일링.
   감사기준서 N 개수, 각 기준서 섹션 패턴, 문단번호 체계(`n.` 요구사항
   vs `An.` 적용지침), 표·부록·목차 분포를 `docs/isa_structure_profile.md`
   로 산출. Phase 1 의 numbering.xml 파싱에 쓸 numId/ilvl/lvlText 3~5개
   샘플을 뽑아둬.

3. parser-implementer — `src/audit_parser/**` 쓰기. **구현 전 plan
   approval 필수**. pyproject.toml (python>=3.12, python-docx, lxml,
   qdrant-client, openai, typer, python-dotenv, tiktoken), 디렉토리
   골격(src/audit_parser/{ir,convert,ingest}/, tests/, output/),
   .env.example, docker-compose.yml (Qdrant 공식 이미지), CLAUDE.md
   를 작성. CLAUDE.md 는 PLAN.md 의 요약 + 개발 시 중요 포인트.

4. devils-advocate-critic — read-only. 세 팀원의 산출물을 모두 읽고,
   설계 결함·edge case·운영 리스크를 공격적으로 반박. 최소 5가지 비판
   제기. 특히 다음 항목 검증: (a) 왜 pgvector → Qdrant 변경이 정당한가
   (b) 파일별 별도 collection vs 단일 collection+tag trade-off (c)
   Solar 4096 차원 HNSW 최적성.

팀원 간 서로 도전·토론 허용. 모든 팀원이 유휴 상태가 되면 리더가 결과를
종합해 나(사용자)에게 CHECKPOINT 0 보고. 내 승인 전에는 Phase 1 로
진행하지 말 것. 모델은 전부 Sonnet 사용.

작업 소유권 충돌 방지: Scout 은 /home/shin/Project/_IFRS_parsing/ 만
읽음. Domain Reviewer 는 raw/ 와 docs/·tests/fixtures/. Implementer 는
src/·루트 설정파일. 서로 같은 파일을 편집하지 않게 할 것.
```

---

## 9. 향후 Phase 팀 소환 템플릿

각 Phase 시작 시 위 템플릿 구조를 재사용하되 팀원 프롬프트를 해당 Phase 작업으로 교체. CHECKPOINT 승인 후 반드시 `Clean up the team` 으로 정리.

---

## 10. 변경 이력

| 일자 | 변경 |
|---|---|
| 2026-04-20 | 초안 작성. 사용자 결정사항 1~4 반영 |
| 2026-04-20 | Phase 0 CHECKPOINT 0 반영: ① 결정 #5 Qdrant 전환 근거 명시, ② 결정 #3 파일별 collection 재확인, ③ Phase 1 numbering 동적 fallback 요구사항 추가 (742 numId, 9+ 패턴 실측), ④ ISA-200·ISA-1200 섹션 예외처리 명시, ⑤ 1×1 박스 표 paragraph 승격 결정, ⑥ 목차 스타일 764개 산재 규칙 추가, ⑦ 리스크 매트릭스 numbering 항목 업데이트 + ISA-200/1200 예외 리스크 추가 |

---

## 11. CHECKPOINT 0 기록 (2026-04-20)

### Phase 0 산출물

- `docs/ifrs_reference_map.md` (472줄) — IFRS 컨벤션 분석, Scout
- `docs/isa_structure_profile.md` (466줄) — ISA 구조 프로파일, Domain Reviewer
- `tests/fixtures/isa_profile_samples.json` — numbering.xml 샘플 raw 데이터
- `docs/devils_advocate_checkpoint_0.md` (377줄) — 8개 비판, Go/No-Go
- `pyproject.toml` + 13개 부트스트랩 파일 — Implementer

### 검증 결과

- `import audit_parser` → `v0.1.0` 통과
- `.gitignore`: `output/`, `.embed_cache.sqlite`, `qdrant_storage/`, `tmp/` 포함. `CLAUDE.md` 제거 (커밋 대상)

### Devil's Advocate 지적 처리 현황

| ID | 지적 | 처리 |
|---|---|---|
| B1 | `.gitignore` 에 `output/` 등 누락 | **False positive** — Implementer 가 이미 추가함. DA 가 구 버전 참조 |
| B2 | `CLAUDE.md` gitignore 에 있음 | **False positive** — Implementer 가 제거함 |
| S1 | pgvector→Qdrant 근거 PLAN.md 미기재 | **해결** — 결정 #5 로 추가 |
| S2 | 파일별 collection 교차 검색 trade-off | **유지** — 결정 #3 에 사유 명시, 교차 검색 요구 없음 |
| S3 | numbering.xml fallback 미설계 | **해결** — Phase 1 numbering.py 동적 fallback 요구사항 추가 |
| S4 | 1×1 박스 58개 처리 | **해결** — paragraph 승격 규칙 명시 |

### Go/No-Go 판정

**GO** — Phase 1 진입 승인. CHECKPOINT 0 팀 정리(`TeamDelete`) 후 신규 팀 소환.

