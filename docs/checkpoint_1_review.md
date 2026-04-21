# CHECKPOINT 1 검수 보고서

**검수자**: `audit-standard-domain-reviewer`
**검수일**: 2026-04-21
**대상 산출물**: `output/md/*.md` (37 개 파일, 총 34,569 줄)
**대상 원본**: `raw/0. 회계감사기준 전문(2025 개정).docx`
**판정**: **❌ FAIL (rework 요청)** — critical numbering loss, Phase 2 진입 보류 권고

---

## 0. Executive Summary

Phase 1 구현은 다음 영역에서는 정상 작동한다:
- 감사기준서 경계 탐지 (`heading 1` = styleId `10`) 및 36 개 기준서 분리 ✓
- 목차(`ad` 스타일) 격리 → `00_전문.md` 로 전량 이동, ISA-\*.md 내 목차 잔존 0 건 ✓
- 1×1 표 → `BLOCK_QUOTE` (`> `) 승격 ✓
- 표 16 건 / 블록 58 건, profile 숫자 일치 ✓
- `numId='0'` vs `numId=None` 구별 처리 ✓
- `schema_version: "1.0"` frontmatter 전량 부착 ✓
- `<!-- idx: N -->` 주석으로 원본 body index 역추적 가능 ✓
- ISA-200 `overall_objective` 섹션 유일성 ✓
- `unknown_numbering` 6 건 (0.053 %, 임계 5 % 한참 아래) ✓

그러나 **치명적 결함 1 건** + **중대 결함 2 건** 이 발견되어 Phase 2 진입 전 rework 가 필요하다.

| ID | 심각도 | 결함 | 범위 | 권고 조치 |
|---|---|---|---|---|
| **F1** | 🔴 CRITICAL | 스타일-상속 `numPr` 미처리로 요구사항·적용지침 번호 대량 손실 | 12 개 ISA, **최소 820 개** 문단 | `numbering.py` + `docx_reader.py` rework 필수 |
| F2 | 🟠 HIGH | ISA-1200 전용 heading 2 들(`일반원칙과 책임`, `감사 계획` 등)이 `section` enum 미분류 | ISA-1200 전체 | `structure.py` ISA-1200 특수 분기 보강 |
| F3 | 🟡 MED | `An` → `n` 부모 링크가 스타일-상속 문단에는 0 건 | F1 에 종속 | F1 해결 시 자동 복구 예상, 후속 확인 필요 |

**Rework 상한**: 2 회 (PLAN.md §8). F1 해결 후 재검수하여 판정 재발행한다. F1 미해결 시 team-lead 에스컬레이션.

---

## 1. 치명적 결함 F1 — 스타일-상속 `numPr` 미처리

### 1.1 증상

파서 출력 MD 에서 ISA-200 의 경우 `kind: requirement` 마커가 **0 개**, `kind: application_guidance` 가 **1 개**에 불과하다. 원본 ISA-200 은 요구사항 14 ~ 24, 적용지침 A1 ~ A91 로 총 100+ 개의 번호 매겨진 문단을 가진다. 따라서 최소 **100 개가량의 번호가 유실**된다.

ISA 별 유실 규모를 DOCX 원본 스캔으로 정량화한 결과:

| ISA | req (explicit) | req (inherited, **유실**) | app (explicit) | app (inherited, **유실**) | 유실 합계 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **200** | 0 | **24** | 1 | **82** | **106** |
| **500** | 11 | 0 | 4 | **64** | **64** |
| **1200** | 1 | **152** | 0 | 0 | **152** |
| 210 | 26 | 0 | 1 | 38 | 38 |
| 220 | 25 | 0 | 1 | 36 | 36 |
| 230 | 16 | 0 | 1 | 23 | 23 |
| 240 | 48 | 0 | 1 | 68 | 68 |
| 250, 260, 265, 300, 315, 320, 330, 402, 450, 501, 505, 510, 520, 530, 540, 560, 570, 580, 610, 620, 700, 701, 705, 706, 710, 720, 1100 (추정) | 합계 상당 | | | 합계 상당 | **최소 300 건** |
| 550 | 28 | 0 | 50 | 0 | 0 ✓ |
| 600 | 60 | 0 | 69 | 0 | 0 ✓ |

**총 유실 문단 추정**: 820+ (ISA-200, 500, 1200 만 합해도 322 건). Collection 전체 번호체계의 ~15~25 % 유실.

### 1.2 근본 원인 분석

Word DOCX 의 자동 번호매김은 **세 경로**로 전달될 수 있다:

1. **문단 직속** `<w:p><w:pPr><w:numPr>` — 현재 파서가 유일하게 처리하는 경로
2. **스타일 기본값** `<w:style><w:pPr><w:numPr>` — `word/styles.xml` 에 정의. **파서 누락** ❌
3. **pStyle 체인의 basedOn 상속** — 현재 스타일에 numPr 없으면 `basedOn` 스타일 추적 (재귀)

`word/styles.xml` 실측:

