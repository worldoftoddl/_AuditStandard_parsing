# Devil's Advocate — CHECKPOINT 1 비판 보고서

> **작성자**: `devils-advocate-critic` (read-only role on `audit-parser-phase1`)
> **작성일**: 2026-04-21
> **대상 산출물**: Phase 1 (DOCX → Structured Markdown 파이프라인) 설계·구현·검수
> **참조 산출물**:
> - `docs/numbering_strategy.md`, `docs/checkpoint_1_review.md` (R1~R6 포함, 최종 PASS)
> - `src/audit_parser/ir/{types,docx_reader,styles,numbering,structure}.py`
> - `src/audit_parser/convert/md_renderer.py`, `src/audit_parser/cli.py`
> - `output/md/` 37 파일 (`00_전문.md` + `ISA-{200..1200}.md` 36 종)
> - 검증 메트릭: pytest 90/90 green, 11,267 blocks, 36 ISA boundaries, BLOCK_QUOTE 58, TABLE 16, unknown_numbering 0.053%, is_toc 761, appendix 43, paragraph_id 잔존 중복 3건
>
> **검증 대상이 “PASS”라는 사실을 알고도 미검증된 가정을 의도적으로 공격하기 위해 작성됨.** 동일 양식·심각도 라벨링은 `docs/devils_advocate_checkpoint_0.md` 와 통일.

---

## 비판 11건 요약

| # | 영역 | 표제 | 심각도 |
|---|------|------|--------|
| C1 | (j) 보안 | lxml `etree.fromstring`/`etree.parse` XXE·entity-expansion 무방어 (3 모듈) | **HIGH** |
| C2 | (b) numbering fallback | `format_counter` lowerLetter/upperLetter 27 이상 → 숫자 fallback (Word 는 `aa,ab,…`) | **HIGH** |
| C3 | (b) numbering | descent 가 ilvl 을 건너뛰면 중간 카운터가 `0` 으로 노출되어 `render_lvl_text` 가 `(0)` 같은 라벨 생산 | MED |
| C4 | (c) abstractNumId 공유 | F4 `_override_applied` key 가 spec(`(numId, ilvl)`) ↔ 구현(`(abstractNumId, ilvl)`) 로 의도적 재해석되었으나 strategy 문서가 동기화되지 않음 + 잔존 3 중복의 의미 검증 미흡 | MED |
| C5 | (a) 상태머신 커버리지 | `Section.APPENDIX` 단일 enum — 한 기준서 내 `보론 1`/`보론 2` 가 payload section 필터로 구분 불가 | MED |
| C6 | (a) 상태머신 커버리지 | `docx_reader._xml_para_text` 가 직속 `w:r` 만 iterate — `w:hyperlink`/`w:smartTag` 안 nested run 텍스트 손실 | MED |
| C7 | (b) numbering / (j) 운영 | 5% UNKNOWN_NUMBERING 임계가 `metrics()` dict 노출에 그치고 CLI/회귀가 자동 fail 시키지 않음 | MED |
| C8 | (g) schema 동기화 | YAML frontmatter 의 `schema_version="1.0"` 과 향후 Phase 2 JSON 스키마가 동일 상수를 공유 — 한쪽 bump 시 호환성 일관성 깨짐 | MED |
| C9 | (i) styles 방어 | `_resolve_style_chain` cycle 보호는 OK 이나 `_MAX_BASED_ON_DEPTH=10` 초과 시 silent `None` 반환 — 라벨이 사일런트 유실 | MED |
| C10 | (d) 1×1 표 승격 | `_is_single_cell` 가 cell 개수만 본다 — shading/border 휴리스틱 부재로 진짜 1×1 데이터 셀(예: 단일값 표) 도 인용으로 오승격 가능 | LOW |
| C11 | (f) 파싱 안정성 | HTML 주석 메타 `\| ` 구분은 paragraph_id 에 `\|` 가 등장하면 깨짐 (현재는 `부록-` prefix 만 안전) — Phase 2 파서 정규식이 fragile | LOW |

