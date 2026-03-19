# Plot Generation — Prompt Evaluation Criteria

## Context

이 문서는 Claude가 생성하는 **plain text 스토리보드**의 품질을 평가하기 위한 기준을 정의한다.

### Pipeline 흐름

```
유저 텍스트 입력
  → Claude (plot_generator): plain text 스토리보드 초안 생성
  → plot_evaluator.full_eval(): 자동 채점  ← plot-generation 루프에서는 항상 full_eval
  │
  ├─ 5점 이상 → Human Eval 진입
  └─ 5점 미만 → plot_advisor.generate_advice(): 가이드라인 생성
                → 유저 수정사항 입력 → generate_plot(previous_storyboard + modification)
                → full_eval() → 루프
  │
  → Human Eval: 유저 직접 판단 (Phase 4)
  → 만족 → plot_converter.parse_storyboard() → JSON 저장 → 이미지 생성
  → 불만족 → 피드백 funnel → plot_advisor → 유저 수정 → 루프
  │
  → 이미지 생성 후 특정 컷 수정 시:
    scenes_to_plain_text() → generate_plot() → plot_evaluator.focused_eval()  ← 여기서만 focused_eval
```

### 핵심 원칙

- Claude 출력은 **confirm 전까지 항상 plain text**를 유지한다.
- JSON 변환은 **confirm 후 backend 책임**이다 (Claude가 하지 않음).
- 따라서 evaluation 기준은 **plain text 품질** + **JSON 파싱 가능성** 두 축을 모두 평가해야 한다.

---

## Evaluation Criteria Table

### Code Grader — 자동화 가능한 프로그래밍 체크

| # | Criteria | What It Checks | Why It Matters | Downstream Impact |
|---|----------|----------------|----------------|-------------------|
| C1 | **Parseable structure** | plain text가 일관된 구분자/패턴을 갖고 있어 backend 파싱이 가능한가 (예: `[Cut 1]`, `[Cut 2]` 등의 반복 패턴) | confirm 후 backend이 regex/split으로 JSON 변환할 때, 패턴이 불규칙하면 파싱 실패 → 이미지 생성 불가 | → JSON 변환 → Hugging Face 이미지 생성 파이프라인 전체 |
| C2 | **Required fields present** | 각 컷에 필수 요소가 모두 포함되어 있는가: characters, composition, background, lighting, mood, story_beat, action, pose | 빠진 필드 = backend template prompt에 빈 슬롯 → Hugging Face 이미지 생성 파이프라인이 무작위 이미지 생성 | → Hugging Face 이미지 생성 파이프라인 prompt 품질 |
| C3 | **Cut count range** | 컷 수가 5–10개 범위 안인가 | 5개 미만 = 최종 영상 15초 미달 (Shorts/TikTok 부적합). 10개 초과 = Veo 2 비용 폭발 + 30초 초과 | → Veo 2 비용 → FFmpeg merge |
| C4 | ~~**No empty descriptions**~~ | **C2에 통합됨.** C2가 필드 존재 여부와 placeholder("없음", "N/A", "-") 모두 검사. | — | — |
| C5 | **Unsafe content filter** | 폭력, NSFW, 혐오 표현 등 Veo 2 safety policy 위반 키워드가 없는가 | Veo 2가 unsafe prompt를 거부 → 해당 컷 영상 생성 실패 → 부분 실패로 merge 품질 저하 | → Veo 2 rejection 방지 |

### Model Grader — AI 기반 품질 평가

