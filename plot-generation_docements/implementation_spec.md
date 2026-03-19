# Plot Generation — MVP Implementation Spec
> Terminal CLI 기준 end-to-end 구현 설계서
> 이후 FastAPI 백엔드 + 프론트엔드 연동 예정

---

## 1. MVP Scope

### 포함
- 터미널에서 가이드 질문 6개(장르, 캐릭터, 분위기, 줄거리, 필수 장면, 추가 요청)를 통해 유저 의도 수집 → 요약 제시 → confirm 후 생성
- Claude API 호출 → plain text 스토리보드 생성
- Code Grader (C1–C5) 자동 평가 → Code 평균 5점 미만 시 (가이드 ↔ Code Eval) 독립 순환
- Model Grader (M1–M6) Claude 기반 평가 → Code 평균 5점 이상일 때만 실행
- 합산 점수 = (Code 평균 + Model 평균) / 2 기반 분기:
  - 5점 미만 → advisor 가이드 → 재입력 → Code Eval부터 재시작
  - 5~7.9점 → 약점 요약 → 유저 선택 (수정 또는 Human Eval 진행)
  - 8점 이상 → 바로 Human Eval
- Human Eval 인터랙션 (터미널 텍스트) + 피드백 funnel
- Confirm → plain text → JSON 변환 → 로컬 파일 저장

### 제외 (이후 연동)
- FastAPI 라우터 / HTTP 엔드포인트
- 프론트엔드 UI (점수 원형, 바 차트, 색상 등)
- DB 저장 (SQLite/PostgreSQL)
- Hugging Face 이미지 생성 파이프라인 실제 연동 (Phase 5)
- 인증/세션 관리

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
  backend/app/prompts/advisor.py    — Advisor 가이드 생성 프롬프트 (C1~M6 rubric 포함)
  backend/app/prompts/templates.py  — 장르별 예시 입력 템플릿 (kpop/anime/game, 3회 미달 시 제시)
  backend/app/services/plot_advisor.py — generate_advice() (failed_items 기반, API 실패 시 static fallback)
  cli.py 업데이트                   — generate → full_eval → 점수 출력 → 가이드라인 → 유저 수정 루프
                                      무한 루프 방지: 3회(템플릿 제안) / 5회(계속 여부 확인) / 7회(중단)
```

**완료 기준:**
- Code 평균 5점 미만 → (가이드 ↔ Code Eval) 순환 작동 확인
- 합산 5점 미만 → 가이드 출력 → 유저 수정 입력 → Code Eval부터 재시작
- 합산 5~7.9점 → 약점 요약 → "수정할래? / 이대로 진행할래?" 선택지 작동 확인
- 합산 8점 이상 → 바로 Human Eval 진입

---

### Phase 4 — Human Eval + 피드백 + 저장 (Converter)
**목표:** 점수 통과 후 유저 최종 확인 → 불만족 시 피드백 funnel → JSON 저장

```
구현 파일:
  backend/app/services/plot_converter.py — plain text → JSON 파싱
  backend/app/schemas/scene.py       — JSON 스키마 검증
  backend/app/schemas/feedback.py    — 유저 피드백 구조 검증 (type, detail, target_cuts, free_text)
  cli.py 업데이트                    — H1/H2/H3 체크 + 피드백 funnel + confirm 인터랙션
  output/                            — JSON 임시 저장 디렉토리
```

**완료 기준:** 유저 confirm → `output/scene_<timestamp>.json` 생성. 불만족 시 피드백 수집 → advisor 가이드 → 재입력 루프.

---

## 3. 파일별 인터페이스 정의

### `core/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    MODEL: str = "claude-sonnet-4-20250514"   # sonnet 사용 (generator+evaluator+advisor 3회 호출 비용 고려)
    SAFETY_MODEL: str = "claude-haiku-4-5-20251001"  # C5 unsafe 사전 검수용 (저비용)
    MAX_TOKENS: int = 4096
    MAX_INPUT_TOKENS: int = 100000            # 컨텍스트 윈도우 초과 방지용 (count_tokens로 사전 체크)
    THINKING_BUDGET: int = 10000              # Model Grader 확장 사고 토큰 예산
    SDK_MAX_RETRIES: int = 3                  # SDK 내장 재시도 횟수

    class Config:
        env_file = ".env"

settings = Settings()
```

---

### `services/claude_client.py`
```python
from anthropic import Anthropic
from app.core.config import settings

# SDK 내장 재시도 사용 — 커스텀 재시도 로직 불필요
# 408/409/429/500+/529 자동 재시도, 지수 백오프 + 지터 적용
client = Anthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    max_retries=settings.SDK_MAX_RETRIES
)

def call_claude(
    system_prompt: str,
    user_message: str,
    cache_system: bool = False  # True면 시스템 프롬프트에 cache_control 적용
) -> str:
    """
    반환: Claude 응답 텍스트 (str)
    내부: settings.MODEL 사용

    재시도: SDK 내장 (max_retries=3, 지수 백오프)
      - 429(rate limit) → retry-after 헤더 자동 파싱 후 대기
      - 500+/529(서버) → 지수 백오프 재시도
      - 401(인증) → 재시도 안 함, 그대로 raise
    
    캐싱: cache_system=True면 시스템 프롬프트에 cache_control 추가
      - eval.py, advisor.py 등 반복 호출 시 비용 최대 90% 절감
      - 캐시 TTL: 5분 (사용할 때마다 갱신)
    """

