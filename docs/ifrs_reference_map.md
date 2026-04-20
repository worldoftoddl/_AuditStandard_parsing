# IFRS 파이프라인 컨벤션 참조 맵

**작성일**: 2026-04-20  
**작성자**: ifrs-convention-scout  
**참조 소스**: `/home/shin/Project/_IFRS_parsing/` (read-only)  
**목적**: AuditStandard 파이프라인 설계 시 K-IFRS 파이프라인의 컨벤션·패턴·이식 가능 요소를 명확히 기술

---

## 1. 네이밍 규칙

### 1.1 모듈명

| 계층 | IFRS 모듈명 | 설명 |
|------|------------|------|
| Stage 1 | `converter/` | docx → IR → MD |
| Stage 2 | `ingester/` | MD → 청크 → DB |
| CLI | `convert.py`, `ingest.py` | 루트 수준 스크립트 |

AuditStandard 에서도 동일 레이아웃 유지 권장: `src/audit_parser/convert/`, `src/audit_parser/ingest/`

### 1.2 IR 데이터클래스명 (`converter/models.py`)

| 클래스 | 역할 |
|--------|------|
| `FormattedRun` | bold/italic 서식이 적용된 텍스트 조각 |
| `MetaInfo` | 파일명 기반 기준서 메타데이터 |
| `SectionHeader` | 섹션 헤더 (1x1 표에서 추출, level 2/3) |
| `AuthorityMarker` | 권위 선언 문구 (`is_authoritative: bool`) |
| `NumberedParagraph` | 번호 있는 문단 (`para_number`, `runs`, `sub_items`) |
| `ContinuationText` | 번호 없는 연속 텍스트 |
| `ContentTable` | 내용 표 (`headers`, `rows`) |
| `SubItem` | 호/목 (⑴⑵⑶, ㈎㈏㈐) |
| `Footnote` | 각주 (`id`, `content`, `runs`) |

타입 유니온: `IRElement = MetaInfo | SectionHeader | AuthorityMarker | NumberedParagraph | ContinuationText | ContentTable`  
주의: `SubItem`은 `IRElement` 아님 — 항상 `NumberedParagraph.sub_items`의 자식으로만 존재

### 1.3 Stage 2 데이터클래스명 (`ingester/models.py`)

| 클래스 | 역할 |
|--------|------|
| `StandardRecord` | 기준서 메타데이터 (프론트매터에서 추출) |
| `ChunkRecord` | 검색 단위 (`chunk_id`, `component`, `authority`, `content_text`, `content_markdown`) |
| `FootnoteRecord` | 각주 |
| `ParagraphLink` | BC/IE → 본문 문단 참조 링크 |
| `StandardSummary` | 기준서 식별용 요약 (목적+적용범위+정의) |

### 1.4 함수 접두사 관행

| 접두사 | 용도 | 예시 |
|--------|------|------|
| `_extract_` | 내부 추출 헬퍼 | `_extract_footnote_refs()`, `_extract_heading_refs()` |
| `_parse_` | 구조 파싱 | `_parse_footnotes()`, `_parse_frontmatter()` |
| `_classify_` | 분류 결정 | `_classify_paragraph()`, `_classify_table()` |
| `_detect_` | 패턴 감지 | `_detect_section_from_text()` |
| `_is_` | 불리언 술어 | `_is_copyright()`, `_is_revision_table()`, `_is_fully_bold()` |
| `_check_` | 조건부 반환 | `_check_bold()`, `_check_authority_marker()` |
| `_make_` | 팩토리 | `_make_meta_from_filename()`, `_make_chunk_id()`, `_make_standard_record()` |
| `_strip_` | 변환/제거 | `_strip_markdown()`, `_strip_number_from_runs()` |
| `_build_` / `build_` | 집계 생성 | `build_summary()` |
| `upsert_` | DB 적재 | `upsert_standard()`, `upsert_chunks()`, `upsert_links()` |
| `parse_` | 공개 파서 | `parse_docx()`, `parse_markdown_file()` |
| `render_` | 렌더링 | `render_markdown()` |
| `embed_` | 임베딩 | `embed_batch()`, `embed_single()`, `embed_query()` |
| `process_` | 파이프라인 처리 | `process_single()`, `process_all()` |