---

## C1 — lxml XXE / entity-expansion 무방어 (HIGH)

**영역**: (j) 보안

**관찰**:
세 모듈이 `lxml.etree.fromstring` / `etree.parse` 를 default parser 로 호출:

- `src/audit_parser/ir/numbering.py:133` — `root = etree.fromstring(raw_xml)`
- `src/audit_parser/ir/styles.py:73` — `root = etree.fromstring(raw_xml)`
- `src/audit_parser/ir/docx_reader.py` — `etree.parse(stream)` (XML body 순회)

세 호출 모두 `XMLParser(resolve_entities=False, no_network=True, dtd_validation=False)` 같은 안전 파서를 명시 주입하지 않으며 `defusedxml.lxml` 도 사용하지 않는다. 실측 raw/ 4 개 파일은 KICPA 공식 출처라 즉시 위험은 없지만, 본 파이프라인이 `audit-parser convert <user-supplied.docx>` 형태로 외부 입력을 받는 즉시 다음 공격 벡터가 열린다:

- **Billion-laughs / quadratic blowup**: lxml 은 default parser 에서 entity expansion 한도를 강제하지 않는다 (libxml2 의 `XML_PARSE_HUGE` 비활성 default 가 있긴 하지만 lxml 의 `huge_tree` 옵션과는 별개; `resolve_entities=True` 가 default).
- **External DTD fetch**: `<!DOCTYPE foo SYSTEM "http://attacker/...">` — `no_network=True` 가 default 이지만 lxml 버전·설정에 따라 다름. defusedxml 이 권고되는 이유.
- **XXE 파일 disclosure**: `<!ENTITY xxe SYSTEM "file:///etc/passwd">` — entity 가 활성화된 default 파서에서는 가능.

**영향**:
HIGH. PLAN.md §6 가 명시한 "신뢰된 KICPA DOCX" 가정을 어기는 즉시 — 즉, Phase 4 의 RAG 서비스에서 사용자 업로드 DOCX 를 수용하는 순간 — DoS·정보 누설 가능. 현재 파이프라인이 stdin 이 아닌 명령행 파일 경로만 받는다는 사실은 위험을 줄이지만 제거하지 않는다 (CI/CD 의 PR 첨부 docx, GitHub Actions 의 외부 PR 등).

**완화안**:

1. `defusedxml.lxml` 의존성 추가 후 3 개 호출지점을 `defusedxml.lxml.fromstring` / `parse` 로 일괄 전환. (~10 line 변경, 행위 동일)
2. 또는 명시적 안전 파서를 모듈 상수로 정의:
   ```python
   _SAFE_PARSER = etree.XMLParser(
       resolve_entities=False, no_network=True, dtd_validation=False, huge_tree=False
   )
   etree.fromstring(raw_xml, parser=_SAFE_PARSER)
   ```
3. CHECKPOINT 1 즉시 fix 권고 — Phase 2 도 `md_parser` 가 외부 도구로 생성된 MD 를 읽으므로 같은 방어가 필요. 한 번에 가이드라인화.

**왜 reviewer 가 놓쳤나**: 도메인 PASS 기준은 “파싱 정확성” 에 집중되었고 보안은 PLAN.md §6 의 “신뢰된 입력” 전제에 위임됨. 그러나 *전제가 문서화되지 않음* 자체가 결함.

---

## C2 — `format_counter` lowerLetter/upperLetter 27 이상 → 숫자 fallback (HIGH)

**영역**: (b) numbering fallback 안전성

**관찰**:
`numbering.py:298-316`:

```python
if num_fmt == "lowerLetter":
    if 1 <= value <= 26:
        return chr(ord("a") + value - 1)
    return str(value)
```

값이 27 이상이면 `"27"` 같은 숫자로 떨어진다. 그러나 Word 는 `(z), (aa), (ab), …` 로 base-26 자릿수 확장 (Excel column letter 와 동일 규칙). 대문자도 동일.