| # | Criteria | What It Checks | Why It Matters | Downstream Impact |
|---|----------|----------------|----------------|-------------------|
| M1 | **Image prompt quality** | composition, background, lighting 묘사가 Hugging Face 이미지 생성 파이프라인이 구체적 이미지를 생성할 만큼 구체적인가 | "예쁜 배경" 같은 모호한 표현 → Hugging Face 이미지 생성 파이프라인이 매번 다른 이미지 생성 → 일관성 파괴 | → Hugging Face 이미지 생성 파이프라인 출력 품질 |
| M2 | **Character consistency** | 동일 캐릭터가 전체 컷에서 동일한 외형(의상, 헤어, 체형 등)으로 묘사되는가 | Hugging Face 이미지 생성 파이프라인은 컷별로 독립 생성 → Claude가 "Cut 1: 빨간 자켓" / "Cut 5: 파란 코트"로 쓰면 캐릭터가 달라짐 | → 컷 간 시각적 일관성 |
| M3 | **Story coherence** | 컷들이 논리적 서사 흐름(도입→전개→클라이맥스→마무리)을 형성하는가 | 무작위 장면 나열 → merge 후 영상이 슬라이드쇼처럼 보임 → 심사 "효과성"(20점) 직결 | → 최종 영상 완성도 |
| M4 | **Motion describability** | 각 컷이 Veo 2가 애니메이션으로 만들 수 있는 명확한 동작을 암시하는가 (시작→끝 움직임) | "캐릭터가 서있다" → Veo 2가 정지 이미지만 생성 → 영상이 아니라 사진 슬라이드가 됨 | → Veo 2 클립 품질 |
| M5 | **Genre rule adherence** | 장르별 우선순위를 따르는가: K-pop(조명+패션), anime(화풍), game(구도+배경) | 장르 특성 무시 → 팬 콘텐츠가 아닌 범용 AI 이미지로 보임 → 심사 "창의성"(30점) 직결 | → 팬 authentic 느낌 |
| M6 | **Backend parseable intent** | plain text의 각 필드가 명확하게 구분되어 있어 backend이 정확히 어떤 값을 어떤 JSON key에 매핑해야 하는지 판단할 수 있는가 | 모호한 서술 → backend 파싱 시 `action`과 `pose`가 뒤섞이거나, `background`와 `era`가 혼동됨 | → JSON 변환 정확도 |

> **Focused Eval 참고:** M5(Genre rule adherence)와 M6(Backend parseable intent)는 Focused Eval에서 제외된다.
> - M5 제외: 부분 수정으로 전체 장르 톤이 바뀌지 않음
> - M6 제외: 전체 파싱 구조는 이미 Full Eval에서 검증됨

### Human Grader — 유저 주관 평가 (Human Eval 단계)

| # | Criteria | What It Checks | Why It Matters | Downstream Impact |
|---|----------|----------------|----------------|-------------------|
| H1 | **Fan-appeal** | K-pop/anime/game 팬이 실제로 보고 싶어할 내용인가 | 심사 기준 "창의성"(30점) + "사용성"(20점) 직결. 팬 크리에이터가 타겟 유저 — 그들의 취향이 ground truth | → 최종 영상 매력도 |
| H2 | **Emotional pacing** | 15–30초 안에서 긴장감, 놀라움, 감정적 보상이 느껴지는가 | 숏폼 영상은 페이싱이 전부. 구조는 맞아도 감정적으로 밋밋하면 시청 유지 불가 | → 최종 영상 몰입감 |
| H3 | **Input faithfulness** | 유저가 입력한 아이디어가 충실히 반영되었는가 (원치 않는 요소 추가나 핵심 누락 없이) | "슬램덩크 강백호 마지막 슛"을 입력했는데 일반 농구 장면이 나오면 실패 — 이건 사람만 판단 가능 | → 유저 만족도 |

---

## Evaluation 실행 순서

```
Step 1: Code Grader (C1–C5)
  → 통과하지 못하면 즉시 유저에게 구체적 실패 사유 + 수정 가이드 제공
  → 여기서 걸리면 Model Grader 단계로 가지 않음

Step 2: Model Grader (M1–M6)
  → 각 항목 1–10점 채점
  → 5점 미만 항목 → plot_advisor가 유저에게 가이드라인 리포트 생성
  → 유저가 직접 수정 → plot_generator 재생성 → 재평가 루프

Step 3: Human Evaluation (H1–H3)
  → Step 1, 2를 5점 이상으로 통과한 결과물만 유저에게 도달
  → 유저가 만족 → confirm → backend JSON 변환
  → 유저가 불만족 → 피드백 funnel → plot_advisor → 유저 수정 → 루프
```

