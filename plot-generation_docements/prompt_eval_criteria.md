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
  → /api/plot/human-eval: 유저 직접 판단 H1/H2/H3 (Phase 4)
  →   H1~H3 모두 통과 → current_stage = "human_eval_passed"
  →   만족 → /api/plot/confirm → plot_converter.parse_storyboard() → JSON 저장 → 이미지 생성
  →   하나라도 실패 → current_stage = "human_eval_failed" → 피드백 funnel → plot_advisor → 유저 수정 → 루프
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

> C4는 C2에 통합됨. C2가 필드 존재 여부 + placeholder("없음", "N/A", "-") 모두 검사.

| # | Criteria | What It Checks | Why It Matters | Downstream Impact |
|---|----------|----------------|----------------|-------------------|
| C1 | **Parseable structure** | plain text가 일관된 구분자/패턴을 갖고 있어 backend 파싱이 가능한가 (예: `[Cut 1]`, `[Cut 2]` 등의 반복 패턴) | confirm 후 backend이 regex/split으로 JSON 변환할 때, 패턴이 불규칙하면 파싱 실패 → 이미지 생성 불가 | → JSON 변환 → 이미지 생성 파이프라인 전체 |
| C2 | **Required fields present** | 각 컷에 필수 요소가 모두 포함되어 있는가: main_character, sub_character, action, pose, background, era, composition, lighting, mood, story_beat, duration_seconds + placeholder("없음", "N/A", "-") 검출 | 빠진 필드 = compose_cut_prompt()에 빈 슬롯 → 이미지 품질 저하 | → 이미지 생성 프롬프트 품질 |
| C3 | **Cut count range** | 컷 수가 5–10개 범위 안인가 | 5개 미만 = 최종 영상 15초 미달 (Shorts/TikTok 부적합). 10개 초과 = 비용 폭발 + 30초 초과 | → 영상 비용 → FFmpeg merge |
| C5 | **Unsafe content filter** | 폭력, NSFW, 혐오 표현 등 safety policy 위반 키워드가 없는가. Haiku 모델(SAFETY_MODEL) 기반 안전 분류 | 이미지/영상 모델이 unsafe prompt를 거부 → 해당 컷 생성 실패 | → FLUX / Kling rejection 방지 |

### Model Grader — AI 기반 품질 평가

| # | Criteria | What It Checks | Why It Matters | Downstream Impact |
|---|----------|----------------|----------------|-------------------|
| M1 | **Image prompt quality** | composition, background, lighting 묘사가 이미지 모델이 구체적 이미지를 생성할 만큼 구체적인가 | "예쁜 배경" 같은 모호한 표현 → 매번 다른 이미지 생성 → 일관성 파괴 | → FLUX 출력 품질 |
| M2 | **Character consistency** | 동일 캐릭터가 전체 컷에서 동일한 외형(의상, 헤어, 체형 등)으로 묘사되는가 | 이미지 모델은 컷별로 독립 생성 → 외형 묘사가 다르면 캐릭터가 달라짐. GlobalContext + 캐릭터 시트로 완화하지만, 원문 품질도 중요 | → 컷 간 시각적 일관성 |
| M3 | **Story coherence** | 컷들이 논리적 서사 흐름(도입→전개→클라이맥스→마무리)을 형성하는가 | 무작위 장면 나열 → merge 후 영상이 슬라이드쇼처럼 보임 | → 최종 영상 완성도 |
| M4 | **Motion describability** | 각 컷이 영상 모델이 애니메이션으로 만들 수 있는 명확한 동작을 암시하는가 (시작→끝 움직임) | "캐릭터가 서있다" → 정지 이미지만 생성 → 영상이 아니라 사진 슬라이드가 됨 | → 영상 클립 품질 |
| M5 | **Genre rule adherence** | 장르별 우선순위를 따르는가: K-pop(조명+패션), anime(화풍), game(구도+배경) | 장르 특성 무시 → 팬 콘텐츠가 아닌 범용 AI 이미지로 보임 | → 팬 authentic 느낌 |
| M6 | **Backend parseable intent** | plain text의 각 필드가 명확하게 구분되어 있어 backend이 정확히 어떤 값을 어떤 JSON key에 매핑해야 하는지 판단할 수 있는가 | 모호한 서술 → backend 파싱 시 `action`과 `pose`가 뒤섞이거나, `background`와 `era`가 혼동됨 | → JSON 변환 정확도 |

> **Focused Eval 참고:** M5(Genre rule adherence)와 M6(Backend parseable intent)는 Focused Eval에서 제외된다.
> - M5 제외: 부분 수정으로 전체 장르 톤이 바뀌지 않음
> - M6 제외: 전체 파싱 구조는 이미 Full Eval에서 검증됨

### Human Grader — 유저 주관 평가 (Human Eval 단계)