### 1.5 CLI 명령 flag 네이밍 (argparse)

**`convert.py`**:
- `--single <path>` — 단일 DOCX 파일 처리
- `--dry-run` — 파싱+통계만 (파일 생성 안 함)
- `--docx-dir <path>` — DOCX 소스 디렉토리 (기본값: `IFRS_docx/`)
- `--output-dir <path>` — 출력 디렉토리 (기본값: `output/md/`)

**`ingest.py`**:
- `--export-json` — 청크를 기준서별 JSON으로 내보내기 (검수용)
- `--parse-only` — 파싱 통계만 (DB 접속 안 함)
- `--skip-embedding` — DB 삽입만 (임베딩 NULL)
- `--single <id>` — 단일 기준서 처리 (예: `'K-IFRS 1115'`)
- `--md-dir <path>` — 마크다운 소스 디렉토리

---

## 2. 2-stage CLI 구조 해부

### 2.1 CLI 설계

- **라이브러리**: `argparse` (typer 미사용)
- **진입점**: `if __name__ == "__main__":` 블록
- **패키징**: `pyproject.toml`에 scripts entry point 없음 — `python convert.py` 직접 실행
- **실행 방식**: `uv run python convert.py` 또는 `python convert.py`

AuditStandard 에서는 `typer` 도입 + `pyproject.toml` scripts (`audit-parser convert`, `audit-parser ingest`) 방식으로 개선 예정 (PLAN.md §4 Phase 1)

### 2.2 파일 루프 패턴

```python
# convert.py 패턴
files = sorted(docx_dir.rglob("*.docx"))  # 재귀 glob
for f in files:
    try:
        stats = process_single(f, output_dir, dry_run=dry_run)
    except Exception as e:
        traceback.print_exc()
        failures.append({"file": f.name, "error": str(e)})
```

- 실패 시 다음 파일 계속 처리 (`try/except` + `failures` 목록 누적)
- 완료 후 전체 요약 출력

### 2.3 플래그 의미 정리

| 플래그 | 목적 | AuditStandard 유지/변경 |
|--------|------|------------------------|
| `--dry-run` | 파싱+통계만, 파일 생성 없음 | **유지** |
| `--single` | 파일 1개 또는 기준서 1개 처리 | **유지** |
| `--parse-only` | DB 없이 파싱 통계만 | **유지** |
| `--skip-embedding` | 임베딩 스킵, DB에 NULL로 삽입 | **유지** (JSON 캐시 설계에서 더 중요) |
| `--export-json` | 검수용 JSON 내보내기 | **변경**: AuditStandard는 JSON이 1차 산출물이므로 별도 플래그 불필요 |
| `--md-dir` | 마크다운 소스 경로 | **유지** |
| `--collection` | (없음) | **추가 필요**: Qdrant collection 이름 지정 |

---

## 3. IR→MD 렌더링 패턴

### 3.1 `converter/models.py` 데이터클래스 역할

섹션 1.2 참조. 핵심 설계 원칙:
- `FormattedRun`이 bold/italic을 run 단위로 보존 → MD에서 `**bold**`, `*italic*`으로 렌더링
- `SubItem`은 두 수준 중첩 가능 (`sub_sub_items`)
- 각주는 `footnote_refs: list[int]`로 ID만 참조, 실제 내용은 별도 `dict[int, Footnote]`

### 3.2 `converter/docx_parser.py`: docx → IR 변환 흐름

```
docx 파일
  → _open_docx()         # zipfile 열기 + 백슬래시 경로 수정 + XML 정제
  → _parse_footnotes()   # word/footnotes.xml → dict[int, Footnote]
  → body 순회 (w:p, w:tbl, w:sdt)
      w:p  → _xml_para_text() + _xml_para_runs() + _extract_footnote_refs()
           → _classify_paragraph() → NumberedParagraph|SubItem|ContinuationText|AuthorityMarker
      w:tbl → _classify_table() → SectionHeader|ContentTable
  → elements: list[IRElement], footnotes, stats 반환
```