---

## Focused Eval — 이미지 수정 후 부분 평가

이미지 생성 완료 후 유저가 특정 컷을 수정하면, Full Eval 대신 Focused Eval을 적용한다.

### 평가 대상 컷 선정
- 유저가 수정 요청한 컷 번호(changed_cuts)
- 인접 컷: changed_cuts 각각의 ±1 (서사 연결성 확인)
- 예: changed_cuts=[3] → 평가 대상: Cut 2, 3, 4

### 적용 기준

| 구분 | Full Eval | Focused Eval | 제외 사유 |
|------|-----------|--------------|-----------|
| C1 Parseable structure | ✓ | ✗ | 전체 구조는 이미 검증됨 |
| C2 Required fields | ✓ | ✓ | 수정된 컷에서 필드 누락 가능 |
| C3 Cut count range | ✓ | ✗ | 컷 수는 변경되지 않음 |
| C4 No empty descriptions | ✓ | ✗ | C2에 통합됨 — C2가 빈 필드 포함하여 검사 |
| C5 Unsafe content | ✓ | ✓ | 수정 내용에 unsafe 표현 가능 |
| M1 Image prompt quality | ✓ | ✓ | 수정된 컷의 이미지 품질 확인 |
| M2 Character consistency | ✓ | ✓ | 수정이 캐릭터 일관성을 깨뜨릴 수 있음 |
| M3 Story coherence | ✓ | ✓ | 인접 컷과의 서사 연결 확인 |
| M4 Motion describability | ✓ | ✓ | 수정된 동작 묘사 품질 확인 |
| M5 Genre adherence | ✓ | ✗ | 부분 수정으로 장르 톤이 바뀌지 않음 |
| M6 Parseable intent | ✓ | ✗ | 전체 파싱 구조는 이미 검증됨 |

### 합격선 및 실패 처리
- 합격선: 5.0 (Full Eval과 동일)
- Focused Eval 실패 → full_eval로 폴백 (전체 재평가)
- Focused Eval 자체 에러 → full_eval로 폴백

---

## Score → Action 매핑

합산 점수 = (Code 평균 + Model 평균) / 2 기준.
Code 평균 5점 미만이면 Model Eval 없이 Code Eval 루프부터 순환.

| 합산 점수 | Action |
|---|---|
| Code 평균 < 5.0 | Model Eval 실행 안 함 → failed_items 가이드 → 유저 수정 입력 → full_eval 재실행 |
| 합산 1.0–4.9 | failed_items 기반 가이드라인 출력 → 유저 수정 입력 → 재생성 → full_eval 재실행 |
| 합산 5.0–10.0 | 통과 → Human Eval 진입 (Phase 4) |

> **현행 CLI (Phase 3) 기준:** 5.0 이상이면 점수 구간 관계없이 바로 통과 처리.
> 5.0~7.9 구간의 "약점 요약 + 유저 선택" 분기는 Phase 4 Human Eval UI에서 구현 예정.

---

## Score Display UI — 유저에게 점수를 보여주는 방식

매번 prompt evaluation이 실행될 때, 유저에게 "점수 + 피드백/가이드라인/추천"을 보여줘야 한다.
핵심 원칙: **한눈에 점수 파악 + 필요한 만큼만 디테일**.

### 1. 전체 점수 — 큰 숫자 + 색상 원형

화면 상단에 원형 안에 큰 숫자로 표시. 유저가 0.5초 안에 현재 상태를 파악할 수 있어야 한다.

| 점수 구간 | 원형 색상 | 아래 한 줄 메시지 |
|----------|----------|-----------------|
| 8.0–10.0 | 초록 | "좋은 스토리보드예요! 확인 후 영상을 만들어보세요" |
| 5.0–7.9 | 노랑 | "조금만 더 보완하면 더 좋은 영상이 됩니다" |
| 1.0–4.9 | 빨강 | "아래 가이드를 참고해서 보완해보세요" |