def call_claude_structured(
    system_prompt: str,
    user_message: str,
    output_schema: type,         # Pydantic BaseModel 클래스
    use_thinking: bool = False,  # ⚠️ forced tool_choice와 동시 사용 불가 — 현재 미사용
    cache_system: bool = False
):
    """(Phase 2에서 구현 예정)
    반환: output_schema 타입의 Pydantic 객체 (파싱 보장)
    내부: client.messages.parse() + Structured Outputs 사용
    
    JSON 파싱 실패가 원천적으로 불가능 — 제약된 디코딩으로 스키마 준수 보장
    prefill 불필요 (Claude 4.6에서 prefill 지원 중단됨)
    
    주의: stop_reason이 "refusal"이면 안전 거부 → None 반환 + 로그 기록
          stop_reason이 "max_tokens"이면 스키마 미준수 가능 → None 반환 + 재시도 안내
    
    확장 사고: use_thinking 파라미터는 forced tool_choice와 API 호환 불가로 현재 미사용
      - Model Grader에서 활용 → 채점 전 내부 추론으로 평가 품질 향상
    """

def count_tokens(system_prompt: str, user_message: str) -> int:
    """
    반환: 예상 입력 토큰 수 (int)
    내부: client.messages.count_tokens() 사용 (무료 API)
    용도: 호출 전 MAX_INPUT_TOKENS 초과 여부 체크 → 초과 시 컨텍스트 압축 또는 경고
    """
```

---

### `services/plot_generator.py`
```python
def generate_plot(
    answers: dict,                           # 가이드 질문 6개 답변 dict (genre, character, mood, story, must_have, extra)
    previous_storyboard: str | None = None,  # 재생성 시 이전 스토리보드 전달 (컨텍스트 유지)
    modification_request: str | None = None  # 유저 수정 요청 ("Cut 3 의상을 빨간 자켓으로")
) -> str:
    """
    반환: plain text 스토리보드 (str)
    내부: call_claude(system.py 프롬프트, user_message)

    시스템 프롬프트: get_system_prompt(answers) → <role> + <user_context>(답변 기반) + <output_format> + <constraints>
    유저 메시지:
      첫 생성: "위 user_context를 바탕으로 스토리보드를 작성해주세요." (답변 내용은 시스템 프롬프트에만 존재)
      수정: <previous_storyboard> + <modification> → 수정 요청 부분만 반영

    컨텍스트 관리:
      첫 생성: previous_storyboard=None
      수정: previous_storyboard + modification_request를 user_message에 포함
        → Claude가 이전 스토리보드를 알고 있으므로 수정된 부분만 반영
        → 시스템 프롬프트의 <user_context>는 원래 의도 유지 역할 (cache_system=True로 비용 절감)

    에러 처리:
      빈 응답 → 1회 재시도 → 여전히 비어있으면 "생성에 실패했습니다. 다른 아이디어로 시도해보세요"
      예상 외 형식 ([Cut 패턴 없음) → 1회 재시도 → 2회 연속 실패 시 GenerationError
    """
```

---

### `services/plot_evaluator.py`
```python
from pydantic import BaseModel, Field

# Structured Outputs용 Pydantic 모델 — JSON 파싱 실패가 원천적으로 불가능
class ModelGraderResult(BaseModel):
    M1_image_prompt_quality: float = Field(description="이미지 프롬프트 구체성 1-10")
    M2_character_consistency: float = Field(description="캐릭터 일관성 1-10")
    M3_story_coherence: float = Field(description="서사 흐름 1-10")
    M4_motion_describability: float = Field(description="동작 묘사 구체성 1-10")
    M5_genre_adherence: float = Field(description="장르 규칙 준수 1-10")
    M6_parseable_intent: float = Field(description="필드 구분 명확성 1-10")
    reasoning: str = Field(description="평가 근거 요약")

@dataclass
class EvalResult:
    code_scores: dict[str, float]   # {"C1": 10, "C2": 8, ...}
    code_average: float             # Code Grader 평균 (C1~C5)
    model_scores: dict[str, float]  # {"M1": 7.2, "M2": 3.1, ...} — code_average < 5.0이면 빈 dict
    model_average: float            # Model Grader 평균 (M1~M6) — code_average < 5.0이면 0.0
    total_average: float            # (code_average + model_average) / 2
    passed: bool                    # total_average >= 5.0
    failed_items: list[str]         # 5점 미만 항목 ID 목록
    previous_total: float | None    # 재평가 시 변화량 계산용
    model_reasoning: str | None     # Model Grader의 평가 근거 (확장 사고 결과 포함)

