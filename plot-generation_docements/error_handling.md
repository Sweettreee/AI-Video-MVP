# Plot Generation — Error Handling Strategy

---

## 1. Error Analysis: Where can errors occur?

파이프라인의 모든 단계를 순서대로 훑으면서, 각 지점에서 발생할 수 있는 에러를 식별한다.

### Phase 1 — Generation

| Error point | What can go wrong | Likelihood |
|---|---|---|
| 유저 입력 | 빈 문자열, 공백만 입력 | 높음 |
| 유저 입력 | genre가 kpop/anime/game 중 하나가 아님 | 중간 |
| claude_client.py — API 호출 | API 키 무효 (만료, 오타) | 중간 |
| claude_client.py — API 호출 | Rate limit 초과 (429) | 낮음 (MVP 단계) |
| claude_client.py — API 호출 | 네트워크 타임아웃 | 낮음 |
| claude_client.py — API 호출 | Anthropic 서버 에러 (500) | 낮음 |
| plot_generator.py | Claude가 빈 응답 반환 | 낮음 |
| plot_generator.py | Claude가 plain text 대신 JSON이나 마크다운 등 예상 외 형식 반환 | 중간 |

### Phase 2 — Code Eval

| Error point | What can go wrong | Likelihood |
|---|---|---|
| run_code_grader — C1 | `[Cut N]` 패턴이 아예 없는 자유 서술 형태 | 중간 (Claude 프롬프트가 좋으면 낮음) |
| run_code_grader — C5 | unsafe 키워드 탐지 regex 자체의 false positive | 낮음 |
| run_model_grader — API 호출 | claude_client.py와 동일한 API 에러들 | 낮음 |
| run_model_grader — 응답 파싱 | Claude가 M1~M6 JSON 형식을 안 지킴 (키 누락, 숫자 아닌 값) | 중간 |
| run_model_grader — 점수 범위 | Claude가 1~10 범위 밖의 점수 반환 (0, 15 등) | 낮음 |

### Phase 3 — Advisor

| Error point | What can go wrong | Likelihood |
|---|---|---|
| plot_advisor.py — API 호출 | claude_client.py와 동일한 API 에러들 | 낮음 |
| plot_advisor.py — 응답 | 빈 응답 또는 50자 미만 가이드 반환 | 낮음 |
| cli.py — 재입력 루프 | 유저가 무한 루프에 갇힘 (계속 5점 미만) | 중간 |
| run_model_grader — API 호출 | thinking + forced tool_choice 동시 사용 시 400 에러 | 없음 (수정됨) |

### Phase 4 — Human Eval + Converter

| Error point | What can go wrong | Likelihood |
|---|---|---|
| schemas/feedback.py | 피드백 데이터 형태 불일치 (잘못된 feedback_type, target_cuts가 비어있음) | 낮음 (CLI는 선택지 기반) |
| plot_converter.py — 파싱 | plain text → JSON 변환 시 특정 필드 추출 실패 | 중간 |
| schemas/scene.py | 변환된 JSON에 필수 필드 누락 | 낮음 (Code Eval C2 통과했으면) |
| schemas/scene.py | 필드 타입 불일치 (duration_seconds가 문자열 등) | 낮음 |
| save_to_file | output/ 디렉토리가 없음 | 중간 (첫 실행 시) |
| save_to_file | 디스크 공간 부족, 파일 쓰기 권한 없음 | 낮음 |

---

## 2. Error Handling Strategy by Phase

### Phase 1 — Generation