| styleId | 이름 | 스타일-상속 numPr | 이 스타일이 렌더링해야 할 번호 |
|---|---|---|---|
| `a1` | `문단` | numId=119 (abstractNumId=98), ilvl=0, `%1.` decimal | **`1.`, `2.`, `3.`, …** (requirement) |
| `A`  | `문단A` | numId=105 (abstractNumId=51), ilvl=0, `A%1.` decimal | **`A1.`, `A2.`, `A3.`, …** (application_guidance) |
| `A0` | `불릿목록A` | numId=105, ilvl=1 | 불릿 |
| `A2` | `목록A` | numId=119, ilvl=1 | `(a)`, `(b)` 하위항목 |
| `B0` | `목록B` | (parent `A2` 상속) ilvl=2 | `(i)`, `(ii)` |
| `B`  | `불릿목록B` | (parent `A0` 상속) ilvl=2 | 깊은 불릿 |

ISA-200 의 서론 첫 문단(DOCX body idx 78):
```xml
<w:p>
  <w:pPr>
    <w:pStyle w:val="a1"/>
    <!-- numPr 없음 → 스타일 a1 의 기본 numId=119 상속 -->
  </w:pPr>
  <w:r><w:t>이 감사기준서는 독립된 감사인이 감사기준 …</w:t></w:r>
</w:p>
```

- 파서가 문단-직속 `<w:numPr>` 만 검사 → 해당 문단은 `numId=None`, `kind='paragraph'` 로 분류
- 실제로는 `numId=119` → `abstractNumId=98` → ilvl=0 `%1.` decimal → **`1.` requirement**

ISA-550, ISA-600 은 작성자가 모든 문단에 명시적 numPr 을 박아서 영향 없음. 나머지 ISA 는 작성 시기·담당자에 따라 혼재.

### 1.3 재현 절차

```bash
# DOCX 원본 확인
python3 -c "
import zipfile
from xml.etree import ElementTree as ET
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
with zipfile.ZipFile('raw/0. 회계감사기준 전문(2025 개정).docx') as z:
    ntree = ET.parse(z.open('word/numbering.xml'))
    stree = ET.parse(z.open('word/styles.xml'))
# 1) style a1 의 numPr 확인
for s in stree.getroot().iter(f'{W}style'):
    if s.get(f'{W}styleId') == 'a1':
        print(ET.tostring(s.find(f'.//{W}numPr'), encoding='unicode'))
# 2) numId 119 → abstractNumId
for num in ntree.getroot().iter(f'{W}num'):
    if num.get(f'{W}numId') == '119':
        print('abstractNumId:', num.find(f'{W}abstractNumId').get(f'{W}val'))
"
```

출력:
```
<ns0:numPr …><ns0:numId ns0:val="119"/></ns0:numPr>
abstractNumId: 98
```

→ abstractNumId=98 의 ilvl=0 lvlText=`%1.` numFmt=`decimal` → 요구사항 번호.

### 1.4 설계 문서와의 관계

`docs/numbering_strategy.md` §6.4 "contract" 는 다음과 같이 기술한다:
> `docx_reader.py` 는 `<w:p>` iterate 시 각 문단의 `numPr` → `(numId, ilvl)` 을 추출하여 `NumberingEngine.advance()` 를 문단 순서대로 호출한다.

이 문장은 **문단-직속 `<w:numPr>` 만을 전제**했다. `parser-implementer` 가 스타일-상속 경로를 파악하기 어려웠던 이유는 Phase 0 프로파일링(`docs/isa_structure_profile.md`) 이 top_numId 사용량만 집계하고 스타일-상속 메커니즘을 다루지 않았기 때문이다. 본 검수자의 **Phase 0 프로파일링이 스타일-레벨 numPr 수집을 빠뜨린 점**이 근원적 원인이다.

### 1.5 권고 수정 사항 (parser-implementer 대상)

**1.5.1 `docx_reader.py` / `ir/types.py` 변경**

문단 iterate 시 numPr 해석 순서:
1. 문단-직속 `<w:pPr><w:numPr>` 존재 → 그대로 사용
2. 없으면 `<w:pStyle>` styleId → `styles_index[styleId].numPr` 조회
3. 없으면 해당 스타일의 `basedOn` 을 타고 재귀 조회 (최대 10 회 안전장치)
4. 그래도 없으면 진정한 "번호 없음" → `numId=None`

**1.5.2 `numbering.py` 확장**

`parse_styles_xml(raw_xml: bytes) -> dict[str, StyleNumDefault]` 헬퍼 추가:
```python
@dataclass(frozen=True)
class StyleNumDefault:
    styleId: str
    numId: Optional[str]
    ilvl: int
    basedOn: Optional[str]

def parse_styles_xml(raw_xml: bytes) -> dict[str, StyleNumDefault]: ...

def resolve_paragraph_numPr(
    p_numPr: Optional[tuple[str, int]],    # 문단 직속
    style_id: Optional[str],
    style_index: dict[str, StyleNumDefault],
) -> Optional[tuple[str, int]]:
    """문단 + 스타일 체인 상속. basedOn 재귀."""
```

**1.5.3 카운터 replay 상 주의사항**

스타일-상속 numId 는 **전체 문서에서 단일 카운터**를 공유한다 (예: 모든 style=`a1` 문단이 numId=119 의 동일 카운터 사용). 따라서:
- numId=119 카운터는 ISA-200 부터 ISA-1200 까지 **연속 누적**됨 → 렌더 문자열이 `1.`, `2.`, …, `수백` 범위
- Word 는 `<w:lvlOverride>` + `<w:startOverride>` 로 기준서 경계마다 재시작할 수 있으나, 본 DOCX 에서 numId=119 · 105 에는 해당 재정의가 **없음**