실측 메트릭만으로는 트리거되지 않을 가능성이 높지만:

- 36 개 기준서 + 보론 43 + 본문 11,267 블록 = (a)~(z) 27 항목 이상 sub-item 이 한 단일 numbering stream 에 등장하지 않는다는 보장은 없음. 특히 ISA-315 (위험평가 — KICPA 본문 50+ 항목), ISA-540 (회계추정치) 등 부록의 “감사문서 예시 항목” 은 (a) 부터 빈번히 사용.
- F4 rework 가 abstractNumId 단위 카운터로 통합되면서 "한 abstract 의 한 ilvl" 이 누적되는 항목 수가 *늘어났다*. 즉 27 초과 가능성이 F4 이전보다 높음.

**영향**:
HIGH (잠재적). 트리거되면 paragraph_id 가 `(27)` 처럼 깨지고 (1) Phase 2 의 paragraph_id 정규식 (예상: `^[A-Za-z0-9가-힣().-]+$`) 통과해버려 silent corruption, (2) parent linking 이 child 의 lvlText `%1.%2` 를 렌더할 때 `1.27` 같은 비정상 키 생산, (3) Qdrant payload 의 paragraph_id 검색 (`section: APPLICATION AND OTHER MATERIAL`) 에서 사용자가 `aa` 로 검색해도 매칭 안 됨.

현재 회귀 테스트에 lowerLetter 27 경계 검증이 없다 (90/90 green 이지만 *없는 케이스를 검증할 수 없음*).

**완화안**:

1. `_to_alpha(value)` helper 추가 — base-26 conversion (Excel column letter 와 동일):
   ```python
   def _to_alpha(value: int, upper: bool) -> str:
       if value <= 0: return str(value)
       letters = []
       while value > 0:
           value, rem = divmod(value - 1, 26)
           letters.append(chr(ord("A" if upper else "a") + rem))
       return "".join(reversed(letters))
   ```
2. pytest 회귀: `format_counter(27, "lowerLetter") == "aa"`, `format_counter(703, "upperLetter") == "AAA"`.
3. 로마자도 점검 권고 — `_to_roman` 은 매우 큰 값 (5000+) 에서 `mmmmm…` 무한히 늘어남. 실측 트리거 가능성은 낮지만 cap (예: 3999 초과 시 `str(value)`) 가 문서화되지 않음.

**메모**: 이 결함은 reviewer 의 “93→3 잔존 중복” 검증으로는 발견되지 않는다 — 잔존 중복은 *동일 abstract stream 내* 충돌이고, C2 는 *고유 라벨이 깨지는* 문제다.

---

## C3 — descent 시 ilvl skip → 중간 카운터 0 노출 (MED)

**영역**: (b) numbering replay

**관찰**:
`numbering.py:491-499`:

```python
prev = self._last_ilvl.get(abstract_id)
if prev is not None and ilvl > prev:
    starts = self._starts[abstract_id]
    for lv in range(prev + 1, ilvl + 1):
        counters[lv] = starts[lv] - 1
counters[ilvl] += 1
counter_tuple = tuple(counters[: ilvl + 1])
```

문서가 `ilvl=0 → ilvl=2` 로 한 단계 건너뛰는 descent 에서:

1. `prev=0`, `ilvl=2` → 루프가 `lv=1, 2` 를 모두 `start-1` 로 세팅.
2. `counters[2] += 1` → `start[2]` 값. 그러나 `counters[1]` 은 `start[1] - 1` (보통 0).
3. `counter_tuple = (counters[0], 0, start[2])` 같은 튜플.
4. `render_lvl_text` 가 `lvlText="(%1)(%2)(%3)"` 같은 식을 만나면 `%2` placeholder 로 `format_counter(0, "lowerLetter")` 호출 → C2 의 fallback path 인 `"0"` 반환.
5. 결과 paragraph_id: `"(1)(0)(i)"` 같은 잘못된 라벨.