섹션 감지: 1x1 표 텍스트를 `_SECTION_TEXT_MAP`으로 매칭 (`결론도출근거`→`bc`, `적용지침`→`ag` 등)  
번호 감지: `_PARA_NUMBER_RE` 정규식 + TAB 구분 (`번호\t내용` 패턴)  
Preamble 필터: 첫 `SectionHeader` 등장 전 모든 문단 스킵

### 3.3 `converter/md_renderer.py`: IR → MD 출력 형식

**YAML 프론트매터**:
```yaml
---
standard_id: "K-IFRS 1115"
standard_number: "1115"
title: "고객과의 계약에서 생기는 수익"
standard_type: "standard"
standard_family: "IFRS"
original_number: "IFRS 15"
base_authority: 1
last_amended_year: "2017"
components: [ag, bc, definitions, ie, main, transition]
has_korean_additions: false
---
```

**섹션 메타데이터 HTML 코멘트**:
```markdown
## 결론도출근거
<!-- component: bc | authority: 4 -->
```

**번호 문단**:
```
1	일반 문단 내용
<!-- para: 1 -->

**2	핵심 원칙 문단 (전체 bold)**
<!-- para: 2 | bold_para -->

한2.1	한국 고유 추가사항
<!-- para: 한2.1 | korean_addition -->
```

**서식**: 번호와 내용 사이 `\t` (탭) 구분, bold 문단은 전체를 `**...**`로 감쌈

**각주**: 파일 하단 `---` 뒤에 `[^1]: 내용` 형식

**섹션 authority 매핑**:
| section_type | authority |
|---|---|
| main, definitions, ag, transition | 1 |
| bc, ie | 4 |

### 3.4 AuditStandard 재사용 가능 여부

| 컴포넌트 | 판정 | 사유 |
|---------|------|------|
| `converter/models.py` 전체 구조 | △ | 클래스 구조 재사용, 필드명 일부 변경 필요 (§7 상세) |
| `converter/docx_parser.py` 전체 | △ | XML 파싱 유틸리티 재사용, 섹션/번호 감지 로직은 재설계 |
| `converter/md_renderer.py` | △ | 렌더링 패턴 재사용, 프론트매터 필드 변경 필요 |
| YAML frontmatter 패턴 | ✓ | `standard_id`, `schema_version`, `source_file` 유지 |
| HTML 코멘트 메타데이터 패턴 | ✓ | `<!-- para: N | kind -->` 패턴 그대로 채택 |
| TAB 구분 번호 렌더링 | ✗ | ISA는 numbering.xml 자동넘버링 → 텍스트에 번호 없음 (§8 상세) |

---

## 4. Stage 2 처리 흐름

### 4.1 전체 파이프라인

```
output/md/*.md
  → md_parser.parse_markdown_file()
      → StandardRecord + ChunkRecord[] + FootnoteRecord[]
      → 프론트매터 파싱 (_parse_frontmatter)
      → 라인별 상태머신: component/authority 추적, 번호문단 감지 (_PARA_LINE_RE)
      → _flush_chunk(): 누적 줄 → ChunkRecord (plain text + markdown 양쪽 보존)

  → chunk_splitter.split_oversized_chunks()
      → 정의 섹션: 용어별 분리 (_split_definition_chunk)
      → 일반 초과: 빈줄 기준 단락 그룹화 (_split_by_structure)
      → 최후 수단: 강제 절단 (_truncate_chunk)
      → chunk_id 중복 시 suffix: `-def1`, `-pt2` 추가

  → link_extractor.extract_links()
      → BC/IE 청크만 처리
      → 전략1: 섹션 헤딩 "(문단 X~Y)" 패턴 → section_heading 링크
      → 전략2: 본문 내 "문단 X~Y" 패턴 → body_reference 링크

  → summary_builder.build_summary()
      → 목적/적용범위 섹션 청크 → scope_text (임베딩 대상)
      → 정의 섹션 청크 → definitions_text (LLM 컨텍스트 직접 주입)

  → embedder.embed_batch/embed_single()
      → Upstage Solar embedding-passage (문서용)
      → embedding-query (검색 쿼리용, 비대칭 모델)
      → 4096차원, 한국어 ~5000자 절단

  → db_writer.upsert_*()
      → upsert_standard(), upsert_chunks(), upsert_footnotes()
      → upsert_links(), upsert_summary()
      → ON CONFLICT ... DO UPDATE 패턴 (idempotent)
```