표시 형태: 원형 안에 **"7.2"** (큰 숫자) + 바로 아래 **"/ 10"** (작은 숫자)
한 줄 메시지 외에 추가 텍스트 없음.

### 2. 항목별 점수 — 낮은 항목만 바(bar)로 표시

C1~M6 전체를 나열하면 11줄이라 너무 많다. 대신:

- **5점 미만 항목만** 짧은 가로 바로 표시. 항목명은 한국어 한 줄로 축약.
- **5점 이상 항목은 접어두고** "✓ 6개 항목 통과" 같은 뱃지로 요약.

| 표시 예시 | 의미 |
|----------|------|
| `캐릭터 일관성 ████░░░░░░ 3.2` | M2가 3.2점 — 보완 필요 |
| `동작 묘사 ██░░░░░░░░ 2.8` | M4가 2.8점 — 보완 필요 |
| `✓ 7개 항목 통과` | 나머지는 5점 이상 — 문제 없음 |

이렇게 하면 유저는 **"어디가 문제인지"만 빠르게 파악**하고, 잘 된 부분에 시간을 뺏기지 않는다.

### 3. 가이드라인 — 낮은 항목 바를 탭하면 펼쳐지는 구조

바 자체가 버튼 역할. 탭하면 아래로 1~2줄 가이드가 펼쳐진다.
안 탭하면 점수 바만 보이니까 화면이 깔끔하고, 관심 있는 항목만 골라서 볼 수 있다.

| 상태 | 화면에 보이는 것 |
|------|----------------|
| 접힌 상태 | `캐릭터 일관성 ████░░░░░░ 3.2  ▼` |
| 펼친 상태 | `캐릭터 일관성 ████░░░░░░ 3.2  ▲` |
| | `Cut 1에서는 "빨간 자켓"인데 Cut 5에서 "파란 코트"로 달라요.` |
| | `→ 캐릭터 외형을 한 번 정해서 전체 컷에 동일하게 적용해보세요.` |

펼쳐지는 내용은 Low-Score Guidance 테이블의 "유저에게 안내할 내용"과 "예시"에서 가져온다.

### 4. 재평가 시 점수 변화량 표시

수정 후 재평가하면 이전 점수 대비 변화를 작게 표시한다.
유저가 "내가 고친 게 효과 있었구나"를 느낄 수 있어서 수정 동기부여가 된다.

| 상황 | 표시 형태 |
|------|----------|
| 첫 평가 | **4.2** / 10 |
| 수정 후 재평가 | **7.1** / 10  `(+2.9 ↑)` |
| 점수 하락 시 | **3.8** / 10  `(-0.4 ↓)` |

항목별 바에서도 동일하게 변화량 표시:
`캐릭터 일관성 ████████░░ 7.5  (+4.3 ↑)`

첫 평가에서는 변화량 없이 현재 점수만 표시.

### 5. Confirm 버튼 연동

전체 평균 점수가 5점 이상이 되는 순간:
- 점수 원형이 초록 또는 노랑으로 바뀜
- 아래 Confirm 버튼이 활성화 (비활성 → 활성)
- 별도 설명 없이 **색상 변화 + 버튼 활성화**로 "다음 단계 가능"을 전달

5점 미만일 때:
- Confirm 버튼은 비활성 (회색, 클릭 불가)
- 버튼 위에 작은 텍스트: "점수를 5점 이상으로 올려야 다음 단계로 갈 수 있어요"

---

## Low-Score Guidance — 점수가 낮을 때 유저에게 안내할 내용

점수가 5 미만일 때, 해당 criteria별로 **유저가 무엇을 구체적으로 써야 하는지** 안내한다.
단순히 "더 구체적으로 써주세요"가 아니라, 빠진 것이 무엇이고 어떻게 보완하면 되는지를 알려줘야 한다.

### Code Grader 항목 — 구조적 문제

