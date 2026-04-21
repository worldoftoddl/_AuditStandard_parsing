# Numbering Strategy — `word/numbering.xml` 파싱·카운터 replay 설계

**작성자**: `audit-standard-domain-reviewer`
**작성일**: 2026-04-20
**대상**: `src/audit_parser/ir/numbering.py` 구현(Task #3) + `structure.py` 소비(Task #4)
**근거 데이터**:
- `docs/isa_structure_profile.md` §3 (문단번호 체계 실측)
- `tests/fixtures/isa_profile_samples.json` (key_abstractNums, top_numId_usage)
- `raw/0. 회계감사기준 전문(2025 개정).docx`

> 본 문서는 Phase 1 착수 전 필수 설계 산출물이다. `parser-implementer` 는 본 문서의 §3 매핑, §4 카운터 replay, §5 fallback 규칙, §6 인터페이스 초안을 **그대로 구현**해야 한다. 수정이 필요하면 DM 으로 합의 후 본 문서를 개정한다.

---

## 0. Why — 왜 설계 문서가 먼저인가

Word 문서에서 "1.", "A1." 같은 **문단번호는 본문 텍스트에 저장되지 않는다**. 자동 넘버링 엔진이 `w:numPr` 의 `numId` + `ilvl` 조합을 `word/numbering.xml` 에 정의된 `lvlText`(예: `%1.`, `A%1.`) 템플릿에 대입해 렌더링 시점에 생성한다. 따라서 파서는 Word 의 카운터 상태를 **그대로 replay** 해야 ISA 원문과 동일한 번호(`1`, `2`, `A1`, `A2` …)를 복원할 수 있다.

실측 복잡도(Phase 0, CHECKPOINT 0):
- 총 **742 numId 인스턴스**
- 핵심 `abstractNumId` 5 계열: `{15, 51, 70, 98, 140}`
- 9 종 이상의 `lvlText` 패턴(decimal, lowerLetter, lowerRoman, upperLetter, upperRoman, bullet, `○`, `\uf097`)
- `numId='0'` 특수 케이스 **303 건** (명시적 번호 제거 마커)
- `lvlOverride` 는 드물지만 존재

잘못 설계하면 **전체 문단 번호가 한 칸씩 밀리거나**, 요구사항·적용지침 구별이 붕괴되어 검색·인용 품질이 근본적으로 망가진다.

---

## 1. `word/numbering.xml` 구조 요약

### 1.1 최상위 계층

```
<w:numbering>
  ├── <w:abstractNum w:abstractNumId="51">   ← "번호 스타일 템플릿" (공유 가능)
  │     ├── <w:lvl w:ilvl="0"> … </w:lvl>
  │     ├── <w:lvl w:ilvl="1"> … </w:lvl>
  │     └── …  (ilvl 0~8, 최대 9 단계)
  │
  └── <w:num w:numId="118">                   ← "문단이 참조하는 인스턴스"
        ├── <w:abstractNumId w:val="51"/>     ← abstractNum 연결
        └── [<w:lvlOverride w:ilvl="0">       ← (선택) 카운터 재시작
              <w:startOverride w:val="1"/>
            </w:lvlOverride>]
```

- **`w:abstractNum`**: 재사용 가능한 "번호 매기기 스타일". `ilvl 0~8` 각각에 `lvlText`, `numFmt`, `start`, `suff`, `pStyle` 이 정의됨.
- **`w:num`**: 본문 문단이 실제로 참조하는 인스턴스. 여러 `w:num` 이 같은 `w:abstractNumId` 를 공유할 수 있다. **한 ISA 기준서 = 1 개 `numId`** 패턴이 대부분이므로(§3.3 실측), 각 기준서 경계에서 카운터가 자동 리셋된다.
- **`w:lvlOverride`**: 특정 `w:num` 이 abstractNum 의 start 값을 덮어쓸 때 사용. `w:startOverride` 로 카운터 재시작 가능.

### 1.2 본문 문단의 참조

문단 `<w:p>` 내부:

```
<w:pPr>
  <w:numPr>
    <w:ilvl w:val="0"/>
    <w:numId w:val="118"/>
  </w:numPr>
</w:pPr>
```

- `numId` 없으면 → 번호 없는 단락 (`None`)
- `numId=0` 이면 → **명시적 번호 제거** (스타일 상속으로 붙던 번호를 제거). §4.3 참조.

### 1.3 `lvlText` 템플릿 문법

| 토큰 | 의미 |
|---|---|
| `%1` | ilvl=0 의 현재 카운터 값 |
| `%2` | ilvl=1 의 현재 카운터 값 |
| … | … |
| `%N` | ilvl=N-1 의 현재 카운터 값 |
| 그 외 문자 | 리터럴 (예: `A`, `.`, `(`, `)`) |

`numFmt` 로 변환:
- `decimal` → 1, 2, 3…
- `lowerLetter` → a, b, c…
- `lowerRoman` → i, ii, iii…
- `upperLetter` → A, B, C…
- `upperRoman` → I, II, III…
- `bullet` → 고정 glyph (lvlText 자체가 bullet 문자, 카운터 값 무시)

예시:
- `lvlText='%1.'`, `numFmt='decimal'`, 카운터=5 → `"5."`
- `lvlText='A%1.'`, `numFmt='decimal'`, 카운터=3 → `"A3."`
- `lvlText='(%2)'`, `numFmt='lowerLetter'`, 카운터=2 → `"(b)"`

> **주의**: `A%1.` 에서 `A` 는 리터럴이다. 카운터는 `%1` 하나만 존재하며, `numFmt='decimal'` 이 `%1` 에만 적용된다.

---

## 2. 핵심 abstractNum 인벤토리 (실측)

`tests/fixtures/isa_profile_samples.json` 에서 추출한 **5 개 핵심 abstractNum 의 전체 ilvl 테이블**이다. 나머지 abstractNum 은 §5 fallback 처리.

### 2.1 abstractNumId 15 · 51 (적용지침 계열)

| ilvl | lvlText | numFmt | 해석 |
|:---:|:---:|:---|:---|
| 0 | `A%1.` | decimal | **적용지침 번호** (`A1.`, `A2.`, …) |
| 1 | (없음) | bullet | 불릿 (적용지침 내부) |
| 2 | `○` | bullet | 중첩 불릿 (O 문자 glyph) |
| 3 | `%4.` | decimal | 하위 번호 (ilvl=3 카운터) |
| 4 | `%5.` | lowerRoman | 하위 로마자 (i, ii, …) |
| 5 | `%6.` | lowerRoman | 더 깊은 로마자 |
| 6 | `%7.` | decimal | 깊은 decimal |
| 7 | `%8.` | upperLetter | 깊은 대문자 |
| 8 | `%9.` | lowerRoman | 가장 깊은 로마자 |

### 2.2 abstractNumId 70 · 98 · 140 (요구사항 계열)

| ilvl | lvlText | numFmt | 해석 |
|:---:|:---:|:---|:---|
| 0 | `%1.` | decimal | **요구사항 번호** (`1.`, `2.`, …) |
| 1 | `(%2)` | lowerLetter | 하위 `(a)`, `(b)`, … |
| 2 | `(%3)` | lowerRoman | 더 하위 `(i)`, `(ii)`, … |
| 3 | `%4.` | lowerLetter | 깊은 letter |
| 4 | `%5.` | lowerRoman | 깊은 로마자 |
| 5 | `%6.` | lowerRoman | |
| 6 | `%7.` | decimal | |
| 7 | `%8.` | upperLetter | |
| 8 | `%9.` | lowerRoman | |

> 세 계열(70, 98, 140) 의 **ilvl 0~8 템플릿이 완전히 동일**하다. 왜 3 개로 분리돼 있는지는 Word 의 스타일 상속 역사 때문으로 보이며, 파서는 **3 개 모두를 동등하게 처리**하면 된다.

### 2.3 핵심 numId → abstractNumId 매핑 (top 10)

| numId | abstractNumId | 문단 수 | 역할 |
|:---:|:---:|:---:|:---|
| 86 | 140 | 418 | 요구사항 (최다) |
| 0 | — | 303 | **명시적 번호 제거** (§4.3) |
| 113 | 98 | 247 | 요구사항 |
| 118 | 51 | 222 | 적용지침 (최다) |
| 87 | 140 | 186 | 요구사항 |
| 78 | 140 | 142 | 요구사항 |
| 8 | 72 | 138 | 불릿 (abstractNum 72 는 bullet 계열) |
| 432 | 1 | 84 | 요구사항 (abstractNum 1 → §5 fallback 대상) |
| 51 | 51 | 66 | 적용지침 |
| 138 | 70 | 66 | 요구사항 |

---

## 3. abstractNum → kind 매핑 테이블 (동적)

파서는 다음 **판정 순서**로 `kind` 를 결정한다. **abstractNumId 화이트리스트 hard-coding 은 금지** — 동일 조건의 신규 abstractNum 도 자동 포섭되어야 한다.

### 3.1 ilvl=0 판정 (최상위 번호)

| 조건 | kind |
|---|---|
| `lvlText == '%1.'` && `numFmt == 'decimal'` | `requirement` |
| `lvlText == 'A%1.'` && `numFmt == 'decimal'` | `application_guidance` |
| `numFmt == 'bullet'` (lvlText 무관) | `bullet` |
| 그 외 (lowerRoman `%1.`, upperLetter `%1.`, `(%1)` decimal 등) | `unknown_numbering` + 경고 |

> **중요**: 5 개 핵심 계열 `{15, 51, 70, 98, 140}` 은 위 조건에 자동 매칭되므로 별도 분기가 불필요하다. 단, §5.1 의 "확인된 패턴 캐시" 는 첫 등장 시 INFO 로그를 찍어 운영 가시성을 확보한다.

### 3.2 ilvl ≥ 1 판정 (하위 항목)

| 조건 | kind |
|---|---|
| 모든 ilvl ≥ 1 (lowerLetter, lowerRoman, decimal, bullet, `○` 등) | `sub_item` |

`sub_item` 은 상위 번호 문단의 **하위 목록**으로 간주되어, `parent_paragraph_id` 가 **직전 동일 numId 의 ilvl=0 문단 id** 로 연결된다(§4.2 EC-7).

### 3.3 예외: isa_structure_profile §3.4 에서 관찰된 비표준 패턴

| 패턴 | abstractNumId 예 | 예상 kind |
|---|---|---|
| `(%1)` lowerLetter (ilvl=0 이 `(a)` 부터 시작) | 0, 10, 20, 21, 24, 36 | `unknown_numbering` → ilvl 재해석 검토 |
| `(%1)` decimal | 131, 143 | `unknown_numbering` |
| `%1.` lowerRoman (ilvl=0 이 `i.`) | 45, 50, 60, 86, 108 | `unknown_numbering` |
| `%1)` lowerRoman | 63, 111, 135, 177 | `unknown_numbering` |
| `%1.` upperLetter | 109 | `unknown_numbering` |
| `%1.` upperRoman | 161 | `unknown_numbering` |
| `%1` decimal (마침표 없음) | 38 | `unknown_numbering` |
| `\uf097` bullet | 72 | `bullet` |

> 위 패턴들은 **ilvl=0 이면서도 의미상 "하위 항목"** 일 가능성이 크다(상위 블록이 이미 있는데 sub-list 만 별도 numId 로 분리된 경우). 파서는 이들을 `unknown_numbering` + 경고로 태깅하고, `structure.py` 가 heading_trail 과 직전 문단 문맥으로 재분류할 수 있게 **원본 lvlText / numFmt 를 payload 에 보존**한다.

---

## 4. 카운터 replay 알고리즘

> ⚠️ **DEPRECATED (2026-04-21)**: §4.1~§4.4 의 "numId 기반 독립 카운터" 설계는 CHECKPOINT 1 F4 결함(93건 duplicate marker)의 원인으로 확인되어 **§10 (abstractNumId 기반 공유 카운터)** 로 supersede 되었다. 신규 구현자는 §10 pseudocode 를 그대로 따라야 한다. 본 §4.x 는 설계 진화 이력으로 보존한다.

### 4.1 설계 원칙 (DEPRECATED — §10 supersede)

1. **numId 별 독립 카운터**: 동일 문서 내 `numId=86` 과 `numId=113` 은 서로 다른 카운터를 유지한다.
2. **ilvl 9 칸 스택**: 각 numId 별로 `counters[numId] = [c0, c1, …, c8]`.
3. **상승(descend) 시 하위 리셋**: 현재 ilvl=1 에서 ilvl=2 로 내려가면 `c2` 를 해당 ilvl 의 `start` 값으로 초기화.
4. **하강(ascend) 시 하위 값 무효**: ilvl=2 에서 ilvl=0 으로 올라가면 `c1`, `c2` 는 "다음 descend 시 리셋" 상태로 표시.
5. **현재 ilvl 증가**: 문단을 만날 때마다 해당 ilvl 카운터 +1.
6. **`w:lvlOverride` + `w:startOverride`**: `numId` 인스턴스 생성 시 ilvl 의 start 값을 초기화. 파서는 **문서 스캔 시작 시** 이 값을 `counters[numId][ilvl]` 에 반영.
7. **기준서 경계 리셋 불필요**: 실측상 각 기준서가 고유 numId 를 사용하므로(대부분), 기준서가 바뀌면 자연스럽게 "처음 쓰는 numId" 가 되어 `start=1` 부터 시작. 단, 같은 numId 가 여러 기준서에 걸치는 드문 경우(top_numId 테이블의 numId=86 등)는 §4.4 에서 다룸.

### 4.2 의사코드

```python
class CounterState:
    """numId 별 ilvl 0~8 카운터."""
    # 최초값은 abstractNum 의 start + lvlOverride 반영
    counters: dict[str, list[int]]
    starts: dict[str, list[int]]           # 리셋 시 복귀할 값
    last_ilvl: dict[str, int | None]       # 직전 문단의 ilvl

def advance(numId: str, ilvl: int) -> list[int]:
    """문단을 하나 만났을 때 호출. 해당 문단에 '확정된' 카운터 튜플을 반환."""
    prev = last_ilvl.get(numId)
    # 1) descend: 하위 ilvl 내려왔으면 그 ilvl 및 아래를 start 로 리셋
    if prev is not None and ilvl > prev:
        for lv in range(prev + 1, ilvl + 1):
            counters[numId][lv] = starts[numId][lv]
    # 2) 현재 ilvl +1
    counters[numId][ilvl] += 1
    # 3) ilvl 보다 깊은 값은 "다음 descend 시 리셋" — 여기서는 건드리지 않고 last_ilvl 만 갱신
    last_ilvl[numId] = ilvl
    return tuple(counters[numId][: ilvl + 1])
```

**렌더링**은 `render(abstractNum, ilvl, counter_tuple) → str` 로 분리:

```python
def render(abstract_num, ilvl, counter_tuple) -> str:
    lvl = abstract_num.levels[ilvl]
    if lvl.numFmt == 'bullet':
        return ''  # 불릿은 번호 없음 (lvlText 는 glyph 이지만 paragraph_id 로는 공백)
    text = lvl.lvlText
    # %1 ~ %9 치환
    for i, val in enumerate(counter_tuple, start=1):
        placeholder = f'%{i}'
        if placeholder in text:
            text = text.replace(placeholder, format_num(val, lvl.numFmt_for_level(i-1)))
    return text
```

> **핵심 디테일**: `lvlText='(%2)'` 일 때 `%2` 는 ilvl=1 의 카운터이고, 그 렌더링 포맷은 **ilvl=1 의 numFmt** (= `lowerLetter`) 이다. 즉, `%N` placeholder 의 포맷은 "해당 `%N` 이 가리키는 ilvl 의 numFmt" 에서 가져온다. `format_num(val, numFmt_for_level(i-1))` 의 `numFmt_for_level(i-1)` 이 그것.

### 4.3 `numId='0'` 처리 (303 건 특수 케이스)

- `<w:numId w:val="0"/>` 는 "상속된 번호 매기기를 **제거**" 하는 Word 의 특수 마커.
- 파서 규약:
  - `numId == '0'` (str) → `paragraph_id = None`, `kind = 'paragraph'` (본문 단락), **메타에 `numbering_suppressed = True`** 표시.
  - `numId == None` (numPr 자체가 없음) → `paragraph_id = None`, `kind = 'paragraph'`, `numbering_suppressed = False`.
- 구분 사유: 운영 중 "왜 이 문단에 번호가 없지?" 디버깅에 필요. 의도적 제거 vs 원래 없음을 로그·payload 로 구분해야 이슈 re-triage 가 가능하다.

### 4.4 `lvlOverride` / 동일 numId 의 기준서 간 재사용

실측상 top_numId 중 `numId=86` 은 418 회 사용되어 **여러 기준서에 걸쳐 등장**할 가능성이 있다. 이 경우:

1. **옵션 A (채택)**: 파서는 카운터를 끊지 않고 연속 누적한다. 이후 `structure.py` 가 "기준서 경계(heading 1 변경)" 에서 **paragraph_id 를 기준서별로 재-라벨링**한다. 즉, numbering 계층은 순수하게 Word 의 상태를 복원하는 역할만 하고, "기준서 내 1 번부터 시작" 보장은 상위 레이어에서 한다.
2. **옵션 B (기각)**: 기준서 경계에서 강제 리셋. → `lvlOverride` 가 없는데 리셋하면 Word 원문과 불일치. 오탐 위험.

> 의사결정: **옵션 A**. 구현 복잡도가 낮고 Word 원문과 1:1 대응이 보장된다. 만약 CHECKPOINT 1 검수에서 실제로 번호가 밀린 사례가 발견되면 옵션 B 로 전환 검토.

### 4.5 EC-7 연계 — parent_paragraph_id 스택

`structure.py` 담당이지만 `numbering.py` 가 제공해야 하는 데이터:

- 각 문단마다 `(numId, ilvl, counter_tuple, rendered)` 반환.
- `structure.py` 는 numId 별 "최근 ilvl=0 문단 id" 를 스택으로 유지하여, ilvl ≥ 1 문단의 `parent_paragraph_id` 를 해당 스택 top 으로 연결.

---

## 5. 동적 Fallback 처리 흐름

### 5.1 미지 abstractNumId / lvlText 조합 만났을 때

```
문단 P(numId=X, ilvl=Y) 진입
   ↓
numId → abstractNumId 매핑 조회
   ├─ numId 자체가 missing → kind='unknown_numbering', warn once per numId
   └─ abstractNumId 획득
        ↓
   abstract_nums[abstractNumId][ilvl] 조회
        ├─ 해당 ilvl 정의 없음 → kind='unknown_numbering', warn once per (abstractNumId, ilvl)
        └─ (lvlText, numFmt) 획득
             ↓
        §3.1 / §3.2 매핑 적용
             ├─ 매칭 → kind 확정 (requirement / application_guidance / sub_item / bullet)
             └─ 미매칭 → kind='unknown_numbering', warn once per (lvlText, numFmt)
```

### 5.2 경고 정책

- **Python `warnings.warn(…, UserWarning)`** 사용 (표준 라이브러리).
- 한 문서 파싱 세션 내에서 **동일 (numId / abstractNumId-ilvl / lvlText-numFmt) 조합당 한 번**만 발생(중복 억제 — `_seen: set[tuple]` 로 관리).
- 메시지 포맷:
  - `[numbering] unknown pattern: abstractNumId=X, ilvl=Y, lvlText='...', numFmt='...' → tagging kind='unknown_numbering'`
  - `[numbering] missing numId={X} in numbering.xml → tagging kind='unknown_numbering'`
- **파싱 계속**: 경고 후에도 문단은 파이프라인에 남으며 `paragraph_id` 는 공백 문자열(`''`) + `numbering_suppressed=False` + `numbering_raw={numId, ilvl, lvlText, numFmt}` 메타로 기록한다. Phase 2 스키마에서 후속 재분류 가능.
- **임계치 검수**: `unknown_numbering` 문단 비율이 전체의 **5 %를 초과하면** Domain Reviewer 재검토 + parser-implementer rework (PLAN.md CHECKPOINT 1 기준).

### 5.3 bullet · `○` · `\uf097` 처리

| lvlText | numFmt | 처리 |
|---|---|---|
| `''` (빈 문자열) | bullet | `paragraph_id=''`, `kind='bullet'`, 렌더링 시 `*` 또는 `-` 로 Markdown 대체 |
| `○` | bullet | 동일. `○` 는 원본 시각 정보로 `numbering_raw` 에 보존 |
| `\uf097` | bullet | Symbol 폰트 PUA 문자. 동일 처리. md_renderer 는 `*` 로 정규화 |

`bullet` 은 `paragraph_id` 가 없으므로 **chunk 분할 단위로 쓰이지 않는다**. 상위 번호 문단(`requirement` / `application_guidance`) 의 본문에 **이어 붙인다** (`structure.py` 에서 합쳐서 하나의 chunk 로 구성).

### 5.4 ilvl ≥ 2 의 lowerRoman · decimal (`%4.`, `%5.`)

- abstractNum 15/51 의 ilvl=3 은 `%4.` decimal — 이는 `%4` (ilvl=3 카운터) 를 decimal 로 렌더 → `"1."`, `"2."` 형.
- abstractNum 15/51 의 ilvl=4 는 `%5.` lowerRoman → `"i."`, `"ii."` 형.
- 이들 모두 `kind='sub_item'` 로 통일. 렌더 문자열은 `paragraph_id` 에 저장되어 heading_trail 에서 참조 가능.

### 5.5 기준선(sanity baseline)

파싱 종료 시 다음 카운터를 로그로 출력(metrics):

```
[numbering] total paragraphs with numPr : <N>
[numbering] kind=requirement           : <N>
[numbering] kind=application_guidance  : <N>
[numbering] kind=sub_item              : <N>
[numbering] kind=bullet                : <N>
[numbering] kind=paragraph (numId=0)   : 303 expected / <N> actual
[numbering] kind=unknown_numbering     : <N>  ← 5% 임계치 비교
```

---

## 6. `src/audit_parser/ir/numbering.py` 인터페이스 초안

**구현자(`parser-implementer`) 참고용 시그니처만 제시**. 세부 구현(예외 클래스, 로깅 형식)은 구현자 재량.

### 6.1 데이터 클래스

```python
from dataclasses import dataclass
from typing import Literal, Optional

NumFmt = Literal[
    "decimal", "lowerLetter", "lowerRoman",
    "upperLetter", "upperRoman", "bullet",
]

Kind = Literal[
    "requirement",
    "application_guidance",
    "sub_item",
    "bullet",
    "paragraph",           # numId=0 또는 numPr 없음
    "unknown_numbering",
]

@dataclass(frozen=True)
class LevelDef:
    ilvl: int
    lvlText: str              # 원본 문자열 (ex. '%1.', 'A%1.', '(%2)', '○')
    numFmt: NumFmt
    start: int                # 1 기반
    suff: Optional[str]       # 'tab' | 'space' | 'nothing' | None

@dataclass(frozen=True)
class AbstractNumDef:
    abstractNumId: str
    levels: dict[int, LevelDef]   # ilvl → LevelDef

@dataclass(frozen=True)
class NumDef:
    numId: str
    abstractNumId: str
    level_overrides: dict[int, int]   # ilvl → startOverride

@dataclass
class NumberedParagraph:
    """문단 1 개에 대해 numbering.py 가 반환하는 결과."""
    numId: Optional[str]              # '0' 또는 None 구별
    ilvl: Optional[int]
    kind: Kind
    paragraph_id: str                 # '1', 'A3', '(a)', '' (bullet/suppressed)
    counter_tuple: tuple[int, ...]    # 빈 튜플 허용 (bullet/unknown)
    numbering_suppressed: bool        # numId=='0' 일 때 True
    numbering_raw: dict[str, object]  # 디버깅용: {numId, ilvl, lvlText, numFmt, abstractNumId}
```

### 6.2 Public API

```python
def parse_numbering_xml(raw_xml: bytes) -> tuple[
    dict[str, AbstractNumDef],    # abstractNumId → def
    dict[str, NumDef],             # numId → def (abstractNumId 연결 포함)
]:
    """word/numbering.xml 파싱. side-effect 없음."""


class NumberingEngine:
    """DOCX 1 개에 대한 카운터 상태를 보유한다."""

    def __init__(
        self,
        abstract_nums: dict[str, AbstractNumDef],
        num_defs: dict[str, NumDef],
    ) -> None: ...

    def advance(
        self,
        numId: Optional[str],
        ilvl: Optional[int],
    ) -> NumberedParagraph:
        """문단 하나를 주입. 내부 카운터를 전진시키고 결과 반환.
        - numId=None → kind='paragraph' (numPr 없음)
        - numId='0' → kind='paragraph', numbering_suppressed=True
        - 그 외 → §3 / §5 규칙 적용
        """

    def metrics(self) -> dict[str, int]:
        """파싱 종료 시 kind 별 카운트 반환 (§5.5)."""
```

### 6.3 Helper 함수

```python
def classify_kind(
    lvlText: str,
    numFmt: NumFmt,
    ilvl: int,
) -> Kind:
    """§3.1, §3.2 규칙을 순수 함수로 구현. abstractNumId 에 의존하지 않음."""


def format_counter(value: int, numFmt: NumFmt) -> str:
    """카운터 값 + numFmt → 렌더 문자열.
    bullet 은 ''. upperRoman/lowerRoman 은 roman 변환.
    """


def render_lvl_text(
    lvlText: str,
    counter_tuple: tuple[int, ...],
    abstract_num: AbstractNumDef,
) -> str:
    """'%N' placeholder 치환. 각 '%N' 의 포맷은 abstract_num.levels[N-1].numFmt."""
```

### 6.4 `structure.py` / `docx_reader.py` 와의 계약

- `docx_reader.py` 는 `<w:p>` iterate 시 각 문단의 `numPr` → `(numId, ilvl)` 을 추출하여 `NumberingEngine.advance()` 를 **문단 순서대로** 호출한다(순서 위반 시 카운터 오염).
- 반환된 `NumberedParagraph.kind` · `paragraph_id` · `numbering_suppressed` · `numbering_raw` 를 `RawBlock` / `Block` 에 그대로 전달한다.
- `structure.py` 는 `kind` 와 section(heading 2)·기준서 경계(heading 1) 를 조합해 최종 분류 및 `parent_paragraph_id` 연결을 한다.

---

## 7. 검수 체크리스트 (CHECKPOINT 1 에서 Domain Reviewer 가 확인)

- [ ] `output/md/ISA-200.md` 의 요구사항 `1.` ~ `29.` 가 원본과 일치 (ISA-200 특수 구조)
- [ ] `output/md/ISA-315.md` 의 적용지침 `A1.` ~ `An.` 연속성 (315 는 적용지침이 매우 많음)
- [ ] `numbering_suppressed=true` 문단이 303 건 ± 10 이내로 잡힘
- [ ] `kind='unknown_numbering'` 비율 < 5 %
- [ ] 같은 numId 가 여러 기준서에 걸치는 경우(numId=86 등) 카운터가 연속 누적되어 있고, `structure.py` 의 기준서별 재라벨링이 성공했는지 확인
- [ ] lvlOverride 가 적용된 numId 가 원본과 동일한 start 값을 사용하는지 확인
- [ ] `(%2)` lowerLetter 렌더링 `(a)`, `(b)` 가 정상
- [ ] `(%3)` lowerRoman 렌더링 `(i)`, `(ii)` 가 정상
- [ ] ISA-1200 의 `목적` 3 회 반복에서 번호 체계가 무너지지 않았는지 확인

---

## 8. 알려진 미해결 이슈 / Follow-up

1. **비표준 ilvl=0 패턴**(§3.3) — `(%1) lowerLetter` 같은 abstractNum 이 본문에 실제로 얼마나 쓰이는지 실측 필요. CHECKPOINT 1 검수에서 `unknown_numbering` 비율로 확인.
2. **하나의 문단에 여러 numPr 적용 여부** — 실측 불가. 만약 발견되면 `advance()` 시그니처 확장 필요.
3. **numId 간 카운터 cross-contamination** — 동일 ilvl 의 다른 numId 가 연쇄 descend 할 때 리셋 누락 가능. 4.2 알고리즘은 numId 별 독립이지만, 인접 문단이 numId 를 바꾸는 경우의 시각적 번호 연속성은 보장하지 않는다. 대부분의 ISA 문서는 동일 numId 내에서 구조가 끝나므로 실무상 문제 없음.
4. **Phase 4 확장** — ISQM 1 · 인증업무개념체계 등은 abstractNum 분포가 다를 수 있다. 본 문서는 ISA 2025 전용이므로, Phase 4 파일 추가 시 재프로파일링 후 §2.1~§2.2 테이블을 파일별 Appendix 로 확장.

---

*본 문서는 Phase 1 Task #1 산출물. Task #3(`numbering.py`) 구현 완료 후 `parser-implementer` 가 실측값으로 §2, §5.5 를 업데이트할 수 있다. 단, §3 매핑 규칙·§5 fallback 정책·§6 인터페이스 시그니처 변경은 `audit-standard-domain-reviewer` 와 DM 합의 후 본 문서를 개정한다.*

---

## 9. ADDENDUM — CHECKPOINT 1 검수 후 개정 (2026-04-21)

> `docs/checkpoint_1_review.md` 의 F1 CRITICAL 결함 대응. 본 addendum 은 §1.2, §4.4, §6.2 를 **supersede** 한다.

### 9.1 style 레벨 numPr 상속 (§1.2 보강)

CHECKPOINT 1 검수 결과, Word 의 numbering 참조는 **문단 직접 `<w:pPr><w:numPr>` 이외에 style 레벨에서도 상속**됨이 확인되었다. `word/styles.xml` 의 `<w:style>` 이 `<w:pPr><w:numPr>` 을 가질 수 있고, 해당 style 을 사용하는 문단은 별도 numPr 지정 없이도 자동 번호 매김에 포함된다.

#### 우선순위 (높음 → 낮음)

1. 문단 직접 `<w:pPr><w:numPr>` — 단, `numId='0'` 은 **suppress** (문단 본문으로 강등, §4.3)
2. 문단 style 의 `<w:pPr><w:numPr>` (styles.xml 에서 조회)
3. 그 style 의 `<w:basedOn>` 체인 재귀 (최대 10 depth, cycle guard)

#### 본 ISA 2025 문서의 실측 style→num 매핑

`word/styles.xml` 에서 확인한 6 개 핵심 style:

| styleId | 한글명 | based_on | numId | ilvl | abstractNum 연결 | kind |
|---|---|---|---|---|---|---|
| `a1` | 문단 | (없음) | **119** | 0 | 98 | `requirement` (`1.`) |
| `A` | 문단A | (없음) | **105** | 0 | 51 | `application_guidance` (`A1.`) |
| `A0` | 불릿목록A | (없음) | 105 | 1 | 51 | `sub_item` (`(1)`) |
| `A2` | 목록A | (없음) | 119 | 1 | 98 | `sub_item` (`(1)`) |
| `B` | ? | `A0` | 105 | 2 (상속+오버라이드) | 51 | `sub_item` (`(가)`) |
| `B0` | ? | `A2` | 119 | 2 (상속+오버라이드) | 98 | `sub_item` (`(가)`) |

> **결정적 사실**: ISA-200 의 모든 요구사항(`1.`~`29.`) 과 적용지침(`A1.`~`A82.`), ISA-1200 의 모든 요구사항(`1.`~`152.`) 은 style `a1` / `A` 로 번호가 붙는다. 문단 직접 numPr 은 없다. 파서가 style 상속을 읽지 않으면 이들이 전부 `paragraph_body` 로 떨어진다.

#### 정량 영향 (파싱 전 추정)
- style 상속 미구현 시 손실 문단: **≥ 820** (전체 ~3000 문단의 27%)
- 영향 ISA: 최소 12 개 (ISA-200/210/220/230/240/260/450/500/550/610/700/1200 확인)

### 9.2 Option C — style-inherited numId 는 ISA 경계에서 카운터 리셋 (§4.4 supersede)

**기존 §4.4 Option A 는 기각**. style `a1`/`A` 는 문서 전역에 공유되는 단일 style 이므로, numId 105/119 의 카운터도 문서 전역 단일 스트림이 된다. 그러나 Word 렌더링 시 각 ISA (heading 1 경계) 마다 `A1.`, `1.` 부터 **재시작** 되는 것이 원본과 일치한다(Word 의 "목록 연속/재시작" 규칙이 내부적으로 style 경계를 고려).

#### 확정 정책

- **style-inherited numId (본 문서 기준 105, 119) 는 ISA 경계 (heading 1 전환) 시 카운터를 `start` 값으로 리셋**.
- 문단 직접 numId (86, 113, 118, 138 등) 는 기존 Option A 유지 (문서 전역 연속 누적).
- 리셋 대상 numId 목록은 `NumberingEngine` 이 styles.xml 파싱 결과에서 자동 수집.

#### 인터페이스

```python
class NumberingEngine:
    def reset_for_standard(self, numIds: Optional[Iterable[str]] = None) -> None:
        """ISA 경계(heading 1)에서 structure.py 가 호출.
        numIds 기본값 = styles.xml 에서 수집한 style-inherited numId 전체.
        해당 numId 의 counters / last_ilvl 엔트리를 삭제 → 다음 advance() 시 start 로 재초기화.
        """
```

호출 위치: `structure.py` 가 heading 1 을 만나 `state = STANDARD_BODY` 로 전환하는 시점 (새 ISA 시작 직전).

### 9.3 인터페이스 추가 (§6.2 보강)

`src/audit_parser/ir/styles.py` **신규 모듈** (Task #3 scope 에 포함).

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class StyleNumDefault:
    """word/styles.xml 의 <w:style> 이 정의하는 numPr 기본값."""
    style_id: str                          # w:styleId
    based_on: Optional[str]                # w:basedOn
    num_id: Optional[str]                  # style 의 pPr/numPr/numId
    ilvl: Optional[int]                    # style 의 pPr/numPr/ilvl (기본 0)


def parse_styles_xml(raw_xml: bytes) -> dict[str, StyleNumDefault]:
    """word/styles.xml 파싱.
    모든 <w:style w:type='paragraph'> 를 순회하여 styleId → StyleNumDefault.
    numPr 이 없는 style 도 basedOn 체인 해결을 위해 엔트리는 생성 (num_id=None).
    """


def resolve_paragraph_numPr(
    p_numPr: Optional[tuple[str, int]],     # 문단 직접 (numId, ilvl) or None
    style_id: Optional[str],
    style_index: dict[str, StyleNumDefault],
    *,
    max_depth: int = 10,
) -> Optional[tuple[str, int]]:
    """문단 → style → basedOn 체인으로 (numId, ilvl) 확정.
    우선순위:
      1. p_numPr 이 존재하면 그대로 반환 (numId='0' 포함 — suppress 판정은 advance() 가 수행).
      2. style_index[style_id].num_id 가 존재하면 (num_id, ilvl) 반환.
         ilvl 은 style.ilvl (기본 0); 단 문단이 ilvl 만 override 하는 경우(드묾) 는 문단값 우선.
      3. based_on 체인을 max_depth 까지 재귀. cycle 감지 시 None.
      4. 어디에도 numPr 없음 → None.
    """
```

`NumberingEngine.__init__` 에 `style_index: dict[str, StyleNumDefault]` 인자를 추가 (선택 인자, 기본 `{}` — 하위 호환).

`docx_reader.py` 는 기존 문단 직접 numPr 추출 후 `resolve_paragraph_numPr` 를 호출하여 최종 `(numId, ilvl)` 를 결정한 다음 `engine.advance(numId, ilvl)` 에 전달한다.

### 9.4 테스트 fixture (tests/fixtures/style_numpr_cases.json)

재현 가능 회귀 테스트를 위해 본 검수자가 별도 커밋으로 추가 예정:

| case | p_numPr | style | expected |
|---|---|---|---|
| C1 | None | `a1` | `('119', 0)` (style 직접) |
| C2 | `('0', 0)` | `a1` | `('0', 0)` → advance() 에서 suppress |
| C3 | `(None, 1)` override | `A` | `('105', 1)` (style numId + 문단 ilvl) |
| C4 | None | `B0` → `A2` | `('119', 2)` (basedOn 체인 + B0 의 ilvl=2) |
| C5 | None | `미존재ID` | None + warn |
| C6 | None | 체인 cycle `X→Y→X` | None + warn |

### 9.5 기타 CHECKPOINT 1 지적사항

- **F2 (ISA-1200 section enum)**: `structure.py` 의 SECTION_ENUM 확장 필요 — `general_principles`, `ethical_requirements`, `engagement_acceptance`, `planning`, `materiality`, `risk_assessment`, `risk_response`, `conclusion_reporting`, `other_considerations`. 본 문서가 아닌 `isa_structure_profile.md` §Appendix-B 에 매핑 명세 추가 예정.
- **F3 (An→n parent link)**: F1 해결의 부수효과로 자동 복구 예상. 별도 구현 불요.

### 9.6 재검수 기준

parser-implementer-2 의 rework 완료 후 본 검수자가 재검증할 판정 기준:

1. `output/md/ISA-200.md` 에 marker `A1.` ~ `A82.` 가 전부 등장 (이전: `A1.` 한 개만 존재)
2. `output/md/ISA-1200.md` 에 marker `1.` ~ `152.` 전부 등장 (이전: 1 개만 존재)
3. `output/md/ISA-500.md` 에 marker `A1.` ~ `A64.` 전부 등장
4. 20-샘플 재검증 pass rate ≥ 95 %
5. `unknown_numbering` 비율 여전히 < 5 %
6. ISA 경계에서 `A1.` / `1.` 로 재시작 (이전 ISA 마지막 번호에서 연속되지 않음)

---

## 10. abstractNumId 기반 공유 카운터 설계 (2026-04-21, §4 supersede)

> **Status:** ACTIVE — 실제 `src/audit_parser/ir/numbering.py` 구현과 동치.
> **Supersedes:** §4.1~§4.4 (numId 기반 독립 카운터).
> **근거:** CHECKPOINT 1 F4 (93 건 duplicate marker) 조사 결과, ISA-315 등에서
> **동일한 `w:abstractNumId` 를 7 개의 서로 다른 `w:num` 이 공유**하는 케이스가 다수 확인됨.
> numId 기반 카운터는 동일 abstract 를 참조하는 신규 numId 출현 시마다 리셋 — `A1→A1→A2`
> 가 아닌 `A1→A1→A1` 패턴이 대량 발생. Word 의 실제 번호 렌더링은 abstractNumId 단위.

### 10.1 데이터 모델 (numbering.py 실구현 요약)

```python
class NumberingEngine:
    # numId → abstractNumId 룩업 테이블 (numbering.xml parse 시점에 1회 구축)
    _num_to_abstract: dict[str, str]

    # ↓ 전부 abstractNumId 로 keying (§4.1 구 설계는 numId 로 keying 했음)
    _counters:          dict[str, list[int]]                   # abstractNumId → level counter array
    _starts:            dict[str, list[int]]                   # abstractNumId → level start values (lvlOverride 반영)
    _last_ilvl:         dict[str, int]                         # abstractNumId → 직전 ilvl (하위→상위 복귀 감지)
    _override_applied:  set[tuple[str, int]]                   # (abstractNumId, ilvl) startOverride 1회 가드
```

핵심 차이:
- **§4.1 (DEPRECATED)**: `_counters: dict[str, list[int]]` keyed by `numId` — 7개 numId 가 동일 abstract 를 공유해도 7개 독립 카운터 → 매번 리셋.
- **§10 (ACTIVE)**: `_counters` keyed by `abstractNumId` — 7개 numId 가 동일 카운터를 공유 → Word 렌더링과 일치.

### 10.2 advance() pseudocode

```python
def advance(num_id: str | None, ilvl: int | None) -> NumberingResult:
    # 0) suppress guard: num_id=None / '0' → UNKNOWN (본문 스타일 불명)
    if num_id is None or num_id == '0':
        return UNKNOWN

    # 1) numId → abstractNumId 해석. 없으면 UNKNOWN (fallback metric 에 기록)
    abstract_id = self._num_to_abstract.get(num_id)
    if abstract_id is None:
        return UNKNOWN

    # 2) abstract 단위 카운터 초기화 (최초 1회)
    if abstract_id not in self._counters:
        self._counters[abstract_id] = [0] * MAX_LEVELS
        self._starts[abstract_id]   = self._extract_level_starts(abstract_id)  # w:lvl/w:start

    # 3) lvlOverride / startOverride 1회 적용 가드
    #    — (abstract_id, ilvl) 튜플이 _override_applied 에 없을 때만 1회 반영
    key = (abstract_id, ilvl)
    if key not in self._override_applied:
        override = self._lookup_start_override(num_id, ilvl)   # num_id(!) 기준으로 XML 조회
        if override is not None:
            self._counters[abstract_id][ilvl] = override - 1   # advance 직전 값
        self._override_applied.add(key)

    # 4) 상위 level 복귀 시 하위 카운터 리셋 (abstract 단위)
    last = self._last_ilvl.get(abstract_id)
    if last is not None and ilvl < last:
        for deeper in range(ilvl + 1, MAX_LEVELS):
            self._counters[abstract_id][deeper] = self._starts[abstract_id][deeper] - 1

    # 5) 실제 증가 + 마커 emit
    self._counters[abstract_id][ilvl] += 1
    self._last_ilvl[abstract_id] = ilvl
    return self._emit_numbered(abstract_id, ilvl)
```

핵심 포인트:
- `_lookup_start_override()` 의 XML 조회는 여전히 **`num_id` 단위** (lvlOverride 는 `w:num` 노드에 걸림) 이지만, 가드(`_override_applied`) 는 abstract 단위.
  → 동일 abstract 를 공유하는 여러 numId 중 "먼저 등장한 numId 의 startOverride" 만 적용됨. 실측에서 문제 없음 (ISA-315 sharing 케이스 모두 startOverride 부재).
- `_last_ilvl` 이 numId 별에서 abstract 별로 변경된 결과, "새 numId 지만 동일 abstract" 전환 시에도 하위→상위 복귀 감지가 올바르게 작동.

### 10.3 reset() 동작 (기준서 경계)

```python
def reset() -> None:
    """`heading 1 == "감사기준서 NNN"` 경계에서 structure.py 가 호출.
    abstractNumId-scoped 상태를 **전부** 초기화해야 카운터 leak 을 방지."""
    self._counters.clear()
    self._starts.clear()
    self._last_ilvl.clear()
    self._override_applied.clear()   # ← 누락 시 기준서 간 startOverride 1회 가드가 영구 차단
```

`_override_applied.clear()` 누락 시 증상: ISA-210 이후 모든 기준서에서 `A{n}.` startOverride 가 무시되어 마커가 이전 기준서 끝 값에서 연속(`A83.`...)됨. **실제 F4 fix 과정에서 이 누수를 재발견**.

### 10.4 구 설계 대비 변경 요약

| 항목 | §4.1 (DEPRECATED) | §10 (ACTIVE) |
|---|---|---|
| `_counters` key | `numId` | `abstractNumId` |
| `_starts` key | `numId` | `abstractNumId` |
| `_last_ilvl` key | `numId` | `abstractNumId` |
| override 가드 | `set[numId]` (ilvl 미분리) | `set[(abstractNumId, ilvl)]` |
| reset() 지우는 것 | counters/starts | counters/starts/last_ilvl/**override_applied** |
| ISA-315 sharing | 7 개 독립 카운터 (BUG) | 1 개 공유 카운터 (CORRECT) |

### 10.5 잔존 false-positive duplicate (F4 Phase 2 이월)

§10 설계로 93 건 → **6 쌍 (12 건)** 으로 감축되었으나 잔존분은 **Word 스펙 준수 하에서 동일 marker 가 발생하는 정상 케이스** (`startOverride` / 다중 `w:abstractNumId` / 스타일 상속 조합). 상세 enumeration 및 raw DOCX 증거는 별도 문서 참조:

→ [`docs/f4_known_duplicates.md`](./f4_known_duplicates.md)

Phase 2 `md_parser` / Qdrant payload 레이어에서 composite key `(standard_no, section, heading_trail_hash, paragraph_id)` 로 해소할 것.
