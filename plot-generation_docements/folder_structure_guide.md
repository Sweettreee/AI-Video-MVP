# Backend 폴더 구조 — 역할 및 필요성 설명

## 전체 구조

```
backend/
├── app/
│   ├── api/           # 프론트엔드가 호출하는 문(입구)
│   ├── core/          # 앱 전체 설정
│   ├── db/            # 데이터 저장소
│   ├── schemas/       # 데이터 형태 검증
│   ├── services/      # 실제 일을 하는 곳
│   ├── prompts/       # Claude에게 보내는 지시서 모음
│   └── main.py        # 앱 시작점 (FastAPI)
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 레이어별 설명

### api/ — "프론트엔드가 두드리는 문"

프론트엔드에서 HTTP 요청이 들어오면 가장 먼저 닿는 곳.
여기서는 직접 일을 하지 않고, services/에 "이거 해줘"라고 넘기기만 한다.

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| plot.py | `/api/plot` 라우터 (6개 엔드포인트) | generate, evaluate, advice, modify, human-eval, confirm — 스토리보드 생성~확정까지의 전체 플로우 |
| image.py | `/api/image` 라우터 (4개 엔드포인트) | 단건 생성/수정, 일괄 생성(generate-all), 텍스트 수정 기반 부분 재생성(modify-by-text) |
| video.py | `/api/video` 라우터 (2개 엔드포인트) | 단건 영상 생성, 일괄 영상 생성(generate-all) |
| deps.py | 공통 의존성 함수 | `load_project()`, `load_global_context()`, `load_scenes_from_db()` — DB 로드 + 404/400 처리를 한 곳에서 관리 |

> 비즈니스 로직은 services/에 있고, api/는 요청 검증 + services 호출 + 응답 변환만 담당.

---

### core/ — "앱 전체 설정 금고"

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| config.py | .env에서 API 키를 읽어와서 앱 전체에서 쓸 수 있는 settings 객체로 만듦 | .env는 텍스트 파일일 뿐이라 오타 검증이 안 됨. config.py가 앱 시작 시 "ANTHROPIC_API_KEY가 없네?" 하고 즉시 에러를 던져줘서, 배포 후 삽질을 막아줌. |

---

### db/ — "데이터 저장소"

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| database.py | SQLite 연결, 세션 관리, 런타임 마이그레이션 | DB 연결 코드가 services/ 여기저기에 흩어지면, 나중에 DB를 바꿀 때 모든 파일을 다 수정해야 함. `_migrate()` 함수: 앱 기동 시 기존 DB에 신규 컬럼(failure_count, human_eval_json 등)을 idempotent하게 추가. |
| models.py | projects, scenes 테이블 정의 | Project: answers_json, plain_text, global_context_json, failure_count(연속 실패 횟수), human_eval_json 포함. Scene: 12 필드 + 이미지/영상 URL 컬럼 포함. 런타임 마이그레이션(_migrate)으로 기존 DB에 컬럼 추가. |

---

### schemas/ — "데이터 형태 검증관"

API로 들어오고 나가는 데이터의 형태(타입, 필수값 등)를 검증하는 곳.
Pydantic 모델을 정의한다.

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| project.py | PlotRequest, PlotGenerateResponse, PlotEvalResponse(failure_count/loop_warning/template_suggestions 포함), PlotModifyRequest, PlotConfirmRequest, HumanEvalRequest, HumanEvalResponse | plot API의 요청/응답 스키마. 가이드 질문 답변의 필수/선택 필드 자동 검증. |
| scene.py | Scene (12 필드) + GlobalContext (캐릭터 시트, 화풍, 색감) | confirm 후 JSON 변환 결과의 필수 필드 자동 검증. GlobalContext는 이미지 일관성의 핵심. |
| image.py | ImageGenerateRequest, ImageModifyRequest, ImageGenerateAllRequest, ImageModifyByTextRequest | 이미지 API의 요청 스키마. |
| video.py | VideoGenerateRequest, VideoGenerateAllRequest | 영상 API의 요청 스키마. |
| feedback.py | Feedback (type, detail, target_cuts, free_text) | 피드백 funnel 데이터 구조. 프론트가 이상한 형태로 보내면 여기서 걸러짐. |

---

### services/ — "실제 일을 하는 곳" (가장 중요)

비즈니스 로직이 사는 곳. Claude API 호출, 평가, 가이드 등 핵심 작업이 여기서 일어난다.

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| claude_client.py | Anthropic client 생성 + call_claude() / call_claude_structured() / count_tokens() 공통 함수. SDK 내장 재시도(max_retries), 프롬프트 캐싱(cache_control), 토큰 카운팅 포함 | Claude 호출 코드를 한 곳에만 정의. 모델 변경, retry, 캐싱 설정을 여기만 고치면 전체 반영. |
| plot_generator.py | `generate_plot(answers, previous_storyboard, modification_request)` → plain text 스토리보드 생성 | 가이드 질문 답변 + system prompt를 조합해서 Claude에게 보내고 결과를 받는 로직. |
| plot_evaluator.py | `full_eval()` (C1~C3/C5 + M1~M6 전체 평가) + `focused_eval()` (이미지 수정 후 부분 평가: 변경컷+인접컷, C2/C5 + M1~M4) | 이중 평가 구조: 최초 생성은 전체 평가, 이미지 수정 후는 부분 평가로 비용·시간 절감. |
| plot_advisor.py | `generate_advice(plain_text, eval_result, previous_advice=None)` — failed_items 기반 개선 가이드라인 생성 | Claude는 코치이지 작가가 아님. 유저가 직접 수정할 수 있도록 가이드. |
| plot_converter.py | `parse_storyboard()` (plain text→JSON) + `scenes_to_plain_text()` (JSON→plain text) + `diff_scenes()` (old/new 비교→변경 컷 번호) | 양방향 변환 + 차이 감지. |
| character_sheet.py | `generate_character_sheet()` (Claude→캐릭터 시트) + `extract_global_context()` (→GlobalContext) + `compose_cut_prompt()` (GlobalContext+Scene→이미지 프롬프트) | 캐릭터 일관성의 핵심. 캐릭터 시트가 모든 컷 프롬프트에 동일하게 삽입됨. |
| image.py | `generate_image_from_hf()` (FLUX.1-schnell 호출) + `upload_to_cloudinary()` + `backend_compose_prompt()` (단건용 프롬프트 조립) | 이미지 생성 + 클라우드 업로드. |
| video.py | `generate_video_from_fal()` (Fal.ai Kling Video 호출 + 폴링) | 이미지→영상 변환. 향후 Veo 2로 전환 예정. |

**왜 8개로 나눴는가:**
파이프라인 단계별로 분리하면 각 단계를 독립적으로 테스트/수정할 수 있고, 팀원이 다른 파일 작업할 때 충돌이 안 남.

```
claude_client.py    → "Claude한테 전화 거는 방법" (공통)
plot_generator.py   → "만들어"
plot_evaluator.py   → "채점해"
plot_advisor.py     → "유저한테 뭘 고치면 좋을지 알려줘"
plot_converter.py   → "JSON으로 바꿔 / plain text로 복원해 / 차이 찾아"
character_sheet.py  → "캐릭터 시트 만들고 프롬프트에 끼워"
image.py            → "이미지 생성해"
video.py            → "영상 만들어"
```

---

### prompts/ — "Claude에게 보내는 지시서 모음"

Claude API에 보내는 프롬프트 텍스트를 코드와 분리해서 관리하는 곳.

| 파일 | 언제 쓰이는가 | 누가 가져다 쓰는가 | 왜 분리했는가 |
|------|-------------|-------------------|-------------|
| system.py | 유저가 가이드 질문 답변 완료 후 | plot_generator.py | 역할 지시 + 유저 답변 기반 `<user_context>` 동적 생성 + 출력 포맷. 캐릭터 일관성 강화 프롬프트 포함 (매 컷마다 외형 전문 반복 작성 지시). |
| eval.py | plain text 생성 직후 | plot_evaluator.py | M1~M6 채점 지시. Model Grader calibration하면서 자주 수정됨. |
| advisor.py | 점수 낮거나 유저 피드백 시 | plot_advisor.py | 유저에게 보여줄 가이드라인 생성 지시. |
| templates.py | 3회 연속 미달 시 | cli.py + plot_advisor.py | 장르별 예시 입력 (kpop/anime/game 각 1개). |

**왜 services/ 안에 문자열로 안 넣는가:**
프롬프트는 코드보다 훨씬 자주 바뀜. 200줄짜리 프롬프트가 로직 코드 사이에 있으면 찾기도 힘들고, 프롬프트 수정하다 코드를 실수로 건드릴 수 있음.

---

### 루트 파일들

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| main.py | FastAPI 앱 생성, CORS 미들웨어 추가, 라우터 등록 (plot, image, video) | 앱의 시작점. uvicorn이 이 파일을 실행함. |
| .env | API 키 원본 저장 (ANTHROPIC_API_KEY, FAL_KEY, HF_API_TOKEN 등) | 키를 코드에 직접 쓰면 Git에 올라감 → 보안 사고. |
| .gitignore | Git에 올리지 않을 파일 목록 | .env, __pycache__, *.sqlite3 등 제외. |
| requirements.txt | 의존성 패키지 목록 | pip install -r requirements.txt로 환경 세팅. |
| README.md | 실행 방법, 환경변수 템플릿 | 팀원이 프로젝트 받고 바로 시작 가능. |

---

## 데이터 흐름 요약

```
[프론트엔드/CLI] — 가이드 질문 6개 답변 → 요약 confirm
    │
    ▼