**영향**:
MED. ISA DOCX 에서 ilvl skip 은 작가가 “(가) → (1) → (i)” 처럼 한 단계 건너뛸 때 발생. 실측에서 빈번하지는 않지만 *발생 시 silent corruption* 이고, BlockKind 분류는 여전히 SUB_ITEM 으로 남아 검출 자체가 어렵다 (UNKNOWN_NUMBERING 으로 떨어지지 않음).

또한 reviewer 의 R6 PASS 에 “93→3” 으로 표기된 잔존 3 건 중 일부가 실은 이 버그의 결과일 가능성 — strategy 문서·검수 보고서 어디에도 “3 건의 abstract/ilvl 분포” 가 정량 분석되지 않았다.

**완화안**:

1. descent 시 중간 ilvl 도 `+= 1` 처리 (논리: skip 은 작가의 typo 로 보고 1 부터 시작):
   ```python
   for lv in range(prev + 1, ilvl + 1):
       counters[lv] = starts[lv]   # not -1
   ```
   단, 이렇게 바꾸면 `counters[ilvl] += 1` 이 `start+1` 을 만들어 oversahot. 따라서 `if lv == ilvl: counters[lv] = starts[lv] - 1; else counters[lv] = starts[lv]` 로 분기.
2. `render_lvl_text` 가 `value == 0` 인 placeholder 를 만나면 *경고 + lvlText 통째로 raw 반환*.
3. 회귀 테스트: 인공 RawBlock 시퀀스 `(numId=X, ilvl=0), (numId=X, ilvl=2)` 에 대해 두 번째 paragraph_id 가 “0” 을 포함하지 않는지 단언.

---

## C4 — F4 `_override_applied` key 재해석 — 문서·구현 불일치 + 잔존 3 중복 미설명 (MED)

**영역**: (c) abstractNumId 공유 부수효과

**관찰**:
`numbering.py:381` 의 `_override_applied: set[tuple[str, int]]` 가 `(abstractNumId, ilvl)` 로 키되어 있다. 코드 주석(367-380, 481-483) 은 이를 “reviewer 지시문은 `(numId, ilvl)` 이었으나 실측에 맞춰 abstract 단위로 재해석” 했다고 명시.

문제:
1. `docs/numbering_strategy.md` (Domain Reviewer 소유) 가 *F4 rework 후 갱신되지 않음*. spec 문서는 여전히 numId 단위 기술. 차후 외부 기여자가 strategy 문서만 읽고 구현을 “수정” 하면 회귀 발생.
2. `docs/checkpoint_1_review.md §R5/R6` 에 “93 → 3 잔존 중복” 이라고만 표기되어 있고, 잔존 3 건의 실제 (standard_no, paragraph_id, abstract_id) 가 *기록되지 않음*. PLAN.md §11 CHECKPOINT 1 결과에도 “정상”이라고만 평가.
3. 잔존 3 건이 *어떤 패턴* (예: 동일 기준서 내 두 abstract 가 동시에 (a) 를 만들어 본문·부록 충돌, 또는 두 보론 영역의 부록-1 충돌) 인지 분석되지 않으면 Phase 2 의 "paragraph_id 단독 키" 전략이 *암묵적으로 깨짐*.

**영향**:
MED. 잔존 3 건이 본문 vs 보론 처럼 *section 으로 구분되는* 경우라면 Phase 2 composite key (section, paragraph_id) 로 안전. 그러나 동일 section 내 충돌이라면 Qdrant payload 검색에서 ambiguous match → RAG 응답 정확도 저하. 본 비판은 “문서가 침묵하므로 알 수 없다” 그 자체를 결함으로 본다.

**완화안**:

1. `docs/numbering_strategy.md §4.2/§4.3` 에 F4 결정 (abstract 단위 override 적용) 을 *공식화* 하고 그 근거 (실측 ISA-315 의 numId 7 개가 동일 abstract 공유) 를 인라인 인용.
2. `docs/checkpoint_1_review.md` 에 잔존 3 건의 enumeration (standard_no + paragraph_id + heading_trail tail + section) 추가. parser-implementer-2 가 30 분 내 산출 가능 (`output/md/` grep 으로 충분).
3. Phase 2 `md_parser` 의 unique key 전략을 `(standard_no, section, paragraph_id)` 로 명문화. 단순 `(standard_no, paragraph_id)` 가정 회피.

