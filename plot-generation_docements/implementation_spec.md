# Plot Generation — MVP Implementation Spec
> Terminal CLI 기준 end-to-end 구현 설계서
> FastAPI 백엔드 연동 완료 — 프론트엔드 연동 예정

---

## 1. MVP Scope

### 포함
- 터미널에서 가이드 질문 6개(장르, 캐릭터, 분위기, 줄거리, 필수 장면, 추가 요청)를 통해 유저 의도 수집 → 요약 제시 → confirm 후 생성
- Claude API 호출 → plain text 스토리보드 생성
- Code Grader (C1–C3, C5) 자동 평가 → Code 평균 5점 미만 시 (가이드 ↔ Code Eval) 독립 순환
- Model Grader (M1–M6) Claude 기반 평가 → Code 평균 5점 이상일 때만 실행
- 합산 점수 계산 기준:
- 정상: (Code 평균 + Model 평균) / 2
- Code 실패 or Model Eval 스킵: total = code_avg (페널티 없이 Code 점수만 사용)

분기:
  - 5점 미만 → advisor 가이드 → 재입력 → Code Eval부터 재시작
  - 5~7.9점 → 약점 요약 → 유저 선택 (수정 또는 Human Eval 진행)
  - 8점 이상 → 바로 Human Eval
- Human Eval 인터랙션 (터미널 텍스트) + 피드백 funnel
- Confirm → plain text → JSON 변환 → DB 저장
- GlobalContext(캐릭터 시트 + 화풍/색감) 생성 → 컷별 이미지 생성
- diff 기반 부분 이미지 재생성 + focused_eval
- 컷별 영상 생성 (Fal.ai Kling → 향후 Veo 2)

### 포함 (FastAPI 연동)
- FastAPI 라우터 / HTTP 엔드포인트 (plot, image, video)
- DB 저장 (SQLite — Project, Scene 테이블)
- GlobalContext 기반 캐릭터 일관성 보장
- diff_scenes + focused_eval 기반 부분 이미지 재생성

### 제외 (이후 연동)
- 프론트엔드 UI (점수 원형, 바 차트, 색상 등)
- 인증/세션 관리
- FFmpeg 최종 영상 병합
- Veo 2 전환 (현재 Fal.ai Kling 사용 중)

---

## 2. 구현 Phase

### Phase 1 — 뼈대 세팅 ✅ 완료
**목표:** Claude를 호출해서 plain text 스토리보드가 나오는 것 확인

```
구현 파일:
  backend/app/core/config.py       — .env에서 API 키 로드
  backend/app/services/claude_client.py  — Claude 호출 공통 함수
  backend/app/prompts/system.py    — plot_generator 시스템 프롬프트
  backend/app/services/plot_generator.py — 스토리보드 생성
  cli.py                           — 터미널 진입점 (루트에 위치)
```

**완료 기준:** `python cli.py` 실행 → 가이드 질문 답변 → 요약 confirm → plain text 스토리보드 출력 ✅ 완료

---

### Phase 2 — 평가 (Evaluator) ✅ 완료
**목표:** 생성된 스토리보드를 자동 채점 (Code Eval 독립 → Code 통과 시 Model Eval)

```
구현 파일:
  backend/app/prompts/eval.py       — Model Grader 평가 프롬프트
  backend/app/services/plot_evaluator.py — Code Grader + Model Grader
```

**완료 기준:**
- Code 평균 5점 미만 → Model Grader 실행 안 됨 확인
- Code 평균 5점 이상 → Model Grader 실행 → 합산 점수 = (Code 평균 + Model 평균) / 2 출력

> **⚠️ 구현 제약:** Anthropic API에서 `tool_choice` 강제와 `extended thinking` 동시 사용 불가 (400 BadRequestError).
> `run_model_grader()`의 `use_thinking=True`를 제거함. Structured Outputs만으로 일관된 채점 형식 확보.

---

### Phase 3 — 가이드 + 루프 (Advisor) ✅ 완료
**목표:** 점수 미달 시 유저에게 가이드 제공 → 재입력 → 재평가 루프

```
구현 파일:
  backend/app/prompts/advisor.py   — Advisor 시스템 프롬프트
  backend/app/services/plot_advisor.py — 가이드라인 생성
  backend/app/prompts/templates.py — 장르별 예시 입력
```