이 경우 파서가 낼 수 있는 선택지:
- **옵션 A**: 원본 그대로 누적 번호 사용 → MD 상 `547.` 같은 번호가 노출됨. 사용자 기대와 불일치.
- **옵션 B (권고)**: `structure.py` 에서 기준서 경계(`heading 1` 변경) 마다 스타일-상속 numId (119, 105) 의 카운터를 강제 리셋. Word 렌더링과 불일치할 가능성이 있지만, ISA 관습상 "각 기준서 1 번부터 시작" 이 정상이므로 사용자 기대 부합.
- **옵션 C**: 옵션 B + 추가 안전장치 — 기준서 경계 전에 `numId=119` 가 도달한 카운터 값을 로그로 기록. CHECKPOINT 1 재검수 시 실제 원본 Word 렌더링(PDF 버전 등)과 대조해 옵션 B 의 리셋이 맞았는지 검증.

→ **권고: 옵션 C**. `docs/numbering_strategy.md` §4.4 에서 "옵션 A" 로 기록했으나, 스타일-상속 numId 에 한해 **옵션 B 로 변경** 필요. 문서 개정안은 F1 해결 후 본 검수자가 작성한다.

**1.5.4 검증 기준**

Rework 후 다음이 재현되어야 한다:
- ISA-200 MD 에 `para: 1. | kind: requirement` 부터 `para: 24. | kind: requirement` 까지 출현
- ISA-200 MD 에 `para: A1. | kind: application_guidance` 부터 `para: A91.` (또는 실제 마지막 번호) 출현
- ISA-1200 MD 에 `para: 1.` ~ `para: 152.` (또는 근사값) 출현 (ISA-1200 은 요구사항/적용지침 섹션이 없으므로 전부 prose 형식의 번호 매긴 문단)
- `parent:` 링크 복구 (F3 연동)
- `unknown_numbering` 비율 여전히 < 5 %
- ISA-550, ISA-600 카운팅 불변 (회귀 없음)

---

## 2. 중대 결함 F2 — ISA-1200 섹션 enum 미분류

### 2.1 증상

ISA-1200 의 heading 2 목록:
```
## 서론                            → section: intro ✓
## 일반원칙과 책임                 → (섹션 enum 없음)
## 감사업무의 수임 또는 유지       → (섹션 enum 없음)
## 감사 계획                      → (섹션 enum 없음)
## 위험평가                       → (섹션 enum 없음)
## 평가된 위험에 대한 감사인의 대응 → (섹션 enum 없음)
## 결론 및 보고                   → (섹션 enum 없음)
## 보론 1 용어의 정의              → section: appendix ✓
## 보론 2 감사보고서               → section: appendix ✓
```

ISA-1200 은 요구사항/적용지침 섹션이 없고 대신 감사 절차 단계별 7 개 heading 2 로 재구조화되었다. PLAN.md §4 Phase 1 은 "ISA-1200 특수처리: 요구사항·적용지침 섹션 없음, `목적` 3 회 반복" 만 언급했으며, 이 7 개 heading 2 의 섹션 enum 매핑을 명시하지 않았다.

결과: ISA-1200 의 본문 문단 대부분이 section 없음으로 Phase 2 chunk 메타에 `section=None` 이 전파될 위험.

### 2.2 권고 수정 사항

`section` enum 확장 제안:

| heading 2 텍스트 | 신규 section 값 | 또는 기존값 재사용 |
|---|---|---|
| `일반원칙과 책임` | `general_principles` | 또는 `requirements` 로 매핑 |
| `감사업무의 수임 또는 유지` | `engagement_acceptance` | 또는 `requirements` |
| `감사 계획` | `planning` | 또는 `requirements` |
| `위험평가` | `risk_assessment` | 또는 `requirements` |
| `평가된 위험에 대한 감사인의 대응` | `risk_response` | 또는 `requirements` |
| `결론 및 보고` | `conclusion_reporting` | 또는 `requirements` |

**권고**: 개별 enum 을 추가 (상세 검색 품질 위해) + payload 에 `isa_1200_subsection: true` 플래그. Phase 2 스키마에서 섹션 기반 필터링 시 이들을 `requirements` 의 특수 서브분류로 취급.

또한 `목적` heading 3 반복(6 회 확인, profile 은 3 회로 기록) — ISA-1200 은 "각 heading 2 섹션마다 목적 subsection 을 둠" 패턴이므로 `heading 3='목적'` 은 heading_trail 에 그대로 유지하고 섹션 enum 은 상위 heading 2 값을 따른다.

### 2.3 부속 관찰

- profile(docs/isa_structure_profile.md §2.2)이 "ISA-1200 `목적` 3 회" 라 기록했으나 실측 6 회 (line 22, 364, 442, 541, 769, 1279). → profile 개정 필요. F1 rework 와 함께 본 검수자가 profile 보완.
- section enum 전역 분포(ISA 36 개 대상):
  ```
  intro: 36 ✓ (모든 ISA)
  overall_objective: 1 ✓ (ISA-200 유일)
  purpose: 34   (기대: 35, 1 건 유실 — ISA-1200 의 heading 3 '목적' 이 매핑 안됨)
  definitions: 32  (기대: 34 per profile, ISA-1200 보론 1 용어 포함 여부 확인 필요)
  requirements: 35 ✓
  application: 35 ✓
  appendix: 19 (profile 18, 거의 일치)
  ```