| Error | Handling | 구현 위치 |
|---|---|---|
| 빈 입력 / 공백만 | 입력 받은 직후 `strip()` 체크. 비어있으면 "스토리보드 아이디어를 입력해주세요" 출력 후 재입력 요청. API 호출 안 함 | cli.py |
| 잘못된 genre | 입력 받은 직후 `["kpop", "anime", "game"]`에 포함 여부 체크. 아니면 "kpop, anime, game 중 하나를 선택해주세요" 후 재입력 | cli.py |
| API 키 무효 (401) | `anthropic.AuthenticationError` catch → "API 키가 유효하지 않습니다. .env 파일을 확인해주세요" 출력 후 앱 종료 | claude_client.py |
| Rate limit (429) | `anthropic.RateLimitError` catch → 30초 대기 후 1회 재시도. 재시도도 실패하면 "잠시 후 다시 시도해주세요" 후 앱 종료 | claude_client.py |
| 네트워크 타임아웃 | `anthropic.APITimeoutError` catch → 1회 재시도 (5초 간격). 실패 시 "네트워크 연결을 확인해주세요" | claude_client.py |
| 서버 에러 (500) | `anthropic.InternalServerError` catch → 1회 재시도 (5초 간격). 실패 시 "Anthropic 서버에 문제가 있습니다. 잠시 후 다시 시도해주세요" | claude_client.py |
| Claude 빈 응답 | `response.content[0].text`가 빈 문자열이면 1회 재시도. 여전히 비어있으면 "스토리보드 생성에 실패했습니다. 다른 아이디어로 시도해보세요" | plot_generator.py |
| 예상 외 형식 | `[Cut` 패턴이 응답에 하나도 없으면 1회 재시도. 여전히 없으면 "생성 형식에 문제가 있습니다. 다시 시도합니다" 후 재생성. 3회 연속 실패 시 앱 종료 | plot_generator.py |

### Phase 2 — Code Eval

| Error | Handling | 구현 위치 |
|---|---|---|
| C1 패턴 없음 | 이건 에러가 아니라 "낮은 점수"로 처리. C1 = 0점 → code_average 하락 → Phase A 루프에서 advisor 가이드 제공 | plot_evaluator.py |
| C5 false positive | unsafe 키워드 리스트를 보수적으로 관리. 의심 시 유저에게 "이 표현이 영상 생성 시 거부될 수 있습니다: [키워드]. 변경하시겠습니까?" 확인 후 유저 판단에 맡김 | plot_evaluator.py |
| Model Grader API 에러 | SDK 내장 재시도 소진 후에도 실패 → Model Eval 스킵 → Code 점수만으로 판단 → 유저에게 "AI 평가를 일시적으로 수행할 수 없어 구조 평가만 진행했습니다" 안내 | plot_evaluator.py |
| Model Grader JSON 파싱 | **Structured Outputs로 해결됨.** `client.messages.parse()` + Pydantic 스키마로 JSON 파싱 실패가 원천적으로 불가능. prefill/regex 기반 파싱 불필요. | plot_evaluator.py |
| Model Grader stop_reason "refusal" | 안전 거부 — Model Eval 스킵, Code 점수만 사용 + "평가 내용에 안전 정책 위반 표현이 포함되어 있습니다" 안내 | plot_evaluator.py |
| Model Grader stop_reason "max_tokens" | Structured Outputs 스키마 미준수 가능 — Model Eval 스킵 + "평가 응답이 너무 길어 완료되지 못했습니다" 안내 | plot_evaluator.py |
| 점수 범위 벗어남 | Pydantic validator로 사후 검증 `max(1, min(10, score))`. 로그에 경고 기록 | plot_evaluator.py |

### Phase 3 — Advisor

| Error | Handling | 구현 위치 |
|---|---|---|
| Advisor API 에러 | SDK 재시도 소진 후에도 실패 → static fallback 문자열 반환 (루프 중단 방지). "캐릭터 외형을 첫 컷에서 구체적으로 묘사하고..." | plot_advisor.py |
| 가이드라인 빈 응답 | response 없거나 strip() 후 빈 문자열 → static fallback | plot_advisor.py |
| 무한 루프 (계속 5점 미만) | fail_count 카운터 유지. 3회→템플릿 제안, 5회→계속 여부 확인, 7회→강제 종료 | cli.py |
| Model Grader thinking + tool_choice 충돌 | use_thinking=True 제거로 해결됨. forced tool_choice와 extended thinking은 Anthropic API에서 동시 사용 불가 (400 error) | plot_evaluator.py (수정 완료) |

#### 무한 루프 방지 전략 (3단계)