**완료 기준:**
- 점수 5점 미만 → 가이드라인 출력 → 유저 재입력 → 재평가 루프 동작 확인
- 3회 연속 미달 → 템플릿 예시 제공
- 5회 연속 미달 → 계속 진행 여부 확인
- 7회 연속 미달 → 강제 종료

---

### Phase 4 — Human Eval + Converter ✅ 완료
**목표:** 유저 주관 평가 (H1–H3) + plain text → JSON 변환

```
구현 파일:
  backend/app/schemas/feedback.py   — 피드백 구조 (type, detail, target_cuts, free_text)
  backend/app/schemas/project.py    — HumanEvalRequest, HumanEvalResponse 스키마
  backend/app/services/plot_converter.py — parse_storyboard(), scenes_to_plain_text(), diff_scenes()
  backend/app/schemas/scene.py      — Scene (12 필드) + GlobalContext
  backend/app/api/plot.py           — POST /api/plot/human-eval 엔드포인트
```

**완료 기준:**
- `/api/plot/human-eval`: H1/H2/H3 체크 결과 수신 → DB `human_eval_json` 저장
- H1~H3 모두 True → `current_stage = "human_eval_passed"` → `/api/plot/confirm` 허용
- 하나라도 False → `current_stage = "human_eval_failed"` → `/api/plot/modify` 유도
- Confirm → plain text → JSON 변환 → DB 저장
- `/api/plot/evaluate`는 failure_count를 Project DB에 누적 저장 (3/5/7회 임계값 로직 포함)

---

### Phase 5 — 이미지 생성 ✅ 완료
**목표:** 캐릭터 일관성이 보장된 컷별 이미지 생성 + diff 기반 부분 재생성

```
구현 파일:
  backend/app/services/character_sheet.py — 캐릭터 시트, GlobalContext 생성, compose_cut_prompt()
  backend/app/services/image.py           — FLUX.1-schnell 호출, Cloudinary 업로드
  backend/app/schemas/image.py            — ImageGenerateAllRequest, ImageModifyByTextRequest
  backend/app/api/image.py                — /generate-all, /modify-by-text 엔드포인트
```

**핵심 설계:**
- 캐릭터 시트(Character Sheet): Claude 1회 호출 → 상세 캐릭터 외형 묘사 (영어, 100~200단어)
- GlobalContext: 캐릭터 시트 + art_style + era + color_palette
- compose_cut_prompt(): GlobalContext(고정) + Scene(가변) → FLUX 프롬프트
- diff_scenes(): old/new Scene 비교 → 변경 컷 번호 반환 (9개 필드 비교)
- focused_eval(): 변경컷 + 인접 ±1컷만 부분 평가 (C2/C5 + M1~M4)

> 상세 스펙: `plot-generation_docements/image.md` 참조

---

### Phase 6 — 영상 생성 ✅ 완료
**목표:** 이미지 → 영상 클립 변환

```
구현 파일:
  backend/app/services/video.py    — Fal.ai Kling Video API 호출
  backend/app/schemas/video.py     — VideoGenerateRequest, VideoGenerateAllRequest
  backend/app/api/video.py         — 단건/일괄 영상 생성 엔드포인트
```

**핵심 설계:**
- image-to-video: 이미지 URL(첫 프레임) + 동작 프롬프트 → 영상 클립
- 비동기 폴링: 5초 간격, 최대 5분
- 일괄 생성 시 개별 실패 격리 (skipped/failed/done)

> 상세 스펙: `plot-generation_docements/video-generate.md` 참조

---

### Phase 7 — FastAPI 연동 ✅ 완료
**목표:** CLI 파이프라인을 FastAPI HTTP 엔드포인트로 전환

```
구현 파일:
  backend/app/main.py             — FastAPI 앱 생성, CORS, 라우터 등록
  backend/app/api/plot.py         — Plot Generation 5개 엔드포인트
  backend/app/api/image.py        — Image Generation 4개 엔드포인트
  backend/app/api/video.py        — Video Generation 2개 엔드포인트
  backend/app/db/database.py      — SQLite 세션 관리
  backend/app/db/models.py        — Project, Scene 테이블 ORM
```

**API 엔드포인트 목록:**