---

## 3. 중대 결함 F3 — `An` → `n` 부모 링크 손실

F1 에 직접 종속. 원본에서 `A7.` (application guidance) 이 `(문단 8 참조)` 로 8 번 요구사항을 설명한다고 할 때, 파서는 현재:
- `A7.` 이 스타일-상속 문단이면 `kind='paragraph_body'` 로 분류 → `parent:` 주석 없음
- `8.` 요구사항도 스타일-상속이면 존재하지 않음 → 링크 대상 없음

ISA-550, ISA-600 은 명시 numPr 덕분에 `parent:` 링크 106 건 / 161 건 정상 생성. 나머지 ISA 는 거의 0 건.

F1 수정 시 자동으로 복구될 것으로 예상. F1 rework 후 `parent:` 링크 수를 재측정하여 다음 기대값과 비교:
- ISA-200 parent 링크 ≥ 70 건 (A1~A91 중 대부분)
- ISA-500 parent 링크 ≥ 50 건
- ISA-1200 parent 링크 = 0 (요구사항/적용지침 구조 없음)

---

## 4. 20 개 샘플 문단 대조 결과

랜덤 층화추출(ISA × section). 각 샘플에서 원본 DOCX 의 문단 위치(body idx) 와 MD 출력을 비교.

| # | ISA | section | 원본 body idx | 원본 기대 번호 | MD 출력 | 판정 | 비고 |
|:---:|:---:|:---|:---:|:---|:---|:---:|:---|
| 1 | 200 | intro | 78 | `1.` requirement | `paragraph_body`, 번호 없음 | ❌ | F1 |
| 2 | 200 | intro | 79 | `2.` requirement | `paragraph_body` | ❌ | F1 |
| 3 | 200 | definitions | 101 | suppressed (numId=0) | `paragraph_body`, numbering_suppressed | ✓ | numId=0 처리 정상 |
| 4 | 200 | definitions | 102 | `(i)` sub_item | `para: (i) | kind: sub_item` | ✓ | ilvl=1 정상 |
| 5 | 200 | requirements | 125 | `14.` requirement (ethical) | `paragraph_body` | ❌ | F1 |
| 6 | 200 | application | 159 | `A1.` application | `para: A1. | kind: application_guidance` | ✓ | 유일 성공 케이스 |
| 7 | 200 | overall_objective | 93 | section heading | `## 감사인의 전반적인 목적`, section=overall_objective | ✓ | ISA-200 유일 섹션 정상 |
| 8 | 500 | application | 4830 | `A1.` | `para: A1.` | ✓ | |
| 9 | 500 | application | 4839 | `A5.` (inferred) | `paragraph_body` 혹은 bullet | ❌ | F1 + bullet 혼동 가능성 |
| 10 | 550 | requirements | first req | `1.` | `para: 1. | kind: requirement` | ✓ | numId=86 리셋 성공 |
| 11 | 550 | application | sample | `A1.`~`A50.` | 전부 정상 | ✓ | explicit numPr |
| 12 | 600 | requirements | sample | `1.`~`60.` | 전부 정상 | ✓ | explicit numPr |
| 13 | 1200 | 서론 > 목적 | 10531 | `1.` | `para: 1.` | ✓ | 유일 성공 |
| 14 | 1200 | 서론 > 적용대상 | 10533 | `2.` (inferred) | `paragraph_body` | ❌ | F1 |
| 15 | 1200 | 일반원칙과 책임 | — | section 값 | section enum 없음 | ❌ | F2 |
| 16 | 240 | appendix | 보론 1 | appendix heading | `## 보론 1 …`, section=appendix | ✓ | 보론 매핑 정상 |
| 17 | 240 | (1×1 박스) | idx 1048 | `> ` block quote | `> 이 감사기준서는 …` | ✓ | 1×1 승격 정상 |
| 18 | 315 | (2×N 표) | sample | `| … | … |` table | TABLE 렌더 확인 | ✓ | 표 보존 정상 |
| 19 | 700 | application | 감사보고서 예시 | `example_text` 권장 | `paragraph_body` | △ | example_text 분류 미구현, isa_structure_profile.md EC-3 참조 (Phase 2 과제로 이월 가능) |
| 20 | 00_전문 (목차) | — | TOC 전체 | `00_전문.md` 로 격리 | 764 건 전량 격리, ISA-\*.md 0 건 | ✓ | TOC 필터링 완벽 |

**집계**: 통과 12 / 실패 7 / 부분 1 = **통과율 60 %**

실패의 **전부가 F1 (6 건)** 및 **F2 (1 건)** 에 기인. 이들 2 개 결함만 해결하면 통과율 95 %+ 도달 예상.

---

## 5. `unknown_numbering` 분포 확인

전수 스캔:

```
ISA-210.md : 3
ISA-600.md : 3
(다른 파일 0)
```

총 6 건 / 전체 ~11,400 문단 ≈ 0.053 %. 임계 5 % 한참 아래 ✓.

내용 샘플 확인 시 모두 비표준 `lvlText` 패턴 (`(%1)` lowerLetter 등) 이며 `numbering_raw` 메타 보존 확인 완료. `numbering_strategy.md §3.3` 예상 패턴과 일치.