### 4.2 `db_writer.py` → `qdrant_writer.py` 변경 폭

| 기존 (`db_writer.py`) | 신규 (`qdrant_writer.py`) | 변경 크기 |
|----------------------|--------------------------|----------|
| `psycopg.connect()` + `pgvector` | `qdrant_client.QdrantClient()` | 완전 교체 |
| `init_schema()` — schema.sql 실행 | `create_collection()` — HNSW 파라미터 설정 | 교체 |
| `upsert_standard()` — standards 테이블 | payload 필드로 평탄화 (§6 상세) | 교체 |
| `upsert_chunks()` — chunks 테이블 | `client.upsert(collection, points)` | 교체 |
| `upsert_summary()` — standard_summaries | named vector `summary` 또는 별도 collection | 설계 선택 |
| `upsert_links()` — paragraph_links | payload `paragraph_links` JSON 배열 또는 별도 저장소 | 설계 필요 |
| `create_vector_indexes()` — 주석 처리 (4096d 제한) | Qdrant HNSW 기본 지원 (`m=16, ef_construct=200`) | 단순화 |
| `register_vector()` (pgvector 확장) | 불필요 | 제거 |

**결론**: `db_writer.py`는 완전 재작성. 다른 모듈(`md_parser`, `chunk_splitter`, `embedder`)은 대부분 재사용 가능.

---

## 5. pyproject.toml 의존성 전략

### 5.1 IFRS 파이프라인 현황

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "python-docx>=1.1.0",
    "lxml>=5.0.0",
    "openai>=1.0.0",          # Upstage는 OpenAI 호환 API 사용
    "psycopg[binary]>=3.1.0",
    "pgvector>=0.3.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]
```

- **버전 핀 정책**: `>=` 하한만 지정, 상한 없음 (느슨한 정책)
- **dev 의존성**: pytest만 포함, ruff/mypy 미포함
- **tiktoken 없음**: 토큰 추정을 `chars // 2` 휴리스틱으로 대체
- **sentence-transformers 없음**: Upstage API 사용

### 5.2 AuditStandard 파이프라인 변경사항

| 패키지 | IFRS | AuditStandard | 이유 |
|--------|------|--------------|------|
| `python-docx>=1.1.0` | ✅ | ✅ 유지 | docx 파싱 동일 |
| `lxml>=5.0.0` | ✅ | ✅ 유지 | numbering.xml 파싱 필요 (더 중요) |
| `openai>=1.0.0` | ✅ | ✅ 유지 | Upstage 호환 |
| `psycopg[binary]>=3.1.0` | ✅ | ✗ 제거 | Qdrant로 교체 |
| `pgvector>=0.3.0` | ✅ | ✗ 제거 | Qdrant로 교체 |
| `python-dotenv>=1.0.0` | ✅ | ✅ 유지 | .env 로딩 |
| `qdrant-client` | ✗ | ✅ 추가 | Qdrant 클라이언트 |
| `typer` | ✗ | ✅ 추가 | CLI 개선 |
| `tiktoken` | ✗ | ✅ 추가 | 정확한 토큰 추정 |
| `ruff` / `mypy` | ✗ | ✅ dev 추가 | 코드 품질 |

---

## 6. schema.sql / DB_USAGE_GUIDE.md → Qdrant 이식 재매핑

### 6.1 pgvector `vector(4096)` → Qdrant Named Vector 구조

**pgvector 현황**:
- `chunks.embedding vector(4096)` — 청크 임베딩
- `standard_summaries.embedding vector(4096)` — 기준서 요약 임베딩
- 인덱스: IVFFlat 주석 처리 (4096d 제한), 현재 exact search