api/plot.py POST /generate           "요청 받음"
    │
    ├─ services/character_sheet.py    "캐릭터 시트 + GlobalContext 생성"
    │    extract_global_context(answers, scenes)
    │    → GlobalContext { main_character, art_style, era, color_palette }
    │    → DB Project.global_context_json 저장
    │
    └─ services/plot_generator.py     ← prompts/system.py
       (claude_client.py 사용)         "Claude야, 스토리보드 만들어"
    │
    ▼
api/plot.py POST /evaluate
    │
    └─ services/plot_evaluator.py     ← prompts/eval.py
       (claude_client.py 사용)         "이거 몇 점이야?"
    │
    ├─ 5점 이상 → [Human Eval 진입] (failure_count 리셋, current_stage = "evaluated")
    │
    └─ 5점 미만 → api/plot.py POST /advice
                      │
                      └─ services/plot_advisor.py  ← prompts/advisor.py
                              generate_advice(plain_text, eval_result)
                      │
                      ▼
                  [점수 + 가이드라인 → 프론트 응답]
                      │
                      ├─ 3회 연속 미달: 장르별 템플릿 예시 제시
                      ├─ 5회 연속 미달: 계속 진행 여부 확인
                      └─ 7회 연속 미달: 중단
                      │
                      ▼
                  [유저 수정사항 입력]
                      │
                      └─ api/plot.py POST /modify → plot_generator → POST /evaluate → 루프
    │
    ▼
