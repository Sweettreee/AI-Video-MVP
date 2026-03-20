# Backend 폴더 구조 — 역할 및 필요성 설명

## 전체 구조 (plot generation 집중 버전)

```
backend/
├── app/
│   ├── api/           # 프론트엔드가 호출하는 문(입구)
│   ├── core/          # 앱 전체 설정
│   ├── db/            # 데이터 저장소
│   ├── schemas/       # 데이터 형태 검증
│   ├── services/      # 실제 일을 하는 곳
│   ├── prompts/       # Claude에게 보내는 지시서 모음
│   ├── utils/         # 공통 도구
│   └── main.py        # 앱 시작점
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
| plot.py | POST /api/plot 라우터 | 유저 입력을 받아서 services/에 전달하고, 결과를 프론트에 돌려주는 중간 다리. 여기에 비즈니스 로직을 넣으면 라우터가 뚱뚱해져서 나중에 엔드포인트 추가할 때 복잡해짐. |

> Phase 5에서 character_sheet.py(캐릭터 시트 생성), image.py(FLUX.1-schnell 컷 이미지 생성), video.py(Veo 2 영상 변환), merge.py(FFmpeg 합치기) 추가 예정.

---

### core/ — "앱 전체 설정 금고"

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| config.py | .env에서 API 키를 읽어와서 앱 전체에서 쓸 수 있는 settings 객체로 만듦 | .env는 텍스트 파일일 뿐이라 오타 검증이 안 됨. config.py가 앱 시작 시 "ANTHROPIC_API_KEY가 없네?" 하고 즉시 에러를 던져줘서, 배포 후 삽질을 막아줌. |

---

### db/ — "데이터 저장소"

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| database.py | SQLite 연결 및 세션 관리 | DB 연결 코드가 services/ 여기저기에 흩어지면, 나중에 DB를 바꾸거나 연결 설정을 고칠 때 모든 파일을 다 수정해야 함. 한 곳에서 관리하면 여기만 고치면 됨. |
| models.py | projects, scenes 테이블 정의 | 테이블 구조를 코드로 정의해두면, DB 스키마가 뭔지 파일 하나만 보면 바로 알 수 있음. SQL 직접 치는 것보다 실수가 줄어듦. |

---

### schemas/ — "데이터 형태 검증관"

API로 들어오고 나가는 데이터의 형태(타입, 필수값 등)를 검증하는 곳.
Pydantic 모델을 정의한다.

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| project.py | /api/plot 요청(answers dict: genre, character, mood, story, must_have, extra) 및 응답(project_id) 스키마 | 가이드 질문 답변의 필수/선택 필드를 자동 검증. services/ 코드에서 일일이 if문으로 체크 안 해도 됨. |
| scene.py | confirm 후 JSON 변환 결과의 스키마 (main_character, action, pose 등 11개 필드) | plain text → JSON 변환 후 필수 필드가 다 있는지 자동 검증. 빠진 필드가 있으면 Hugging Face 이미지 생성 파이프라인에 넘기기 전에 잡아냄. |
| feedback.py | 유저 피드백 구조 (type, detail, target_cuts, free_text) | 피드백 funnel에서 수집한 데이터의 형태를 고정. 프론트엔드가 이상한 형태로 보내면 여기서 걸러짐. |

---

### services/ — "실제 일을 하는 곳" (가장 중요)

비즈니스 로직이 사는 곳. Claude API 호출, 평가, 가이드 등 핵심 작업이 여기서 일어난다.

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| claude_client.py | Anthropic client 생성 + call_claude() / call_claude_structured() / count_tokens() 공통 함수. SDK 내장 재시도(max_retries), 프롬프트 캐싱(cache_control), 토큰 카운팅 포함 | Claude 호출 코드를 한 곳에만 정의. 모델 변경, retry, 캐싱 설정을 여기만 고치면 전체 반영. generator/evaluator/advisor가 모두 이 함수를 가져다 씀. |
| plot_generator.py | `generate_plot(answers, previous_storyboard, modification_request)` → plain text 스토리보드 생성. 첫 생성 시 answers dict 기반, 수정 시 previous_storyboard + modification_request로 변경 부분만 반영. 시스템 프롬프트 캐싱(cache_system=True)으로 수정 시 비용 절감. | 가이드 질문 답변 + system prompt를 조합해서 Claude에게 보내고 결과를 받는 로직. |
| plot_evaluator.py | `full_eval()` (C1~C3/C5 + M1~M6 전체 평가) + `focused_eval()` (이미지 수정 후 부분 평가: 변경컷+인접컷, C2/C5 + M1~M4). C4는 C2에 통합됨. C5 사전 검수는 Haiku. Focused Eval 실패 시 full_eval 폴백. Model Grader API 실패 시 Code fallback. | 이중 평가 구조: 최초 생성은 전체 평가, 이미지 수정 후는 부분 평가로 비용·시간 절감. Structured Outputs로 JSON 파싱 실패 원천 제거. (extended thinking은 forced tool_choice와 호환 불가로 미사용) |
| plot_advisor.py | `generate_advice(plain_text, eval_result, previous_advice=None)` — failed_items 기반 개선 가이드라인 생성. previous_advice 있으면 다른 방향 조언 요청. API 실패 시 static fallback 문자열 반환 (루프 중단 방지). Phase 4에서 feedback dict 기반 Human Eval 불만족 가이드도 여기서 처리 예정. | Claude는 코치이지 작가가 아님. 유저가 직접 수정할 수 있도록 가이드. |
| plot_converter.py | `scenes_to_plain_text()` (JSON→plain text 역변환, 이미지 수정 시 사용) + `parse_storyboard()` (plain text→JSON 파싱). full_eval/focused_eval 통과 후 동일하게 호출. 파싱 에러 시 구체적 위치 안내, 타입 불일치 시 캐스팅+경고, 파일 저장 실패 시 터미널 출력 fallback | 양방향 변환: JSON↔plain text. Hugging Face 이미지 생성 파이프라인에 넘길 구조화 데이터 생성 + 이미지 수정 시 Claude에게 넘길 plain text 복원. |

**왜 5개로 나눴는가:**
하나의 claude.py에 다 넣으면, 생성→평가→가이드→변환이 한 파일 안에서 서로 얽힘.
분리하면 각 단계를 독립적으로 테스트/수정할 수 있고, 팀원이 다른 파일 작업할 때 충돌이 안 남.

```
claude_client.py  → "Claude한테 전화 거는 방법" (공통)
plot_generator.py → "만들어"
plot_evaluator.py → "채점해"
plot_advisor.py   → "유저한테 뭘 고치면 좋을지 알려줘"
plot_converter.py → "JSON으로 바꿔"
```

**plot_rewriter.py가 아니라 plot_advisor.py인 이유:**
rewriter는 Claude가 자동으로 고치는 구조.
advisor는 유저에게 가이드라인을 제공해서 유저가 직접 고치도록 유도하는 구조.
우리 서비스는 후자 — Claude는 코치이지 작가가 아님.

---

### prompts/ — "Claude에게 보내는 지시서 모음"

Claude API에 보내는 프롬프트 텍스트를 코드와 분리해서 관리하는 곳.

| 파일 | 언제 쓰이는가 | 누가 가져다 쓰는가 | 왜 분리했는가 |
|------|-------------|-------------------|-------------|
| system.py | 유저가 가이드 질문 답변 완료 후 | plot_generator.py | 역할 지시 + 유저 답변 기반 `<user_context>` 동적 생성 + 출력 포맷. 장르 프리셋(GENRE_RULES) 삭제됨 — 유저가 직접 입력한 장르/분위기를 기반으로 Claude가 자유 구성. |
| eval.py | plain text 생성 직후 | plot_evaluator.py | M1~M6 채점 지시. Model Grader calibration하면서 자주 수정됨. |
| advisor.py | 점수 낮거나 유저 피드백 시 | plot_advisor.py | 유저에게 보여줄 가이드라인 생성 지시. "어디가 부족하고 어떻게 고치면 되는지"를 안내하는 프롬프트. |
| templates.py | 3회 연속 미달 시 | cli.py + plot_advisor.py | 장르별 예시 입력 (kpop/anime/game 각 1개). 유저가 참고하거나 수정해서 쓸 수 있는 기준점. Code Eval 통과 수준으로 작성. |

**왜 services/ 안에 문자열로 안 넣는가:**
프롬프트는 코드보다 훨씬 자주 바뀜. 200줄짜리 프롬프트가 로직 코드 사이에 있으면 찾기도 힘들고, 프롬프트 수정하다 코드를 실수로 건드릴 수 있음. 파일로 분리하면 프롬프트만 열어서 고치고 바로 테스트 가능.

---

### utils/ — "공통 도구함"

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| prompt.py | `compose_cut_prompt(global_ctx, scene)` — GlobalContext(캐릭터 시트+스타일) + Scene(컷별 필드)를 FLUX.1-schnell 텍스트 프롬프트로 조립 | 캐릭터 시트가 모든 컷에 문자열 수준으로 동일하게 삽입됨 → 텍스트 기반 일관성 확보 |

---

### 루트 파일들

| 파일 | 역할 | 왜 필요한가 |
|------|------|------------|
| main.py | FastAPI 앱 생성, CORS 미들웨어 추가, 라우터 등록 | 앱의 시작점. uvicorn이 이 파일을 실행함. |
| .env | API 키 원본 저장 | 키를 코드에 직접 쓰면 Git에 올라감 → 보안 사고. .env에 넣고 .gitignore로 제외. |
| .gitignore | Git에 올리지 않을 파일 목록 | .env, __pycache__, *.sqlite3 등이 실수로 커밋되는 걸 방지. |
| requirements.txt | 의존성 패키지 목록 | 팀원이나 Railway가 pip install -r requirements.txt 한 줄로 환경 세팅 가능. |
| README.md | 실행 방법, 환경변수 템플릿 | 팀원이 프로젝트 받고 "이거 어떻게 돌려?" 안 물어봐도 되게. |

---

## 데이터 흐름 요약

```
[프론트엔드/CLI] — 가이드 질문 6개 답변 (장르, 캐릭터, 분위기, 줄거리, 필수 장면, 추가 요청) → 요약 confirm
    │
    ▼