**Qdrant 매핑**:
```python
# collection 생성 예시
client.create_collection(
    collection_name="audit_standards_회계감사기준_2025",
    vectors_config={
        "passage": VectorParams(size=4096, distance=Distance.COSINE),
        "summary": VectorParams(size=4096, distance=Distance.COSINE),
    },
    hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
)
```

- `passage` vector: 청크 본문 임베딩 (`embedding-passage`)
- `summary` vector: 기준서 요약 임베딩 (기준서 식별용 Step 1)
- HNSW 기본 지원 → 인덱스 제약 해소

### 6.2 5개 테이블 → Qdrant payload 평탄화 전략

| pgvector 테이블 | Qdrant 매핑 전략 |
|----------------|----------------|
| `standards` (메타데이터) | 각 point의 payload에 `standard_id`, `standard_no`, `standard_title`, `source_file`, `base_authority` 포함 |
| `chunks` (검색 대상) | **메인 Point**: `id=chunk_id`, `vector=passage`, payload에 `para_number`, `section`, `kind`, `authority`, `heading_trail`, `content_text`, `content_markdown`, `token_estimate` |
| `standard_summaries` | `summary` named vector에 scope_text 임베딩, payload에 `scope_text`, `scope_markdown`, `definitions_text` |
| `paragraph_links` | payload 내 `paragraph_links: [{source, target, link_type}]` JSON 배열로 청크에 비정규화, 또는 별도 SQLite 저장소 |
| `footnotes` | payload 내 `footnotes: {1: "내용", 2: "내용"}` dict로 기준서 레벨에 비정규화, 또는 별도 저장소 |

**권장 전략**:
- `paragraph_links`와 `footnotes`는 Qdrant 검색 대상이 아님 → 별도 `.sqlite` 또는 JSON 파일로 분리 저장
- Qdrant payload는 검색 필터용 메타데이터에 집중

### 6.3 인덱스 전환 주의점

| pgvector | Qdrant | 주의 |
|----------|--------|------|
| `CREATE INDEX idx_chunks_standard ON chunks(standard_id)` | payload 인덱스: `create_payload_index("standard_id", PayloadSchemaType.KEYWORD)` | 수동 생성 필요 |
| `CREATE INDEX idx_chunks_component ON chunks(component)` | `create_payload_index("section", PayloadSchemaType.KEYWORD)` | 수동 생성 필요 |
| IVFFlat (주석 처리, 4096d 제한) | HNSW 자동 적용 (4096d 지원) | 파라미터 `m`, `ef_construct` 튜닝 필요 |
| `ON CONFLICT ... DO UPDATE` (upsert) | `client.upsert(collection, points)` — Qdrant는 id 기반 upsert 기본 지원 | 동일 의미론 |

**HNSW 메모리 추정** (4096d, 최대 ~15,000 청크):  
각 포인트 ≈ 4096 × 4 bytes + HNSW 그래프 ≈ ~20KB → 전체 ≈ 300MB. 로컬 실측 권장.

---

## 7. AuditStandard 파싱에 재사용 가능한 IR 데이터클래스 목록

### 7.1 판정 기준

ISA (국제감사기준) 파싱과 K-IFRS 파싱의 근본 차이:

| 항목 | K-IFRS | ISA (회계감사기준) |
|------|--------|-----------------|
| 문단번호 위치 | **텍스트에 TAB으로 포함** (`1\t내용`) | **numbering.xml 자동넘버링** (텍스트에 없음) |
| 번호 추출 방식 | `_PARA_NUMBER_RE` + TAB 분리 | `word/numbering.xml` 파싱 + 카운터 replay |
| 요구사항 번호 | `1`, `2`, `3` ... | `numId=64 ilvl=0 %1.` → `1.`, `2.`, `3.` |
| 적용지침 번호 | `AG5`, `B12` (텍스트에 직접) | `numId=57 ilvl=0 A%1.` → `A1.`, `A2.` |
| 권위 구조 | 5단계 (§8 참조) | 2단계 (요구사항 vs 적용지침) |
| 섹션 감지 | 1x1 표 텍스트 | 스타일명 + 텍스트 패턴 혼용 |

### 7.2 클래스별 판정