---

## C5 — `Section.APPENDIX` 단일 enum — 보론 1/2/3 구분 불가 (MED)

**영역**: (a) 상태머신 커버리지

**관찰**:
`structure.py:_classify_heading2` 는 `보론 N ...` 패턴을 모두 `Section.APPENDIX` 단일 값으로 매핑. ISA-315/540 등은 보론 1·보론 2·보론 3·보론 4 가 등장 (예: ISA-315 보론 1 “위험평가절차 사례”, 보론 2 “정보기술 통제”, 보론 3 “…”).

block payload 에는 `section: APPENDIX` + `heading_trail: ("감사기준서 315", ..., "보론 2 …")` 식으로 들어가지만, *Qdrant payload filter* `section == "appendix"` 만으로는 어느 보론인지 구분할 수 없다. Phase 3 RAG 의 사용자 쿼리 “ISA-315 보론 2 의 IT 통제 항목” 을 정확히 매칭하려면 `heading_trail` startswith filter 가 추가로 필요.

**영향**:
MED. heading_trail 로 보완 가능하므로 데이터 자체는 잃지 않음. 그러나 (1) Qdrant payload 인덱스를 section 에 만들면 효과 절감, (2) Phase 2 JSON 스키마에서 `section: "appendix"` 의 enum 카디널리티가 작아 통계·집계 부정확.

**완화안**:

1. `Section.APPENDIX` 를 유지하되, Block 에 `appendix_index: int | None` (보론 N 의 N) 필드 추가. structure.py 가 `_APPENDIX_HEADING2_RE = re.compile(r"^보론\s*(\d+)\b")` 의 그룹 1 을 추출.
2. 또는 enum 을 `APPENDIX_1`, `APPENDIX_2`, …, `APPENDIX_N` (N=8 정도면 충분) 로 확장 — 단순하지만 카디널리티 폭발.
3. md_renderer 의 HTML 주석에 `appendix: 2` 추가 하여 Phase 2 가 추출.

reviewer 는 이미 R3 에서 “F5 — 보론 heading 마다 section 주석 emit” 을 적용했으므로 *영역 인지* 는 했으나 *구분 자체* 는 손대지 않음.

---

## C6 — `_xml_para_text` 가 `w:hyperlink`/`w:smartTag` 안 nested run 텍스트 손실 (MED)

**영역**: (a) 상태머신·DOCX body 순회

**관찰**:
`docx_reader.py` 의 `_xml_para_text` 는 `<w:p>` 의 직속 `<w:r>` 만 iterate 한다. 그러나 OOXML 은 `<w:p>` 자식으로 `<w:hyperlink>` (외부/내부 링크), `<w:smartTag>`, `<w:fldSimple>`, `<w:ins>`/`<w:del>` (변경 추적) 등이 올 수 있고, 그 내부에 `<w:r>` 이 nested 된다.

ISA DOCX 에는 “감사기준서 200 의 23 호 참조” 같은 cross-reference 가 자주 등장하는데, Word 가 자동 cross-reference 로 만든 경우 `<w:fldSimple>` 또는 `<w:hyperlink>` 안의 `<w:r>` 로 들어간다. 이런 텍스트가 *통째로 누락*될 수 있다.

**영향**:
MED. 빈도는 추정 — 11,267 블록 중 cross-ref 비율 1~3% 가정하면 100~300 블록의 *부분 텍스트 손실*. block 자체는 보존되지만 본문 일부가 사라져 RAG 응답에 “문장이 끝맺지 않음” 같은 증상으로 나타날 수 있다.

검증 방법: `Grep "(([0-9]+호|문단 [0-9]+))" output/md/` 의 매칭 수와 KICPA 원문 PDF 의 동일 패턴 수 비교.

