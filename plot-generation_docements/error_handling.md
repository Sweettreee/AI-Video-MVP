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
| run_code_grader — C1 | `[Cut N]` 패턴이 아예 없는 자유 서술 형태 | 중간 |
| run_code_grader — C5 | Haiku 모델 기반 안전 분류의 false positive | 낮음 |
| run_model_grader — API 호출 | claude_client.py와 동일한 API 에러들 | 낮음 |
| run_model_grader — 응답 파싱 | Structured Outputs(tool_choice)로 해결됨 | 없음 |
| run_model_grader — 점수 범위 | Claude가 1~10 범위 밖의 점수 반환 | 낮음 |

### Phase 3 — Advisor

| Error point | What can go wrong | Likelihood |
|---|---|---|
| plot_advisor.py — API 호출 | claude_client.py와 동일한 API 에러들 | 낮음 |
| plot_advisor.py — 응답 | 빈 응답 또는 50자 미만 가이드 반환 | 낮음 |
| 재입력 루프 | 유저가 무한 루프에 갇힘 (계속 5점 미만) | 중간 |

### Phase 4 — Human Eval + Converter

| Error point | What can go wrong | Likelihood |
|---|---|---|
| schemas/feedback.py | 피드백 데이터 형태 불일치 | 낮음 |
| plot_converter.py — 파싱 | plain text → JSON 변환 시 특정 필드 추출 실패 | 중간 |
| schemas/scene.py | 변환된 JSON에 필수 필드 누락 | 낮음 |
| schemas/scene.py | 필드 타입 불일치 (duration_seconds가 문자열 등) | 낮음 |

### Phase 5 — Image Generation

| Error point | What can go wrong | Likelihood |
|---|---|---|
| character_sheet.py — Claude 호출 | 캐릭터 시트 생성 실패 | 낮음 |
| character_sheet.py — GlobalContext | 화풍/색감 추론 실패 (매칭 키워드 없음) | 낮음 (기본값 있음) |
| image.py — FLUX API | HuggingFace API 503 (모델 웜업) | 중간 |
| image.py — FLUX API | HuggingFace API 기타 에러 | 낮음 |
| image.py — Cloudinary | 업로드 실패 | 낮음 |
| diff_scenes | 컷 수 변경 | 낮음 |
| focused_eval | 부분 평가 자체 에러 | 낮음 |

### Phase 6 — Video Generation

| Error point | What can go wrong | Likelihood |
|---|---|---|
| video.py — FAL_KEY | .env에 FAL_KEY 없음 → VideoGenerationError | 중간 |
| video.py — Fal API 제출 | 비200 응답 | 낮음 |
| video.py — 폴링 | FAILED 상태 반환 | 낮음 |
| video.py — 타임아웃 | 5분 초과 | 낮음 |
| video.py — Scene 데이터 | 이미지 미생성 상태에서 영상 생성 요청 | 중간 |

---

## 2. Error Handling Strategy by Phase

### Phase 1 — Generation

| Error | Handling | 구현 위치 |
|---|---|---|
| 빈 입력 / 공백만 | `strip()` 체크 후 재입력 요청. FastAPI: 422 Validation Error | cli.py / api/plot.py |
| 잘못된 genre | `["kpop", "anime", "game"]` 체크 후 재입력 | cli.py / api/plot.py |
| API 키 무효 (401) | `anthropic.AuthenticationError` catch → 앱 종료 / 500 에러 | claude_client.py |
| Rate limit (429) | SDK 내장 재시도 (retry-after 대기) | claude_client.py |
| 네트워크 타임아웃 | SDK 내장 재시도 (지수 백오프) | claude_client.py |
| 서버 에러 (500) | SDK 내장 재시도 (지수 백오프) | claude_client.py |
| Claude 빈 응답 | 1회 재시도, 여전히 비어있으면 에러 | plot_generator.py |
| 예상 외 형식 | `[Cut` 패턴 없으면 1회 재시도, 3회 연속 실패 시 종료 | plot_generator.py |

### Phase 2 — Code Eval