| # | Criteria | 낮은 점수 원인 | 유저에게 안내할 내용 | 예시 |
|---|----------|---------------|---------------------|------|
| C1 | Parseable structure | 컷 구분이 불명확하거나 자유 서술형으로 작성됨 | "각 장면을 [Cut 1], [Cut 2] 처럼 번호로 나눠서 입력해주세요. 하나의 장면에 하나의 상황만 넣어주세요." | ❌ "강백호가 슛하고 관중이 환호하고 채치수가 울었다" → ✅ 3개의 개별 컷으로 분리 |
| C2 | Required fields present | 특정 필드(조명, 구도, 배경 등)에 대한 정보가 아예 없음 | "지금 장면에 [빠진 필드명]에 대한 묘사가 없어요. 예를 들어 [필드별 예시]를 추가해주세요." | ❌ "강백호가 슛한다" → ✅ "체육관 안, 스포트라이트 조명 아래, 클로즈업 구도로 강백호가 점프슛을 한다" |
| C3 | Cut count range | 장면이 너무 적거나(1–4개) 너무 많음(11개+) | 적을 때: "15초 영상을 만들려면 최소 5개 장면이 필요해요. 중간 과정을 더 넣어볼까요?" / 많을 때: "10개가 넘으면 영상이 30초를 초과해요. 핵심 장면만 골라주세요." | — |
| C4 | No empty descriptions | "없음", "해당없음", 빈칸 등 실질적 내용 없는 필드 존재 | "Cut [N]의 [필드명]이 비어 있어요. 이미지를 만들 때 이 정보가 꼭 필요합니다. [구체적 질문]을 생각해보세요." | 빈 lighting → "이 장면이 낮인가요, 밤인가요? 조명은 자연광인가요, 네온인가요?" |
| C5 | Unsafe content filter | 폭력/선정적/혐오 표현 포함 | "영상 생성 AI가 [감지된 표현] 때문에 이 장면을 거부할 수 있어요. [대체 표현 제안]으로 바꿔보세요." | ❌ "피를 흘리며 쓰러진다" → ✅ "지친 표정으로 무릎을 꿇는다" |

### Model Grader 항목 — 품질 문제

| # | Criteria | 낮은 점수 원인 | 유저에게 안내할 내용 | 예시 |
|---|----------|---------------|---------------------|------|
| M1 | Image prompt quality | 배경, 구도, 조명 묘사가 추상적이거나 모호함 | "이미지 AI가 정확한 그림을 그리려면 구체적인 묘사가 필요해요. [모호한 표현]을 [구체적 대안]으로 바꿔보세요." | ❌ "예쁜 배경" → ✅ "벚꽃이 흩날리는 일본식 교정, 석양빛" |
| M2 | Character consistency | 같은 캐릭터의 외형이 컷마다 다르게 묘사됨 | "Cut [A]에서는 [묘사1]인데 Cut [B]에서는 [묘사2]로 달라요. 캐릭터 외형(헤어, 의상, 체형)을 처음 한 번 정해두면 모든 장면에 동일하게 적용돼요." | ❌ Cut1 "빨간 자켓" / Cut5 "파란 코트" → ✅ 전체 컷에서 "빨간 자켓, 검은 바지, 붉은 머리" 통일 |
| M3 | Story coherence | 컷들 사이에 서사적 연결이 없음 (랜덤 장면 나열) | "지금 장면들이 하나의 이야기로 연결되지 않아요. 이 순서로 생각해보세요: ① 상황 설정 → ② 사건 발생 → ③ 긴장 고조 → ④ 클라이맥스 → ⑤ 마무리" | ❌ "카페 / 전투 / 산책 / 요리" → ✅ "카페에서 만남 → 오해 → 갈등 → 화해 → 함께 걷기" |
| M4 | Motion describability | 정적 묘사만 있고 동작/움직임 표현이 없음 | "영상은 움직임이 필요해요. 각 장면에서 캐릭터가 어떤 동작을 하는지 넣어주세요. '서있다'보다 '천천히 고개를 돌린다'가 훨씬 좋은 영상이 됩니다." | ❌ "캐릭터가 창문 앞에 있다" → ✅ "캐릭터가 창문을 열고 바깥을 내다본다, 바람에 머리카락이 날린다" |
| M5 | Genre rule adherence | 장르 특유의 요소가 반영되지 않음 | K-pop: "K-pop 영상이라면 조명과 패션이 핵심이에요. 무대 조명 색, 의상 디테일을 추가해보세요." / Anime: "애니메이션 스타일이면 화풍을 지정해주세요 (예: 90년대 셀화, 현대 디지털 등)." / Game: "게임 장르라면 배경의 디테일과 카메라 구도가 중요해요." | — |
| M6 | Backend parseable intent | 하나의 문장에 여러 필드 정보가 뒤섞여 있어 파싱이 어려움 | "각 장면에서 '누가(캐릭터) / 어디서(배경) / 어떻게(구도·조명) / 무엇을(행동)'을 구분해서 써주면 더 정확한 이미지가 나와요." | ❌ "어두운 골목에서 긴장한 채 뒤를 돌아보는 장면" (배경+mood+action 혼합) → ✅ 배경: 어두운 골목 / 분위기: 긴장 / 행동: 뒤를 돌아본다 |