**완화안**:

1. `_xml_para_text` 를 `for r in p.iter("{...}r")` (descendant) 로 변경. 단, `<w:rPr>`/`<w:numPr>` 안의 noise run 이 없는지 확인 필요.
2. 또는 명시적으로 `w:hyperlink`, `w:smartTag`, `w:fldSimple`, `w:ins` 4 종을 children 으로 인정하는 화이트리스트 추가.
3. 회귀 fixture: ISA-200 의 cross-reference 1 줄을 잘라낸 미니 DOCX 로 unit test.

---

## C7 — 5% UNKNOWN 임계 미강제 (MED)

**영역**: (b) numbering fallback / (j) 운영

**관찰**:
`docs/numbering_strategy.md §5.2` 가 “unknown_numbering 비율이 5% 초과 시 abort + 사람 검토” 를 정책으로 명시. 그러나 `numbering.py.metrics()` 는 단지 dict 를 반환할 뿐, CLI (`audit-parser convert`) 가 종료 시 임계를 *체크하지 않는다*. `cli.py` (검수 시점 58 line) 에는 metrics 호출 자체가 없다.

R6 검수가 “unknown 0.053%” 라고 PASS 한 것은 *수동 측정*이며, 향후 신규 DOCX (예: ISQM 1, 인증업무개념체계) 에 대해 임계가 자동 발효된다는 보장이 없다.

**영향**:
MED. Phase 2/3 진입 시 silent regression 위험. unknown 이 5% 가 되는 입력이 들어와도 파이프라인은 “success” 로 끝나고 산출물 MD 가 깨진 채 ingest 단계로 전파.

**완화안**:

1. `cli.py` 의 `convert` 명령 종료 직전:
   ```python
   metrics = engine.metrics()
   total = sum(metrics.values())
   unknown_ratio = metrics.get("unknown_numbering", 0) / total if total else 0
   if unknown_ratio > 0.05:
       typer.echo(f"FAIL: unknown_numbering {unknown_ratio:.2%} > 5%", err=True)
       raise typer.Exit(code=1)
   ```
2. 회귀 fixture: 의도적으로 망가진 numbering.xml 로 임계 초과 → exit code 1 단언.
3. 임계 자체는 환경변수 (`AUDIT_PARSER_UNKNOWN_THRESHOLD=0.05`) 로 노출.

---

## C8 — `schema_version="1.0"` 의미적 공유 (MED)

**영역**: (g) schema_version 동기화

**관찰**:
`md_renderer.py:28` `SCHEMA_VERSION: Final = "1.0"` 가 YAML frontmatter 의 `schema_version: "1.0"` 으로 출력된다. PLAN.md §4 와 CLAUDE.md §4 가 향후 Phase 2 JSON 스키마도 같은 키 (`schema_version`) 를 갖는다고 명시.

만약 두 스키마 (MD frontmatter ↔ JSON) 가 같은 상수를 공유하는데, 둘 중 *하나만* breaking change 를 일으켜 bump 해야 할 때 — 예: MD HTML 주석 포맷이 `kind:` 에서 `k:` 로 변경되어 “1.1” 로 올렸다면 JSON 스키마는 호환되지만 같은 “1.1” 라벨을 강요받음.

**영향**:
MED. Phase 2 진입 시 “MD schema 1.x ↔ JSON schema 1.y” 분리가 강제되거나, 한쪽 호환성을 깨면서 의도치 않게 다른 쪽도 “bump” 한 것처럼 보이게 된다.

**완화안**:

1. 명시적 분리: `md_renderer.MD_SCHEMA_VERSION = "1.0"`, 향후 `md_parser.JSON_SCHEMA_VERSION = "1.0"`. 같은 모듈에 두지 말고 각 layer 책임.
2. PLAN.md §4 와 `docs/json_schema.md` (Phase 2 산출 예정) 에 “두 스키마 버전은 독립 bump” 명문화.
3. YAML frontmatter 키도 명시적으로 `md_schema_version` 으로 rename 권고 (1.0 라벨 동안).