def evaluate_plot(plain_text: str, previous_total: float | None = None) -> EvalResult:
    """
    Phase A: Code Grader (C1–C5)
      → code_average 산출
      → code_average < 5.0이면 여기서 즉시 반환 (Model Grader 실행 안 함)
      → C5 unsafe 사전 검수: settings.SAFETY_MODEL(Haiku)로 저비용 안전 분류
        → 의심 시 유저에게 "이 표현이 거부될 수 있습니다: [키워드]. 변경하시겠습니까?" 확인

    Phase B: Model Grader (M1–M6) — code_average >= 5.0일 때만 실행
      → call_claude_structured(eval.py 프롬프트, output_schema=ModelGraderResult, cache_system=True)
      → Structured Outputs: JSON 파싱 실패 원천 불가능 (prefill/regex 불필요)
      → 확장 사고: 채점 전 내부 추론으로 평가 품질 향상 (budget: settings.THINKING_BUDGET)
      → 프롬프트 캐싱: cache_system=True (채점 기준이 매번 동일하므로)
      → 에러 처리:
          stop_reason "refusal" → Model Eval 스킵, Code 점수만 사용 + "안전 거부" 안내
          stop_reason "max_tokens" → 스키마 미준수 가능 → Model Eval 스킵 + 경고
          API 실패 (SDK 재시도 소진 후) → Model Eval 스킵, Code 점수만 사용
          점수 범위: Pydantic validator로 사후 검증 max(1, min(10, score))

    Phase C: 합산
      → total_average = (code_average + model_average) / 2

    반환: EvalResult
    """

def full_eval(plain_text: str, previous_total: float | None = None) -> EvalResult:
    """최초 생성 시 전체 평가. evaluate_plot()과 동일.
    적용 기준: C1~C5 + M1~M6 전체"""

def focused_eval(
    changed_cuts: list[int],
    plain_text: str,
    previous_total: float | None = None
) -> EvalResult:
    """이미지 생성 후 수정 시 부분 평가.
    대상: 변경된 컷 + 인접 컷(±1)
    적용 기준: C2/C5 + M1~M4
    제외: C1/C3 (전체 구조 이미 검증), M5/M6 (전체 서사·장르 큰 변화 없음)
    합격선: full_eval과 동일 (5.0)
    실패 시: full_eval로 폴백"""

def run_code_grader(plain_text: str) -> dict[str, float]:
    """C1–C5 각 항목 점수 반환 (10 또는 0, 일부는 부분 점수)
    C5: settings.SAFETY_MODEL(Haiku)로 사전 검수 → 저비용 안전 분류"""

def run_model_grader(plain_text: str) -> ModelGraderResult | None:
    """Structured Outputs로 M1–M6 채점. 실패 시 None 반환."""
```

---

### `services/plot_advisor.py`
```python
def generate_advice(
    plain_text: str,
    eval_result: EvalResult,
    feedback: dict | None = None,
    previous_advice: str | None = None  # 이전에 준 가이드 요약 (중복 안내 방지)
) -> str:
    """
    두 가지 호출 시점:

    1) 자동 평가 후 (Phase 3) — feedback=None
       eval_result.failed_items만 보고 가이드 생성
       참조: prompt_eval_criteria.md의 Low-Score Guidance 테이블
       → criteria별 "유저에게 안내할 내용"과 "예시"를 기반으로 구체적 가이드 생성

    2) Human Eval 불만족 시 (Phase 4) — feedback=피드백_dict
       유저가 피드백 funnel에서 선택한 type/detail/target_cuts/free_text를
       eval_result와 함께 받아서 타겟팅된 가이드 생성

    컨텍스트 관리:
      previous_advice가 있으면 <previous_advice> XML 태그로 포함
      → Claude가 이전 가이드를 알고 있으므로 같은 안내 반복 방지, 새로운 약점에 집중

    캐싱: call_claude(cache_system=True) — advisor 시스템 프롬프트 + Low-Score Guidance 테이블 캐싱

    반환: 유저에게 보여줄 가이드라인 리포트 텍스트 (str)
    내부: call_claude(advisor.py 프롬프트, eval_result + failed_items + feedback + previous_advice)

    에러 처리:
      API 실패 → Low-Score Guidance 테이블 기반 정적 가이드 출력 (Claude 없이)
      응답 50자 미만 → 정적 가이드로 fallback
      stop_reason "refusal" → 정적 가이드로 fallback + 로그 기록
    """
```

---

### `services/plot_converter.py`
```python
# Scene은 schemas/scene.py의 Pydantic BaseModel로 정의됨
# plot_converter.py는 직접 Scene을 정의하지 않고 schemas.scene.Scene을 import
# from backend.app.schemas.scene import Scene

# schemas/scene.py:
class Scene(BaseModel):
    cut_number: int
    main_character: str
    sub_character: str | None = None
    action: str
    pose: str
    background: str
    era: str
    composition: str
    lighting: str
    mood: str
    story_beat: str
    duration_seconds: float  # 3.0–8.0, coerce_duration validator 포함

def scenes_to_plain_text(scenes: list[Scene]) -> str:
    """
    Scene JSON → [Cut N] plain text 복원.
    이미지 수정 시 generate_plot()의 previous_storyboard로 전달.
    라벨:값 1:1 대응이므로 정보 손실 없음. API 호출 불필요.
    """

def parse_storyboard(plain_text: str) -> list[Scene]:
    """
    plain text → Scene 리스트 파싱
    full_eval 통과 후 또는 focused_eval 통과 후 모두 동일하게 호출.
    반환: list[Scene]

    에러 처리:
      ParseError → "Cut [N]의 [필드명]을 파싱할 수 없습니다" 구체적 위치 안내
      타입 불일치 → 캐스팅 시도 → 실패 시 기본값 적용 + 유저에게 경고 출력
        예: "Cut 3의 duration이 '5초'로 파싱됐는데 5.0으로 자동 변환했습니다"
      schema 검증 실패 → "Cut [N]에서 [필드명]이 누락되었습니다" 안내
    """

