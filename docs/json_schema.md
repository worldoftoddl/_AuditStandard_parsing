# JSON 중간형식 공식 스펙 — `output/json/ISA-<nnn>.json`

> **Status:** ACTIVE (Phase 2 기준)
> **Schema Version:** `"1.1.1"`
> **작성자:** `audit-standard-domain-reviewer` (Phase 2 Task #1)
> **작성일:** 2026-04-21 (v1.1.1 개정 2026-04-21)
> **근거 문서:**
> - [`PLAN.md §4 Phase 2`](../PLAN.md) — JSON 스키마 요구사항 (결정 #2)
> - [`docs/PHASE_1_REPORT.md`](./PHASE_1_REPORT.md) §7 — Phase 2 로 이월된 이슈 C4/C5/C7/C8/C11
> - [`docs/devils_advocate_checkpoint_1.md`](./devils_advocate_checkpoint_1.md) — C4/C5/C7/C8/C11 근거
> - [`docs/f4_known_duplicates.md`](./f4_known_duplicates.md) §4 — composite key 제안
> - [`docs/numbering_strategy.md §10`](./numbering_strategy.md) — abstractNumId-scoped counter 최종 설계
> - [`src/audit_parser/ir/types.py`](../src/audit_parser/ir/types.py) — `BlockKind`, `Section` enum 권위
> - [`output/md/`](../output/md/) 37 파일 — HTML 주석 포맷 실측 근거

---

## 0. 목적과 청중

본 문서는 Phase 2 산출물 `output/json/ISA-<nnn>.json` 의 **공식 외부 연계 스펙**이다. 다음 3 가지 용도를 모두 충족한다 (PLAN.md 결정 #2, a+b+c):

1. **사람 검수(a)** — Domain Reviewer 가 Phase 2 CHECKPOINT 에서 20 개 샘플을 원본 MD 와 대조할 때 사용.
2. **타 시스템 연계(b)** — 외부 RAG·감사 도구가 JSON 을 직접 소비할 수 있도록 공식 스키마 고정.
3. **재임베딩 캐시(c)** — `embedding` 필드 null 로 적재 후, 이후 `embedder.py` 가 passage/query 벡터만 갱신해도 `chunk_id` 가 불변.

**청중:**
- `parser-implementer` (Phase 2 Task #2, #3, #4 — `md_parser.py`, `chunk_splitter.py`, `cli.py`)
- `qdrant_writer` (Phase 3) — payload 매핑 권위
- 외부 연계 개발자 — 본 문서만으로 `ParsedStandard` 구조를 복원할 수 있어야 함.

---

## 1. 파일 및 최상위 구조

### 1.1 파일 네이밍

| 경로 | 내용 | 생성 주체 |
|---|---|---|
| `output/json/ISA-200.json` | ISA-200 본문 1 기준서 | `md_parser.py` ← `output/md/ISA-200.md` |
| `output/json/ISA-<nnn>.json` | ISA-210~1200, 각 1 기준서 | 동일 |
| **`output/json/00_전문.json`** | **(생성하지 않음)** — TOC/prelude 는 chunk 대상 아님 | — |

**총 36 개 JSON** (Phase 1 MD 37 개 중 `00_전문.md` 제외).

> **Prelude skip 규약 (확정):** `md_parser.py` 는 `output/md/00_전문.md` 를 **반드시 건너뛴다**. 이유: (1) TOC entry 만 포함되어 있어 chunk 대상 아님, (2) heading_trail 복원이 기준서 단위로만 의미 있음. CLI `audit-parser ingest output/md/` 실행 시 filename stem 이 `00_전문` 또는 `^\d{2}_` pattern 매칭되면 warning 없이 skip. 반드시 36 JSON 생성되어야 하며, 이는 Task #6 검수 체크 항목.

### 1.2 최상위 객체 (`ParsedStandard`)

```json
{
  "schema_version": "1.1.1",
  "standard": { ... },
  "summary":  { ... },
  "chunks":   [ ... ],
  "paragraph_links": [ ... ]
}
```

**필수 필드 (required):** `schema_version`, `standard`, `summary`, `chunks`, `paragraph_links` — 5 개 모두.

**추가 필드 금지 (additionalProperties: false):** Phase 2 는 엄격 검증. 미래 확장은 §10 SemVer bump 으로 관리.

---

## 2. `schema_version` 과 SemVer 정책 (C8 대응)

### 2.1 현재 값

```json
"schema_version": "1.1.1"
```

**MD frontmatter 와 동기화:**
- `src/audit_parser/convert/md_renderer.py::SCHEMA_VERSION = "1.0"` 는 **MD 스키마 (HTML 주석/YAML frontmatter) 계속 v1.0 유지** — JSON 만 1.0→1.1→1.1.1 bump (두 스키마 독립 카운터).
- Phase 1 MD frontmatter `schema_version: "1.0"` 의 의미: "HTML 주석 포맷 + YAML frontmatter 키 스키마 v1.0" (불변)
- Phase 2 JSON `schema_version: "1.1"` 의 의미: "ParsedStandard 구조 v1.1 — chunk_id collision-resolve 규칙 추가, appendix_index 9 ISAs 커버, heading_trail canonical form 확정"
- Phase 2 JSON `schema_version: "1.1.1"` 의 의미: v1.1 과 **구조 동등**. PATCH-level 문서 명확화 (§2.2 각주, §8.4 idempotency 적용 범위, §9.4/§9.5 header 중복 bias finding) 만 추가 — chunks·paragraph_links·payload 바이트 동등, 재임베딩 불필요.
- 두 스키마는 **독립 카운터**. 한쪽 bump 가 다른 쪽을 강제하지 않음.

### 2.2 SemVer bump 정책

**형식:** `MAJOR.MINOR` (PATCH 생략 — PATCH 변경은 문서 정정이므로 스키마 불변).

| 종류 | 예시 | 정책 |
|---|---|---|
| **MAJOR** | `1.0` → `2.0` | (a) `chunk_id` 컴포지트 스킴 변경 (예: 해시 길이 8→12, 구분자 `:` → `/`) <br> (b) 기존 필드 **의미 변경** (예: `authority` 의 단위 변경) <br> (c) 기존 필드 **타입 변경** (예: `paragraph_id: str` → `str \| null` 만으로는 MINOR, 의미 파괴 시 MAJOR) <br> (d) 필수 필드 삭제 또는 이름 변경 <br> → **적재된 Qdrant collection 재빌드 필요** |
| **MINOR** | `1.0` → `1.1` | (a) 신규 optional 필드 추가 (backward compat) <br> (b) 기존 enum 값 확장 (예: `Section` 에 신규 값 추가, `link_type` 에 새 enum 추가) <br> (c) 기존 필드의 description/example 갱신 <br> → **기존 적재 데이터 유효, 새 필드는 null 로 읽힘** |
| **PATCH** | `1.1` → `1.1.1` | (a) 본 스펙 문서의 명확화·주석·오탈자 정정 <br> (b) 기존 규범의 **비구조적 보충 설명** (예: 한계·적용 범위 footnote 추가) <br> (c) 구조/의미/enum/필드 타입 불변 <br> → **`chunk_id`·`embedding`·`heading_trail_hash`·`paragraph_links` 전부 불변** (재임베딩·Qdrant 재적재 불필요). 오직 `schema_version` 문자열만 `"1.1"` → `"1.1.1"` 갱신 (in-place string replace 로 충분, 36 JSON 일괄 재작성 OK). |

> **v1.1 조건부 MINOR 판정 (각주):** `chunk_id` 산출 함수의 출력이 동일 입력에 대해 변경되었음에도 MINOR 로 판정한 근거는 (a) 배포된 v1.0 JSON 데이터 0 건, (b) v1.0 `chunk_id` 를 조회하는 외부 consumer 부재 — 두 조건 충족. 향후 유사 변경 시 이 두 조건이 성립하지 않으면 MAJOR bump 필수. 특히 Phase 4 RAG 서비스 deploy 후에는 `chunk_id` format 확장이 **항상 MAJOR** (근거: devils_advocate_checkpoint_2.md §2).

### 2.3 MD ↔ JSON 동기화 규칙

**독립 bump 원칙:**

1. `md_renderer.py::SCHEMA_VERSION` 만 올릴 수 있는 경우 → HTML 주석 포맷·YAML 키 변경. Phase 2 파서(`md_parser.py`) 만 upgrade.
2. JSON `schema_version` 만 올릴 수 있는 경우 → `ParsedStandard` 필드 추가·의미 변경. Phase 1 산출 MD 재생성 불필요.
3. **양쪽 동시 bump 필요 조건** — 오직 HTML 주석에 담긴 필드가 JSON 구조에 그대로 전파되고, 그 필드의 의미가 변경될 때 (예: `para` 주석 키를 `para_id` 로 rename 하고 JSON `paragraph_id` 도 의미 변경).

**운영 점검:**
- `pyproject.toml` 또는 `src/audit_parser/__init__.py` 에 `MD_SCHEMA_VERSION` 과 `JSON_SCHEMA_VERSION` 두 상수를 분리 정의. 현재는 `md_renderer.SCHEMA_VERSION` 하나만 존재 — Phase 2 Task #2 에서 `md_parser.JSON_SCHEMA_VERSION = "1.0"` 신설.
- CI 검사: `output/md/*.md` 의 frontmatter `schema_version` 과 `md_renderer.SCHEMA_VERSION` 이 일치해야 함. 마찬가지로 `output/json/*.json` 과 `JSON_SCHEMA_VERSION` 일치.

### 2.4 마이그레이션 가이드

MAJOR bump 발생 시 반드시 추가할 산출물:
1. `docs/migrations/json_schema_v1_to_v2.md` — breaking change 리스트 + 자동 변환 스크립트.
2. `src/audit_parser/ingest/migrate.py` — `v1.x → v2.0` 일괄 변환 CLI (`audit-parser migrate output/json/`).
3. PHASE_N_REPORT 에 "breaking change" 명시 섹션.

MINOR bump 시:
- 본 문서 §13 Changelog 에 1 줄 추가. Phase 2/3 코드 변경은 optional.

---

## 3. `standard` 레코드

기준서 전역 메타 1 건. `output/md/ISA-<nnn>.md` YAML frontmatter 에서 파생.

```json
"standard": {
  "standard_id": "ISA-200",
  "standard_no": "200",
  "standard_title": "독립된 감사인의 전반적인 목적 및 감사기준에 따른 감사의 수행",
  "source_file": "0. 회계감사기준 전문(2025 개정).docx",
  "authority_base": 1
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `standard_id` | `str` | ✅ | `"{PREFIX}-<standard_no>"` 포맷. 전역 고유. PREFIX ∈ {`ISA`, `ISQM`, `ASSR`, `FRMK`} (v1.2.0 확장). |
| `standard_no` | `str` | ✅ | 숫자 문자열. ISA: `"200"` ~ `"1200"`, ISQM: `"1"`~`"99"`, ASSR: `"3000"`~`"9999"`, FRMK: `"1"`~`"9"`. MD frontmatter 동일. |
| `standard_title` | `str` | ✅ | 기준서 제목. ISA-200 은 `raw/` heading 1 자식 텍스트. 없는 기준서는 `""` (빈 문자열). |
| `source_file` | `str` | ✅ | 원본 DOCX 파일명. Collection 네이밍 역추적용. |
| `authority_base` | `int` | ✅ | 기준서 자체의 권위 레벨. ISA-200 = 1 (KICPA 공식). 보조 기준 있을 시 0. 현 4 DOCX 모두 1. |

**제약 (v1.2.0):**
- `standard_id` 는 `^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)$` 매칭. v1.1.x 36 ISA `standard_id` 전수 alt 1 (`ISA-\d{3,4}`) 매칭 — backward-compat. (Phase 4 Pre-Kickoff PK-2 3자 합의 — `docs/checkpoint_4_prep.md §1.3.4`)
- `standard_no` 는 `^\d{1,4}$` 매칭. v1.1.x 의 `^\d{3,4}$` 에서 relax — ISQM-1 / FRMK-1 의 1-digit 수용. ISA 36 standard_no 전수 (`200`~`1200`) 새 regex 통과 — backward-compat.
- **Phase 5+ alt 추가 규약**: alternation order = longer prefix 선행 (예: 향후 `ISAE` 추가 시 `ISA` 보다 앞에 배치). regex 가 `:` 또는 `#` 문자 포함 금지 (chunk_id separator 안전성).
- `authority_base ∈ {0, 1}` (열린 집합 아님, MINOR bump 시 확장 가능).

---

## 4. `summary` 레코드

기준서별 검색 필터·UI 요약용. 범위(`scope_*`) 와 정의(`definitions_*`) 섹션 텍스트 추출.

```json
"summary": {
  "scope_text": "이 감사기준서는 독립된 감사인이 ...",
  "scope_markdown": "이 감사기준서는 독립된 감사인이 ...",
  "definitions_text": "감사 — 재무제표가 ...",
  "definitions_markdown": "(a) 감사 — 재무제표가 ...",
  "embedding": null,
  "embedded_at": null,
  "embedding_model": null
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `scope_text` | `str \| null` | ✅ | `## 서론` 하위 `### 이 감사기준서의 범위` 문단 연결본. MD 제거 (heading, HTML 주석, 탭). null = 해당 heading 3 미존재. |
| `scope_markdown` | `str \| null` | ✅ | `scope_text` 의 markdown 원본 (탭 구분, heading 제외). `md_parser` 가 추출. |
| `definitions_text` | `str \| null` | ✅ | `## 용어의 정의` 섹션 전체 본문 plain. |
| `definitions_markdown` | `str \| null` | ✅ | 동 섹션 markdown. |
| `embedding` | `List[float] \| null` | ✅ | `summary` 용 단일 벡터 (Upstage Solar, 4096d). 초기 null. |
| `embedded_at` | `str \| null` (ISO 8601) | ✅ | `embedding` 최종 갱신 시각. `2026-04-22T10:30:00Z`. null = 미생성. |
| `embedding_model` | `str \| null` | ✅ | 예: `"solar-embedding-1-large-passage"`. null = 미생성. |

**추출 규칙 (`md_parser`):**
- `scope_*` — heading_trail 끝이 `"이 감사기준서의 범위"` 인 연속 block 을 concat. ISA-1200 등 해당 heading 3 없는 기준서 → null.
- `definitions_*` — `section: definitions` 범위 block 을 concat. ISA-1200 보론 1 이 용어정의 역할이면 해당 블록 포함 여부는 `md_parser` 가 별도 규칙 `standard_no == "1200" and heading_trail startswith ("보론 1",)` 으로 처리.
- **markdown ≠ text** — `markdown` 은 `1.\t...` 탭 포함, `text` 는 탭 제거 + 연속 공백 단일 공백 압축.

**embedding idempotency:** §8 참조. `embedding` 이 null ↔ non-null 로 바뀌어도 `standard_id` 는 안정 키.

---

## 5. `chunks[]` 배열

**핵심 레코드.** Qdrant 에 1:1 로 업서트되는 단위.

```json
"chunks": [
  {
    "chunk_id": "ISA-300:requirements:a1b2c3d4:7.",
    "paragraph_id": "7.",
    "kind": "requirement",
    "section": "requirements",
    "appendix_index": null,
    "heading_trail": ["감사기준서 300", "요구사항", "전반감사전략"],
    "heading_trail_hash": "a1b2c3d4",
    "content_text": "감사인은 감사의 범위, 시기 및 방향을 수립하고 ...",
    "content_markdown": "7.\t감사인은 감사의 범위, 시기 및 방향을 수립하고 ...",
    "authority": 1,
    "parent_paragraph_id": null,
    "is_application_guidance": false,
    "token_estimate": 112,
    "chunk_index": 0,
    "chunk_of": 1,
    "source_idx": 2101,
    "part_of": null,
    "table_cells": null,
    "embedding": null,
    "embedded_at": null,
    "embedding_model": null
  }
]
```

### 5.1 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `chunk_id` | `str` | ✅ | **Composite key (§6)**. Qdrant payload 의 external id. 전역 고유. |
| `paragraph_id` | `str \| null` | ✅ | Phase 1 `Block.paragraph_id` 그대로 (`"1."`, `"A1."`, `"(a)"`, `"(i)"`, `"부록-1."`, `""`). null = bullet/paragraph_body. |
| `kind` | `BlockKind` (§5.2) | ✅ | Phase 1 `Block.kind.value`. 열거형. |
| `section` | `Section \| null` | ✅ | Phase 1 `Block.section.value`. null = 섹션 미진입 (prelude). |
| `appendix_index` | `int \| null` | ✅ | **C5 대응 (§7)**. `section == "appendix"` 일 때 `^보론\s*(\d+)\b` 그룹 1. non-appendix → null. |
| `heading_trail` | `List[str]` | ✅ | 상위→하위. 예: `["감사기준서 300", "요구사항", "전반감사전략"]`. 빈 배열 허용 (prelude). |
| `heading_trail_hash` | `str` | ✅ | **SHA1 [:8] 십육진 (§6.2)**. `chunk_id` 에 포함된 것과 동일 값. 검색 편의상 별도 필드 보유. |
| `content_text` | `str` | ✅ | 본문 plain (HTML 주석·heading·탭 제거). Upstage 임베딩 입력. |
| `content_markdown` | `str` | ✅ | 본문 markdown (탭 + `paragraph_id` prefix 유지). |
| `authority` | `int` | ✅ | 기준서 `authority_base` 상속. 섹션별 차등 부여는 Phase 2 범위 밖 (MINOR bump 대상). |
| `parent_paragraph_id` | `str \| null` | ✅ | Phase 1 `Block.parent_paragraph_id`. `An` → `n` 부모 링크. null = 부모 없음. |
| `is_application_guidance` | `bool` | ✅ | Phase 1 `Block.is_application_guidance`. `A%1.` 계열 여부. `section == "application"` 이 아니어도 True 가능 (혼합 케이스 방어). |
| `token_estimate` | `int` | ✅ | **tiktoken cl100k_base (§9)**. `content_text` 기준. |
| `chunk_index` | `int` | ✅ | 단일 문단이 분할된 경우 0-based 순번. 분할 안 된 경우 0. |
| `chunk_of` | `int` | ✅ | 같은 문단 분할 총 개수. 분할 안 된 경우 1. `chunk_of >= 1`. |
| `source_idx` | `int` | ✅ | Phase 1 `Block.idx` (원본 DOCX body 순번). 디버깅·역추적용. |
| `part_of` | `str \| null` | ✅ | **chunk 분할 시 부모 chunk_id** (chunk_of>1, chunk_index>0 인 2번째 이상 조각이 참조). `chunk_of == 1` 또는 `chunk_index == 0` 에서는 null. 분할 역추적 및 원본 문단 재조립에 사용. |
| `table_cells` | `List[List[str]] \| null` | ✅ | **`kind == "table"` 전용 필드**. MD table row 를 inverse-parse 한 2D 배열 (header 포함). 각 cell 은 `\|` unescape 적용 (§10). `kind != "table"` → 강제 null. `kind == "block_quote"` (1×1 승격) → `[[cell_text]]`. Qdrant 파생 검색용. |
| `embedding` | `List[float] \| null` | ✅ | Upstage Solar 4096d passage 벡터. 초기 null. |
| `embedded_at` | `str \| null` | ✅ | ISO 8601. null = 미생성. |
| `embedding_model` | `str \| null` | ✅ | 예: `"solar-embedding-1-large-passage"`. null = 미생성. |

### 5.2 `kind` enum (closed set, MINOR bump 으로 확장)

Phase 1 `BlockKind` 와 일치:

| 값 | 설명 |
|---|---|
| `"requirement"` | 요구사항 `%1.` decimal |
| `"application_guidance"` | 적용지침 `A%1.` decimal |
| `"sub_item"` | 하위 목록 `(a)`/`(i)`/`(1)` 등 |
| `"bullet"` | 불릿 (번호 없음) |
| `"paragraph_body"` | 번호 없는 본문 |
| `"heading"` | heading 1/2/3 자체 — chunk 포함 여부는 §5.4 |
| `"toc_entry"` | 목차 항목 — chunk 대상 아님 (prelude 필터) |
| `"table"` | 2×N 이상 표 |
| `"block_quote"` | 1×1 표 승격본 |
| `"unknown_numbering"` | fallback (5% 이하) |

### 5.3 `section` enum (closed set, MINOR bump 으로 확장)

Phase 1 `Section` 와 일치 (types.py):

- `"intro"`, `"overall_objective"`, `"purpose"`, `"definitions"`, `"requirements"`, `"application"`, `"appendix"`, `"unknown"`
- **ISA-1200 전용:** `"general_principles"`, `"ethical_requirements"`, `"engagement_acceptance"`, `"planning"`, `"materiality"`, `"risk_assessment"`, `"risk_response"`, `"conclusion_reporting"`, `"other_considerations"`

null 허용 (prelude/TOC 구간, Phase 2 chunk 생성 시점에 배제).

### 5.4 chunk 생성 대상과 제외 대상

**chunks 에 포함:** `requirement`, `application_guidance`, `sub_item`, `bullet`, `paragraph_body`, `table`, `block_quote`, `unknown_numbering` (총 8 종).

**chunks 에서 제외:**
- `heading` — heading_trail 로 전파될 뿐 자체 chunk 미생성.
- `toc_entry` — prelude 전용이며 `ISA-*.md` 에는 없어야 함 (Phase 1 R6 검증 완료).

**ISA-1200 보론 포함:** `section == "appendix"` chunk 는 생성하되 `authority=1` 유지. Qdrant filter 로 appendix-only/exclude-appendix 토글 가능.

---

## 6. `chunk_id` Composite Key (C4 대응)

### 6.1 공식 정의

```
chunk_id := {standard_id} ":" {section} ":" {heading_trail_hash} ":" {paragraph_id_or_fallback}
```

where `standard_id = "ISA-" + standard_no` (예: `"ISA-200"`, `"ISA-1200"`).

**정확한 문자열 구성:**

```python
def make_chunk_id(
    standard_id: str,         # "ISA-200", "ISA-1200"
    section: str,             # Section.value, e.g. "requirements"
    heading_trail_hash: str,  # §6.2 정의, 정확히 8자
    paragraph_id: str,        # "1.", "A1.", "(a)", "(i)", "부록-1.", ""
    kind: str,                # BlockKind.value (fallback 판단)
    source_idx: int,          # Phase 1 Block.idx (fallback suffix)
) -> str:
    # §6.4 의사결정표 구현 — chunk_index/chunk_of 분할 suffix (§6.3) 는 caller 가 부착
    if paragraph_id:
        return f"{standard_id}:{section}:{heading_trail_hash}:{paragraph_id}"
    return f"{standard_id}:{section}:{heading_trail_hash}:{kind}#{source_idx}"
```

**예시 (F4 6쌍 실측 검증 — 2026-04-21 MD 재검증 결과, v1.1 bump 근거):**

| # | standard | paragraph_id | #1 heading_trail (실측) | #2 heading_trail (실측) | 해소 축 | v1.1 chunk_id 형태 |
|---|---|---|---|---|---|---|
| 1 | ISA-250 | `12.` | `용어의 정의` (section=definitions, idx=1607) | `법규준수에 대한 감사인의 고려사항` (section=requirements, idx=1615) | **section** (definitions vs requirements) | `ISA-250:definitions:{h1}:12.` / `ISA-250:requirements:{h2}:12.` — 정상 해소 |
| 2 | ISA-260 | `5.` | `요구사항 > 감사인의 책임` (idx=1793) | `요구사항 > 감사에서의 유의적 발견사항` (idx=1823) | **heading_trail** | `ISA-260:requirements:{h1}:5.` / `ISA-260:requirements:{h2}:5.` — 정상 해소 |
| 3 | ISA-260 | `6.` | `요구사항 > 감사인의 책임` (idx=1794) | `요구사항 > 감사인의 독립성` (idx=1832) | **heading_trail** | `ISA-260:requirements:{h1}:6.` / `ISA-260:requirements:{h2}:6.` — 정상 해소 |
| 4 | **ISA-300** | **`7.`** | `요구사항 > 계획수립 활동` (idx=2237) | **`요구사항 > 계획수립 활동` (idx=2238)** | ⚠️ **heading_trail 동일 → 충돌** | `ISA-300:requirements:{h}:7.#2237` / `ISA-300:requirements:{h}:7.#2238` — **source_idx suffix 해소 (§6.4)** |
| 5 | ISA-300 | `10.` | `요구사항 > 계획수립 활동` (idx=2248, before `### 문서화`) | `요구사항 > 초도감사 시 추가적인 고려사항` (idx=2256) | **heading_trail** | `ISA-300:requirements:{h1}:10.` / `ISA-300:requirements:{h2}:10.` — 정상 해소 |
| 6 | **ISA-701** | **`4.`** | `서론 > 이 감사기준서의 범위` (idx=8422) | **`서론 > 이 감사기준서의 범위` (idx=8427)** | ⚠️ **heading_trail 동일 → 충돌** | `ISA-701:intro:{h}:4.#8422` / `ISA-701:intro:{h}:4.#8427` — **source_idx suffix 해소 (§6.4)** |

> **v1.0 에서 v1.1 로의 보정 이유:** v1.0 §6.1 은 "6 쌍 모두 heading_trail 로 해소" 로 단순화 기재했으나 2026-04-21 MD 재검증 결과 **pair #4 (ISA-300 `7.`)** 와 **pair #6 (ISA-701 `4.`)** 은 heading_trail 이 동일하여 composite key 충돌. `f4_known_duplicates.md §4.2` open item 이 negative 로 확정됨. v1.1 은 §6.4 의 **충돌 감지 후 `#{source_idx}` suffix** 규칙으로 두 쌍을 deterministic 하게 해소.
>
> `{h}` 는 `heading_trail_hash` placeholder — 실제 sha1[:8] 값은 Task #2 산출 시 실측 대체.

### 6.2 `heading_trail_hash` 정의

```python
import hashlib, json

def compute_heading_trail_hash(heading_trail: list[str]) -> str:
    """heading_trail → 8자리 sha1 hex.

    Canonical form:
      (1) 각 원소 .strip() (leading/trailing whitespace 제거)
      (2) json.dumps(list, ensure_ascii=False, separators=(",", ":")) — 공백 없음, 한글 그대로
    """
    # STEP 1: canonical form — whitespace 정규화 (v1.1 확정 규범)
    normalized = [h.strip() for h in heading_trail]
    # STEP 2: 직렬화 + sha1
    canonical = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha1(canonical.encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:8]
```

**불변조건:**
1. **안정성:** 같은 `heading_trail` 입력 → 같은 hash. 파싱 재실행 시 불변.
2. **대소문자 구분:** `"보론 1"` 과 `"보론1"` 은 다른 hash (실제 heading 텍스트 그대로 해시, `.strip()` 후 비교).
3. **공백 정규화 규범 (v1.1 확정):** 각 원소에 **반드시 `.strip()`** 적용 후 직렬화. leading/trailing whitespace 는 hash 에 영향 없음. 중간 공백은 보존 (`"보론 1"` 과 `"보론  1"` 은 다른 hash — 이는 의도된 동작, raw DOCX 저자 공백 차이가 의미 구분 가능성).
4. **빈 heading_trail:** `json.dumps([])` = `"[]"` → 특정 hash 1개 (`"77c80f89"`). prelude chunk 는 모두 동일 hash 지만 `paragraph_id` 가 다르므로 chunk_id 충돌 없음.
5. **sha1[:8] 32-bit 충돌 확률:** 2^-32 per pair. 기준서 36 × 평균 150 chunk ≈ 5,400 chunk → ~1.5e7 pair × 2^-32 ≈ **0.0034 건 기댓값** (birthday approx). Practical zero 이지만 non-negligible — 아래 §6.2.1 충돌 감지 필수.

### 6.2.1 sha1[:8] 충돌 감지 규범 (v1.1 신설)

`md_parser` 는 **파일 단위 파싱 완료 시 chunk_id 전수 unique check 를 수행**해야 한다:

```python
from collections import Counter

def assert_chunk_id_uniqueness(chunks: list[ChunkRecord]) -> None:
    counts = Counter(c.chunk_id for c in chunks)
    dups = {cid: n for cid, n in counts.items() if n > 1}
    if dups:
        raise ChunkIdCollisionError(
            f"chunk_id collision detected after §6.4 resolution: {dups}. "
            f"This should never happen post-§6.4 source_idx suffix. "
            f"If seen, investigate heading_trail_hash sha1[:8] 32-bit collision — "
            f"consider bumping hash length to [:12] (48-bit, v2.0 MAJOR) or adding standard_no to hash input."
        )
```

**해소 계층 (우선순위 순):**
1. `(standard_id, section, heading_trail_hash, paragraph_id)` 4-tuple 로 natural unique (99%+ 케이스).
2. 충돌 시 `#{source_idx}` suffix (§6.4) 로 deterministic 해소 (F4 2 쌍 포함, Phase 1 실측 2026-04-21 기준 총 2 건).
3. 그래도 충돌 시 → **hash length 확장 필요** (v2.0 MAJOR bump) 또는 Phase 1 `source_idx` 안정성 재검토.

**운영:** `md_parser` 가 step 3 에서 raise 하면 즉시 team-lead 에스컬레이션. Task #5 전수 생성 단계에서 이를 CI check 로 강제.

### 6.3 chunk_of > 1 일 때 (청크 분할)

4000 토큰 초과로 `chunk_splitter` 가 문단을 분할한 경우:

```
chunk_id := {standard_id} ":" {section} ":" {heading_trail_hash} ":" {paragraph_id} "#" {chunk_index}
```

**조건부 suffix:**
- `chunk_of == 1` → suffix 없음. 기존 chunk_id 유지.
- `chunk_of > 1` → `#0`, `#1`, ... 부착. `chunk_index` 는 0-based.

예: `ISA-300:requirements:aaaaaaaa:7.#0`, `ISA-300:requirements:aaaaaaaa:7.#1`.

**이유:** 기존 단일-chunk 의 id 를 변경하지 않아 재임베딩 시 안정성 보존 (§8). 분할이 일어나는 문단만 suffix 부착.

**`part_of` 필드 (§5.1) 와의 관계:**
- 분할이 발생하면 `chunk_index == 0` 인 첫 조각의 `chunk_id` 가 **정본 id** 로 간주.
- `chunk_index >= 1` 인 후속 조각의 `part_of` 에 첫 조각 `chunk_id` 를 저장 → 역추적 가능.
- 예: 첫 조각 `ISA-300:requirements:aaaaaaaa:7.#0` 의 `part_of = null`, 후속 `ISA-300:requirements:aaaaaaaa:7.#1` 의 `part_of = "ISA-300:requirements:aaaaaaaa:7.#0"`.
- `chunk_of == 1` 인 단일 chunk 는 `part_of = null`.

### 6.4 `paragraph_id` 가 빈 문자열인 경우 — `{kind}#{source_idx}` fallback

`bullet`, `paragraph_body`, `table`, `block_quote` 는 `paragraph_id == ""` (Phase 1 MD HTML 주석에 `para:` 키 부재).

단순히 `":{pid}"` 를 공백으로 두면 끝의 `":"` 가 남아 **heading_trail_hash 내부에 차별점이 없으면 chunk_id 충돌** 이 발생한다.

**해결 (parser-implementer 제안 채택, 2026-04-21 합의):** `paragraph_id == ""` 인 경우 4번째 segment 를 `{kind}#{source_idx}` 로 채움:

```
chunk_id := {standard_no} ":" {section} ":" {heading_trail_hash} ":" {kind} "#" {source_idx}
```

예:
- `ISA-200:application:b4e8d3f2:bullet#37`
- `ISA-1200:appendix:c5f9e4a3:table#1669`
- `ISA-315:requirements:d7e2f1b8:paragraph_body#812`
- `ISA-240:appendix:e9a3c2d1:block_quote#1045`

**설계 이유:**
1. **4-segment 형식 유지** — `split(":")` 으로 항상 정확히 4 part 로 parse 가능 (제 6.1 형식과 일관).
2. **사람 가독성** — `#1669` 만 보면 무엇인지 불명확하지만 `table#1669` 는 즉시 의미 파악 가능.
3. **BlockKind 분리** — 같은 heading_trail 하위에 table 과 bullet 이 공존 시 kind 가 natural disambiguator.
4. **source_idx** — Phase 1 `Block.idx` (원본 DOCX body 순번) 이며 재파싱 시 불변 (numbering.xml 구조가 안 바뀌는 한).

**파서 의사결정표 (v1.1 — 2-Pass, Phase 2 Task #2 필수 구현):**

chunk_id 는 **2-pass** 로 결정론적으로 산출:

**Pass 1 — candidate chunk_id (구조적 규칙 4 케이스):**

| 조건 | candidate chunk_id 형태 | 예시 |
|---|---|---|
| `paragraph_id != ""` and `chunk_of == 1` | `{std_id}:{sec}:{hash}:{pid}` | `ISA-300:requirements:aaaaaaaa:7.` |
| `paragraph_id != ""` and `chunk_of > 1` | `{std_id}:{sec}:{hash}:{pid}#{chunk_index}` | `ISA-300:requirements:aaaaaaaa:7.#0` |
| `paragraph_id == ""` and `chunk_of == 1` | `{std_id}:{sec}:{hash}:{kind}#{source_idx}` | `ISA-1200:appendix:c5f9e4a3:table#1669` |
| `paragraph_id == ""` and `chunk_of > 1` | `{std_id}:{sec}:{hash}:{kind}#{source_idx}#{chunk_index}` | `ISA-1200:appendix:c5f9e4a3:table#1669#1` |

**Pass 2 — collision resolution (v1.1 신설, F4 2 쌍 필수):**

```python
from collections import Counter

def resolve_chunk_id_collisions(chunks: list[ChunkRecord]) -> None:
    """Pass 1 산출 candidate 중복 시 전원에 source_idx suffix 부착 (deterministic)."""
    counts = Counter(c._candidate_chunk_id for c in chunks)
    dup_candidates = {cid for cid, n in counts.items() if n > 1}
    for c in chunks:
        if c._candidate_chunk_id in dup_candidates:
            # 충돌 참여 chunk 전원에 append (first-only 금지 — 결정론 보장)
            c.chunk_id = f"{c._candidate_chunk_id}#{c.source_idx}"
        else:
            c.chunk_id = c._candidate_chunk_id
```

**확장 의사결정표 (collision 포함 6 케이스):**

| 조건 | chunk_id 형태 | 예시 |
|---|---|---|
| `pid != ""` / `chunk_of == 1` / **no collision** | `{std_id}:{sec}:{hash}:{pid}` | `ISA-300:requirements:a1b2c3d4:8.` |
| `pid != ""` / `chunk_of == 1` / **collision** (F4 pair #4, #6) | `{std_id}:{sec}:{hash}:{pid}#{source_idx}` | `ISA-300:requirements:aaaaaaaa:7.#2237` |
| `pid != ""` / `chunk_of > 1` | `{std_id}:{sec}:{hash}:{pid}#{chunk_index}` | `ISA-300:requirements:aaaaaaaa:7.#0` |
| `pid != ""` / `chunk_of > 1` / **collision + split** (이론상, 실측 0) | `{std_id}:{sec}:{hash}:{pid}#{source_idx}#{chunk_index}` | `ISA-300:requirements:aaaaaaaa:7.#2237#0` |
| `pid == ""` / `chunk_of == 1` | `{std_id}:{sec}:{hash}:{kind}#{source_idx}` | `ISA-1200:appendix:c5f9e4a3:table#1669` |
| `pid == ""` / `chunk_of > 1` | `{std_id}:{sec}:{hash}:{kind}#{source_idx}#{chunk_index}` | `ISA-1200:appendix:c5f9e4a3:table#1669#1` |

**F4 2 쌍 최종 chunk_id (실측 source_idx 사용):**
- ISA-300 `7.` #1 → `ISA-300:requirements:{h}:7.#2237`
- ISA-300 `7.` #2 → `ISA-300:requirements:{h}:7.#2238`
- ISA-701 `4.` #1 → `ISA-701:intro:{h}:4.#8422`
- ISA-701 `4.` #2 → `ISA-701:intro:{h}:4.#8427`

**Separator 규약:** `#` suffix 는 `source_idx` (DOCX body 0-based 순번, Phase 1 `Block.idx`) 과 `chunk_index` (0-based split index) 양쪽에 사용. Parser 가 구분: 첫 `#` 뒤 숫자가 매우 크면 `source_idx` (DOCX 전체 body 순번, 보통 수천), 작으면 `chunk_index` (0~20 수준). 그러나 정규식 기반 파싱은 하지 말 것 — **JSON 의 `source_idx`, `chunk_index` 필드에서 역공학 권장**.

**Idempotency 보장:** `source_idx` 는 원본 DOCX body 순번이므로 재파싱 시 불변 (DOCX 변경이 없다면). `chunk_index` 는 `chunk_splitter` 의 결정론적 분할 결과로 재파싱 불변. 따라서 chunk_id 는 stable — §8 idempotency 유지.

> **Standard ID prefix 규약 (v1.1 확정 + v1.2.0 확장):** chunk_id 는 **`{PREFIX}-{number}` 형태 prefix 포함** (예: `ISA-300:...`, `ISQM-1:...`, `ASSR-3000:...`, `FRMK-1:...`). 이전 v1.0 draft 에서 `300:...` 형태 예시가 혼재했으나 §6.1/§6.3/§6.4 전체를 `standard_id` (`"ISA-300"`) 로 통일. v1.2.0 에서 PREFIX ∈ {ISA, ISQM, ASSR, FRMK} 4종 확장 (PK-2 3자 합의, `docs/checkpoint_4_prep.md §1.3.4`). payload 에도 `standard_id` 포함 저장 (§13).

### 6.5 Qdrant `point.id` 와의 관계 (v1.1.2 사실 교정)

Qdrant 는 `point.id` 로 **UUID 또는 양의 정수**만 허용. `chunk_id` 는 사람이 읽는 payload 필드이고, `point.id` 는 별도로 생성 — **결정성 보장 + Qdrant 요구 format**:

```python
# src/audit_parser/ingest/qdrant_writer.py
import uuid
_QDRANT_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
# 값은 RFC 4122 Appendix C 의 NAMESPACE_DNS 와 동일 (uuid.NAMESPACE_DNS 등가)

point_id = str(uuid.uuid5(_QDRANT_POINT_NAMESPACE, chunk_id))
```

`qdrant_writer.py` 담당. 본 스키마의 `chunk_id` 는 payload 에 그대로 저장되어 Qdrant scroll/filter 로 검색 가능.

**⚠ Frozen constant 경고 (v1.1.2 신설)**: `_QDRANT_POINT_NAMESPACE` 값 `6ba7b810-9dad-11d1-80b4-00c04fd430c8` 은 **동결 상수**. 변경 시 다음 breaking change 전수 발생:

- 기존 collection 의 `point.id` 전량 재계산 → 업서트 불일치 → **collection 전수 re-index** 필요 (8,626 points 기준 ~350s 재적재, Phase 4 통합 시 비례 증가).
- `.embed_cache.sqlite` 의 `chunk_id → embedding` 캐시는 namespace 변경 영향 없음 (cache key 는 `chunk_id` 자체). 단 재적재 시 Qdrant 쪽 orphan point 정리 필요.
- 본 변경은 **v2.0 MAJOR trigger** 에 해당 (C4/§2.2 SemVer 정책). v1.x 유지 범위 내에서는 namespace 변경 금지. Phase 4+ 신규 DOCX (ISQM-1 / 인증개념 / 기타인증) 통합 시에도 **동일 namespace 유지 필수**.

#### 6.5.1 ⚠ v1.1 ~ v1.1.1 spec-implementation divergence 경고 (v1.1.2 정정)

> **본 정정은 단순 typo 가 아니라 spec-implementation divergence — reproducibility hazard 수준**. 외부 컨슈머가 구 spec literal 구현 시 **collection 전수 orphan** 경험 가능.

**과거 결함**: v1.1 ~ v1.1.1 의 §6.5 는 `point_id = uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)` 로 기재되어 있었으나 실제 `qdrant_writer.py` 구현은 `NAMESPACE_DNS` 상수 사용. RFC 4122 표준 UUID 는 **한 hex digit 차이** 로 완전히 다른 값:

| namespace | UUID |
|---|---|
| `uuid.NAMESPACE_DNS` (**실 구현**) | `6ba7b81` **`0`** `-9dad-11d1-80b4-00c04fd430c8` ← |
| `uuid.NAMESPACE_URL` (**구 spec 오기재**) | `6ba7b81` **`1`** `-9dad-11d1-80b4-00c04fd430c8` |

UUID5 알고리즘의 namespace 입력이 1바이트 다르면 **모든 `point_id` 가 전혀 다른 UUID 로 산출됨**. 즉:
- **실 적재 현황**: Qdrant collection `audit_standards_회계감사기준_2025` 의 8,626 points 는 전수 **DNS-derived UUIDs**
- **구 spec literal 구현 시**: URL-derived UUIDs 생성 → 기존 point 와 단 하나도 일치 안 함 → 외부 컨슈머 (예: Phase 4+ 통합 팀, 외부 RAG deploy 팀) 가 "내가 만든 point 가 기존 DB 에 왜 없지?" 디버깅 수 시간 소요

**v1.1.2 정정**: 실 구현 기준 (`NAMESPACE_DNS`) 으로 spec 을 정정. **외부 컨슈머는 본 정정본 기준 구현 필수**. 구 v1.1/v1.1.1 spec 기반 구현은 point_id mismatch 야기하므로 즉시 본 §6.5 로 sync 요망. (Finding F2 — `docs/checkpoint_3_review.md §6`)

---

## 7. `appendix_index` (C5 대응)

### 7.1 의미

`Section.APPENDIX` 단일 enum 은 한 기준서 내 `보론 1`, `보론 2`, ... 을 payload filter 로 구분할 수 없다. Phase 2 는 `Section.APPENDIX` 를 **유지**하고 별도 정수 필드 `appendix_index` 를 추가.

### 7.2 추출 규칙

`md_parser` 의 heading_trail 기반 추출:

```python
import re
_APPENDIX_RE = re.compile(r"^보론\s*(\d+)\b")
_APPENDIX_UNNUMBERED_RE = re.compile(r"^보론(?!\s*\d)")  # "보론" 단독 or "보론 명칭"

def extract_appendix_index(
    section: Section | None,
    heading_trail: list[str],
) -> int | None:
    if section != Section.APPENDIX:
        return None
    # heading_trail 역순 탐색 — 가장 가까운 "보론 N" 을 찾음
    for heading in reversed(heading_trail):
        stripped = heading.strip()
        match = _APPENDIX_RE.match(stripped)
        if match:
            return int(match.group(1))
        # Un-numbered 보론 fallback — "보론" 단독 또는 "보론 감사보고서 예시" 등
        if _APPENDIX_UNNUMBERED_RE.match(stripped):
            return 1   # §7.2.1 규약
    return None   # APPENDIX 이지만 "보론" 텍스트조차 없는 edge case (현 실측 0건)
```

#### 7.2.1 Un-numbered 보론 → `appendix_index = 1` 규약 (v1.1 확정, 9 ISA 전수 검증)

2026-04-21 `output/md/` 전수 grep (`^### 보론`) 결과 다음 **9 ISA** 가 보론이 **단 1 개이고 번호가 없다**:

| ISA | 원본 heading | 유형 |
|---|---|---|
| ISA-230 | `### 보론(문단 1 참조)` | 공백 없이 `(` 직접 |
| ISA-300 | `### 보론 (문단 7-8과 문단 A8 –A11 참조)` | 공백 + `(` |
| ISA-510 | `### 보론 (문단 A8 참조)` | 공백 + `(` |
| ISA-570 | `### 보론 (문단 A29 및 A31-A32 참조)` | 공백 + `(` |
| ISA-620 | `### 보론 (문단 A25 참조)` | 공백 + `(` |
| ISA-700 | `### 보론 (문단 A19 참조)` | 공백 + `(` |
| ISA-705 | `### 보론 (문단 A17-A18, A25 참조)` | 공백 + `(` |
| ISA-710 | `### 보론 (문단 A5, A7 및 A10 참조)` | 공백 + `(` |
| ISA-1100 | `### 보론. 내부회계관리제도 감사보고서 사례` | `.` + 제목 |

> v1.0 draft §7.2.1 은 4 개 (ISA-230/300/510/1100) 로 기재되어 있었으나 **실제는 9 개**. devils-advocate-critic 2026-04-21 advisory 에서 지적되어 v1.1 bump 시 정정.

**번호 있는 보론 edge case — `보론N` (공백 없음):**

ISA-580 L370 (`### 보론1 (문단 2 참조)`) 와 ISA-530 L265 (`### 보론1(문단 A8 참조)`) 는 공백 없이 숫자 붙여쓰기. `_APPENDIX_RE = r"^보론\s*(\d+)\b"` 의 `\s*` (0 회 이상 공백) 가 이를 커버 → `appendix_index = 1` 정상 추출. 별도 처리 불필요.

**결정 대안:**

| 대안 | 선택 | 이유 |
|---|---|---|
| A. `appendix_index = null` | ❌ | RAG UX — 사용자 질의 `"ISA-510 보론"` 이 `appendix_index = 1` 로 매핑되면 자연스럽지만, null 이면 "부록 없음" 과 혼동. |
| **B. `appendix_index = 1`** | ✅ **채택** | 각 ISA 내 유일한 부록이므로 의미적으로 1 번째. Phase 3 Qdrant filter `appendix_index >= 1` 으로 모든 부록 chunk 일괄 조회 가능. |
| C. `appendix_index = 0` | ❌ | 0 은 "부록이지만 번호 없음" 을 표현하나 §7.3 실측 분포와 불일치 (1~6 만 관측). |

**Regex 동작 (9 ISA 전수 커버 검증):**

`_APPENDIX_RE = r"^보론\s*(\d+)\b"` 가 실패 → `_APPENDIX_UNNUMBERED_RE = r"^보론(?!\s*\d)"` 로 fallback.
- `"보론(문단 1 참조)"` → `(?!\s*\d)` 통과 (`(` 는 digit 아님) ✅
- `"보론 (문단 A5 참조)"` → `(?!\s*\d)` 통과 (공백 뒤 `(`) ✅
- `"보론. 내부회계관리제도..."` → `(?!\s*\d)` 통과 (`.` 는 digit 아님) ✅

9 ISA 전수 `appendix_index = 1` 로 매핑됨.

#### 7.2.1a FRMK spec 예외 — `special_appendix_name` 신규 필드 (v1.2.0, Phase 4)

§7.2.1 의 "ISA un-numbered 보론 = `appendix_index=1`" 규약은 **ISA 9 un-numbered 보론** 의 구조적 균일성 (각 ISA 내 유일 부록) 에 근거한다. 그러나 **FRMK (인증업무개념체계) 는 un-numbered 보론 1건 + numbered 보론 3건 (`보론 1/2/3`) 이 공존** — `appendix_index=1` 매핑 적용 시 `보론 1` 과 충돌 발생.

**v1.2.0 확정 해소 (3자 합의, 2026-04-22)**: FRMK 전용 **`special_appendix_name: str | null`** 신규 optional 필드 추가 (§12 참조). ISA 규약 (§7.2.1) 은 **불변 유지**, FRMK 만 spec-specific 처리. **대안 C (`appendix_index.minimum: 1 → 0` relax) 는 ISA 의미 파급 우려로 기각** (3 대안 비교: `docs/framework_structure_profile.md §6.2`).

##### 7.2.1a.1 처리 규약

| 스펙 | heading 유형 | `appendix_index` | `special_appendix_name` |
|---|---|:---:|---|
| ISA (9 un-numbered) | `보론`, `보론 (참조)` 등 | `1` | `null` |
| ISA (numbered) | `보론 1`, `보론 2`, … | `1`~`6` (실측 상한) | `null` |
| ISQM, ASSR | 보론 부재 (2026-04-22 실측) | — | — |
| **FRMK (un-numbered)** | `보론: 역할과 책임` | `null` | `"역할과 책임"` |
| **FRMK (numbered)** | `보론 1: …`, `보론 2: …`, `보론 3: …` | `1`, `2`, `3` | `null` |

**FRMK heading text 처리**:
- `보론:` 또는 `보론 :` (공백 뒤 콜론) 접두 → un-numbered 로 판정, 콜론 이후 텍스트가 `special_appendix_name`
- `보론 N:` (숫자 포함) → numbered, `appendix_index = N`

##### 7.2.1a.2 `StandardSpec.appendix_extractor` callable

```python
# src/audit_parser/spec/standard_spec.py
appendix_extractor: Callable[[str], tuple[int | None, str | None]]

# ISA default (isa_spec, isqm_spec, assr_spec 공유):
def _isa_default_extractor(heading: str) -> tuple[int | None, str | None]:
    """ISA 규약 — un-numbered → (1, None), numbered → (N, None)."""
    h = heading.strip()
    m_num = re.match(r"^보론\s*(\d+)", h)
    if m_num:
        return (int(m_num.group(1)), None)
    if re.match(r"^보론(?!\s*\d)", h):  # un-numbered
        return (1, None)
    return (None, None)

# FRMK override (frmk_spec):
def _frmk_extract_appendix(heading: str) -> tuple[int | None, str | None]:
    """FRMK 규약 — un-numbered → (None, name), numbered → (N, None)."""
    h = heading.strip()
    if h.startswith("보론:") or h.startswith("보론 :"):
        name = h.split(":", 1)[1].strip()
        return (None, name)
    m_num = re.match(r"^보론\s*(\d+)\s*:?\s*(.*)", h)
    if m_num:
        return (int(m_num.group(1)), None)
    return (None, None)
```

##### 7.2.1a.3 JSON Schema 영향 (§12 참조)

- `chunks[].appendix_index`: `{"type": ["integer", "null"], "minimum": 1}` — **기존 `minimum: 1` 유지** (ISA bit-level 불변)
- `chunks[].special_appendix_name`: `{"type": ["string", "null"]}` — **v1.2.0 신규 optional 필드** (`required` 배열 포함)
- ISA 36 JSON: `schema_version: "1.1.2" → "1.2.0"` + `special_appendix_name: null` 추가 in-place replace (전수, chunks 양쪽). **chunk_id / embedding 불변 → 재임베딩 불필요**.

##### 7.2.1a.4 RAG UX 부가 효과 (공동 credit)

`special_appendix_name` 필드는 payload 에 저장되어 **title 기반 검색** 가능:
- 사용자 질의 `"역할과 책임"` → FRMK un-numbered 보론 chunk 적중 가능
- Qdrant filter `payload.special_appendix_name = "역할과 책임"` 으로 직접 조회

이 부수 효과는 **초기 대안 B 제안 시 명시되지 않았으나** Domain Reviewer cross-check 중 `§7.2.1` 파편 분기 최소화 논거 검토 과정에서 발견 → 합의 근거로 편입 (Critic `docs/devils_advocate_checkpoint_4.md §11.6` 공동 credit 기록).

##### 7.2.1a.5 Backward compatibility

| 축 | 영향 | 근거 |
|---|---|---|
| ISA 36 JSON `chunk_id` | 불변 | `chunk_id` 생성 입력 (standard_id / section / heading_trail_hash / paragraph_id) 무변경 |
| ISA 36 JSON `embedding` | 불변 | `content_text` / `content_markdown` 무변경 → 재임베딩 불필요 |
| ISA 36 JSON payload | 신규 필드 추가 (`special_appendix_name: null`) | Qdrant `update_payload` 호출로 기존 point 에 필드 추가 (point.id 불변) |
| 외부 consumer | 신규 optional 필드 ignore 가능 | `additionalProperties: false` 유지, 기존 consumer 가 새 필드 무시해도 동작 |

##### 7.2.1a.6 Phase 5+ 확장 여지

ISA 9 un-numbered 보론에도 선택적으로 `special_appendix_name` 채움 가능 (현재는 `null`):
- ISA-230: `special_appendix_name="다른 기준서의 문서화 요구사항"` 등
- 변경 시 §7.2.1 재개정 필요 (MINOR bump) — Phase 4 scope 아님, Phase 5+ 재평가.

**근거 문서 cross-ref**:
- `docs/framework_structure_profile.md §6.2` — 4 대안 (A / B-v1 / B-v2 / C) 비교 + B-v2 확정 채택
- `docs/checkpoint_4_prep.md §1.5` — 2차 scaffold sync (Phase 4a Scout 합의 종결 시점) 기록
- `docs/devils_advocate_checkpoint_4.md §11` — Critic scaffold un-numbered 보론 대안 비교 + §11.6 공동 credit
- `tests/fixtures/phase4_profile_samples.json targets.FRMK-1.heading_2_sections[149-152]` — 실측 데이터

### 7.3 실측 분포 (Phase 1 MD 37 파일 기준)

| ISA | 보론 최대 번호 | 참고 |
|---|---|---|
| ISA-210 | 2 | |
| ISA-230 | 1 | (appendix 43 중 1건) |
| ISA-240 | 3 | |
| ISA-260 | 2 | |
| ISA-300 | 1 | |
| ISA-315 | 6 | **최다** — 보론 1~6 |
| ISA-510 | 1 | |
| ISA-530 | 4 | |
| ISA-540 | 2 | |
| ISA-570 | 1 | |
| ISA-580 | 2 | |
| ISA-600 | 5 | |
| ISA-700 | 1 | |
| ISA-705 | 1 | |
| ISA-706 | 4 | |
| ISA-710 | 1 | |
| ISA-720 | 2 | |
| ISA-1100 | 1 | |
| ISA-1200 | 2 | (heading 2 level — 유일) |
| ISA-620 | 1 | |

총 37 heading 발생. `appendix_index ∈ {1, 2, 3, 4, 5, 6}` 관측. 상한 6.

### 7.4 `section=APPENDIX` non-appendix_index chunk

적용지침 / 요구사항 chunk 도 `heading_trail` 에 `"보론 N"` 이 포함될 수 있으나 `section` 자체가 `APPENDIX` 인 경우에만 `appendix_index` 추출. 다른 section 은 강제 null.

### 7.5 Qdrant payload index

Phase 3 `qdrant_writer` 는 `appendix_index` 에 **keyword index** 생성 (integer 지만 filter 값 종류가 1-6 로 제한적).

---

## 8. 재임베딩 Idempotency (C4 간접 대응)

### 8.1 보장 사항

`chunk_id` 는 **`content_text` 내용에 의존하지 않는다**. 순수하게 composite key (`standard_no`, `section`, `heading_trail_hash`, `paragraph_id`, [`chunk_index` | `source_idx`]) 로 파생.

**결과:**
- `embedding` 필드를 null → List[float] 로 변경해도 `chunk_id` 불변.
- `content_text` 가 오탈자 수정으로 바뀌어도 `chunk_id` 불변 (단, heading_trail 이 변경되면 hash 가 바뀌므로 전 체인 재생성).
- `chunk_splitter` 가 토큰화 방식을 바꿔 재분할해도 `chunk_of == 1` 케이스의 id 는 불변.

### 8.2 Qdrant 업서트 전략

`qdrant_writer` 는 `chunk_id → point_id (uuid5)` 매핑이 결정론적이므로 **upsert** 안전. embedding 만 갱신되는 경우 payload 전체를 재기록해도 외부 관찰 효과는 `embedding` 값 변경 + `embedded_at` 갱신뿐.

### 8.3 예외 — MAJOR bump 시

§2 에서 정의한 대로 `chunk_id` 스킴 변경은 MAJOR bump. 이 경우 모든 point 재작성 필요 (`migrate.py` 제공 예정).

### 8.4 Idempotency 적용 범위 한정 (v1.1.1 명확화)

`chunk_id` 의 **재실행 idempotency (동일 입력 MD → 동일 출력 chunk_id)** 는 다음 조건 하에서만 보장된다:

1. **v1.1 `md_parser` 구현 (§6.4 2-Pass) 불변** — Pass 2 의 `source_idx` suffix 부착이 결정론적이려면, `source_idx` 자체가 Phase 1 MD 의 `<!-- ... idx: N ... -->` 주석에서 안정 파생되어야 함. MD 재생성 (Phase 1 re-run) 시 `source_idx` 가 변할 수 있음 → `chunk_id` 도 변화.
2. **F4 collision cluster 크기 변화 없음** — `source_idx` suffix 는 cluster 전원에 일괄 부착되므로, 새로 동일 composite key 를 갖는 chunk 가 추가 (예: 원본 개정으로 `heading_trail` 이 병합) 되면 기존 chunk 의 suffix 는 동일하지만 cluster 구성원은 확장됨. **cluster 가 줄어 단일원소가 되어도 v1.1 에서는 suffix 유지** (§6.4, first-only 금지).

**한계 실측 (Phase 2 Task #5 측정):** `source_idx` suffix 대상 cluster 중 최대 크기는 **ISA-720 에서 201 members** (stem `appendix:3d4ed148:paragraph_body`, `paragraph_id=null` + `kind=paragraph_body` fallback — §6.3). 즉 Upstage 재임베딩 시 201 chunk 이 동일 stem 을 공유하되 `#{source_idx}` 로 구분됨. 이는 MD 불변 조건 하에서 전원 안정.

**Phase 3 qdrant_writer 가 주의할 점:**
- 점증적 적재 (incremental ingest) 시 기존 collection 의 `chunk_id` 변경 감지 → 해당 point 를 **삭제 후 재삽입** (upsert 로 충분하나 stale suffix 제거 보장 필요).
- 전수 재적재 (full rebuild) 시 문제 없음.
- 재실행 전후 `METRICS.json` 의 `f4_suffix_chunks.canonical_found` 비교로 회귀 감지 (§15.1 참조).

---

## 9. `token_estimate` — tiktoken `cl100k_base`

### 9.1 계산 방식

```python
import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))
```

**입력:** `content_text` 만. `content_markdown` 이나 heading 은 포함하지 않음 (chunk 분할 결정에 사용되는 metric 이므로 embedding 입력과 동일 기준).

### 9.2 왜 cl100k_base 인가

- Upstage Solar 의 공식 tokenizer 는 공개되지 않음. KICPA 한글 토큰 비율이 OpenAI cl100k_base 에서 대략 1 char ≈ 0.6 token 수준으로 실측 적정.
- Upstage API 의 4000 토큰 상한 (passage 입력) 을 초과하지 **않는** 쪽으로 보수 추정 (cl100k_base 는 한글을 BPE 로 잘게 쪼개 Solar 실제 tokenizer 보다 **더 크게** 카운트하는 경향).
- Phase 3 에서 Upstage API 가 `usage.prompt_tokens` 를 돌려주므로 실측값 대비 caliberation 가능. 괴리가 크면 MINOR bump 로 `token_estimate_method: "tiktoken_cl100k"` enum 추가.

### 9.3 chunk_splitter 임계치

- **상한:** 4000 tokens / chunk (Upstage passage 한계).
- **안전 마진:** 3500 tokens 를 소프트 상한으로 설정. 초과 시 분할.
- **분할 단위:** 문단 경계 > 문장 경계 > 강제 분할 (char 단위). heading_trail 은 모든 분할 chunk 에 동일 유지.

### 9.4 대형 Table 처리 정책 (v1.1 신설, ISA-1200 66×2 대응)

`output/md/ISA-1200.md:1660-1780` 에 **66 rows × 2 cols 대형 테이블** 이 존재 (각 cell 에 `<br>` 다중 포함). 이는 block-atomic 원칙과 token 한계의 충돌:

**정책 (chunk_splitter, Task #3 구현 규범):**

| 조건 | 처리 |
|---|---|
| `kind == "table"` and `token_estimate ≤ 3500` | **atomic** — 단일 chunk (기본값). `table_cells` 에 2D 배열 그대로 보존. |
| `kind == "table"` and `token_estimate > 3500` | **row-wise split** — header row (첫 행) 를 모든 분할 chunk 에 복제하여 의미 보존. `chunk_of > 1`, `chunk_index` 순번 부착. `table_cells` 는 각 조각의 포함 row 들만 보유 (header + data rows). |
| `kind == "table"` and **단일 row > 3500** (이론상 edge case) | **cell-wise split 금지** — row 원자성 유지. 대신 warning 로그 + 조각 생성. 실측 0 건. |
| `kind == "block_quote"` (1×1 table → quote 승격) | 항상 atomic — 분할 금지 (문장 경계 분할도 block_quote 는 예외). |

**ISA-1200 66×2 실측 적용:**
- tiktoken cl100k_base 로 content_text 전체 token 수 추정 → 초과 시 ~30 rows 단위로 2-3 chunk 로 분할.
- 첫 chunk: `chunk_id = ISA-1200:appendix:{hash}:table#{source_idx}`, `chunk_of = N`, `chunk_index = 0`, `part_of = null`, `table_cells = [header] + rows[0:k]`.
- 후속 chunk: `chunk_id = ISA-1200:appendix:{hash}:table#{source_idx}#{chunk_index}`, `part_of = {첫 chunk id}`, `table_cells = [header] + rows[k:2k]`.

**의도:** RAG 검색 시 row 단위 독립 의미 보존 + header 중복으로 각 조각 self-contained. `<br>` multiline cell 은 row 경계를 넘지 않으므로 정보 훼손 없음.

### 9.5 ISA-1200 "용어의 정의" 헤더 중복 — 조건부 bias finding (v1.1.1)

Devils-advocate-critic 이 CHECKPOINT 2 교차검증 중 제기한 open item.

**관찰 (실측):** ISA-1200 의 66×2 용어정의 table 을 `kind == "table"` + token_estimate 초과로 인해 §9.4 규정에 따라 row-wise 3-split 수행 시, **첫 행(header)** "용어의 정의" 를 **분할 조각마다 복제**함. 결과 `content_text` 에 "용어의 정의" 문자열이 3 회 노출 (chunks 11079 / 11079#1 / 11079#2).

**잠재 bias:** passage embedding 생성 시 동일 한국어 표제어가 3 회 반복되는 구조는 Upstage Solar 의 키워드 가중치를 왜곡할 가능성이 있음. 특히 RAG query 가 "용어" / "정의" 관련 시 해당 3 조각이 동점 top-k 로 동시 채택되어 다양성이 소실될 우려.

**본 문서의 입장 (v1.1.1):**
- **§9.4 정책 자체는 유지** — row-split 시 header 복제는 self-contained chunk 생성의 기본 가정이고, 실제 RAG 답변 품질에 header 노이즈가 유의미 영향을 주는지는 **Phase 3 deploy 후에야 측정 가능**.
- **Phase 3 측정 프로토콜** (qdrant_writer Task 에 위임):
  1. `audit_standards_회계감사기준_2025` collection 생성 후 "용어의 정의" 를 포함한 10 개 seed query 로 top-5 retrieval 실시.
  2. 결과에 ISA-1200 `table#11079`, `table#11079#1`, `table#11079#2` 3 조각이 동시 출현하는 빈도를 측정.
  3. 동시 출현 ≥ 30% 이거나 평균 cosine 차이 < 0.01 이면 **MINOR bump (v1.2) 로 header-suppression 규칙 도입 검토** — 첫 조각만 header 보존, 2nd/3rd 조각은 data rows 만 유지하되 `heading_trail` 에 "용어의 정의 (이어서)" 추가하여 문맥 보충.
- **v1.1.1 단계에서는 finding 기록만 수행** — 구조 변경 없음.

**근거 문서:** `docs/devils_advocate_checkpoint_2.md` §3 (Bias finding), `docs/checkpoint_2_review.md` §3.3 (cluster 분포).

---

## 10. HTML 주석 `|` pipe escape 규약 (C11 대응)

### 10.0 정책 요약 (2026-04-21 합의)

parser-implementer 의 freeze 제안과 domain-reviewer 의 forward-compat 요구를 아래와 같이 절충:

| 주체 | 동작 | 근거 |
|---|---|---|
| **Phase 1 MD Generator (`md_renderer.py`)** | **현 상태 freeze — escape 미적용, Phase 1 MD 재생성 불필요** | §10.1 실측 escape 필요 케이스 0건 |
| **Phase 2 MD Parser (`md_parser.py`)** | **Forward-compat unescape 구현 필수** — `\|` → `|` 역변환 지원 | 미래 입력 (ISQM 1, 인증업무개념체계 DOCX) 에서 `\|` 유입 가능성 방어 |
| **Future Generator 확장** | ISQM 1 등 신규 DOCX 파싱 시점에 `_escape_pipe` 활성화 가능 | §10.3 |
| **MINOR bump** | Generator 가 escape 활성화되는 시점에 `md_renderer.SCHEMA_VERSION` 만 1.0 → 1.1 bump | Parser 는 이미 forward-compat 이므로 JSON schema bump 불필요 |

**결론:** 현재 Phase 2 는 **parser side 에서 unescape 로직을 미리 구현**하고, generator 는 필요 시점까지 손대지 않음.

### 10.1 현 실측 결과

Phase 1 output/md/ 37 파일 전수 스캔:

| 검색 패턴 | 파일 수 | 총 매칭 수 | 비고 |
|---|---|---|---|
| `\|` (escape sequence `\\\|`) | 0 | 0 | 현재 escape 미사용 |
| `\|` (raw pipe) | 37 | 9,818 | 거의 전량 table 구분자 or HTML 주석 구분자 |
| `&#124;` (HTML entity) | 0 | 0 | |

**HTML 주석 내부 필드 값에 pipe 포함 사례:** 0건. 현 `paragraph_id` 집합 (`1.`, `A1.`, `(a)`, `(i)`, `(1)`, `(가)`, `부록-1.`, `부록-A1.`, `"[?]"` placeholder) 어디에도 `|` 미포함.

**결론:** Phase 1 실측상 escape 미적용은 **현재 안전**. 그러나 Phase 2 md_parser 정규식이 fragile.

### 10.2 Phase 2 파서 규약 (필수 구현)

`md_parser.py` 의 HTML 주석 파싱 로직은 다음을 **모두** 지원해야 함:

```python
import re

_COMMENT_RE = re.compile(r"<!-- (.+?) -->")
_FIELD_SPLIT_RE = re.compile(r"\s*\|\s*")   # raw pipe 구분
_KEY_VAL_RE = re.compile(r"^([a-z_]+):\s*(.*)$")

def parse_comment_fields(inner: str) -> dict[str, str]:
    """HTML 주석 내부 `key: val | key: val` 파싱."""
    # STEP 1: escaped pipe `\|` 를 U+FFFE (placeholder) 로 치환
    # STEP 2: pipe 로 split
    # STEP 3: 각 field 에서 U+FFFE 를 다시 `|` 로 복원 (unescape)
    ESCAPE_SENTINEL = "￾"
    placeholder = inner.replace(r"\|", ESCAPE_SENTINEL)
    parts = _FIELD_SPLIT_RE.split(placeholder)
    out: dict[str, str] = {}
    for part in parts:
        m = _KEY_VAL_RE.match(part)
        if m:
            key, val = m.group(1), m.group(2)
            out[key] = val.replace(ESCAPE_SENTINEL, "|")
    return out
```

### 10.3 Phase 1 렌더러 변경 (향후 ISQM 1 등)

현 `md_renderer._build_paragraph_comment` 는 escape 미적용. 향후 타 DOCX (ISQM 1, 인증업무개념체계) 에서 `paragraph_id` 에 `|` 유입 가능성이 있을 때 다음 escape 적용:

```python
def _escape_pipe(s: str) -> str:
    return s.replace("\\", "\\\\").replace("|", "\\|")
```

**적용 대상 필드:** `para`, `parent`, `section` (기본 enum 이지만 방어). 값에 포함된 `|` 만 escape. 구분자 `|` 는 escape 하지 않음.

**현 Phase 1 산출 MD (ISA 2025) 는 재생성 불필요** — 실측 escape 필요 케이스 0건.

### 10.4 타 escape 전략 비교

| 전략 | 장점 | 단점 | 채택? |
|---|---|---|---|
| `\|` escape | 최소 변경 | 렌더러·파서 대칭 필요 | ✅ **채택** |
| `&#124;` HTML entity | Markdown 안전 | 가독성 저하, 역변환 복잡 | ❌ |
| `<!-- meta: {"para": "1."} -->` JSON inline | robust | 전면 재작성, Phase 1 MD 재생성 | ❌ (v2.0 후보) |

Phase 2 는 `\|` escape 로 확정. JSON inline 방식은 `schema_version == "2.0"` MAJOR bump 시 재검토.

---

## 11. `paragraph_links[]` 배열

문단 간 명시적 관계 그래프. Phase 1 `Block.parent_paragraph_id` (An → n) 를 1차 입력으로 하되 Phase 2 에서 cross-reference (`(문단 A7 참조)`) 추출로 확장 가능.

```json
"paragraph_links": [
  {
    "source": "ISA-200:application:e3f4a5b6:A1.",
    "target": "ISA-200:requirements:f8a1b2c3:3.",
    "link_type": "guidance_of"
  }
]
```

### 11.1 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `source` | `str` (chunk_id 참조) | ✅ | 전역 chunk_id. 같은 기준서 내 references. 크로스-기준서는 허용되지만 실측 희귀. |
| `target` | `str` (chunk_id 참조) | ✅ | 동일 형식. |
| `link_type` | `str` (enum) | ✅ | §11.2. |

### 11.2 `link_type` enum

**Phase 2 범위 (closed set):**

| 값 | 의미 | 추출 소스 |
|---|---|---|
| `"guidance_of"` | application_guidance(`An`) → requirement(`n`). Phase 1 `parent_paragraph_id` 에서 자동 생성. | Phase 1 IR |

**MINOR bump 으로 확장 예정 (Phase 2 범위 밖, 후속):**

| 후보 값 | 의미 | 추출 방식 |
|---|---|---|
| `"references"` | `(문단 A7-A10 참조)` cross-ref. | Phase 2+ regex |
| `"defined_in"` | 용어의 정의 항목 ↔ 사용처. | Phase 3+ NER |
| `"supersedes"` | 구 문단 → 신 문단 (개정 이력, 2025→2026+). | 외부 메타 |
| `"see_also"` | 느슨한 연관. | 임베딩 유사도 |

Phase 2 Task #2 는 **`guidance_of` 만** 구현. 나머지는 v1.1 MINOR bump 후 Phase 2.5 로 이월.

### 11.3 `guidance_of` 추출 규칙

Phase 1 `Block.parent_paragraph_id != None` 인 `application_guidance` chunk 마다 1 링크 생성:

```python
def make_guidance_link(
    chunk: ChunkRecord,
    standard: StandardRecord,
    by_paragraph_id: dict[str, ChunkRecord],  # Stage 2a 에서 기준서 내 조회 가능
) -> ParagraphLink | None:
    if chunk.kind != "application_guidance":
        return None
    if chunk.parent_paragraph_id is None:
        return None
    target = by_paragraph_id.get(chunk.parent_paragraph_id)
    if target is None:
        return None  # dangling parent — 경고 후 skip
    return ParagraphLink(
        source=chunk.chunk_id,
        target=target.chunk_id,
        link_type="guidance_of",
    )
```

**주의 (F4 composite key 대응):** `parent_paragraph_id` 는 단순 `"7."` 문자열이므로 같은 ISA 내 `7.` 중복 (ISA-300) 이 발생 가능. `md_parser` 는 **동일 heading_trail 상단** 의 `parent_paragraph_id` 를 매칭 (가장 가까운 상위 요구사항 scope 내).

---

## 12. 완전한 JSON Schema (Draft 2020-12)

외부 연계 시 참조할 공식 schema. `docs/json_schema_v1_0.schema.json` 으로 별도 파일화는 Phase 2 Task #2 산출.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audit-parser.local/schema/v1.0.json",
  "title": "AuditStandard ParsedStandard v1.0",
  "type": "object",
  "required": ["schema_version", "standard", "summary", "chunks", "paragraph_links"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.2.0"},
    "standard": {
      "type": "object",
      "required": ["standard_id", "standard_no", "standard_title", "source_file", "authority_base"],
      "additionalProperties": false,
      "properties": {
        "standard_id": {"type": "string", "pattern": "^(ISA-\\d{3,4}|ISQM-\\d{1,2}|ASSR-\\d{3,4}|FRMK-\\d)$"},
        "standard_no": {"type": "string", "pattern": "^\\d{1,4}$"},
        "standard_title": {"type": "string"},
        "source_file": {"type": "string"},
        "authority_base": {"type": "integer", "enum": [0, 1]}
      }
    },
    "summary": {
      "type": "object",
      "required": [
        "scope_text", "scope_markdown",
        "definitions_text", "definitions_markdown",
        "embedding", "embedded_at", "embedding_model"
      ],
      "additionalProperties": false,
      "properties": {
        "scope_text": {"type": ["string", "null"]},
        "scope_markdown": {"type": ["string", "null"]},
        "definitions_text": {"type": ["string", "null"]},
        "definitions_markdown": {"type": ["string", "null"]},
        "embedding": {
          "oneOf": [
            {"type": "null"},
            {"type": "array", "items": {"type": "number"}, "minItems": 4096, "maxItems": 4096}
          ]
        },
        "embedded_at": {"type": ["string", "null"], "format": "date-time"},
        "embedding_model": {"type": ["string", "null"]}
      }
    },
    "chunks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "chunk_id", "paragraph_id", "kind", "section", "appendix_index",
          "special_appendix_name",
          "heading_trail", "heading_trail_hash",
          "content_text", "content_markdown",
          "authority", "parent_paragraph_id", "is_application_guidance",
          "token_estimate", "chunk_index", "chunk_of", "source_idx",
          "part_of", "table_cells",
          "embedding", "embedded_at", "embedding_model"
        ],
        "additionalProperties": false,
        "properties": {
          "chunk_id": {"type": "string", "minLength": 1},
          "paragraph_id": {"type": ["string", "null"]},
          "kind": {
            "type": "string",
            "enum": [
              "requirement", "application_guidance", "sub_item", "bullet",
              "paragraph_body", "heading", "toc_entry", "table",
              "block_quote", "unknown_numbering"
            ]
          },
          "section": {
            "type": ["string", "null"],
            "enum": [
              "intro", "overall_objective", "purpose", "definitions",
              "requirements", "application", "appendix",
              "general_principles", "ethical_requirements", "engagement_acceptance",
              "planning", "materiality", "risk_assessment", "risk_response",
              "conclusion_reporting", "other_considerations", "unknown", null
            ]
          },
          "appendix_index": {"type": ["integer", "null"], "minimum": 1},
          "special_appendix_name": {"type": ["string", "null"]},
          "heading_trail": {"type": "array", "items": {"type": "string"}},
          "heading_trail_hash": {"type": "string", "pattern": "^[0-9a-f]{8}$"},
          "content_text": {"type": "string"},
          "content_markdown": {"type": "string"},
          "authority": {"type": "integer", "minimum": 0, "maximum": 1},
          "parent_paragraph_id": {"type": ["string", "null"]},
          "is_application_guidance": {"type": "boolean"},
          "token_estimate": {"type": "integer", "minimum": 0},
          "chunk_index": {"type": "integer", "minimum": 0},
          "chunk_of": {"type": "integer", "minimum": 1},
          "source_idx": {"type": "integer", "minimum": 0},
          "part_of": {"type": ["string", "null"]},
          "table_cells": {
            "oneOf": [
              {"type": "null"},
              {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {"type": "string"}
                }
              }
            ]
          },
          "embedding": {
            "oneOf": [
              {"type": "null"},
              {"type": "array", "items": {"type": "number"}, "minItems": 4096, "maxItems": 4096}
            ]
          },
          "embedded_at": {"type": ["string", "null"], "format": "date-time"},
          "embedding_model": {"type": ["string", "null"]}
        }
      }
    },
    "paragraph_links": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source", "target", "link_type"],
        "additionalProperties": false,
        "properties": {
          "source": {"type": "string"},
          "target": {"type": "string"},
          "link_type": {"type": "string", "enum": ["guidance_of"]}
        }
      }
    }
  }
}
```

---

## 13. Qdrant Payload 매핑 (Phase 3 참조)

`chunks[]` 각 항목은 Qdrant point 로 1:1 적재. payload 는 `embedding` 제외 전 필드 + `standard.*` 플랫:

```python
payload = {
    # 기준서 메타 (검색 필터 최적)
    "standard_id":      standard.standard_id,      # indexed (keyword)
    "standard_no":      standard.standard_no,      # indexed (keyword)
    "source_file":      standard.source_file,
    "authority_base":   standard.authority_base,
    # chunk 메타 (검색 필터)
    "chunk_id":             chunk.chunk_id,             # indexed (keyword, external id)
    "paragraph_id":         chunk.paragraph_id,         # indexed (keyword)
    "kind":                 chunk.kind,                 # indexed (keyword)
    "section":              chunk.section,              # indexed (keyword)
    "appendix_index":       chunk.appendix_index,       # indexed (integer)
    "heading_trail":        chunk.heading_trail,        # full array
    "heading_trail_hash":   chunk.heading_trail_hash,   # indexed (keyword)
    "parent_paragraph_id":  chunk.parent_paragraph_id,  # indexed (keyword)
    "is_application_guidance": chunk.is_application_guidance,  # indexed (bool)
    "authority":            chunk.authority,
    "token_estimate":       chunk.token_estimate,
    "chunk_index":          chunk.chunk_index,
    "chunk_of":             chunk.chunk_of,
    "source_idx":           chunk.source_idx,
    "part_of":              chunk.part_of,               # indexed (keyword, nullable)
    # 원본
    "content_text":         chunk.content_text,
    "content_markdown":     chunk.content_markdown,
    "table_cells":          chunk.table_cells,           # full 2D array (not indexed)
    # 재임베딩 캐시
    "embedded_at":          chunk.embedded_at,
    "embedding_model":      chunk.embedding_model,
}

named_vectors = {
    "passage": chunk.embedding,            # 4096d, passage 모델
    "summary": standard_summary_embedding, # 4096d, standard.summary 공유 (기준서 식별)
}
```

**indexed 필드 판단 근거:**
- `kind`, `section`, `appendix_index` — 일반 RAG filter.
- `heading_trail_hash` — F4 disambiguation, `chunk_id` 역조회용.
- `standard_no`, `paragraph_id`, `is_application_guidance` — "ISA-200 12 번 요구사항 찾기" 등 직접 lookup.

---

## 14. `md_parser` 구현 체크리스트 (Task #2 필독)

`parser-implementer` 가 `src/audit_parser/ingest/md_parser.py` 구현 시 본 체크리스트 준수:

- [ ] MD YAML frontmatter 에서 `standard_id`, `standard_no`, `standard_title`, `source_file` 추출 → `StandardRecord`.
- [ ] `authority_base = 1` hard-code (현 4 DOCX 모두 KICPA 공식).
- [ ] **`00_전문.md` skip** — filename stem `00_전문` 또는 `^\d{2}_` pattern 매칭 시 warning 없이 건너뜀. 36 JSON 생성 보장.
- [ ] HTML 주석 파싱: §10.2 `parse_comment_fields` 규약 준수 (**parser 는 unescape 반드시 구현**, generator 는 현 상태 유지 — §10.0).
- [ ] heading_trail 복원: `## H2` / `### H3` 스택 유지. `section:` 주석 발견 시 현재 section 업데이트.
- [ ] `paragraph_id = ""` (주석에 `para:` 부재) chunk 는 `{kind}#{source_idx}` fallback (§6.4). 예: `bullet#37`, `table#1669`.
- [ ] `appendix_index` 추출: `section == "appendix"` 시 heading_trail 역순 regex 매칭 (§7.2). **Un-numbered 보론 = 1** (§7.2.1).
- [ ] `parent_paragraph_id` 는 HTML 주석 `parent:` 값 그대로. dangling 체크 후 `paragraph_links` 생성.
- [ ] `token_estimate`: tiktoken cl100k_base (§9). `content_text` 기준.
- [ ] `heading_trail_hash`: §6.2 `compute_heading_trail_hash` 그대로 구현 (json.dumps ensure_ascii=False + sha1[:8]).
- [ ] `chunk_id` 생성: §6.4 **2-Pass** 의사결정표 6 케이스 구현 (Pass 1 candidate + Pass 2 collision resolve). standard_id prefix `ISA-` 포함.
- [ ] `chunk_id` **uniqueness assertion** (§6.2.1 `assert_chunk_id_uniqueness`): Pass 2 이후 전수 Counter 검증 + raise on dup. Task #5 전수 실행 시 CI check.
- [ ] `part_of` 필드 (§5.1, §6.3): `chunk_of > 1` 시 `chunk_index >= 1` 조각이 첫 조각 chunk_id 참조. 단일 chunk 는 null.
- [ ] `table_cells` 필드 (§5.1): `kind == "table"` 시 MD table row 를 inverse-parse (§10 unescape 적용). `kind == "block_quote"` → `[[cell_text]]`. 이외 null.
- [ ] F4 6 쌍 전원 고유성 검증: Task #6 검수 전 자가 점검. **특히 pair #4 (ISA-300 `7.`) 와 pair #6 (ISA-701 `4.`) 은 source_idx suffix 로 해소됨을 직접 확인** (§6.4 2-Pass).
- [ ] **heading_trail `.strip()` 정규화** (§6.2): hash 계산 전 각 원소 strip 필수. md_renderer 가 이미 trailing whitespace 를 emit 해도 parser 가 정규화.
- [ ] `summary.scope_*` / `summary.definitions_*` 추출: heading_trail 기반 필터 후 concat.
- [ ] JSON 직렬화: `ensure_ascii=False`, `indent=2`, 필드 순서 본 문서와 일치 (가독성).
- [ ] JSON Schema 검증: `docs/json_schema_v1_0.schema.json` (Task #2 부수 산출) 으로 생성 후 자동 검증.

---

## 15. 검수 시나리오 (Task #6 CHECKPOINT 2)

Domain Reviewer (Task #6) 검수 체크리스트:

### 15.1 F4 6 쌍 composite key 고유성

각 쌍의 `chunk_id` 가 전역 고유한지 직접 비교:

```bash
jq -r '.chunks[] | select(.paragraph_id == "12.") | .chunk_id' output/json/ISA-250.json | sort -u | wc -l
# 기대: 2
```

### 15.2 sample 20 JSON 검수

- 랜덤 층화추출 (ISA × section) 20 chunk.
- 원본 MD 와 대조: `content_text` 일치, `heading_trail` 완전, `parent_paragraph_id` 링크 유효.
- `appendix_index` 매핑 정확도 (보론 1-6 샘플 포함).
- `paragraph_links[]` 의 source/target 이 chunks[] 에 모두 존재.

### 15.3 schema_version + JSON Schema validation

`jsonschema` CLI 또는 Python `jsonschema.validate()` 으로 37 → 36 JSON 전수 검증. 단 1 건이라도 fail 시 Task #6 FAIL.

### 15.4 rework 상한

2 회 (Phase 1 규약 준수). 2 회 후 미해결 시 team-lead 에스컬레이션.

---

## 15a. v1.2 MINOR bump Candidates (CP3 실측 기반, 2026-04-22 신설)

CHECKPOINT 3 (Phase 3 Qdrant 적재 검수) 의 DEFER 5건 + New Findings 실측 결과를 바탕으로, **v1.2 MINOR bump 후보** 와 **v1.1.2 PATCH 선처리 항목** 을 일괄 가시화. 근거 문서: [`docs/checkpoint_3_review.md §7`](./checkpoint_3_review.md), [`docs/devils_advocate_checkpoint_3.md`](./devils_advocate_checkpoint_3.md) (예정).

| # | 후보 | 근거 섹션 | CP3 실측 결과 | Trigger 충족? | 분류 | 우선순위 |
|---:|---|---|---|---|---|---|
| 1 | **F5 suffix `{kind}#sha1-content` fallback** | §6.4, C-P2-1 | trimmed mean **42.64%** (upper bound; per-ISA max 73.8% ISA-720 / min 13.5% ISA-530) — realized ratio = UB × P(재파싱) × P(초반 삽입) × f(삽입 개수) | ⚠️ REPORT (Phase 4 실측 의무). **자동 trigger 조건: `realized_annual_cache_invalidation > 200%` → v1.2 MINOR bump 자동 발동** | **v1.2 MINOR** | **1순위** |
| 2 | Stale suffix cleanup 정규 scheduler | §8.4, C-P2-9 | stale 0 (현 시점) | ❌ 현 시점 미해당 | v1.2 MINOR (조건부) | Phase 4 stale 실측 후 재판정 |
| 3 | Phase 4 standard_id prefix 확장 (chunk_id regex) | §3 standard, §5.2, §6.1 | 현 v1.1.1 prefix (`ISA-`) 만. ISQM 1 / 인증개념 / 기타인증 통합 시 확장 필요 여부 | Phase 4 착수 시 결정 | v1.2 MINOR | Phase 4 scope (Domain Reviewer + Critic 공동 결정) |
| 4 | ~~Header-suppression rule~~ | ~~§9.5, C-P2-3~~ | 0% co-occur / 0.2046 avg dist (ISA-1200 #11079 한정) | ❌ 미해당 | **제외** | — |
| 5 | ~~soft_limit 축소~~ | ~~§9.3, C-P2-6~~ | Solar ratio mean 0.5175 / max 0.6667 (역방향, 2× 여유) | ❌ 제외 | **제외** | — |
| 6 | **F1 Named vector zero-padding 제거** | §13 payload, Finding F1 | chunk summary slot 500/500 zero + summary passage slot 36/36 zero (전수 census) | ✅ 선처리 | **v1.1.2 PATCH** | Task #9 in_progress |
| 7 | **F2 §6.5 UUID namespace fact fix + frozen note** | §6.5, Finding F2 | 기존 `NAMESPACE_URL` 문서 오류 + frozen 경고 부재 | ✅ 선처리 | **v1.1.2 PATCH** | v1.1.2 동반 (본 문서 §6.5 적용 완료) |

### 15a.1 Phase 4 의무 체크 (C-P2-1 에스컬레이션 트리거)

Critic cross-check §3.3 반영, Phase 4 CHECKPOINT 4 의 **의무 섹션 3-tier**:

1. **재파싱 빈도 기록 의무화** — ISQM-1 / 인증개념 / 기타인증 DOCX revision 기반 실측.
2. **자동 트리거 임계치**: `realized_annual_cache_invalidation > 200%` → v1.2 MINOR bump 자동 발동 (후보 #1).
3. **Phase 4 CHECKPOINT 4 scope 필수 섹션**: `docs/checkpoint_4_review.md` 내 "C-P2-1 재평가 결과" 섹션 부재 시 rework 처리.

### 15a.2 Chunk_id regex 확장 scope 결정 절차 (Phase 4) — ✅ v1.2.0 완료 (2026-04-22)

후보 #3 (Phase 4 standard_id prefix 확장) v1.2.0 에서 집행:

- **공동 결정 주체**: Domain Reviewer + Critic + Parser Implementer (3자 합의 — `docs/checkpoint_4_prep.md §1.5`)
- **변경 scope** (전수 동기화 완료):
  1. `§3 standard.standard_id pattern` — `^(ISA-\d{3,4}|ISQM-\d{1,2}|ASSR-\d{3,4}|FRMK-\d)$`
  2. `§3 standard.standard_no pattern` — `^\d{1,4}$` (relax from `^\d{3,4}$`)
  3. `§7.2.1a` FRMK spec 예외 (신설)
  4. `§12 JSON Schema` standard_id / standard_no pattern 갱신 + `chunks[].special_appendix_name` 신규 필드
- **하위 호환성** (PASS):
  - 36 ISA `standard_id` 전수 alt 1 (`ISA-\d{3,4}`) 매칭 (Critic empirical 36/36)
  - 36 ISA `standard_no` 전수 (`200`~`1200`) `^\d{1,4}$` 매칭 (relax 가 기존 데이터 해치지 않음)
  - chunk_id 8,590건 backward-compat 매칭 (Critic empirical 8,590/8,590)
  - `special_appendix_name` 신규 optional 필드 추가 — `additionalProperties: false` 유지하 추가 (MINOR)
- **Phase 5+ 확장 규약** (alt 추가 시 필수 준수):
  - **Alternation order**: longer prefix 선행 (예: `ISAE` 추가 시 `ISAE-\d{3,4}` 를 `ISA-\d{3,4}` 보다 앞에 배치 — substring greedy 함정 방어)
  - **Separator safety**: 모든 alt 가 `^[A-Z]+(-\d+)?$` 형태 유지. `:` / `#` / whitespace 포함 금지 (chunk_id separator 안전성)
  - **MAJOR lock**: Phase 4 RAG deploy 후 chunk_id format 확장 = **항상 MAJOR** (§2.2 footnote 준수)

---

## 16. Changelog

| Version | 일자 | 변경 |
|---|---|---|
| 1.0 | 2026-04-21 | 초안 확정 — Phase 2 Task #1 산출. C4 composite key, C5 appendix_index, C7/C8/C11 규약, tiktoken cl100k_base 명시. |
| 1.0 (rev 2026-04-21 PM) | 2026-04-21 | parser-implementer 5 항 답변 반영 (v1.0 draft revision): (a) `table_cells: List[List[str]] \| null` 신규 필드 — MD table inverse-parse; (b) §6.4 fallback 포맷 `{kind}#{source_idx}` 로 변경 (이전 `#{source_idx}` → 4-segment 유지 목적); (c) `standard_id` prefix `ISA-` 일관화; (d) `part_of: str \| null` 신규 필드 — chunk 분할 역추적; (e) §7.2.1 un-numbered 보론 = `appendix_index=1` 규약 (4 ISA 리스트, 추후 오류 확인); (f) §10.0 pipe escape 절충 정책 (generator freeze + parser forward-compat); (g) §1.1 prelude skip 규약 명시. |
| **1.1** | **2026-04-21 EVE** | **MINOR bump — devils-advocate-critic advisory 3 건 대응 + team-lead 지시 반영**. Backward-compatible (JSON 아직 미생성). 주요 변경: <br> • **§6.1 F4 실측 정정** — v1.0 의 "6 쌍 모두 heading_trail 해소" 주장 오류. MD 재검증 결과 **ISA-300 `7.` 와 ISA-701 `4.` 2 쌍은 heading_trail 동일 → composite key 충돌**. `f4_known_duplicates.md §4.2` open item 이 negative 로 확정. <br> • **§6.4 2-Pass chunk_id 알고리즘 신설** — Pass 1 candidate 생성, Pass 2 Counter 기반 collision 감지 후 전원에 `#{source_idx}` suffix 부착 (deterministic). F4 2 쌍 해소 확정. <br> • **§6.2 heading_trail `.strip()` 정규화 규범화** — canonical form 명시. <br> • **§6.2.1 sha1[:8] 충돌 감지 규범 신설** — 5,400 chunk × birthday 2^-32 ≈ 0.0034 건 기댓값, 비-zero. `assert_chunk_id_uniqueness` 필수. <br> • **§7.2.1 un-numbered 보론 리스트 4 → 9 정정** — ISA-230, 300, 510, 570, 620, 700, 705, 710, 1100 전수 (MD `^### 보론` grep 실측). <br> • **§9.4 대형 table 분할 정책 신설** — ISA-1200 66×2 대응, row-wise split + header replication. <br> • **§12 JSON Schema `schema_version: {"const": "1.1"}`** 갱신. <br> • MD frontmatter `md_renderer.SCHEMA_VERSION = "1.0"` **불변** (JSON 만 bump, 독립 카운터 정책 §2.3 적용). |
| **1.1.1** | **2026-04-21 EVE+** | **PATCH bump — CHECKPOINT 2 검수 및 devils-advocate-critic Task #7 (v1.1.1 batch) 대응. 구조 불변, 문서 명확화만.** 적재된 chunks·paragraph_links·payload 바이트 동등성 보장 → 재임베딩·재적재 불필요. 주요 변경: <br> • **§2.2 PATCH row 추가 + 조건부 MINOR 판정 각주** — v1.1 의 `chunk_id` 출력 변경이 MINOR 로 처리된 근거 2 조건 (v1.0 데이터 0건, 외부 consumer 부재) 명시. Phase 4 RAG deploy 후에는 `chunk_id` format 확장이 **항상 MAJOR** 라는 forward 규약 고정. <br> • **§8.4 Idempotency 적용 범위 한정 신설** — `source_idx` suffix 의 재실행 idempotency 가 보장되는 2 조건 (md_parser 불변 + cluster 구성원 불변) 명시. 최대 cluster 실측 **ISA-720 201 members** (`appendix:3d4ed148:paragraph_body` stem) 기록. Phase 3 incremental ingest 시 stale suffix 처리 지침 추가. <br> • **§9.5 ISA-1200 header 중복 bias finding 신설** — "용어의 정의" 3회 복제가 Upstage passage embedding 을 왜곡할 가능성. **Phase 3 측정 프로토콜 (10 seed query top-5, 동시 출현 ≥30% 또는 cosine Δ<0.01 시 v1.2 MINOR bump 로 header-suppression 규칙 도입)** 을 조건부 이월. 현 v1.1.1 단계에서는 finding 기록만. <br> • **§12 JSON Schema `schema_version: {"const": "1.1.1"}`** 갱신. <br> • 근거 문서: [`docs/devils_advocate_checkpoint_2.md`](./devils_advocate_checkpoint_2.md) §2/§3, [`docs/checkpoint_2_review.md`](./checkpoint_2_review.md) §3.3. |
| **1.2.0** | **2026-04-23** | **MINOR bump — Phase 4 Pre-Kickoff PK-2 + Phase 4a Scout 3자 합의 결과 일괄 반영. backward-compat 보장 (36 ISA `standard_id` / `standard_no` / `chunk_id` 8,590건 전수 매칭, `special_appendix_name: null` in-place 추가).** 주요 변경: <br> • **§3 / §12 `standard_id` pattern 확장** — `^ISA-\d{3,4}$` → `^(ISA-\d{3,4}\|ISQM-\d{1,2}\|ASSR-\d{3,4}\|FRMK-\d)$` (PK-2 3자 합의 — Domain Reviewer + parser-implementer + devils-advocate-critic, `docs/checkpoint_4_prep.md §1.3.4`). Critic empirical cross-check 36/36 + 8,590/8,590 + suffix depth `{0:4209, 1:4379, 2:2}` PASS. <br> • **§3 / §12 `standard_no` pattern relax** — `^\d{3,4}$` → `^\d{1,4}$`. ISQM-1 / FRMK-1 의 1-digit 수용. ISA 36 전수 (`200`~`1200`) 새 regex 통과. <br> • **§7.2.1a 신설 — FRMK spec 예외** (un-numbered 보론 처리, `special_appendix_name` 신규 필드). 4 대안 비교 (A=appendix_index=0 / B-v1=null only / B-v2=신규 필드 / C=minimum relax) 중 **B-v2 채택**. ISA 36 JSON bit-level 불변 + RAG UX 개선 (title 기반 검색) + `§7.2.1` 파편 분기 회피. 공동 credit (Critic `docs/devils_advocate_checkpoint_4.md §11.6`). <br> • **§12 `chunks[].special_appendix_name` 신규 optional 필드** — `{"type": ["string", "null"]}`. `appendix_index.minimum: 1` 유지 (relax 안 함). `required` 배열 포함, `additionalProperties: false` 유지. <br> • **§15a.2 Phase 5+ 규약 추가** — alternation order (longer prefix 선행), separator safety (`^[A-Z]+(-\d+)?$` 유지), MAJOR lock 재확인. <br> • **chunk_splitter 2-level assertion guard** — Critic β-1 (`chunk_id` suffix chain max 2-level, 3-level 시도 시 assertion fail). Phase 4 §9.5 추가 split 측정 시 `ISA-540 table#0#1` 까지만 허용. <br> • **§12 `schema_version: {"const": "1.2.0"}`** 갱신. <br> • 추가 sync 대상 (parser-implementer 4 commit chain Task #6 범위): `src/audit_parser/spec/standard_spec.py` (신규) + 4 spec 파일 + `ChunkRecord.special_appendix_name` 필드 추가 / `tests/fixtures/json_schema_v1_1.schema.json` → `json_schema_v1_2.schema.json` rename + const + special_appendix_name 추가 / `output/json/ISA-*.json` 36 파일 schema_version + `special_appendix_name: null` 전수 in-place / `chunk_splitter.py` 2-level assertion. <br> • **분할 진행** (4b-1 / 4b-2): 본 v1.2.0 bump 6-file atomicity 는 **4b-1** 에서 완결. 4b-2 (ISQM/ASSR/FRMK spec + TwoColumnTableBodyParser) 는 schema 영향 없음. <br> • 근거 문서: `docs/checkpoint_4_prep.md` (§1 PK-2 / §0.2 Critic 선행 리스크 / §3 Mini Golden 3안), `docs/framework_structure_profile.md §6.2` (B-v2 채택), `docs/{isqm,assurance_other}_structure_profile.md` (Scout), `docs/devils_advocate_checkpoint_4.md` (Critic scaffold v0 + 2차 sync). |
| **1.1.2** | **2026-04-22** | **PATCH bump — CHECKPOINT 3 (Phase 3 Qdrant 적재 검수) 의 2 Finding + Critic cross-check 강화 권고 3건 일괄 반영. 문서 + qdrant_writer.py 업서트 로직 최적화, schema 구조 불변.** 주요 변경: <br> • **Finding F1 — Named vector zero-padding 제거 (Task #9 parser-implementer rework, 1/2 rework budget)**: chunk points 의 `summary` 슬롯 + summary points 의 `passage` 슬롯에 전수 `[0.0]*4096` 이 적재되던 현상 확정 (chunk 500/500 census + summary 36/36 census, Domain Reviewer + Critic 양측 독립 census 일치). `qdrant_writer.py` 업서트 시 사용되지 않는 named vector 슬롯을 **per-point omit** 하여 `indexed_vectors_count 17,252 → 8,626` 감소 (≈50%), 저장 **~137~141 MB 절감** (Domain 137MB 추정 / Critic Qdrant scroll 141MB census — ±5% 일관). HNSW edges 276,032 → ~138,016. 재적재 필요하나 embedding cache (SQLite) 는 보존. <br> • **§6.5 namespace spec-implementation divergence 사실 교정 (독립 bullet)**: 구 v1.1 ~ v1.1.1 §6.5 의 `uuid.NAMESPACE_URL` (UUID `6ba7b811-...`) 기재는 **reproducibility hazard 수준의 spec-implementation divergence** — 실제 `qdrant_writer.py` 구현은 `_QDRANT_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")` (NAMESPACE_DNS 등가) 사용. 한 hex digit 차이로 UUID5 출력 전수 상이 → 외부 컨슈머 literal 구현 시 collection 전수 orphan. v1.1.2 에서 **실 구현 기준으로 spec 정정 + §6.5.1 경고 박스 신설**. 외부 컨슈머는 본 정정본 기준 재sync 필수. <br> • **§6.5 Frozen constant 경고 신설**: `_QDRANT_POINT_NAMESPACE` 변경 = v2.0 MAJOR trigger. collection 전수 re-index + embedding cache orphan. Phase 4+ 신규 DOCX 통합 시에도 동일 namespace 유지 의무. <br> • **C-P2-1 F5 drift 기록 (Phase 4 재평가 trigger)**: per-ISA trimmed mean 42.64%, max 73.8% (ISA-720), min 13.5% (ISA-530). 본 수치는 **theoretical upper bound** — realized ratio = UB × P(재파싱) × P(초반 삽입) × f(삽입 개수). Phase 4 실사용 시 realized ratio 측정 후 v1.2 결정 (자동 trigger: realized_annual_cache_invalidation > 200%). prep §3.4 Phase 4 재평가 약속 실질 이행 보장. <br> • **§15a v1.2 MINOR bump Candidates 표 신설** — CP3 DEFER 5건 + Findings 재분류 일괄 가시화. F5 fallback 1순위 (연환산 > 200% 자동 trigger) + stale cleanup + Phase 4 prefix + F1/F2 v1.1.2 PATCH 선처리 기재. Phase 4 CHECKPOINT 4 의무 3-tier (재파싱 빈도 기록 / 200% trigger / 필수 섹션 — Critic cross-check §3.3 반영) 명시. <br> • **§12 JSON Schema `schema_version: {"const": "1.1.2"}`** 갱신. 추가 sync 대상 (parser-implementer 원자 커밋 처리 — Task #9 범위): `src/audit_parser/ingest/types.py JSON_SCHEMA_VERSION` / `tests/fixtures/json_schema_v1_1.schema.json` const / `scripts/validate_json.py` drift gate / `output/json/*.json` 36 파일 schema_version 문자열 전수 교체. <br> • 근거 문서: [`docs/checkpoint_3_review.md`](./checkpoint_3_review.md) (Critic cross-check 2026-04-22 PASS CONFIRMED, 5항 반영), [`docs/devils_advocate_checkpoint_3.md`](./devils_advocate_checkpoint_3.md) (Task #8 예정). |

---

## 17. 참조 문서

- [`PLAN.md`](../PLAN.md) — 전체 설계 (§4 Phase 2)
- [`CLAUDE.md`](../CLAUDE.md) — 개발 컨벤션
- [`docs/PHASE_1_REPORT.md`](./PHASE_1_REPORT.md) — Phase 1 완료
- [`docs/numbering_strategy.md §10`](./numbering_strategy.md) — abstractNumId counter
- [`docs/checkpoint_1_review.md §R6`](./checkpoint_1_review.md) — CHECKPOINT 1 PASS
- [`docs/devils_advocate_checkpoint_1.md`](./devils_advocate_checkpoint_1.md) — C1~C11
- [`docs/f4_known_duplicates.md`](./f4_known_duplicates.md) — F4 6 쌍 enumeration
- [`docs/isa_structure_profile.md`](./isa_structure_profile.md) — Phase 0 DOCX 프로파일
- [`src/audit_parser/ir/types.py`](../src/audit_parser/ir/types.py) — Phase 1 IR
- [`src/audit_parser/convert/md_renderer.py`](../src/audit_parser/convert/md_renderer.py) — MD frontmatter + HTML 주석

---

**서명:** `audit-standard-domain-reviewer` — Phase 2 Task #1 공식 산출물. 본 스키마 MINOR+ 변경은 본 검수자와 DM 합의 후 개정. MAJOR bump 는 team-lead 승인 필수.