### Human Grader 항목 — 주관적 판단 (유저 자신이 평가)

Human Grader는 유저 본인이 판단하므로, 아래는 **유저가 스스로 체크할 수 있는 질문 형태**로 안내한다.

| # | Criteria | 유저에게 던질 셀프 체크 질문 |
|---|----------|---------------------------|
| H1 | Fan-appeal | "이 스토리보드대로 만들어진 영상을 내 팬덤 커뮤니티에 올렸을 때, 사람들이 좋아할까요?" |
| H2 | Emotional pacing | "처음부터 끝까지 쭉 읽었을 때, 어디선가 '오!' 하는 순간이 있나요? 아니면 전체가 비슷한 톤인가요?" |
| H3 | Input faithfulness | "처음에 머릿속에 그렸던 장면이 여기에 다 담겨 있나요? 빠진 것이나 원하지 않은 것이 추가된 건 없나요?" |

---

## Human Eval UI — 유저 피드백 수집 설계

### 1. Confirm 직전 셀프 체크리스트

유저가 confirm 버튼을 누르기 전에, H1~H3 기준을 유저 친화적 질문으로 보여준다.
세 개 모두 체크해야 confirm 버튼이 활성화된다.

| 체크박스 | 대응 기준 | 유저에게 보이는 문구 |
|---------|----------|---------------------|
| ☐ | H1 (Fan-appeal) | "이 스토리보드가 내 팬덤 취향에 맞아요" |
| ☐ | H2 (Emotional pacing) | "처음부터 끝까지 읽었을 때 흐름이 자연스러워요" |
| ☐ | H3 (Input faithfulness) | "내가 처음에 상상한 내용이 잘 반영되어 있어요" |

하나라도 체크하지 않으면 → 아래 "2. 피드백 Funnel"로 진입.

### 2. 불만족 시 단계적 좁히기(Feedback Funnel)

유저가 "뭔가 부족한 것 같은데, 뭐라고 해야 할지 모르겠다"를 해결하기 위한 구조.
선택지를 점점 좁혀가면서 유저의 불만족 포인트를 구조화한다.

#### Step 1 — 어디가 아쉬워? (대분류, 복수 선택 가능)

체크하지 않은 항목에 해당하는 선택지만 표시된다.

| 버튼 텍스트 | 대응 기준 | plot_advisor에 전달되는 힌트 |
|------------|----------|-------------------------------|
| "캐릭터/분위기가 내 취향이 아니야" | H1 | `feedback_type: fan_appeal_mismatch` |
| "흐름이 밋밋하거나 어색해" | H2 | `feedback_type: pacing_issue` |
| "내가 원한 게 이게 아니야" | H3 | `feedback_type: input_mismatch` |

#### Step 2 — 구체적으로 뭐가? (선택한 대분류에 따라 세부 선택지 펼침)

**"캐릭터/분위기가 내 취향이 아니야" (H1) 선택 시:**