def save_to_file(scenes: list[Scene], output_dir: str = "output") -> str:
    """
    반환: 저장된 파일 경로 (str)
    파일명: scene_<YYYYMMDD_HHMMSS>.json

    에러 처리:
      output/ 없음 → os.makedirs("output", exist_ok=True) 자동 생성
      파일 쓰기 실패 → JSON 내용을 터미널에 그대로 출력 (유저가 복사 가능)
    """
```

---

### `schemas/feedback.py`
```python
from pydantic import BaseModel

class Feedback(BaseModel):
    feedback_type: str    # "fan_appeal_mismatch" | "pacing_issue" | "input_mismatch"
    detail: str           # "character_appearance" | "no_climax" | "missing_scene" 등
    target_cuts: list[int]  # [1, 3, 7]
    free_text: str | None = None
```

---

### `cli.py` (터미널 진입점)
```python
def main():
    previous_total = None  # 점수 변화량 추적용
    loop_counter = 0       # 연속 미달 횟수 추적용

    # 1. 가이드 질문 6개 (장르, 캐릭터, 분위기, 줄거리, 필수 장면, 추가 요청)
    #    → 필수 4개(장르/캐릭터/분위기/줄거리): 빈 입력 시 재입력 요청
    #    → 선택 2개(필수 장면/추가 요청): Enter로 스킵 가능
    #    → API 호출 안 함 (비용 절약)
    # 2. 요약 제시 → confirm (y) 또는 항목 수정 (번호 선택)
    #
    # === Phase A: Code Eval 루프 ===
    # 3. plot_generator 호출 → plain text 생성
    # 4. run_code_grader 호출 → code_average 산출
    # 5. Code 점수 출력
    #
    # 6. code_average < 5.0?
    #    → Yes: loop_counter += 1
    #           Code 실패 항목 가이드 출력 (plot_advisor, feedback=None)
    #           → 3회 미달 시: 장르별 템플릿 제시 (prompts/templates.py)
    #           → 5회 미달 + Code 미통과: 템플릿 + "장면 수를 줄이거나 캐릭터를 1명만 넣어보세요"
    #           "어떤 부분을 바꾸고 싶으세요?" → 유저가 수정 포인트만 입력 → generate_plot(previous_storyboard + modification) → 3번으로 (Phase A 루프)
    #    → No: Phase B로 진행
    #
    # === Phase B: Model Eval ===
    # 7. run_model_grader 호출 → model_average 산출
    # 8. total_average = (code_average + model_average) / 2
    # 9. 합산 점수 출력 (이전 점수 대비 변화량 포함)
    #
    # === Phase C: 합산 점수 분기 ===
    # 10. total_average 구간별 분기:
    #
    #     10a. 5점 미만
    #          → loop_counter += 1
    #          → 3회 미달 시: 장르별 템플릿 제시
    #          → 5회 미달 + Code 통과 시: 부분 진행 허용
    #              "1. 이대로 진행 (리스크 감수) / 2. 템플릿 재시도 / 3. 새로 시작"
    #              → 1: Human Eval 진입 + loop_counter 리셋
    #              → 2: 템플릿 제시 + loop_counter 리셋
    #              → 3: 장르 선택부터 재시작 + loop_counter 리셋
    #          → Code + Model 전체 실패 항목 가이드 출력 (plot_advisor, feedback=None)
    #          → "어떤 부분을 바꾸고 싶으세요?" → 유저가 수정 포인트만 입력 → generate_plot(previous_storyboard + modification) → 3번으로 (Phase A부터 재시작)
    #
    #     10b. 5~7.9점
    #          → loop_counter 리셋
    #          → 약점 요약 출력 ("이 부분을 보강하면 더 좋은 영상이 됩니다")
    #          → "수정하시겠습니까? (y: 수정 / n: 이대로 진행)"
    #              → y: plot_advisor 가이드 출력 → 유저 재입력 → 3번으로 (Phase A부터 재시작)
    #              → n: Phase D(Human Eval)로 진행
    #
    #     10c. 8점 이상
    #          → loop_counter 리셋
    #          → 바로 Phase D(Human Eval)로 진행
    #
    # === Phase D: Human Eval ===
    # 11. H1/H2/H3 셀프 체크리스트
    # 12. 모두 확인 → confirm → plot_converter → JSON 저장
    # 13. 하나라도 미체크 → 피드백 funnel (Step 1~4)
    #     → plot_advisor 호출 (feedback=피드백_dict) → 가이드라인 출력
    #     → 유저 재입력 → 3번으로 (Phase A부터 재시작)
    #
    #
    # === Post-Image 수정 시 (이미지 생성 후 수정 요청) ===
    # 14. 이미지 생성 후 유저가 특정 컷 수정 요청
    #     → generate_plot(previous_storyboard + modification) → 수정된 스토리보드
    #     → focused_eval(changed_cuts, plain_text) — C2/C4/C5 + M1~M4, 변경컷+인접컷만
    #     → focused_eval 실패 시 full_eval로 폴백
    #     → 통과 시 변경된 컷만 이미지 재생성 (diff 기반)
    #
    # previous_total 업데이트 후 루프