| Error | Handling | 구현 위치 |
|---|---|---|
| C1 패턴 없음 | 낮은 점수로 처리 (에러 아님) | plot_evaluator.py |
| C5 안전 분류 | Haiku 모델(SAFETY_MODEL)로 전체 텍스트 분류 | plot_evaluator.py |
| Model Grader API 에러 | SDK 재시도 소진 후 → Model Eval 스킵 → Code 점수만 사용 | plot_evaluator.py |
| Model Grader JSON 파싱 | **Structured Outputs로 해결됨.** `client.messages.create() + tool_choice` | plot_evaluator.py |
| stop_reason "refusal" | Model Eval 스킵 + 안전 정책 위반 안내 | plot_evaluator.py |
| stop_reason "max_tokens" | Model Eval 스킵 + 응답 초과 안내 | plot_evaluator.py |
| 점수 범위 벗어남 | Pydantic validator `max(1, min(10, score))` | plot_evaluator.py |

### Phase 3 — Advisor

| Error | Handling | 구현 위치 |
|---|---|---|
| Advisor API 에러 | static fallback 문자열 반환 (루프 중단 방지) | plot_advisor.py |
| 가이드라인 빈 응답 | static fallback | plot_advisor.py |
| 무한 루프 | 3회→템플릿, 5회→계속 여부, 7회→강제 종료 | cli.py / 프론트 |

#### 무한 루프 방지 전략 (3단계)

**3회 연속 미달 → Step 1: 템플릿 제공**
해당 장르의 예시 입력 제시 (prompts/templates.py).

**5회 연속 미달 → Step 2: 부분 진행 허용**
Code Eval 통과 시 리스크 경고 후 Human Eval 허용.

**7회 연속 미달 → Step 3: 강제 종료**
  - `/api/plot/evaluate` API 레이어에서 failure_count ≥ 7 감지 시 즉시 HTTP 422 반환
  - 응답 body에 `action: "abort"` + `template_suggestions` 포함

### Phase 4 — Human Eval + Converter

| Error | Handling | 구현 위치 |
|---|---|---|
| 피드백 데이터 검증 실패 | Pydantic 검증 → CLI: 재시작 / FastAPI: 422 | schemas/feedback.py |
| plain text → JSON 파싱 실패 | 구체적 위치 안내 "Cut [N]의 [필드명]" | plot_converter.py |
| scene.py 스키마 검증 실패 | 빠진 필드명 출력 + 재시도 안내 | plot_converter.py |
| 타입 불일치 | 타입 캐스팅 시도 → 실패 시 기본값 적용 | plot_converter.py |

### Phase 5 — Image Generation

| Error | Handling | 구현 위치 |
|---|---|---|
| 캐릭터 시트 생성 실패 | GlobalContext = null, 스토리보드 데이터만 반환 | character_sheet.py / api/image.py |
| 화풍/색감 추론 실패 | 기본값 적용 ("high quality, detailed, cinematic" / "natural balanced tones") | character_sheet.py |
| FLUX API 503 (웜업) | 5초 대기 후 최대 5회 재시도 | image.py |
| FLUX API 기타 에러 | 해당 컷 실패 처리, 나머지 컷 계속 진행 | api/image.py |
| Cloudinary 업로드 실패 | 2초 대기 후 최대 3회 재시도 | image.py |
| diff_scenes 후 변경 없음 | "변경된 컷이 없습니다" 반환 | api/image.py |
| focused_eval 미통과 | eval_result + failed_items 반환 (프론트에서 가이드 표시) | api/image.py |
| focused_eval 자체 에러 | full_eval로 폴백 | plot_evaluator.py |

### Phase 6 — Video Generation

| Error | Handling | 구현 위치 |
|---|---|---|
| FAL_KEY 미설정 | `VideoGenerationError` raise → api/video.py에서 500 응답 | video.py |
| Fal API 제출 실패 (비200) | `VideoGenerationError` raise → api/video.py에서 500 응답 | video.py |
| 폴링 중 FAILED | `VideoGenerationError` raise → api/video.py에서 500 응답 | video.py |
| 5분 초과 타임아웃 | `VideoGenerationError` raise → api/video.py에서 500 응답 | video.py |
| 네트워크/시스템 에러 | Exception → `VideoGenerationError` wrap → 500 응답 | video.py |
| Scene에 이미지 없음 | 단건: 400 에러 / 일괄: skipped 처리 | api/video.py |
| Project 미존재 | 404 에러 | api/video.py |
| 일괄 생성 시 개별 실패 | `VideoGenerationError` catch → 해당 Scene `video_status="failed"` DB 저장, 나머지 계속 | api/video.py |