---

## C9 — `_resolve_style_chain` depth 초과 시 silent `None` 반환 (MED)

**영역**: (i) styles.xml basedOn 방어

**관찰**:
`styles.py:153-187` 의 `_resolve_style_chain`:

```python
if depth >= _MAX_BASED_ON_DEPTH:
    return None
```

depth 10 초과 시 `None` 반환 → caller (`resolve_paragraph_numPr`) 가 `(None, p_ilvl)` 를 받아 *그 문단을 numbering 없는 일반 본문* 으로 처리. 즉 라벨 silent 유실.

ISA 본문은 basedOn 체인이 보통 2~4 단계지만 KICPA 가 향후 styles.xml 을 재구조화하거나 ISQM 1 / 인증업무개념체계 에서 더 깊은 체인이 있을 가능성이 있다. F1 rework 가 이 케이스를 고친 것은 정상이지만 *방어 결과를 사용자가 알 길이 없다*.

또한 cycle 방어 (`visited.add(style_id)`) 가 cycle 발견 시 `None` 반환 — 동일하게 silent.

**영향**:
MED. F1 reworked 가 “820+ 문단 라벨 유실” 을 고친 그 동일 카테고리의 silent failure 가 “depth 초과” / “cycle” 두 path 로 잔존. 빈도는 낮지만 발생 시 *어느 styleId 가 truncate 됐는지조차 알 수 없다*.

**완화안**:

1. 두 path 모두 `warnings.warn(..., UserWarning)` 1 회 발행 (style_id 포함).
2. 깊이 초과의 정의 자체를 재고: 10 은 충분히 보수적이지만, 도달 시 warn + best-effort `(None, p_ilvl)` 반환.
3. parse_styles_xml 시점에 cycle 을 한 번에 검출하고 `StyleIndex` 에 `cycle_styles: frozenset[str]` 를 추가하면 런타임 검사 비용 0.

---

## C10 — 1×1 표 BLOCK_QUOTE 승격 휴리스틱 단순 (LOW)

**영역**: (d) BLOCK_QUOTE 승격

**관찰**:
`structure.py:_is_single_cell` 은 `len(cells) == 1 and len(cells[0]) == 1` 만 검사. R-section 보고서의 “78% 표가 인용 박스” 통계는 정확하나, 22% 의 “진짜 단일 셀 데이터 표” (예: ISA-540 의 단일값 추정 박스, 예시 표) 도 함께 인용으로 승격된다.

**영향**:
LOW. 인용으로 잘못 승격되어도 텍스트는 보존됨. 단, MD 렌더 시 `> ` prefix + `<!-- kind: block_quote -->` 메타가 붙어 Phase 2 chunk_splitter 가 “인용 청크” 로 분리하면 의미 단위가 어긋날 수 있다.

**완화안**:

1. `<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="…"/>` 의 fill 색이 회색/배경색이 있을 때만 BLOCK_QUOTE 로 승격. ISA 의 인용 박스는 보통 음영 처리.
2. 또는 단순히 `len(text) > 50` 같은 길이 휴리스틱 — 짧은 단일 셀은 데이터 셀로 가정.
3. 현재 산출물 58 BLOCK_QUOTE 를 sample 검토 — false positive 비율이 0~2 건이면 휴리스틱 강화 불필요. 측정만 권고.

---

## C11 — HTML 주석 메타 `|` 구분의 fragility (LOW)

**영역**: (f) Phase 2 파싱 안정성

**관찰**:
`md_renderer.py:_build_paragraph_comment` 는 `<!-- para: X | kind: Y | parent: Z | idx: N -->` 형식. Phase 2 가 이를 파싱하려면 `re.split(r"\s*\|\s*", inner)` 같은 정규식이 필요. 만약 paragraph_id 또는 그 어떤 값에 `|` 가 등장하면 split 이 깨진다.

현재는 paragraph_id 가 `1.`, `(a)`, `(i)`, `A1.`, `부록-1.` 패턴만 있어서 안전. 그러나:

