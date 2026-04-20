# CLAUDE.md — 회계감사기준 파싱 파이프라인

> Phase 0 기준 초기본. Scout(`ifrs-convention-scout`)의 `docs/ifrs_reference_map.md` 완성 후 개발 컨벤션 섹션을 업데이트할 것.

---

## 1. 프로젝트 개요

`_IFRS_parsing` 의 2-stage 설계를 계승하되 3가지 차별화된 파이프라인 구축:

- **차이 1**: pgvector → **Qdrant** (파일별 별도 collection, HNSW 인덱스)
- **차이 2**: 중간 산출물을 `docx → md → json → Qdrant` 로 명시적 4단계화
- **차이 3**: `raw/` 내 파일별 **별도 Qdrant collection** (임베딩 공간 분리)

### 대상 문서

| 우선순위 | 파일 | 용도 |
|---|---|---|
| 1차 | `raw/0. 회계감사기준 전문(2025 개정).docx` | KICPA ISA 전문, 메인 타겟 |
| 2차 | `raw/3. 품질관리기준서1(2018년 제정)_국어전문.docx` | ISQM 1 |
| 3차 | `raw/역사적 재무정보...` | 기타 인증업무 |
| 4차 | `raw/인증업무개념체계(2022년 개정)_전문.docx` | 인증업무 개념체계 |

전체 목표 및 설계 결정사항은 **[PLAN.md](./PLAN.md)** 참조.

---

## 2. 저장소 구조

```
_AuditStandard_parsing/
├── PLAN.md                        # 전체 설계 계획 (읽기 전용)
├── CLAUDE.md                      # 이 파일
├── README.md                      # 프로젝트 소개
├── pyproject.toml                 # 패키지 메타데이터 & 의존성
├── docker-compose.yml             # Qdrant 로컬 컨테이너
├── .env.example                   # 환경변수 템플릿 (실제 .env 는 gitignore)
│
├── src/audit_parser/              # 핵심 파이프라인 패키지
│   ├── __init__.py                # __version__ = "0.1.0"
│   ├── cli.py                     # typer CLI 진입점
│   ├── ir/                        # 중간 표현(Intermediate Representation) 레이어
│   │   ├── __init__.py
│   │   ├── types.py               # RawBlock, Block 데이터클래스 (Phase 1)
│   │   ├── docx_reader.py         # DOCX body iterate (Phase 1)
│   │   ├── numbering.py           # word/numbering.xml 파싱 (Phase 1)
│   │   └── structure.py           # 상태머신: PRE_TOC→TOC→STANDARD_BODY (Phase 1)
│   ├── convert/                   # docx → Markdown 렌더러
│   │   ├── __init__.py
│   │   └── md_renderer.py         # YAML frontmatter + HTML 주석 출력 (Phase 1)
│   └── ingest/                    # Markdown → JSON → Qdrant
│       ├── __init__.py
│       ├── md_parser.py           # MD → ParsedStandard (Phase 2)
│       ├── chunk_splitter.py      # 4000 토큰 초과 청크 분할 (Phase 2)
│       ├── embedder.py            # Upstage Solar 임베딩 + SQLite 캐시 (Phase 3)
│       └── qdrant_writer.py       # Collection 생성/업서트 (Phase 3)
│
├── docs/                          # 도메인 지식 문서 (Scout/Reviewer 소유)
│   ├── ifrs_reference_map.md      # Scout 산출물 (작성 중)
│   ├── isa_structure_profile.md   # Domain Reviewer 산출물 (작성 중)
│   ├── json_schema.md             # JSON 중간형식 공식 스펙 (Phase 2 산출물)
│   └── devils_advocate_checkpoint_0.md  # 설계 반박 (Phase 0 산출물)
│
├── tests/
│   ├── __init__.py
│   └── fixtures/                  # 테스트용 샘플 데이터
│
├── output/                        # 파이프라인 산출물 (gitignore)
│   ├── md/                        # output/md/ISA-<nnn>.md
│   └── json/                      # output/json/ISA-<nnn>.json
│
└── raw/                           # 원본 DOCX (gitignore)
```

---

## 3. 빌드 & 실행 커맨드

### 환경 설정

```bash
# Python 3.12+ 필요
python -m venv .venv
source .venv/bin/activate

# 의존성 설치 (uv 권장)
uv sync
# 또는 pip
pip install -e ".[dev]"

# 환경변수 설정
cp .env.example .env
# .env 편집: UPSTAGE_API_KEY, QDRANT_URL 등
```

### Qdrant 로컬 실행

```bash
docker compose up -d
# 확인: http://localhost:6333/dashboard
```

### 파이프라인 실행

```bash
# Phase 1: docx → Markdown
audit-parser convert "raw/0. 회계감사기준 전문(2025 개정).docx" --out output/md/

# Phase 3: JSON → Qdrant
audit-parser ingest output/json/ --collection audit_standards_회계감사기준_2025
audit-parser ingest --single output/json/ISA-200.json --collection audit_standards_회계감사기준_2025
```

### 개발 도구