[유저 Human Eval] — 5점 이상 통과한 결과물
    │
    ├─ 만족 → 셀프 체크리스트 3개 모두 체크
    │         │
    │         ▼
    │    api/plot.py POST /human-eval   (H1/H2/H3 체크 결과 전송)
    │         │  human_eval_json DB 저장
    │         │  H1~H3 모두 통과 → current_stage = "human_eval_passed"
    │         │
    │         ▼
    │    api/plot.py POST /confirm
    │         │  services/plot_converter.py
    │         │  "plain text → JSON 변환"
    │         │  schemas/scene.py 검증
    │         │  DB 저장 → 이미지 생성 파이프라인으로
    │
    └─ 불만족 → 피드백 funnel (schemas/feedback.py)
                  → plot_advisor → 유저 수정 → 루프
    │
    ▼
api/image.py POST /generate-all      "전체 컷 이미지 생성"
    │
    ├─ services/character_sheet.py
    │    compose_cut_prompt(global_ctx, scene) → 각 컷별 프롬프트
    │    (GlobalContext의 캐릭터 시트가 모든 컷에 동일 삽입)
    │
    └─ services/image.py
         generate_image_from_hf(prompt) → FLUX.1-schnell → image bytes
         upload_to_cloudinary(bytes) → image_url
         DB Scene.draft_image_url 저장
    │
    ▼
[유저 이미지 확인]
    │
    ├─ 만족 → 영상 생성으로
    │
    └─ 수정 요청 → api/image.py POST /modify-by-text
                      │
                      ├─ scenes_to_plain_text() → generate_plot(prev + mod)
                      ├─ parse_storyboard() → new_scenes
                      ├─ diff_scenes(old, new) → changed_cuts
                      ├─ focused_eval(changed_cuts)
                      │    C2/C5 + M1~M4 (변경컷 + 인접 ±1)
                      ├─ 통과 → 변경 컷만 이미지 재생성
                      └─ 미통과 → eval_result + failed_items 반환
    │
    ▼
api/video.py POST /generate-all       "전체 컷 영상 생성"
    │
    └─ services/video.py
         generate_video_from_fal(prompt, image_url)
         → Fal.ai Kling Video → 폴링(5초×60회) → video_url
         DB Scene.clip_video_url 저장
    │
    ▼
[FFmpeg 합치기] (미구현)
    cut_1.mp4 + cut_2.mp4 + ... → final.mp4
```

---

## 관련 문서

| 문서 | 내용 |
|------|------|
| `implementation_spec.md` | Phase별 구현 설계, API 엔드포인트, 데이터 스키마 |
| `image.md` | 이미지 생성 파이프라인 상세 |
| `video-generate.md` | 영상 생성 파이프라인 상세 |
| `prompt_eval_criteria.md` | 평가 기준 상세 |
| `error_handling.md` | 에러 처리 전략 |