```

---

## 4. 터미널 Score Display 규칙

프론트엔드의 원형 점수/색상 바를 터미널에서 표현하는 방법:

### 전체 점수 표시
```
전체 점수: 4.2 / 10          ← 첫 평가
전체 점수: 7.1 / 10 (+2.9 ↑) ← 재평가 시 변화량 표시
전체 점수: 3.8 / 10 (-0.4 ↓) ← 하락 시
```

### 통과/미달 항목 표시
```
통과 항목: ✓ 8개 항목 통과
미달 항목:
  M2 캐릭터 일관성    ██░░░░░░░░  2.1
  M4 동작 묘사       ███░░░░░░░  3.0
```
- 5점 미만 항목만 바로 표시
- 5점 이상 항목은 개수만 요약

### 미달 항목 상세 보기 (터미널용 펼침 대안)
프론트엔드에서는 바를 탭하면 가이드가 펼쳐지지만, 터미널에서는 탭이 불가.
대신 미달 항목 번호를 입력하면 상세 가이드를 보여주는 방식:

```
상세 보기 (번호 입력, 스킵은 Enter):
> 1

▸ 캐릭터 일관성 [2.1점]
  Cut 1에서는 흰 드레스인데 Cut 4에서 검은 자켓으로 바뀌어요.
  → 아이유의 의상을 처음 한 번 정해서 전체 컷에 동일하게 적용해보세요.

상세 보기 (번호 입력, 스킵은 Enter):
>
```

### 5점 미만 시 Confirm 차단
5점 미만일 때는 Human Eval로 넘어가지 않고, 반드시 가이드 → 재입력 루프를 거쳐야 한다.
```
현재 4.2점입니다. 5점 이상이어야 다음 단계로 진행할 수 있어요.
아래 가이드를 참고해서 수정해주세요.
```

---

## 5. 터미널 실행 흐름 시뮬레이션

```
$ python cli.py

==================================================
  AI 2차 창작 영상 — 스토리보드 생성기
==================================================

어떤 장르의 영상을 만들고 싶으세요?
  (예: K-pop 뮤비, 애니메이션 액션, 게임 시네마틱, 호러, 로맨스...)
> kpop 뮤비

주인공은 어떤 모습인가요?
  (예: 흰 드레스를 입은 여성 아이돌, 검은 갑옷의 기사...)
> 흰 드레스를 입은 아이유

어떤 분위기를 원하세요?
  (예: 슬프고 감성적인, 신나고 에너지 넘치는, 어둡고 긴장감 있는...)
> 슬프고 감성적인

어떤 이야기가 펼쳐지나요? 간단히 설명해주세요.
  (예: 빗속에서 마지막 콘서트를 마치고 무대를 떠난다)
> 빗속에서 마지막 콘서트를 마치고 무대를 떠난다

꼭 넣고 싶은 장면이 있나요? (없으면 Enter)
  (예: 비가 그치는 장면, 폭발 장면...)
> 비가 그치는 장면

기타 추가하고 싶은 내용이 있나요? (없으면 Enter)
  (예: 컷 전환을 빠르게, 엔딩에 여운을 길게...)
> 엔딩에 여운을 길게

──────────────────────────────────────
[입력 요약]

  장르: kpop 뮤비
  캐릭터: 흰 드레스를 입은 아이유
  분위기: 슬프고 감성적인
  줄거리: 빗속에서 마지막 콘서트를 마치고 무대를 떠난다
  필수 장면: 비가 그치는 장면
  추가 요청: 엔딩에 여운을 길게
──────────────────────────────────────

이대로 진행할까요? (y: 생성 / 번호: 항목 수정)
  1. 장르
  2. 캐릭터
  3. 분위기
  4. 줄거리
  5. 필수 장면
  6. 추가 요청
> y

생성 중...

──────────────────────────────────────
[Generated Storyboard]

[Cut 1] 캐릭터: 흰 드레스를 입은 아이유 ...
[Cut 2] 캐릭터: 흰 드레스의 아이유 ...
...
──────────────────────────────────────

수정하고 싶은 부분이 있나요? (없으면 Enter)
> Cut 3에서 의상을 빨간 자켓으로 바꿔줘

수정 반영 중...

──────────────────────────────────────
[Modified Storyboard]

[Cut 1] 캐릭터: 흰 드레스를 입은 아이유 ...
...
[Cut 3] 캐릭터: 빨간 자켓을 입은 아이유 ...   ← 수정 반영
...
──────────────────────────────────────

수정하고 싶은 부분이 있나요? (없으면 Enter)
>

스토리보드가 확정되었습니다.

[Phase A] Code Eval 중...
(이후 평가 → 가이드 → Human Eval 흐름은 기존과 동일)

...

모두 확인 완료. Confirm 하시겠습니까? (y/n): y