> **Fallback URL 제거:** 이전 버전은 `w3schools.com` 더미 URL을 반환했으나, 프론트가 성공/실패를 구분할 수 없어 제거됨. 실패 시 명시적 예외로 상태를 전달한다.

---

## 3. claude_client.py — SDK 내장 재시도 정책

Anthropic Python SDK의 내장 재시도 메커니즘을 사용한다.

| 설정 | 값 |
|---|---|
| max_retries | 3 (config.py에서 설정) |
| 백오프 방식 | 지수 백오프 (초기 0.5초, 최대 60초) + 지터 (0.75~1.0배) |
| retry-after 헤더 | 자동 파싱, 429 시 서버 지정 대기 시간 적용 |

| 에러 타입 | SDK 재시도 여부 | 실패 시 |
|---|---|---|
| AuthenticationError (401) | 안 함 | 즉시 raise |
| RateLimitError (429) | 함 (retry-after 대기) | raise |
| APITimeoutError (408) | 함 (지수 백오프) | raise |
| InternalServerError (500+) | 함 (지수 백오프) | raise |
| OverloadedError (529) | 함 (지수 백오프) | raise |

---

## 4. Fallback 전략 요약

| 상황 | Fallback |
|---|---|
| Model Grader API 실패 | Code 점수만으로 판단 + "AI 평가 일시 불가" 안내 |
| Advisor API 실패 | Low-Score Guidance 테이블 기반 정적 가이드 출력 |
| Converter 파싱 부분 실패 | 실패한 필드에 기본값 적용 + 경고 표시 |
| 파일 저장 실패 | JSON 내용을 터미널에 출력 (유저가 복사 가능) |
| Focused Eval 실패 | full_eval로 폴백 (전체 재평가) |
| 무한 루프 (3회 미달) | 장르별 템플릿 예시 제공 |
| 무한 루프 (5회 미달) | 리스크 경고 + 부분 진행 허용 |
| GlobalContext 생성 실패 | global_context_json = null, 스토리보드만 반환 |
| FLUX API 실패 (개별 컷) | 해당 컷만 실패, 나머지 계속 |
| Fal.ai API 실패 | VideoGenerationError raise → 단건 500 / 일괄 해당 컷 failed |
| 영상 생성 타임아웃 | VideoGenerationError raise → 단건 500 / 일괄 해당 컷 failed |

---

## 5. FastAPI 에러 응답 매핑

| 상황 | HTTP Status | Response |
|---|---|---|
| 입력 검증 실패 | 422 | Pydantic ValidationError 자동 |
| 리소스 미존재 (Project/Scene) | 404 | `{ "detail": "...을 찾을 수 없습니다" }` |
| AI 평가 전 human-eval 요청 | 400 | `{ "detail": "AI 평가를 먼저 완료해주세요." }` |
| Human Eval 전 confirm 요청 | 400 | `{ "detail": "Human Eval을 먼저 완료해주세요." }` |
| 이미지 미생성 상태에서 영상 요청 | 400 | `{ "detail": "이미지를 먼저 생성해 주세요" }` |
| Scene 없음 | 400 | `{ "detail": "생성된 Scene이 없습니다" }` |
| API 키 / 서버 에러 | 500 | `{ "detail": "서버 에러 발생: ..." }` |
| 외부 API 불가 | 503 | `{ "detail": "서비스 일시 불가" }` |

services/ 내부의 에러 처리 로직은 그대로 유지 — api/ 레이어에서 exception을 HTTP 응답으로 변환하기만 하면 됨.

---

## 관련 문서

| 문서 | 내용 |
|------|------|
| `implementation_spec.md` | Phase별 구현 설계 |
| `image.md` | 이미지 생성 파이프라인 에러 상세 |
| `video-generate.md` | 영상 생성 파이프라인 에러 상세 |
| `prompt_eval_criteria.md` | 평가 기준 (Full Eval / Focused Eval) |
| `folder_structure_guide.md` | 폴더 구조 |