| # | Criteria | What It Checks | Why It Matters | Downstream Impact |
|---|----------|----------------|----------------|-------------------|
| H1 | **Fan-appeal** | K-pop/anime/game 팬이 실제로 보고 싶어할 내용인가 | 팬 크리에이터가 타겟 유저 — 그들의 취향이 ground truth | → 최종 영상 매력도 |
| H2 | **Emotional pacing** | 15–30초 안에서 긴장감, 놀라움, 감정적 보상이 느껴지는가 | 숏폼 영상은 페이싱이 전부 | → 최종 영상 몰입감 |
| H3 | **Input faithfulness** | 유저가 입력한 아이디어가 충실히 반영되었는가 | 이건 사람만 판단 가능 | → 유저 만족도 |

---

## Evaluation 실행 순서

```
Step 1: Code Grader (C1–C3, C5)
  → 통과하지 못하면 즉시 유저에게 구체적 실패 사유 + 수정 가이드 제공
  → 여기서 걸리면 Model Grader 단계로 가지 않음

Step 2: Model Grader (M1–M6)
  → 각 항목 1–10점 채점
  → Structured Outputs: client.messages.create() + tool_choice 강제
  → 5점 미만 항목 → plot_advisor가 유저에게 가이드라인 리포트 생성
  → 유저가 직접 수정 → plot_generator 재생성 → 재평가 루프

Step 3: Human Evaluation (H1–H3) — POST /api/plot/human-eval
  → Step 1, 2를 5점 이상으로 통과한 결과물만 유저에게 도달
  → /api/plot/evaluate의 current_stage = "evaluated" 또는 "human_eval_failed" 상태에서만 호출 가능
  → 유저가 H1/H2/H3 체크 → human_eval_json DB 저장
  → 모두 통과 → current_stage = "human_eval_passed" → /api/plot/confirm 호출 가능
  → 하나라도 실패 → current_stage = "human_eval_failed" → /api/plot/modify 유도
```

---

## Focused Eval — 이미지 수정 후 부분 평가

이미지 생성 완료 후 유저가 특정 컷을 수정하면, Full Eval 대신 Focused Eval을 적용한다.
이미지 수정 API(`/api/image/modify-by-text`)에서 자동으로 호출된다.

### 평가 대상 컷 선정
- `diff_scenes(old_scenes, new_scenes)` → changed_cuts (9개 필드 비교)
- 인접 컷: changed_cuts 각각의 ±1 (서사 연결성 확인)
- 예: changed_cuts=[3] → 평가 대상: Cut 2, 3, 4

### 적용 기준

| 구분 | Full Eval | Focused Eval | 제외 사유 |
|------|-----------|--------------|-----------|
| C1 Parseable structure | ✓ | ✗ | 전체 구조는 이미 검증됨 |
| C2 Required fields | ✓ | ✓ | 수정된 컷에서 필드 누락 가능 |
| C3 Cut count range | ✓ | ✗ | 컷 수는 변경되지 않음 |
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

합산 점수 계산:
- 정상: `(Code 평균 + Model 평균) / 2`
- Code 평가 실패(C1/C3 미달 등) 또는 Model Eval API 실패로 스킵: `total = code_avg` (절반 페널티 없음)
- Code 평균 5점 미만이면 Model Eval 없이 Code Eval 루프부터 순환.

| 합산 점수 | Action |
|---|---|
| Code 평균 < 5.0 | Model Eval 실행 안 함 → failed_items 가이드 → 유저 수정 입력 → full_eval 재실행 |
| 합산 1.0–4.9 | failed_items 기반 가이드라인 출력 → 유저 수정 입력 → 재생성 → full_eval 재실행 |
| 합산 5.0–10.0 | 통과 → Human Eval 진입 |

---

## Score Display UI — 유저에게 점수를 보여주는 방식

매번 prompt evaluation이 실행될 때, 유저에게 "점수 + 피드백/가이드라인/추천"을 보여줘야 한다.
핵심 원칙: **한눈에 점수 파악 + 필요한 만큼만 디테일**.

### 1. 전체 점수 — 큰 숫자 + 색상 원형

| 점수 구간 | 원형 색상 | 아래 한 줄 메시지 |
|----------|----------|-----------------|
| 8.0–10.0 | 초록 | "좋은 스토리보드예요! 확인 후 영상을 만들어보세요" |
| 5.0–7.9 | 노랑 | "조금만 더 보완하면 더 좋은 영상이 됩니다" |
| 1.0–4.9 | 빨강 | "아래 가이드를 참고해서 보완해보세요" |

### 2. 항목별 점수 — 낮은 항목만 바(bar)로 표시

- **5점 미만 항목만** 짧은 가로 바로 표시
- **5점 이상 항목은 접어두고** "✓ N개 항목 통과" 뱃지로 요약

### 3. 가이드라인 — 낮은 항목 바를 탭하면 펼쳐지는 구조

### 4. 재평가 시 점수 변화량 표시

### 5. Confirm 버튼 연동

전체 평균 5점 이상 → Confirm 버튼 활성화. 5점 미만 → 비활성.

---

## Low-Score Guidance — 점수가 낮을 때 유저에게 안내할 내용

### Code Grader 항목 — 구조적 문제