**7회 연속 미달 → Step 3: 강제 종료**

```
생성에 반복적으로 실패했습니다. 다른 아이디어로 새로 시작해주세요.
```
`sys.exit(1)` 호출.

---

**3회 연속 미달 → Step 1: 템플릿 제공**

해당 장르의 예시 입력을 보여줘서 유저가 참고하거나 수정해서 쓸 수 있게 한다.
직접 처음부터 쓰는 것보다 예시를 수정하는 게 훨씬 쉬움.

```
3회 연속 5점 미만입니다. 이런 식으로 입력하면 좋은 점수가 나와요:

[K-pop 예시]
"아이유가 흰 드레스를 입고, 빗속 야외 공연장에서 마지막 노래를 부른다.
 스포트라이트 아래 천천히 마이크를 내려놓고, 관객석을 바라보며 미소 짓다가,
 무대 뒤로 걸어가며 손을 흔든다."

이 예시를 수정하거나, 새로운 아이디어를 입력해보세요:
>
```

장르별 예시는 `prompts/templates.py`에 사전 정의해둔다 (kpop/anime/game 각 1개).

**5회 연속 미달 → Step 2: 부분 진행 허용**

Code Eval을 통과한 상태라면(구조는 맞는데 품질 점수만 낮은 경우),
낮은 항목에 대한 리스크를 경고하면서 Human Eval 진행을 허용한다.

```
5회 연속 5점 미만입니다. 현재 아이디어로 계속 시도하기 어려울 수 있어요.

현재 상태:
  Code Eval: ✓ 통과 (구조는 문제 없음)
  미달 항목:
    M2 캐릭터 일관성 [3.2] — 컷마다 캐릭터 외형이 달라질 수 있어요
    M4 동작 묘사 [2.8] — 영상에서 움직임이 적을 수 있어요

이대로 진행하면 위 항목의 품질이 낮을 수 있습니다.
  1. 이대로 진행 (리스크 감수)
  2. 템플릿 기반으로 다시 시도
  3. 완전히 새로운 아이디어로 시작
선택: 
```

- 1 선택 → 점수 관계없이 Human Eval 진입 허용
- 2 선택 → 템플릿 다시 제시 → 루프 카운터 리셋
- 3 선택 → 처음부터 재시작 (장르 선택부터) → 루프 카운터 리셋



### Phase 4 — Human Eval + Converter

| Error | Handling | 구현 위치 |
|---|---|---|
| 피드백 데이터 검증 실패 | Pydantic `Feedback` 모델로 검증. 실패 시 "피드백 형식이 올바르지 않습니다" 후 피드백 funnel 재시작. CLI에서는 선택지 기반이라 거의 발생 안 하지만, FastAPI 연동 시 422 자동 반환 | schemas/feedback.py + cli.py |
| plain text → JSON 파싱 실패 | `ParseError` raise. "스토리보드 변환 중 문제가 발생했습니다. Cut [N]의 [필드명]을 파싱할 수 없습니다" 구체적 위치 안내. 유저에게 해당 컷 수정 요청 후 재변환 | plot_converter.py |
| scene.py 스키마 검증 실패 | Pydantic `ValidationError` catch. 빠진 필드명 출력: "Cut [N]에서 [필드명]이 누락되었습니다". Code Eval C2를 통과했는데 여기서 걸리면 converter 파싱 버그 → 로그에 warning 기록 + 유저에게 재시도 안내 | plot_converter.py + schemas/scene.py |
| 타입 불일치 | Pydantic이 자동 감지. "Cut [N]의 duration_seconds는 숫자여야 합니다" 후 converter가 타입 캐스팅 시도 (`float("5.0")` 등). 캐스팅도 실패하면 기본값 적용 (duration_seconds: 5.0) | plot_converter.py |
| output/ 디렉토리 없음 | `save_to_file()` 시작 시 `os.makedirs("output", exist_ok=True)` 자동 생성 | plot_converter.py |
| 파일 쓰기 실패 | `IOError` catch → "파일 저장에 실패했습니다. 디스크 공간과 권한을 확인해주세요" 출력. JSON 내용을 터미널에 그대로 출력해서 유저가 복사할 수 있게 fallback 제공 | plot_converter.py |