| 엔드포인트 | 메서드 | 역할 |
|---|---|---|
| `/api/plot/generate` | POST | 유저 입력 → GlobalContext + 스토리보드 생성 |
| `/api/plot/evaluate` | POST | full_eval() 실행 (failure_count 추적) |
| `/api/plot/advice` | POST | 가이드라인 생성 |
| `/api/plot/modify` | POST | 스토리보드 수정 (previous + modification) |
| `/api/plot/human-eval` | POST | Human Eval (H1~H3) 셀프 체크 |
| `/api/plot/confirm` | POST | plain text → JSON 변환 → Scene DB 저장 |
| `/api/image` | POST | 단건 이미지 생성 |
| `/api/image/modify` | POST | 단건 이미지 수정 (프롬프트 변경) |
| `/api/image/generate-all` | POST | 전체 컷 일괄 이미지 생성 |
| `/api/image/modify-by-text` | POST | 텍스트 수정 → diff → focused_eval → 부분 재생성 |
| `/api/video` | POST | 단건 영상 생성 |
| `/api/video/generate-all` | POST | 전체 컷 일괄 영상 생성 |

---

## 3. Code Grader — 자동화 평가 기준

> C4는 C2에 통합됨 (C2가 필드 존재 여부 + placeholder 모두 검사)

| # | Criteria | 로직 |
|---|---|---|
| C1 | Parseable structure | `[Cut N]` 패턴 존재 여부 + 반복 패턴 일관성 검사 |
| C2 | Required fields present | 각 컷에서 12개 필수 필드 존재 + placeholder("없음", "N/A", "-") 검출 |
| C3 | Cut count range | 컷 수 5~10개 범위 검증 |
| C5 | Unsafe content filter | Haiku 모델(SAFETY_MODEL) 기반 안전 분류 (키워드 리스트 불필요) |

---

## 4. Model Grader — AI 기반 평가

```python
# Structured Outputs — client.messages.create() + tool_choice 강제
response = client.messages.create(
    model=settings.MODEL_NAME,
    max_tokens=settings.MAX_OUTPUT_TOKENS,
    system=[{
        "type": "text",
        "text": MODEL_GRADER_PROMPT,
        "cache_control": {"type": "ephemeral"}
    }],
    messages=[{"role": "user", "content": storyboard}],
    tools=[{
        "name": "submit_evaluation",
        "description": "Submit M1-M6 scores",
        "input_schema": EvalScores.model_json_schema()
    }],
    tool_choice={"type": "tool", "name": "submit_evaluation"}
)
```

> `messages.parse()` 미사용. `client.messages.create() + tool_choice` 패턴으로 Structured Outputs 보장.
> Extended thinking은 forced tool_choice와 호환 불가 (400 에러) → 미사용.

---

## 5. Focused Eval — 이미지 수정 후 부분 평가

이미지 생성 완료 후 유저가 특정 컷을 수정하면, Full Eval 대신 Focused Eval을 적용한다.

**평가 대상 컷:** changed_cuts ∪ (각 ±1 인접 컷)
**적용 기준:** C2, C5 + M1~M4 (M5/M6 제외)
**합격선:** 5.0 (Full Eval과 동일)
**실패 시:** full_eval로 폴백

> 상세: `plot-generation_docements/prompt_eval_criteria.md` 참조

---

## 6. 데이터 스키마

### Scene (12 필드)

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

### GlobalContext

```
main_character      string      캐릭터 시트 (영어, 100~200단어)
sub_character       string|null 보조 캐릭터 시트
art_style           string      장르 기반 화풍 (규칙 추론)
era                 string      시간대
color_palette       string      분위기 기반 색감 (규칙 추론)
```

### EvalScores

```python
class EvalScores(BaseModel):
    model_config = {"strict": True}
    M1: float = Field(ge=1, le=10)
    M2: float = Field(ge=1, le=10)
    M3: float = Field(ge=1, le=10)
    M4: float = Field(ge=1, le=10)
    M5: float = Field(ge=1, le=10)
    M6: float = Field(ge=1, le=10)
    justification: str
```

---

## 7. 관련 문서

| 문서 | 내용 |
|------|------|
| `image.md` | 이미지 생성 파이프라인 상세 (캐릭터 시트, GlobalContext, diff 기반 재생성) |
| `video-generate.md` | 영상 생성 파이프라인 상세 (Fal.ai Kling API, 폴링, 에러 처리) |
| `prompt_eval_criteria.md` | 평가 기준 상세 (C1~C5, M1~M6, H1~H3, Focused Eval) |
| `error_handling.md` | 에러 처리 전략 (Phase별, Fallback, 무한 루프 방지) |
| `folder_structure_guide.md` | 폴더 구조 및 데이터 흐름 |