api/plot.py                        "요청 받음"
    │
    ▼
services/plot_generator.py         ← prompts/system.py
    │  (claude_client.py 사용)        "Claude야, 스토리보드 만들어"
    │
    ▼
services/plot_evaluator.py         ← prompts/eval.py
    │  (claude_client.py 사용)        "이거 몇 점이야?"
    │
    ├─ 5점 이상 → [Human Eval 진입] (Phase 4)
    │
    └─ 5점 미만 → services/plot_advisor.py  ← prompts/advisor.py
                      │  generate_advice(plain_text, eval_result)
                      │
                      ▼
                  [점수 + 가이드라인 출력]
                      │  "총점 3.2 / 10"
                      │  "M1, M3 기준 미달 — 배경/조명을 더 구체적으로..."
                      │
                      ├─ 3회 연속 미달: 장르별 템플릿 예시 제시 (prompts/templates.py)
                      ├─ 5회 연속 미달: 계속 진행 여부 확인
                      └─ 7회 연속 미달: 중단
                      │
                      ▼
                  [유저 수정사항 입력]
                      │
                      ▼
                  plot_generator.py(previous_storyboard + modification_request)
                      │  ← 항상 full_eval (plot-generation 루프 전체)
                      ▼
                  plot_evaluator.full_eval() → 재평가
                      │
                      └─→ 5점 이상이 될 때까지 루프

    ※ focused_eval은 이미지 생성 후 특정 컷 수정 시에만 사용 (Phase 5)
    │
    ▼