| 클래스 | 판정 | 재사용 방식 / 변경 사유 |
|--------|------|----------------------|
| `FormattedRun` | **✓ 그대로 재사용** | bold/italic 구조 동일, 필드 변경 없음 |
| `MetaInfo` | **△ 일부 수정** | ISA 메타 필드 다름: `standard_no` (200/240 등), `standard_title`, `source_file`. `standard_family`/`original_number`/`standard_type` 불필요. `schema_version` 추가 필요 |
| `SectionHeader` | **△ 일부 수정** | `section_type` enum 변경: IFRS (`main/ag/bc/ie`) → ISA (`intro/purpose/definitions/requirements/application_guidance`). level 구조는 유지 |
| `AuthorityMarker` | **✗ 재설계** | ISA는 IFRS 방식의 명시적 권위 선언 문구 없음. ISA 권위는 섹션 종류로 결정 (요구사항=의무, 적용지침=비의무). `AuthorityMarker` 대신 `section_type` 메타데이터로 대체 |
| `NumberedParagraph` | **△ 일부 수정** | `para_number` 추출 방식 완전 변경 (numbering.xml 카운터 replay). `is_korean_addition` 불필요 제거. `is_application_guidance: bool`, `parent_paragraph_id: str|None` 추가 (An→n 연결) |
| `ContinuationText` | **✓ 그대로 재사용** | 번호 없는 연속 텍스트 개념 동일. `is_korean_addition` 불필요하므로 제거 가능 |
| `ContentTable` | **✓ 그대로 재사용** | 표 구조 동일, `headers`/`rows`/`section_type` 유지 |
| `SubItem` | **△ 일부 수정** | 호/목 마커(⑴⑵⑶, ㈎㈏㈐) 동일하게 사용. `sub_sub_items` 필요 여부 확인 후 유지/제거. ISA 들여쓰기 구조가 IFRS와 동일한지 검증 필요 |
| `Footnote` | **✓ 그대로 재사용** | 각주 구조 동일 (word/footnotes.xml 파싱). ISA도 `lxml` 직접 파싱 필요 |

### 7.3 새로 필요한 IR 클래스

| 클래스 (안) | 필요 사유 |
|-----------|---------|
| `RawBlock` | numbering.xml 카운터와 연결된 raw 문단 임시 표현. `paragraph_id`, `numId`, `ilvl`, `style` 포함 |
| `ISAStandardBoundary` | `감사기준서 N` 경계 탐지용 마커. 하나의 DOCX에 여러 기준서(ISA 200~810) 포함 |

---

## 8. 보너스 섹션 — IFRS vs ISA 근본 차이

### 8.1 문서 구성 단위

| 항목 | K-IFRS | ISA (회계감사기준) |
|------|--------|-----------------|
| 파일 단위 | 기준서 1개 = 1 DOCX | **하나의 DOCX에 ISA 200~810 전체 수록** |
| 파싱 경계 | 파일 경계 = 기준서 경계 | `감사기준서 N` 제목으로 경계 탐지 필요 |
| 출력 단위 | 1 DOCX → 1 MD | 1 DOCX → `ISA-<N>.md` 다수 + `00_전문.md` |

### 8.2 "한" 접두어 (carve-in) vs ISA 無

| 항목 | K-IFRS | ISA |
|------|--------|-----|
| 한국 고유 추가사항 | **"한" 접두어 문단** (예: `한2.1`, `한82.1`): 한국채택 carve-in. `is_korean_addition` 메타 태깅 | **없음**: KICPA 번역 감사기준은 IAASB ISA를 그대로 번역. 한국 고유 추가사항 없음 |
| 발행 기구 | KASB (한국회계기준원) | KICPA (한국공인회계사회) |

### 8.3 권위 구조 비교

| 항목 | K-IFRS | ISA |
|------|--------|-----|
| 권위 단계 | **5단계**: ① 기준서/해석서 본문+AG ② IFRIC 안건결정 ③ 개념체계 ④ BC/IE ⑤ 외부문헌 | **2단계**: ① 요구사항(Requirements) — 감사인 준수 의무 ② 적용 및 기타 설명자료 — 맥락·지침 제공 |
| 권위 표시 방식 | 명시적 선언 문구 ("이 부록은... 일부를 구성한다") | 섹션 구분으로 암묵적 결정 (요구사항 섹션 = 의무) |
| 적용지침 지위 | AG = Authoritative (Level 1) | 적용 및 기타 설명자료 = Non-binding (참고용) |