| 세부 선택지 | plot_advisor에게 전달되는 힌트 |
|-----------|-------------------------|
| "캐릭터 외형/의상이 마음에 안 들어" | `detail: character_appearance` |
| "배경/분위기가 다른 느낌이었으면" | `detail: mood_background` |
| "장르 느낌이 안 나 (K-pop/애니/게임다운 느낌 부족)" | `detail: genre_feel` |
| "전반적인 화풍/스타일이 다르면 좋겠어" | `detail: art_style` |

**"흐름이 밋밋하거나 어색해" (H2) 선택 시:**

| 세부 선택지 | plot_advisor에게 전달되는 힌트 |
|-----------|-------------------------|
| "클라이맥스/하이라이트가 없어" | `detail: no_climax` |
| "장면 전환이 갑작스러워" | `detail: abrupt_transition` |
| "전체적으로 너무 단조로워" | `detail: monotone` |
| "시작이나 마무리가 약해" | `detail: weak_opening_ending` |

**"내가 원한 게 이게 아니야" (H3) 선택 시:**

| 세부 선택지 | plot_advisor에게 전달되는 힌트 |
|-----------|-------------------------|
| "내가 원한 장면이 빠져있어" | `detail: missing_scene` |
| "원하지 않은 장면이 추가됐어" | `detail: unwanted_scene` |
| "캐릭터가 다르게 나왔어" | `detail: wrong_character` |
| "상황/설정이 내 입력과 달라" | `detail: wrong_setting` |

#### Step 3 — 어떤 컷? (해당 컷 번호 선택)

모든 컷을 버튼/칩으로 나열한다 (예: `[Cut 1] [Cut 2] [Cut 3] ...`).
유저가 문제되는 컷을 직접 탭해서 선택. 복수 선택 가능.

전달 형태: `target_cuts: [1, 3, 7]`

#### Step 4 (선택) — 자유 입력

위 선택만으로 부족할 경우를 위한 텍스트 입력 필드.
placeholder: "추가로 원하는 게 있다면 자유롭게 적어주세요"

대부분의 경우 Step 1~3만으로 충분하며, 이 필드는 비워도 된다.

### Feedback → plot_advisor 연동

수집된 피드백은 아래 형태로 구조화되어 plot_advisor의 가이드라인 생성에 활용된다:

```
feedback:
  - type: input_mismatch
    detail: missing_scene
    target_cuts: [3, 5]
    free_text: "강백호가 골대 앞에서 멈칫하는 장면이 있었으면"
  - type: pacing_issue
    detail: no_climax
    target_cuts: [4, 5, 6]
    free_text: null
```

이를 통해 plot_advisor는 "전체를 다시 생각해보세요"가 아니라 **"Cut 3, 5에서 이 부분을 이렇게 보완해보세요"** 같은 타겟팅된 가이드라인을 유저에게 제공할 수 있다.
유저가 이 가이드를 참고해 입력을 수정하면, plot_generator가 재생성하고 plot_evaluator가 재평가한다.

---

## 참고: Plain Text → JSON 변환 규칙 (Backend 책임)

confirm 후 backend이 수행하는 변환이므로, Claude의 plain text 출력이 아래 JSON 스키마의 모든 필드를 커버해야 한다:

```
main_character      string      메인 캐릭터 외형 + 의상
sub_character       string|null 보조 캐릭터 (없으면 null)
action              string      캐릭터 행동
pose                string      캐릭터 포즈
background          string      배경 장소 묘사
era                 string      시간대 (예: "modern", "1990s")
composition         string      구도 (closeup, fullshot, birdseye 등)
lighting            string      조명 (backlight, spotlight, natural 등)
mood                string      분위기 (tension, excitement, loneliness 등)
story_beat          string      이 컷의 서사적 역할
duration_seconds    float       목표 클립 길이 3.0–8.0s
```

Claude의 plain text가 이 11개 필드를 명시적으로 또는 추론 가능하게 포함하고 있어야 backend 파싱이 정확하게 동작한다.