- `_finalize_paragraph_id` 가 `부록-` prefix 로 보론을 처리하는 *수동 escape 가 아닌 prefix-by-convention* 만 사용. 향후 “부록-A1” 처럼 patterns 확장 시 `|` 충돌은 없지만, 다른 메타 (예: heading_trail) 를 같은 주석에 추가하면 trail 의 `|` 위험 노출.

**영향**:
LOW. 현재로는 안전. 그러나 “HTML 주석 + pipe-delimited” 자체가 인-밴드 ad-hoc 직렬화이며, JSON 또는 YAML inline 같은 *공식 직렬화* 가 robust.

**완화안**:

1. `<!-- meta: {"para":"1.", "kind":"requirement", "parent":null, "idx":42} -->` JSON inline 으로 변경 — `_render_*` 4 곳 수정 + Phase 2 파서 단순화.
2. 유지하려면 `_escape_pipe(s) -> s.replace("|", "&#124;")` 헬퍼 + Phase 2 파서가 unescape.
3. 회귀 fixture: paragraph_id 에 `|` 를 인위적으로 주입한 RawBlock 을 통과시켜 메타 파싱이 깨지는지 단언 (현재는 깨짐 자체를 검증하지 않음).

---

# Go / No-Go 판정

## 판정: **CONDITIONAL GO**

PLAN.md §11 의 CHECKPOINT 1 PASS 와 reviewer R6 최종 PASS 를 부정하지 않는다. 90/90 pytest green, 0.053% unknown_numbering, 36/36 ISA boundary, 잔존 중복 3 건은 모두 spec 준수 결과로서 **Phase 2 진입 자체는 막을 이유가 없다**.

다만 다음 2 건의 HIGH 결함은 **Phase 2 진입 전에 fix 권고**:

- **C1 (lxml XXE)** — defusedxml 도입 또는 명시적 안전 파서. 30 분 작업.
- **C2 (`format_counter` 27+)** — base-26 conversion + 회귀 테스트. 1 시간 작업.

위 둘은 *현재 산출물에는 영향 없음* 이므로 산출 MD 를 폐기·재생성할 필요 없음. 단, Phase 2 가 동일 파이프라인을 ISQM 1 / 인증업무개념체계에 적용할 때 *위 두 결함이 트리거될 가능성이 비-zero* 이므로 “두 번째 입력 파일 처리 전” 에 fix.

MED 7 건 중 다음 3 건은 **Phase 2 설계 시점에 반드시 명시적 결정**:

- **C4 (잔존 3 중복 enumeration)** — Phase 2 의 unique key 전략이 (standard_no, paragraph_id) 인지 (standard_no, section, paragraph_id) 인지 결정. 30 분 분석.
- **C5 (보론 N 구분)** — appendix_index 필드 추가 또는 명시적 enum. Phase 2 JSON 스키마에 그대로 전파됨.
- **C7 (5% 임계 자동 강제)** — Phase 2 신규 DOCX 처리 시 silent regression 차단.

나머지 MED 4건 + LOW 2건은 Phase 2 진행 중 점진적 개선 권고.

---

## 부록 — Phase 0 보고서와의 일관성

`docs/devils_advocate_checkpoint_0.md` 의 8 비판 (D1~D8) 중 D2 “XXE 무방어” 는 Phase 0 시점에 “파이프라인 미구현” 으로 보류 권고였다. C1 은 D2 의 구현 단계 reaffirmation 이며 fix 가 더 이상 미뤄질 수 없다.

D5 “HTML 주석 ad-hoc 직렬화” 는 본 보고 C11 로 재현. Phase 0 에서 LOW 평가 → Phase 1 에서도 LOW 유지. fix 우선순위 낮음.

D6 “schema_version 카운터 누설” 은 본 보고 C8 로 구체화. Phase 2 진입 전 명시적 분리 결정 권고.

---

**서명**: `devils-advocate-critic` — read-only role, no source modification performed.