변환 중...
저장 완료: output/scene_20260315_143022.json
──────────────────────────────────────
```

---

## 6. 데이터 스키마

### 평가 결과 저장 방식

평가 결과(EvalResult)는 **파이프라인 내 변수로만 존재**한다. DB에 저장하지 않는다.
점수는 통과/미달 판단에만 사용되며, 판단이 끝나면 폐기된다.
DB 저장은 MVP 이후 평가 기준 튜닝/분석이 필요할 때 검토한다.

### 터미널 단계 간 전달 데이터

```
[유저 입력 — 가이드 질문 답변 dict]
{
  "genre": "kpop 뮤비",
  "character": "흰 드레스를 입은 아이유",
  "mood": "슬프고 감성적인",
  "story": "빗속에서 마지막 콘서트를 마치고 무대를 떠난다",
  "must_have": "비가 그치는 장면",    // 선택, null 가능
  "extra": "엔딩에 여운을 길게"        // 선택, null 가능
}

[plot_generator 출력]
plain_text: str  # [Cut 1] ... [Cut 2] ... 형태

[plot_evaluator 출력 — Code 통과 + Model 실행]
EvalResult {
  code_scores: {"C1": 10, "C2": 10, "C3": 10, "C4": 8, "C5": 10},
  code_average: 9.6,
  model_scores: {"M1": 7.0, "M2": 2.1, "M3": 6.5, "M4": 3.0, "M5": 8.0, "M6": 6.0},
  model_average: 5.4,
  total_average: 7.5,           # (9.6 + 5.4) / 2
  passed: true,
  failed_items: ["M2", "M4"],
  previous_total: null
}

[plot_evaluator 출력 — Code 평균 5점 미만]
EvalResult {
  code_scores: {"C1": 0, "C2": 10, "C3": 10, "C4": 3, "C5": 10},
  code_average: 6.6,             # 하지만 C1=0이므로 평균은 괜찮아도 C1이 치명적
  model_scores: {},              # ← 빈 dict, Model Grader 실행 안 됨
  model_average: 0.0,
  total_average: 3.3,            # code_average만으로 산출
  passed: false,
  failed_items: ["C1"],
  previous_total: null
}

[Human Eval 피드백 — schemas/feedback.py로 검증]
{
  "feedback_type": "input_mismatch",
  "detail": "missing_scene",
  "target_cuts": [4, 5],
  "free_text": "비가 그치는 장면이 없어"
}