| # | Criteria | 낮은 점수 원인 | 유저에게 안내할 내용 | 예시 |
|---|----------|---------------|---------------------|------|
| C1 | Parseable structure | 컷 구분이 불명확 | "[Cut 1], [Cut 2] 처럼 번호로 나눠서 입력해주세요" | ❌ "강백호가 슛하고 관중이 환호" → ✅ 3개의 개별 컷으로 분리 |
| C2 | Required fields present | 특정 필드 누락 또는 placeholder | "지금 장면에 [빠진 필드명]에 대한 묘사가 없어요" | ❌ "강백호가 슛한다" → ✅ "체육관 안, 스포트라이트 아래, 클로즈업 구도로 강백호가 점프슛" |
| C3 | Cut count range | 장면이 너무 적거나 많음 | 적을 때: "최소 5개 장면 필요" / 많을 때: "10개 이하로 줄여주세요" | — |
| C5 | Unsafe content filter | 폭력/선정적/혐오 표현 | "영상 생성 AI가 이 장면을 거부할 수 있어요. [대체 표현]으로 바꿔보세요" | ❌ "피를 흘리며" → ✅ "지친 표정으로 무릎을 꿇는다" |

### Model Grader 항목 — 품질 문제

| # | Criteria | 낮은 점수 원인 | 유저에게 안내할 내용 | 예시 |
|---|----------|---------------|---------------------|------|
| M1 | Image prompt quality | 배경, 구도, 조명 묘사가 모호함 | "구체적 묘사 필요: [모호한 표현]을 [구체적 대안]으로" | ❌ "예쁜 배경" → ✅ "벚꽃이 흩날리는 일본식 교정, 석양빛" |
| M2 | Character consistency | 같은 캐릭터의 외형이 컷마다 다름 | "외형(헤어, 의상, 체형)을 한 번 정해서 전체 컷에 통일" | ❌ Cut1 "빨간 자켓" / Cut5 "파란 코트" |
| M3 | Story coherence | 서사적 연결 없음 | "도입→전개→클라이맥스→마무리 순서로" | ❌ "카페/전투/산책/요리" → ✅ "만남→오해→갈등→화해" |
| M4 | Motion describability | 정적 묘사만 있음 | "동작 넣어주세요. '서있다'보다 '고개를 돌린다'" | ❌ "창문 앞에 있다" → ✅ "창문을 열고 바깥을 내다본다" |
| M5 | Genre rule adherence | 장르 특유 요소 부족 | K-pop: 조명+패션 / Anime: 화풍 지정 / Game: 배경+구도 | — |
| M6 | Backend parseable intent | 필드 정보가 뒤섞임 | "누가/어디서/어떻게/무엇을 구분해서 써주세요" | — |

### Human Grader 항목 — 유저 셀프 체크

| # | Criteria | 유저에게 던질 셀프 체크 질문 |
|---|----------|---------------------------|
| H1 | Fan-appeal | "이 영상을 팬덤 커뮤니티에 올렸을 때, 사람들이 좋아할까요?" |
| H2 | Emotional pacing | "처음부터 끝까지 '오!' 하는 순간이 있나요?" |
| H3 | Input faithfulness | "처음에 그렸던 장면이 다 담겨 있나요?" |

---

## Human Eval UI — 유저 피드백 수집 설계

### 1. Confirm 직전 셀프 체크리스트

| 체크박스 | 대응 기준 | 유저에게 보이는 문구 |
|---------|----------|---------------------|
| ☐ | H1 | "이 스토리보드가 내 팬덤 취향에 맞아요" |
| ☐ | H2 | "처음부터 끝까지 읽었을 때 흐름이 자연스러워요" |
| ☐ | H3 | "내가 처음에 상상한 내용이 잘 반영되어 있어요" |

### 2. 불만족 시 단계적 좁히기(Feedback Funnel)

Step 1 → 대분류 (fan_appeal_mismatch / pacing_issue / input_mismatch)
Step 2 → 세부 선택지 (선택한 대분류에 따라)
Step 3 → 컷 번호 선택 (target_cuts)
Step 4 → 자유 입력 (선택)

### Feedback → plot_advisor 연동

```
feedback:
  - type: input_mismatch
    detail: missing_scene
    target_cuts: [3, 5]
    free_text: "강백호가 골대 앞에서 멈칫하는 장면이 있었으면"
```

---

## 참고: Plain Text → JSON 변환 규칙 (Backend 책임)

confirm 후 backend이 수행하는 변환. 12개 필드:

```
cut_number          int         컷 번호
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

---

## 관련 문서

| 문서 | 내용 |
|------|------|
| `implementation_spec.md` | Phase별 구현 설계, API 엔드포인트, 데이터 스키마 |
| `image.md` | 이미지 생성 파이프라인 (캐릭터 시트, GlobalContext, diff 기반 재생성) |
| `video-generate.md` | 영상 생성 파이프라인 (Fal.ai Kling, 폴링, 에러 처리) |
| `error_handling.md` | 에러 처리 전략 |
| `folder_structure_guide.md` | 폴더 구조 및 데이터 흐름 |
