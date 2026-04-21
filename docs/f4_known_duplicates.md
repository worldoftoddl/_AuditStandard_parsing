# F4 잔존 Duplicate Paragraph ID Enumeration

> **작성일:** 2026-04-21
> **작성자:** `audit-standard-domain-reviewer` (Phase 1.5 / Task #13)
> **Supersedes:** —
> **Related:** [`numbering_strategy.md §10`](./numbering_strategy.md#10-abstractnumid-기반-공유-카운터-설계-2026-04-21-4-supersede), [`checkpoint_1_review.md §R6`](./checkpoint_1_review.md#r6-최종-pass-판정-2026-04-21-2차-rework-재재검수-후)

---

## 1. Summary

CHECKPOINT 1 F4 (93 건 duplicate `paragraph_id`) 는 `numbering.py` 를
**abstractNumId-scoped counter** 로 재설계하여 6 건까지 감축되었다. 본 문서는
잔존 6 건을 전수 enumeration 하고, 이들이 **Word OOXML 스펙상 합법적인
멀티-스트림 numbering** 이며 parser 결함이 아님을 raw DOCX 증거로 입증한다.

Phase 2 `md_parser` / Qdrant payload 레이어에서 composite key
`(standard_id, section, heading_trail_hash, paragraph_id)` 로 해소한다.

> **2026-04-21 EVE 업데이트 (v1.1 bump):** 위 4-tuple 중 4 쌍은 자연 해소되나 **2 쌍 (ISA-300 `7.`, ISA-701 `4.`) 은 heading_trail 까지 동일**하여 추가 disambiguator 필요. `docs/json_schema.md §6.4 v1.1 2-Pass 알고리즘` (Pass 1 candidate → Pass 2 collision 감지 + `#{source_idx}` suffix) 로 deterministic 해소. 상세는 §4.2 참조.

---

## 2. 잔존 Duplicate 전수 표 (requirement-level, ilvl=0)

`output/md/ISA-*.md` 를 전수 스캔한 결과 다음 6 건이 남는다. sub_item (ilvl≥1)
중복은 `parent_paragraph_id` 로 이미 disambiguated 되므로 제외한다.

| # | standard_no | paragraph_id | occurrence | numId | abstractNumId | ilvl | 유입경로 | text_snippet |
|---|---|---|---|---|---|---|---|---|
| 1 | ISA-250 | `12.` | #1 | 438 | 137 | 0 | direct numPr | 감사기준에서 사용하는 용어의 정의는 다음과 같다. |
| 2 | ISA-250 | `12.` | #2 | 440 | 98 | 0 | direct numPr (startOverride=15) | 감사인은 재무제표에 중요한 영향을 미칠 수 있는 기타의 법규에 대한 위반사례를 식별… |
| 3 | ISA-260 | `5.` | #1 | 445 | 85 | 0 | direct numPr | 감사인은 이 감사기준서에서 요구되는 사항에 대하여 커뮤니케이션을 할 책임이 있으나… |
| 4 | ISA-260 | `5.` | #2 | 446 | 98 | 0 | direct numPr (startOverride=16) | 감사인은 아래 사항에 대하여 지배기구와 커뮤니케이션하여야 한다. (문단 A17-A18 참조) |
| 5 | ISA-260 | `6.` | #1 | 445 | 85 | 0 | direct numPr | 감사기준이 커뮤니케이션을 요구하는 특정 사항을 명확하게 커뮤니케이션하는 것은… |
| 6 | ISA-260 | `6.` | #2 | (style 상속) `119` | 98 | 0 | style `a1` inherit | 상장기업의 경우, 감사인은 다음 사항에 관하여 지배기구와 커뮤니케이션하여야 한다. |
| 7 | ISA-300 | `7.` | #1 | 452 | 26 | 0 | direct numPr | 감사인은 감사의 범위, 시기 및 방향을 수립하고 감사계획 개발의 지침이 되는 전반감사전략을 수립하여야 한다. |
| 8 | ISA-300 | `7.` | #2 | 453 | 98 | 0 | direct numPr (startOverride=8) | 감사인은 전반감사전략을 수립할 때 다음의 절차를 수행해야 한다 |
| 9 | ISA-300 | `10.` | #1 | 602 | 96 | 0 | direct numPr | 감사인은 감사의 진행 중 필요에 따라 전반감사전략과 감사계획을 갱신하고 변경해야 한다. (문단 A15 참조) |
| 10 | ISA-300 | `10.` | #2 | (style 상속) `119` | 98 | 0 | style `a1` inherit | 감사인은 초도감사를 착수하기 전에 다음의 절차를 수행하여야 한다. |
| 11 | ISA-701 | `4.` | #1 | 607 | 197 | 0 | direct numPr | 감사보고서에서 핵심감사사항에 대하여 커뮤니케이션하는 것은 감사인이 재무제표 전체에 대하여 의견을 형성하는 맥락에서 이루어진다. |
| 12 | ISA-701 | `4.` | #2 | (style 상속) `105` | 51 | 0 | style `A` inherit | 이 감사기준서는 상장기업의 일반목적 전체재무제표에 대한 감사와 감사인이 감사보고서에 핵심감사사항을 커뮤니케이션할 것을 결정하는… |

**중복 쌍 수:** 6 (ISA-250 `12.`, ISA-260 `5.`, ISA-260 `6.`, ISA-300 `7.`,
ISA-300 `10.`, ISA-701 `4.`).

---

## 3. 증거 (Raw DOCX cross-check)

### 3.1 numId → abstractNumId 매핑 (word/numbering.xml)

```
numId  abstractNumId
----   -------------
105    51       ← style "A" 의 default numId
119    98       ← style "a1" 의 default numId
438    137
440     98      ← startOverride ilvl=0 val=15
445     85
446     98      ← startOverride ilvl=0 val=16
452     26
453     98      ← startOverride ilvl=0 val=8
602     96
607    197
```

조회 스크립트: 본 검수 시 사용한 lxml 코드는 git blame 기준으로
`.venv/bin/python` 원-라이너로 수행. 재현은 아래 스니펫으로 가능.

```python
import zipfile
from lxml import etree
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
z = zipfile.ZipFile('raw/0. 회계감사기준 전문(2025 개정).docx')
nb = etree.fromstring(z.read('word/numbering.xml'))
for num in nb.findall('w:num', NS):
    nid = num.get('{%s}numId' % NS['w'])
    a = num.find('w:abstractNumId', NS)
    print(nid, a.get('{%s}val' % NS['w']))
```

### 3.2 해석 — 왜 중복이 발생하는가

**공통 패턴:** 동일 기준서 내에서 서로 다른 `w:num` 엘리먼트가 서로 다른
`w:abstractNumId` (또는 동일 abstract + `startOverride`) 로 **독립적인
번호 카운터 스트림**을 시작한다. Word 는 이를 "새 리스트" 로 렌더링한다.

- **#7/#8 (ISA-300 `7.` pair)**: abs=26 의 독립 스트림 + abs=98 의 스트림
  (startOverride=8 로 재시작). 서로 다른 abstract → 각자 "7." 렌더링.
- **#9/#10 (ISA-300 `10.` pair)**: abs=96 의 독립 스트림 + abs=98 의 스트림
  (carry-over 결과 `10.`). abs=96 은 이 기준서에서 처음 등장, abs=98 은
  기준서 초반부터 누적된 counter.
- **#11/#12 (ISA-701 `4.` pair)**: abs=197 direct + abs=51 style 상속.
  각자 다른 stream → 둘 다 `4.`.
- **#5/#6 (ISA-260 `6.` pair)**: abs=85 direct + abs=98 style `a1` 상속.
  동일 기준서 내 두 리스트를 혼재 사용.

**결론:** 모든 중복은 "1 기준서 = 1 리스트 스트림" 이라는 암묵적 가정을
깨는 실제 DOCX 저자 관행 (`startOverride` + 스타일 상속 + 다중 abstract 분리)
에 기인. Word 스펙상 합법이며, numbering engine 은 정상 동작 중.

### 3.3 Style 상속 증거 (word/styles.xml)

| styleId | numId | abstractNumId |
|---|---|---|
| `a1` | 119 | 98 |
| `A` | 105 | 51 |

상속 경로는 `docx_reader.resolve_paragraph_numPr()` 에서 이미 해결되고 있으며,
해당 로직은 CHECKPOINT 1 F1 fix 의 일부로 검증 완료.

---

## 4. Phase 2 해소 방안 — Composite Key

`paragraph_id` 전역 고유성은 Phase 1 범위 밖이며, Phase 2 의 Qdrant payload
레이어에서 composite key 로 해결한다.

### 4.1 제안 키 조합

```python
chunk_id = (
    standard_no,                      # e.g. "ISA-300"
    section,                          # Section enum value, e.g. "requirements"
    sha1(heading_trail_str)[:8],      # heading_trail 해시 — sub-section 구분
    paragraph_id,                     # e.g. "7."
)
```

**왜 이 조합이 충분한가:**

- **`standard_no`**: 기준서 경계 분리 (이미 `engine.reset()` 으로 counter 분리됨, key 차원에서 한번 더).
- **`section`**: `Section.REQUIREMENTS` vs `Section.APPLICATION` 분리.
  하지만 위 6 건 모두 `requirements` 내부 중복이므로 이 축만으로는 불충분.
- **`sha1(heading_trail_str)[:8]`**: 핵심. 예컨대 ISA-300 `7.` 두 건은
  서로 다른 heading 3 하위 (하나는 "전반감사전략", 다른 하나는
  "감사계획" 아래) 이므로 heading_trail 이 다르다.
- **`paragraph_id`**: 마지막 disambiguator.

실제 heading_trail 은 `structure.py::_heading_stack` 이 유지하고, `Block.heading_trail`
tuple 로 emit 된다. 해시 길이 8 자는 충돌 확률이 2^-32 수준으로 본 데이터 규모
(기준서 30여 개 × 수백 paragraphs) 에서 사실상 0.

### 4.2 Phase 2 에서 검증할 항목

1. ~~위 6 쌍이 composite key 로 모두 unique 해지는지 확인 (각 쌍의 `heading_trail` 가 반드시 다르다는 점을 DOCX 에서 재확인 필요).~~
   **[RESOLVED — 2026-04-21 EVE, devils-advocate-critic advisory + domain-reviewer MD 재검증]**
   **결과:** 4 쌍 해소, **2 쌍 충돌**:
   - ✅ Pair #1 (ISA-250 `12.`) — section 차등 (definitions vs requirements, idx=1607 vs idx=1615)
   - ✅ Pair #2 (ISA-260 `5.`) — heading_trail 차등 (`감사인의 책임` vs `감사에서의 유의적 발견사항`, idx=1793 vs idx=1823)
   - ✅ Pair #3 (ISA-260 `6.`) — heading_trail 차등 (`감사인의 책임` vs `감사인의 독립성`, idx=1794 vs idx=1832)
   - ⚠️ Pair #4 (ISA-300 `7.`) — **heading_trail 동일** (`### 계획수립 활동` 단일, idx=2237 vs idx=2238 연속)
   - ✅ Pair #5 (ISA-300 `10.`) — heading_trail 차등 (`계획수립 활동` vs `초도감사 시 추가적인 고려사항`, idx=2248 vs idx=2256)
   - ⚠️ Pair #6 (ISA-701 `4.`) — **heading_trail 동일** (`### 이 감사기준서의 범위` 단일, idx=8422 vs idx=8427 non-adjacent)

   **충돌 해소:** `docs/json_schema.md §6.4 v1.1 2-Pass 알고리즘` — Pass 1 candidate 중복 발견 시 전원에 `#{source_idx}` suffix 부착. `ISA-300:requirements:{h}:7.#2237` / `:7.#2238`, `ISA-701:intro:{h}:4.#8422` / `:4.#8427`.

2. sub_item (ilvl≥1) 중복 (ISA-300 `(a)`/`(b)`/`(c)` 5+ 회 등) 도 동일 composite key 로 해소되는지 확인 — `parent_paragraph_id` 가 heading_trail_hash 대체 disambiguator 로 충분할 가능성 있음. **[Task #5 전수 생성 시 `assert_chunk_id_uniqueness` (json_schema.md §6.2.1) 가 자동 검증]**
3. Qdrant payload schema 에 `heading_trail_hash` 필드 추가 (payload index 없이 sparse) **[json_schema.md §13 payload indexed keyword 로 확정]**
4. Chunk 의 external ID 를 `{standard_id}:{section}:{heading_trail_hash}:{paragraph_id}[#{source_idx}]` 로 구성하고 Qdrant `id` 필드에 UUID 로 해싱. **[json_schema.md §6.1/§6.4/§6.5 에 v1.1 형식 확정, `standard_id` = `ISA-<no>` prefix 포함]**

### 4.3 대안 및 기각 사유

| 대안 | 기각 사유 |
|---|---|
| numbering engine 에서 abstractNumId suffix 부착 (`7.@abs26`) | 사용자-facing marker 오염. 검색 UX 악화. |
| heading_trail 전체를 key 에 그대로 포함 | 길이 가변, 해시 충돌 없지만 payload 비대 |
| `idx` (문단 원본 순번) 를 key 에 포함 | 재파싱 시마다 변할 수 있어 안정 ID 로 부적절 |

composite key (§4.1) 가 안정성·크기·가독성 trade-off 최적.

---

## 5. Phase 2 브리핑 체크리스트

Phase 2 `md_parser` 담당자가 본 문서를 참조해야 할 시점:

- [ ] `chunk_splitter.py` 에서 chunk ID 부여 로직 설계 시 §4.1 composite key 채택
- [ ] `qdrant_writer.py` payload schema 에 `standard_no`, `section`,
      `heading_trail_hash`, `paragraph_id` 필드 포함
- [ ] E2E 테스트에 위 6 쌍이 모두 별도 chunk 로 저장되는지 검증 추가
- [ ] `docs/json_schema.md` 에 composite key 섹션 명시

---

## 6. 참고

- [`numbering_strategy.md §10`](./numbering_strategy.md#10-abstractnumid-기반-공유-카운터-설계-2026-04-21-4-supersede) — abstractNumId-scoped counter 현행 설계
- [`checkpoint_1_review.md §R6`](./checkpoint_1_review.md#r6-최종-pass-판정-2026-04-21-2차-rework-재재검수-후) — CHECKPOINT 1 최종 PASS 판정 및 F4 잔존 정당성 요약
- `src/audit_parser/ir/numbering.py` L484-489 — `_override_applied` 가드 구현