---

## 6. 다른 검수 항목 결과

| 항목 | 결과 |
|---|---|
| heading_trail 완전성 | △ — MD 에는 `heading_trail` 주석 직접 없음. Heading 계층(`##`/`###`)으로 재구성 가능. Phase 2 에서 MD parser 가 재구성 필요. |
| section enum 매핑 | ✓ (36 ISA 중 35 ISA) / ❌ ISA-1200 (F2) |
| ISA-200 `overall_objective` | ✓ |
| ISA-1200 특수 | ❌ (F2) |
| 1×1 표 → `BLOCK_QUOTE` 승격 | ✓ (ISA-240 등 샘플 확인) |
| 2×N+ 표 → `TABLE` 유지 | ✓ (ISA-315 등 샘플 확인) |
| 목차(`ad` 스타일) 격리 | ✓ (`00_전문.md` 로 764 전량 이동, ISA-\*.md 0 건) |
| `<!-- idx: N -->` 주석 | ✓ (모든 블록에 부착) |
| `numId='0'` vs `None` 구별 | ✓ (ISA-200 idx 101/104 샘플 확인) |
| 명시 numPr 카운터 누수 | ✓ (ISA-550 첫 REQ `paragraph_id='1.'` — numId=86 공유 guard 통과) |
| `unknown_numbering` < 5 % | ✓ (0.053 %) |
| schema_version frontmatter | ✓ (37/37) |

---

## 7. 판정 및 후속 조치

### 7.1 판정

**❌ FAIL** — Phase 2 진입 보류. F1 rework 필수.

### 7.2 조치 계획

1. **본 검수자 → parser-implementer 에 DM 발송** (1차 rework 요청)
   - F1 수정 사양 (§1.5) 명시
   - F2 section enum 확장 (§2.2) 명시
   - F3 은 F1 해결 시 자동 복구 예상, 별도 수정 불요
2. **본 검수자 → `docs/numbering_strategy.md` 개정** (F1 수정안 반영)
   - §4.4 옵션 C 추가
   - §1.3 스타일 체인 상속 규약 추가
   - §6.2 `parse_styles_xml` 시그니처 추가
3. **본 검수자 → `docs/isa_structure_profile.md` 보완**
   - §3 에 스타일-상속 numPr 섹션 신설
   - ISA-1200 `목적` 빈도 3 → 6 정정
   - ISA-1200 heading 2 7 개 섹션 명시
4. **parser-implementer rework** 완료 후 본 검수자 재검수 (최대 2 회)
5. 2 회 rework 이후에도 F1 미해결 시 **team-lead 에스컬레이션**

### 7.3 Phase 2 영향

F1 미수정 상태로 Phase 2 진입 시:
- ISA-200, ISA-1200 의 search chunk 가 번호 없는 prose 로 생성 → 사용자가 "ISA 200 문단 15 찾기" 질의 시 매칭 불가
- `paragraph_id` 가 비어 `chunk_id` 충돌 발생 (동일 ISA 내 여러 chunk 가 id 없이 생성)
- Qdrant payload 의 `paragraph_id` 필터 기능 사용 불가
- 사용자 인용·근거 참조 불가 → 전체 시스템 효용 심각 저하

**→ F1 해결 없는 Phase 2 진입 불가**.

---

## 8. 부록 — 재현용 스크립트

본 검수에서 사용한 DOCX 원본 스캔 스크립트 (inline 실행).

### 8.1 스타일-상속 numPr 유실량 측정

```python
import zipfile, re
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
with zipfile.ZipFile("raw/0. 회계감사기준 전문(2025 개정).docx") as z:
    tree = ET.parse(z.open("word/document.xml"))

paras = list(tree.getroot().find(f"{W}body").iter(f"{W}p"))
bounds = []
for j, p in enumerate(paras):
    pStyle = p.find(f".//{W}pStyle")
    style = pStyle.get(f"{W}val") if pStyle is not None else ""
    if style != "10": continue
    ts = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
    m = re.match(r"감사기준서\s+(\d+)", ts)
    if m: bounds.append((int(m.group(1)), j))

ranges = {}
for i, (n, j) in enumerate(bounds):
    ranges[n] = (j, bounds[i+1][1] if i+1 < len(bounds) else len(paras))

# 각 ISA 의 "style=a1 style=A 인데 explicit numPr 없음" 카운트 = 유실량
for isa, (s, e) in sorted(ranges.items()):
    miss_req = miss_app = 0
    for j in range(s, e):
        pp = paras[j]
        pStyle = pp.find(f".//{W}pStyle")
        style = pStyle.get(f"{W}val") if pStyle is not None else ""
        if pp.find(f".//{W}numPr") is not None: continue
        if style == "a1": miss_req += 1
        elif style == "A": miss_app += 1
    if miss_req + miss_app > 0:
        print(f"ISA-{isa}: lost {miss_req} req + {miss_app} app = {miss_req+miss_app}")
```

### 8.2 parser 출력 req/app 개수 검증

```bash
for f in output/md/ISA-*.md; do
  n=$(basename "$f" .md)
  r=$(grep -c "kind: requirement" "$f")
  a=$(grep -c "kind: application_guidance" "$f")
  echo "$n req=$r app=$a"
done
```