### 8.4 섹션 구조 비교

| K-IFRS 섹션 | ISA 섹션 |
|------------|---------|
| 본문(main) | 서론(Introduction) |
| 용어의 정의(definitions, 부록A) | 목적(Objective) |
| 적용지침(ag, 부록B) | 용어의 정의(Definitions) |
| 경과규정(transition, 부록C) | 요구사항(Requirements) |
| 결론도출근거(bc) | 적용 및 기타 설명자료(Application and Other Explanatory Material) |
| 적용사례(ie) | 부록(Appendix), 적용사례 등 |

### 8.5 문단번호 체계 비교 (핵심 파싱 차이)

| 항목 | K-IFRS | ISA |
|------|--------|-----|
| 번호 위치 | **텍스트에 포함** (`"1\t본 기준서는..."`) | **numbering.xml 자동넘버링** (텍스트에 번호 없음) |
| 번호 추출 | `_PARA_NUMBER_RE` + TAB 분리 | `numbering.xml` → `numId` + `ilvl` + `lvlText` 파싱 + 카운터 replay |
| 요구사항 예상 패턴 | `1.`, `2.`, `3.` (텍스트에 직접) | `numId=64, ilvl=0, lvlText="%1."` → 카운터 누적 |
| 적용지침 예상 패턴 | `AG5`, `AG12` (텍스트에 직접) | `numId=57, ilvl=0, lvlText="A%1."` → `A1.`, `A2.` |
| 파싱 위험도 | 낮음 (텍스트에서 직접 추출) | **높음** (numbering 카운터 오류 시 전체 번호 밀림) |

### 8.6 BC/IE → 본문 링크 적용 가능 여부

| 항목 | K-IFRS | ISA |
|------|--------|-----|
| BC 섹션 | 있음 (결론도출근거) | **없음** (ISA는 BC 섹션 미포함) |
| IE 섹션 | 있음 (적용사례) | 일부 기준서에만 있음 |
| `link_extractor.py` | BC/IE → 본문 문단 추출 (7,952건) | ISA는 BC 없으므로 대폭 단순화 가능 |

---

## 참고: IFRS 파이프라인 모듈별 재사용 요약표

| 파일 | AuditStandard 재사용 가능성 | 변경 규모 |
|------|--------------------------|---------|
| `converter/models.py` | △ 대부분 재사용 | 필드 일부 수정, 2개 클래스 수정 |
| `converter/docx_parser.py` | △ 유틸리티 재사용 | 핵심 파싱 로직 재설계 (`numbering.xml`) |
| `converter/md_renderer.py` | △ 렌더링 패턴 재사용 | 프론트매터/코멘트 구조 수정 |
| `ingester/models.py` | △ 구조 재사용 | `StandardRecord`, `ChunkRecord` 필드 수정 |
| `ingester/md_parser.py` | △ 파싱 패턴 재사용 | 프론트매터 필드, 섹션 코멘트 패턴 수정 |
| `ingester/chunk_splitter.py` | ✓ 거의 그대로 | 임계값 상수만 조정 |
| `ingester/link_extractor.py` | △ 일부 재사용 | BC 없으므로 단순화 |
| `ingester/summary_builder.py` | △ 구조 재사용 | ISA 섹션명 (`목적`, `적용범위`) 맞게 수정 |
| `ingester/embedder.py` | ✓ 그대로 재사용 | Upstage API 동일 사용 |
| `ingester/config.py` | △ 구조 재사용 | `db_url` → `qdrant_url`, `collection_name` 추가 |
| `ingester/db_writer.py` | ✗ 재설계 | `qdrant_writer.py`로 완전 교체 |
| `convert.py` (CLI) | △ 구조 재사용 | argparse → typer, 경로 규칙 변경 |
| `ingest.py` (CLI) | △ 구조 재사용 | `--collection` 플래그 추가, `--export-json` 불필요 |