[plot_converter 출력 — JSON 파일]
[
  {
    "cut_number": 1,
    "main_character": "아이유, 흰 드레스, 긴 갈색 머리",
    "sub_character": null,
    "action": "마이크를 천천히 내려놓는다",
    "pose": "정면, 고개 숙임",
    "background": "야외 대형 공연장, 빗속",
    "era": "modern",
    "composition": "fullshot",
    "lighting": "spotlight, 빗속 반짝임",
    "mood": "melancholy",
    "story_beat": "공연의 마지막 순간",
    "duration_seconds": 5.0
  },
  ...
]
```

---

## 7. 프롬프트 설계 포인트 (prompts/)

### 공통 원칙 (Anthropic 공식 권장)
- **XML 태그 구조화**: 모든 프롬프트에서 `<instructions>`, `<context>`, `<plot>`, `<rubric>`, `<examples>` 등으로 영역 구분. Claude는 XML 태그를 구조화 메커니즘으로 특별히 훈련됨.
- **시스템 프롬프트 경량화**: 역할 설정과 톤 정의에 집중. 상세 지시사항은 user message에 배치.
- **Prefill 사용 금지**: Claude 4.6에서 마지막 assistant 턴의 prefill이 지원 중단됨 (400 에러). JSON 출력은 Structured Outputs로 대체.
- **Few-shot 예제**: 3~5개의 다양한 품질 수준 예제를 `<examples>` 태그로 제공하여 일관성 향상.
- **캐싱 최적화**: 변하지 않는 내용(시스템 프롬프트, 채점 기준)을 프롬프트 앞쪽에 배치하여 cache_control 적중률 극대화.

### `system.py` — plot_generator용
핵심 지시 사항:
- 시스템 프롬프트 구조: `<role>` + `<user_context>` + `<output_format>` + `<constraints>`
- `<user_context>`: 가이드 질문 답변(장르, 캐릭터, 분위기, 줄거리, 필수 장면, 추가 요청)을 동적으로 조합
- ~~장르 프리셋(GENRE_RULES) 삭제~~ → 유저가 직접 입력한 장르/분위기를 기반으로 Claude가 자유 구성
- 출력은 반드시 `[Cut N]` 패턴으로 구분 (C1 통과 보장)
- 각 컷에 11개 필드를 명시적으로 포함 (C2 통과 보장)
- 컷 수 5–10개 범위 준수 (C3 통과 보장)
- plain text 유지 (JSON 출력 금지)
- 수정 시: user_message에 `<previous_storyboard>` + `<modification>` XML 태그로 컨텍스트 전달
- 수정 시 시스템 프롬프트의 `<user_context>`는 원래 의도 유지 역할 (cache_system=True로 비용 절감)

### `eval.py` — Model Grader용
핵심 지시 사항:
- Structured Outputs 사용 — ModelGraderResult Pydantic 스키마로 출력 보장
- prefill 불필요 (Structured Outputs가 대체)
- `<rubric>` 태그 안에 M1–M6 채점 기준 배치 (캐싱 최적화: 앞쪽 배치)
- `<plot>` 태그 안에 평가 대상 plain text 배치 (변동 부분: 뒤쪽 배치)
- 확장 사고 활용: 채점 전 내부 추론으로 middling score 방지
- Few-shot: 높은 점수/낮은 점수 플롯 예시 각 1개 포함

### `advisor.py` — plot_advisor용
핵심 지시 사항:
- failed_items + feedback만 받아서 타겟팅된 가이드 생성
- 전체 재작성 지시 금지, 해당 컷/필드만 안내
- 유저가 직접 수정할 수 있는 구체적 예시 제공
- **prompt_eval_criteria.md의 Low-Score Guidance 테이블을 `<rubric>` 태그에 포함** (캐싱 대상)
- `<previous_advice>` 태그로 이전 가이드 전달 → 중복 안내 방지
- feedback=None일 때: eval_result.failed_items만으로 가이드 생성
- feedback=dict일 때: type/detail/target_cuts/free_text를 추가 힌트로 활용

### `templates.py` — 3회 미달 시 유저 예시용
핵심 지시 사항:
- 장르별 1개씩 (kpop, anime, game) 예시 입력 정의
- 각 예시는 Code Eval C1~C5를 자연스럽게 통과하는 수준으로 작성
- 캐릭터 외형, 동작, 배경, 조명을 포함해서 "이 정도 쓰면 되는구나"를 보여주는 기준점 역할
- 유저가 그대로 쓰는 게 아니라 수정해서 쓰도록 유도 (자기 아이디어를 덧입히게)

---

## 8. 스트리밍 (나중에 추가 예정)

> **현재 MVP CLI에서는 미적용.** FastAPI + 프론트엔드 연동 시 적용 예정.
>
> 적용 대상: plot_generator (실시간 스토리보드 생성 표시), plot_advisor (실시간 가이드 표시)
> 방식: `client.messages.stream()` + SSE 이벤트 처리
> 효과: 체감 대기 시간 감소, max_tokens 클 때 SDK 타임아웃 방지

---

## 9. 비용 최적화 전략

### 프롬프트 캐싱
- 시스템 프롬프트 + 채점 기준(rubric)에 `cache_control: {"type": "ephemeral"}` 적용
- 캐시 읽기 비용: 기본 가격의 10% (90% 절감)
- eval 루프에서 동일 rubric이 반복되므로 효과 극대화
- 최소 캐시 가능 토큰: 1,024~4,096 (모델별 상이)

### 모델 라우팅
- C5 unsafe 사전 검수: Haiku 4.5 ($1/MTok) — 저비용
- 본격 평가 (M1–M6): Sonnet 4.5/4.6 ($3/MTok) — 기본
- 200K 토큰 초과 시 프리미엄 요금 (입력 2배) 주의 → count_tokens()로 사전 체크

### 배치 처리 (FastAPI 연동 후)
- Message Batches API: 표준 가격의 50% 할인
- 배치당 최대 100,000개 요청, 대부분 1시간 이내 완료
- 프롬프트 캐싱과 누적 적용 가능 (최대 95% 절감)
- 적용 시점: 다수 유저가 동시에 평가 요청할 때

---

## 9.5. 이미지 수정 시 부분 재생성 전략 (설계)

> **이미지 생성 단계 구현 시 적용 예정.** 스토리보드 수정 후 전체 이미지를 재생성하지 않고, 변경된 컷만 재생성하여 비용/시간 절감.

### 방식: 컷 단위 diff 기반 부분 재생성

```
유저: "Cut 3 의상을 빨간 자켓으로"
    │
    ▼
scenes_to_plain_text(scenes)            ← JSON → plain text 복원 (API 0회)
    │
    ▼
generate_plot(answers, previous_storyboard, modification)
    │  → 전체 스토리보드 텍스트 재생성 (API 1회)
    ▼
plot_converter → 새 JSON scenes
    │
    ▼
diff(이전 scenes, 새 scenes) → 컷 단위 비교
    │
    ├─ Cut 1: 변경 없음 → 기존 이미지 유지
    ├─ Cut 2: 변경 없음 → 기존 이미지 유지
    ├─ Cut 3: 변경됨    → 이미지 재생성 (API 1회)
    ├─ Cut 4: 변경 없음 → 기존 이미지 유지
    └─ Cut 5: 변경 없음 → 기존 이미지 유지