---

*본 문서 작성 후 parser-implementer 에 rework DM 발송, team-lead 에 판정 보고 DM 발송.*

---

# 재검수 (2026-04-21, 1차 rework 이후)

**재검수자**: `audit-standard-domain-reviewer`
**대상**: parser-implementer-2 의 Task #8 rework 결과
**재검수일시**: 2026-04-21
**최종 판정**: ❌ **PARTIAL FAIL** — F1/F2/F3 ✅ 해결, **F4 신규 결함** 발견

## R1. Rework 결과 검증 (F1/F2/F3)

| 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|
| ISA-200 requirement | 24 건 | 24 건 | ✅ |
| ISA-200 app_guidance paragraphs | 83 건 (raw style='A' 92 - numId=0 suppress 9) | 83 건 | ✅ |
| ISA-200 app_guidance unique labels | A1~A83 (TOC 권위) | **A1~A82 + duplicate A1** | ❌ F4 |
| ISA-1200 requirement paragraphs | 153 (raw style='a1' 156 - suppress 3) | 153 건 | ✅ |
| ISA-1200 requirement unique labels | 1.~153. (TOC 권위) | **1.~152. + duplicate 1.** | ❌ F4 |
| ISA-500 app_guidance | ≥ 64 | 68 건 (A1~A67 + 1 중복) | ✅ count / ❌ label |
| ISA-550 첫 REQ 회귀 | paragraph_id='1.' | '1.' | ✅ |
| ISA-600 req/app 회귀 | 불변 | req=60, app=66 | ✅ |
| ISA-1200 section enum | 6 개 custom 매핑 | 7 개 확인 매핑 | ✅ |
| ISA-1200 parent link (F3) | sub_item → req 연결 | 313 건 | ✅ |
| unknown_numbering | < 5% | 0.053% (6/11267) | ✅ |
| 테스트 | green | 84/84 pass | ✅ |

**F1 CRITICAL (style 상속)** → ✅ **해결**. 820+ 누락 문단 전부 복원.
**F2 HIGH (ISA-1200 section)** → ✅ **해결**. 7 개 heading 2 매핑 확인.
**F3 MED (An→n parent)** → ✅ **해결**. F1 해결의 부수효과.

## R2. F4 신규 결함 — abstractNumId counter 공유 미구현

### R2.1 현상

전체 **36 개 ISA 모두에 duplicate marker 발생**. 통계:

| 항목 | 값 |
|---|---|
| 전체 marker emission 수 | 2,949 |
| 중복 label 종류 (unique) | 93 |
| 영향 ISA 수 | **36 / 36 (100 %)** |
| 중복 label emission 총 건수 | ~131 건 (1 label 당 2~3 회 등장) |

#### 최악 사례

| ISA | 중복 label 종류 |
|---|---|
| ISA-570 | 9 (`1.`×3, `2.`~`8.`×2, `A1.`×2) |
| ISA-500 | 8 |
| ISA-1100 | 7 (`A1.~A4.` 각 3 회) |
| ISA-550 | 7 |
| ISA-210 | 6 |
| ISA-530 | 6 |

### R2.2 근본 원인

`word/numbering.xml` 에서 서로 다른 `w:num` 이 동일 `w:abstractNumId` 를 공유하는 경우:

```xml
<w:num w:numId="57"><w:abstractNumId w:val="51"/>
  <w:lvlOverride><w:startOverride w:val="1"/></w:lvlOverride>
</w:num>
<w:num w:numId="105"><w:abstractNumId w:val="51"/></w:num>

<w:num w:numId="156"><w:abstractNumId w:val="98"/>
  <w:lvlOverride><w:startOverride w:val="1"/></w:lvlOverride>
</w:num>
<w:num w:numId="119"><w:abstractNumId w:val="98"/></w:num>
```

- numId 57, 105 : abstractNum 51 공유 (적용지침 `A%1.`)
- numId 119, 156 : abstractNum 98 공유 (요구사항 `%1.`)

현 파서는 **numId 별 독립 카운터** (Option A) 를 사용 — 즉 numId=57 첫 사용 시 `A1.`, 이어지는 numId=105 첫 사용도 `A1.` → **동일 라벨 중복**.

### R2.3 권위 데이터: raw DOCX TOC

ISA-200 원본 목차 (`style='ad'` 문단):

| TOC 항목 | 문단번호 범위 |
|---|---|
| 이 감사기준서의 범위 | 1-2 |
| 재무제표감사 | 3-9 |
| 시행일 | 10 |
| 감사인의 전반적인 목적 | 11-12 |
| 용어의 정의 | 13 |
| (요구사항) 재무제표감사에 관한 윤리적 요구사항 | 14 |
| (요구사항) 전문가적 의구심 | 15 |
| … | 24 까지 |
| **재무제표감사** (적용) | **A1-A13** |
| 용어의 정의 (적용) | A14-A16 |
| 재무제표감사에 관한 윤리적 요구사항 (적용) | A17-A20 |
| 전문가적 의구심 (적용) | A21-A25 |
| 전문가적 판단 (적용) | A26-A30 |
| 충분하고 적합한 감사증거와 감사위험 (적용) | A31-A57 |
| 감사기준에 따른 감사의 수행 (적용) | A58-A83 |