---

## 3. claude_client.py — SDK 내장 재시도 정책

Anthropic Python SDK의 내장 재시도 메커니즘을 사용한다. 커스텀 재시도 로직은 불필요.

| 설정 | 값 |
|---|---|
| max_retries | 3 (config.py에서 설정) |
| 백오프 방식 | 지수 백오프 (초기 0.5초, 최대 60초) + 지터 (0.75~1.0배) |
| retry-after 헤더 | 자동 파싱, 429 시 서버 지정 대기 시간 적용 |

| 에러 타입 | SDK 재시도 여부 | 실패 시 |
|---|---|---|
| AuthenticationError (401) | 안 함 | 즉시 raise → cli.py에서 "API 키 확인" 안내 후 종료 |
| RateLimitError (429) | 함 (retry-after 대기) | 재시도 소진 후 raise → "잠시 후 재시도" 안내 |
| APITimeoutError (408) | 함 (지수 백오프) | 재시도 소진 후 raise → "네트워크 확인" 안내 |
| InternalServerError (500+) | 함 (지수 백오프) | 재시도 소진 후 raise → "서버 문제" 안내 |
| OverloadedError (529) | 함 (지수 백오프) | 재시도 소진 후 raise → "서버 과부하" 안내 |
| 기타 예외 | 안 함 | 그대로 raise → 에러 메시지 출력 |

추가 고려사항:
- `stop_reason: "refusal"` (안전 거부) → 재시도 의미 없음, 입력 수정 안내
- `stop_reason: "max_tokens"` → Structured Outputs 스키마 미준수 가능, 재시도 또는 fallback

---

## 4. Fallback 전략 요약

에러 발생 시 가능한 한 **서비스를 중단하지 않고 대안을 제공**하는 것이 원칙.

| 상황 | Fallback |
|---|---|
| Model Grader API 실패 | Code 점수만으로 판단 + "AI 평가 일시 불가" 안내 |
| Advisor API 실패 | Low-Score Guidance 테이블 기반 정적 가이드 출력 |
| Converter 파싱 부분 실패 | 실패한 필드에 기본값 적용 + 경고 표시 |
| 파일 저장 실패 | JSON 내용을 터미널에 출력 (유저가 복사 가능) |
| Focused Eval 실패 | full_eval로 폴백 (전체 재평가). full_eval도 실패 시 Code 점수만으로 판단 |
| Focused Eval 자체 에러 | full_eval로 폴백 + "부분 평가 실패, 전체 평가로 전환" 안내 |
| 무한 루프 (3회 미달) | 장르별 템플릿 예시 제공 → 유저가 수정해서 재시도 |
| 무한 루프 (5회 미달) | Code 통과 시: 리스크 경고 + 부분 진행 허용. Code 미통과 시: 템플릿 + 난이도 낮추기 제안 |

---

## 5. 프론트엔드 연동 시 변경사항

CLI에서 `print()` + 재입력으로 처리하던 에러들이 FastAPI 연동 시 HTTP 응답으로 바뀜:

| CLI | FastAPI |
|---|---|
| "API 키를 확인해주세요" + 앱 종료 | 500 Internal Server Error + error message |
| "다시 입력해주세요" + 재입력 요청 | 422 Validation Error (Pydantic 자동) |
| "네트워크를 확인해주세요" + 재시도 안내 | 503 Service Unavailable + retry-after header |
| 터미널에 JSON 출력 (파일 저장 실패) | 200 + JSON body 직접 반환 (저장 실패 flag 포함) |
| "5회 연속 미달, 이대로 진행?" | 프론트에서 리스크 경고 모달 + "이대로 진행 / 템플릿으로 재시도 / 새로 시작" 3개 버튼 |

services/ 내부의 에러 처리 로직은 그대로 유지 — api/ 레이어에서 exception을 HTTP 응답으로 변환하기만 하면 됨.