```

### 비용 비교

| | 전체 재생성 | diff 기반 부분 재생성 |
|---|---|---|
| 스토리보드 | API 1회 | API 1회 (동일) |
| 평가 | Full Eval (API 1~2회) | Focused Eval: C2/C4/C5 + M1~M4, 변경컷+인접컷 (API 0~1회) |
| 이미지 | 5~10회 | 변경 컷만 1~2회 |
| **합계** | **7~13회** | **2~3회** |

### Focused Eval — 이미지 수정 시 부분 평가

이미지 생성 후 수정 시에는 Full Eval 대신 Focused Eval을 적용한다.

| 항목 | Full Eval (최초 생성) | Focused Eval (이미지 수정 후) |
|------|----------------------|------------------------------|
| 평가 대상 | 전체 컷 | 변경된 컷 + 인접 컷(±1) |
| Code 기준 | C1~C5 | C2, C4, C5 |
| Model 기준 | M1~M6 | M1~M4 |
| 제외 사유 | — | C1/C3: 전체 구조 변경 없음. M5/M6: 전체 서사·장르 큰 변화 없음 |
| 합격선 | 5.0 | 5.0 (동일) |
| 실패 시 | advisor → 재입력 루프 | full_eval로 폴백 |

### 필요한 함수 (미구현)
- `diff_scenes(old: list[Scene], new: list[Scene]) -> list[int]` — 변경된 컷 번호 반환
- `regenerate_image(scene: Scene) -> str` — 특정 컷 이미지만 재생성

### Phase 5 — 이미지/영상 생성 (FLUX.1-schnell + 캐릭터 시트)

**이미지 일관성 전략:** 캐릭터 시트 자동 생성 + Global Context 강제 삽입

현재 이미지 모델은 Hugging Face Inference API의 FLUX.1-schnell (텍스트→이미지만 지원, IP-Adapter 미지원).
IP-Adapter 없이 텍스트 프롬프트만으로 일관성을 확보하기 위해:
1. Claude로 캐릭터 시트를 한 번 자동 생성 (상세 묘사 보장)
2. 모든 컷 프롬프트에 동일한 캐릭터 시트를 기계적으로 삽입

```
Step 0: 캐릭터 시트 생성 (Claude 1회 호출)
  answers['character'] + scenes[0].main_character
  → Claude: 헤어/의상/체형/피부/액세서리/특징 구조화
  → character_sheet (상세 텍스트)

Step 1: GlobalContext 생성
  GlobalContext(
    main_character = character_sheet,
    sub_character = (서브캐릭터 있으면 동일 과정),
    art_style = 장르/분위기에서 추론,
    era = scenes[0].era,
    color_palette = 장르/분위기에서 추론,
  )

Step 2: 컷별 이미지 생성 (N회)
  compose_cut_prompt(global_ctx, scene) → FLUX.1-schnell → cut_N.png
  (global_ctx의 캐릭터/스타일이 모든 컷에 동일하게 삽입)

Step 3: 컷별 영상 생성
  cut_N.png (첫 프레임 고정) + 동작 프롬프트 → Veo 2 → cut_N.mp4

Step 4: FFmpeg 합치기
  cut_1.mp4 + cut_2.mp4 + ... → final.mp4
```

**schemas/scene.py 추가:**
```python
class GlobalContext(BaseModel):
    main_character: str       # 캐릭터 시트 (Claude가 생성한 상세 묘사)
    sub_character: str | None
    art_style: str            # anime cel-shading / photorealistic 등
    era: str                  # modern / historical 등
    color_palette: str        # warm golden / cool blue 등
```

**services/character_sheet.py 인터페이스:**
```python
def generate_character_sheet(answers: dict, scenes: list[Scene]) -> str
  # Claude에게 캐릭터 시트 생성 요청 (1회)
  # 필수 항목: 성별/나이, 헤어, 의상, 액세서리, 체형, 피부, 특징

def extract_global_context(answers: dict, scenes: list[Scene]) -> GlobalContext
  # 캐릭터 시트 + 장르/분위기에서 art_style, color_palette 추론
```

**utils/prompt.py 인터페이스:**
```python
def compose_cut_prompt(global_ctx: GlobalContext, scene: Scene) -> str
  # global_ctx.main_character(캐릭터 시트) + global_ctx.art_style + scene 컷별 필드
  # 캐릭터 묘사는 모든 컷에서 문자열 수준으로 100% 동일
```

**services/image.py (팀원 기존 코드 활용):**
```python
generate_image_from_hf(prompt) → bytes  # FLUX.1-schnell 호출 (기존)
upload_to_cloudinary(image_bytes) → str  # Cloudinary 업로드 (기존)
```


---

## 10. 프론트엔드 연동 시 변경 사항 (참고)

터미널 CLI → FastAPI 전환 시 바꿀 부분만 정리:

| 현재 (CLI) | 연동 후 (FastAPI) |
|-----------|-----------------|
| `input()` 가이드 질문 6개 + confirm | `POST /api/plot` body로 answers dict 수신 |
| `print()` 로 결과 출력 | JSON response 반환 |
| `while` 루프로 재생성 | 프론트에서 재요청 |
| 터미널 점수 텍스트 | 프론트 원형 점수 + 색상 바 (Score Display UI) |
| 터미널 "번호 입력" 상세 보기 | 프론트 바 탭 → 가이드 펼침 |
| 터미널 체크리스트 (y/n) | 프론트 H1/H2/H3 체크박스 |
| 터미널 피드백 번호 선택 | 프론트 피드백 funnel 버튼/칩 UI |
| `output/*.json` 파일 저장 | DB 저장 + 이미지 생성 파이프라인 호출 (Phase 5) |
| 빈 입력 → "입력해주세요" 재입력 | 422 Validation Error (Pydantic 자동) |
| API 실패 → "네트워크 확인" 출력 | 503 Service Unavailable + retry-after header |
| 파일 저장 실패 → 터미널 JSON 출력 | 200 + JSON body 직접 반환 (저장 실패 flag 포함) |
| 3회 미달 → 터미널에 템플릿 출력 | 프론트에서 템플릿 모달/카드 표시 |
| 5회 미달 → 터미널 3가지 선택지 | 프론트에서 리스크 경고 모달 + 3개 버튼 |

services/ 코드는 그대로 재사용 — api/ 레이어만 추가하면 됨.