**결정적**: ISA-200 적용지침은 **A1-A83 연속 단일 스트림**이 저자 의도이며, 이는 Word 의 실제 렌더링과 일치한다. 파서의 "A1 중복 + A2~A82 시퀀스" 는 오류.

ISA-1200 TOC 유사: 목적 `1`, 적용대상 `2-5` … → **`1.`~`153.` 단일 스트림**.

### R2.4 Phase 2 에 미치는 영향 (블로커)

`docs/json_schema.md` (Phase 2 산출 예정) 의 paragraph_id 는 기준서 내 **unique key** 역할:
- Qdrant payload: `(standard_no, section, paragraph_id)` composite key
- Chunk id 해시: paragraph_id 기반
- "ISA-200 A1 참조" 등 cross-ref 파싱

`A1` 이 ISA-200 내 2 개 paragraph 에 달려있으면:
- Qdrant 업서트 시 후자가 전자를 overwrite → 데이터 손실
- 교차참조 디스앰비규에이션 불가
- 131 건의 잘못된 문단 id 발생 (전체 2949 중 4.4 %)

### R2.5 수정 사양 (2차 rework)

`numbering.py` 의 카운터 저장소를 **numId 기반 → abstractNumId 기반** 으로 전환:

```python
class NumberingEngine:
    # 현재: self._counters: dict[str, list[int]]  # numId → [c0..c8]
    # 변경: self._counters: dict[str, list[int]]  # abstractNumId → [c0..c8]
    
    def advance(self, numId: Optional[str], ilvl: Optional[int]) -> NumberedParagraph:
        # 1. numId → abstractNumId 해결 (num_defs[numId].abstractNumId)
        # 2. lvlOverride startOverride 반영:
        #    num_defs[numId] 가 ilvl 에 startOverride 를 갖고 있고
        #    이 numId 가 "이번 기준서에서 처음 등장"이면
        #    self._counters[abstractNumId][ilvl] = startOverride - 1  (advance 후 = startOverride)
        # 3. counter 증가: self._counters[abstractNumId][ilvl] += 1
        # 4. render
```

#### 핵심 불변조건

- **같은 abstractNumId 를 공유하는 모든 numId 는 하나의 카운터 스트림 공유**.
- **startOverride 는 "첫 등장 시 1 회 리셋"** 이지, 해당 numId 가 또 나올 때마다 리셋하지 않음. `_startoverride_applied: set[tuple[str, str, int]]` 로 (standard, numId, ilvl) 별 1 회 적용 가드.
- `reset()` / ISA 경계 리셋은 기존처럼 abstractNumId 별 모든 카운터 초기화 + startOverride applied set 비우기.

#### 회귀 가드

- numId=86 (ISA-550 등) 의 `1.` 유지 — 기존 동작 회귀 없음
- `unknown_numbering` < 5% 유지
- 20-샘플 재검증 통과율 100 %
- 전체 36 ISA **중복 marker 수 = 0** (TOC 대조로 저자 의도 중복 없음 확인)

#### 테스트 fixture 증분

`tests/fixtures/shared_abstract_counter_cases.json` 신규 (별도 커밋, 본 검수자 작성):
- Case 1: numId=57 (override 51) 첫 등장 → A1, 이어지는 numId=105 (no override) → A2
- Case 2: numId=105 먼저 등장 → A1, 이어지는 numId=57 (override 51) → A1 로 리셋 (rare)
- Case 3: ISA 경계에서 abstractNum 카운터 + override applied set 모두 초기화
- Case 4: suppress (numId=0) 는 카운터 미증가 (기존 동작 유지)

## R3. 20-샘플 재검증 (요약)

F1 해결로 과거 `paragraph_body` 로 떨어졌던 샘플 대부분 복원. F4 의 중복 label 은 일부 샘플의 paragraph_id 정확도를 해치지만 heading_trail · section enum 은 정상. 20-샘플 중:

- 완전 pass: 17 / 20 (85 %) — F1 복원분 포함
- F4 로 partial: 3 / 20 (duplicate label 관련)
- Fail: 0 / 20

F4 만 해결하면 pass rate ≥ 95 % 달성 가능.

## R4. 최종 판정 및 조치

| 항목 | 판정 |
|---|---|
| F1/F2/F3 rework 완수 | ✅ PASS |
| Phase 2 진입 가능 여부 | ❌ **블록** (F4 미해결 시 paragraph_id 무결성 훼손) |
| 추가 rework 요청 | ✅ **2차 rework 발동** (F4 전용) |
| team-lead 에스컬레이션 | ❌ 아직 불필요 (2-rework 예산 내) |
| 예상 수정 범위 | `numbering.py` 1 개 모듈, ~30-50 줄 |
| 예상 rework 소요 | ≤ 30 분 |
| 재-재검수 기준 | 전체 ISA duplicate label 총합 = 0, 20-샘플 pass rate ≥ 95 % |

## R5. 조치 계획

1. ✅ 본 재검수 리포트 작성 완료 (본 §재검수 섹션)
2. → parser-implementer-2 에 F4 rework DM (2차, 최종)
3. → team-lead 에 PARTIAL FAIL 보고 DM
4. Task #6 `in_progress` 유지 (2차 rework 대기)
5. 2차 rework 실패 시 team-lead 에스컬레이션

---

## R6. 최종 PASS 판정 (2026-04-21, 2차 rework 재재검수 후)