[유저 Human Eval] — 5점 이상 통과한 결과물
    │
    ├─ 만족 → 셀프 체크리스트 3개 모두 체크 → Confirm 클릭
    │         │
    │         ▼
    │    services/plot_converter.py
    │         │  "plain text → JSON 변환"
    │         ▼
    │    schemas/scene.py 검증
    │         │
    │         ▼
    │    DB 저장 → 이미지 생성 파이프라인
    │
    ▼
[캐릭터 시트 생성]  services/character_sheet.py
    │  answers['character'] + scenes[0].main_character
    │  → Claude 1회 호출 → 상세 캐릭터 시트 (헤어/의상/체형/피부/특징)
    │  → GlobalContext 생성 (캐릭터 시트 + art_style + color_palette)
    │
    ▼
[컷별 이미지 생성]  services/image.py
    │  compose_cut_prompt(global_ctx, scene) → FLUX.1-schnell → cut_N.png
    │  (global_ctx의 캐릭터/스타일이 모든 컷에 동일하게 삽입)
    │
    ▼
[컷별 영상 생성]  services/video.py
    │  cut_N.png (첫 프레임 고정) + 동작 프롬프트 → cut_N.mp4
    │  (Veo 2)
    │
    ▼
[FFmpeg 합치기]
    cut_1.mp4 + cut_2.mp4 + ... → final.mp4
    │
    └─ 불만족 → 피드백 funnel (schemas/feedback.py)
                  │  Step 1: 어디가 아쉬워?
                  │  Step 2: 구체적으로 뭐가?
                  │  Step 3: 어떤 컷?
                  │  Step 4: 자유 입력 (선택)
                  │
                  ▼
              services/plot_advisor.py → 피드백 기반 가이드라인 생성
                  │
                  ▼
              [유저가 수정 포인트만 입력] → plot_generator.py(previous_storyboard + modification) → 재생성 → 루프
```