```bash
# 린팅
ruff check src/ tests/
ruff format src/ tests/

# 타입 검사
mypy src/

# 테스트
pytest
```

---

## 4. 파이프라인 아키텍처 (4단계)

```
Stage 1: docx → Structured Markdown
- python-docx + lxml: DOCX body iterate
- numbering.xml 파싱: numId/ilvl → 문단번호 카운터 replay
- 상태머신: PRE_TOC → TOC → STANDARD_BODY
- 출력: output/md/ISA-<nnn>.md (YAML frontmatter + HTML 주석)

Stage 2a: Structured Markdown → JSON
- md_parser.py: MD → ParsedStandard (StandardRecord + Chunks)
- chunk_splitter.py: Upstage 4000 토큰 초과 시 분할
- JSON 스키마: schema_version, embedding(nullable), 메타데이터
- 출력: output/json/ISA-<nnn>.json

Stage 2b: JSON → Qdrant
- embedder.py: Upstage Solar passage/query, SQLite 캐시
- qdrant_writer.py: Named vectors (passage + summary)
- HNSW: m=16, ef_construct=200

Qdrant Collections
- 파일별 별도 collection (임베딩 공간 분리)
- payload: standard_no, section, paragraph_id, heading_trail
```

---

## 5. Collection 네이밍 규칙

| 원본 DOCX | Qdrant Collection |
|---|---|
| `0. 회계감사기준 전문(2025 개정).docx` | `audit_standards_회계감사기준_2025` |
| `3. 품질관리기준서1(2018년 제정)_국어전문.docx` | `audit_standards_품질관리기준서_2018` |
| `역사적 재무정보에 대한 감사 및 검토 이외의 인증업무기준(2022년 개정)...` | `audit_standards_기타인증업무기준_2022` |
| `인증업무개념체계(2022년 개정)_전문.docx` | `audit_standards_인증업무개념체계_2022` |

패턴: `audit_standards_{문서종류}_{연도}`

---

## 6. 주요 도메인 지식 참조

| 문서 | 상태 | 설명 |
|---|---|---|
| `docs/ifrs_reference_map.md` | **작성 중** (Scout) | IFRS 파이프라인 컨벤션 분석, 재사용 모듈 목록 |
| `docs/isa_structure_profile.md` | **작성 중** (Domain Reviewer) | ISA DOCX 구조 프로파일, numbering.xml 샘플 |
| `docs/json_schema.md` | Phase 2 산출 예정 | JSON 중간형식 공식 스펙 (외부 연계용) |
| `docs/devils_advocate_checkpoint_0.md` | Phase 0 완료 후 | 설계 반박 및 리스크 분석 |

> Scout의 `docs/ifrs_reference_map.md` 완성 후 아래 개발 컨벤션 섹션을 업데이트할 것.

---

## 7. 개발 컨벤션

> 이 섹션은 Scout(`ifrs-convention-scout`)의 `docs/ifrs_reference_map.md` 완성 후 구체화 예정.

현재 확정된 컨벤션:

- **Python**: 3.12+, 타입 힌트 필수 (`mypy --strict`)
- **라인 길이**: 100자 (`ruff`)
- **패키지 구조**: `src/` 레이아웃 (`hatchling` 빌드)
- **IR 데이터클래스**: `src/audit_parser/ir/types.py` 에 집중
- **파일 소유권**:
  - `docs/**`: Scout / Domain Reviewer 전용
  - `src/audit_parser/**`, 루트 설정 파일: Parser Implementer 전용
  - `raw/**`: 읽기 전용 (gitignore)

---

## 8. Agent Teams 실행 지침

Phase 0 팀 구성 (PLAN.md §3, §8 참조):

| 역할 | 에이전트 | 담당 |
|---|---|---|
| Scout | `ifrs-convention-scout` | `_IFRS_parsing` 스캔 → `docs/ifrs_reference_map.md` |
| Domain Reviewer | `audit-standard-domain-reviewer` | ISA DOCX 프로파일링 → `docs/isa_structure_profile.md` |
| Parser Implementer | `parser-implementer` | 프로젝트 골격 생성 (이 파일 포함) |
| Devil's Advocate | `devils-advocate-critic` | 설계 반박 → `docs/devils_advocate_checkpoint_0.md` |

### 실행 원칙

1. **CHECKPOINT 마다** `Clean up the team` 으로 팀 정리 후 다음 Phase 신규 팀 생성
2. **Parser Implementer**: 구현 전 `team-lead`에게 plan approval 필수
3. **파일 충돌 방지**: 각 팀원의 소유 경로 엄수 (위 표 참조)
4. **토큰 예산**: Phase 0 전체 ~120k 토큰 (4 teammates × 30k)
5. **중간 산출물**: 모든 결과를 파일로 저장 (세션 재개 불가 대비)

### Phase 진행 순서

```
Phase 0 (현재) → CHECKPOINT 0 사용자 승인 → Clean up team
→ Phase 1 신규 팀 → CHECKPOINT 1 → ...
```

자세한 실행 계획: **[PLAN.md §7~9](./PLAN.md)**