### 최종 결과

| 결함 | 검증 결과 |
|---|---|
| F1 (style 상속) | ✅ PASS (1차 rework) |
| F2 (ISA-1200 9 섹션) | ✅ PASS (1차 rework) |
| F3 (parent 매핑) | ✅ PASS (1차 rework) |
| F4 (abstractNumId 공유) | ✅ PASS (2차 rework, 잔존 6 쌍 정당 — §R6 F4 잔존 duplicate 표 참조) |
| F5 (보론 section enum) | ✅ PASS (2차 rework 내 보완) |

### F4 rework 구현 요점
- `numbering.py`: counter 저장 키 `numId` → `abstractNumId` 전환
- `_override_applied: set[tuple[str, int]]` — `(abstractNumId, ilvl)` 키 (리뷰어 초안 `(numId, ilvl)` 에서 의도적 편차)
  - 근거: ISA-315 의 7개 numId (582/586/589/591/593/595/597) 가 동일 abstract + 각자 `override={0:1}` → numId 키로는 24건 중복 발생. abstract stream 의 "첫 시작 재조정" 의미에 부합하도록 abstract 단위 1회 적용.
- `reset()` 에서 override_applied 도 clear → 기준서 경계 재적용 허용
- `structure._finalize_paragraph_id`: `section=APPENDIX` 시 `부록-` prefix 로 전역 고유성 확보 (404 건 적용)

### F5 rework 구현 요점
- `structure.py`: `_APPENDIX_HEADING2_RE = re.compile(r"^보론\s*\d+\b")` 추가
- `_classify_heading2()` 헬퍼: `_SECTION_BY_HEADING2` 정적 매핑 실패 시 regex fallback → `Section.APPENDIX` 동적 할당
- 오탐 방어: word boundary `\b` 로 "보론적인 고려사항" 등 유사어 차단
- `md_renderer`: 보론 h2/h3 는 prev_section 비교 없이 매 heading 마다 `section: appendix` 마커 발행

### 실측 지표 (재재검수)
- pytest: **90/90 pass** (F4 regression 3건 + F5 regression 2건 신규 포함)
- ruff / mypy --strict: clean
- `section: appendix` markers: 43건 / 20 파일, ISA-1200 = 2건 ✓
- `부록-` prefix 적용: 404건
- 보론 오탐: 0건
- top-level (REQ/APP) 중복: **93 → 3** (97% 감축)
- unknown_numbering_rate: 0.053% (<5% 유지)
- ISA-550 first REQ = `1.` (numId=86 독립 유지)
- ISA-200 req=24 / app=83, ISA-1200 req=153, ISA-500 app=68 (F3 이후 불변)

### F4 잔존 duplicate — Phase 2 이월 (정당성 입증)

> **2026-04-21 추가**: Phase 1.5 Task #13 (C4) 에서 잔존 duplicate 를 전수 재스캔한 결과 **6 쌍 (12 건)** 으로 확정. 각 쌍의 numId/abstractNumId/ilvl/유입경로 및 raw DOCX 증거는 **[`docs/f4_known_duplicates.md`](./f4_known_duplicates.md)** 참조 (단일 권위 소스).

raw DOCX 대조 결과 서로 다른 abstractNumId / startOverride 로 구성된 독립 stream:

| ISA | 중복 label | 첫 문단 | 둘째 문단 |
|---|---|---|---|
| ISA-250 | `12.` | numId=438, absId=**137** | numId=440, absId=**98** (startOverride=15) |
| ISA-260 | `5.` | numId=445, absId=**85** | numId=446, absId=**98** (startOverride=16) |
| ISA-260 | `6.` | numId=445, absId=**85** | style `a1` 상속 → numId=119, absId=**98** |
| ISA-300 | `7.` | numId=452, absId=**26** | numId=453, absId=**98** (startOverride=8) |
| ISA-300 | `10.` | numId=602, absId=**96** | style `a1` 상속 → numId=119, absId=**98** |
| ISA-701 | `4.` | numId=607, absId=**197** | style `A` 상속 → numId=105, absId=**51** |

**Word list independence 명세상 정상** — parser bug 아님. 상세 증거·해설은 `f4_known_duplicates.md` §3 참조.

### Phase 2 이관 제안 — composite key 강화

Phase 2 Qdrant payload composite key 를 `(standard_no, section, heading_trail_hash, paragraph_id)` 로 확장하여 `paragraph_id` 단독 고유성 부담 완화. `heading3` (subsection) 정보가 hash 에 포함되면 ISA-300 `7.` 충돌도 자동 해소. 상세 설계·대안 평가는 [`f4_known_duplicates.md §4`](./f4_known_duplicates.md#4-phase-2-해소-방안--composite-key) 에 명세. Phase 2 `md_parser` / `chunk_splitter` / `qdrant_writer` 담당은 해당 문서의 §4~§5 체크리스트를 필독할 것.

### Task 운영 마무리

- Task #6 `completed` (본 검수)
- Task #8 `completed` (F1/F2 rework)
- Task #9 `completed` (F4+F5 rework)
- Task #10 `deleted` (F5 3차 rework 불필요 — 2차 내 완료)
- Task #11 생략 (본 R6 이 precheck 대체)
- Task #7 `unblock` → devils-advocate-critic Phase 1 critique 착수 가능
