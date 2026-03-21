# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 2차 창작 영상 제작 서비스 — a backend service for generating AI fan-content video storyboards from text prompts (K-pop, anime, game genres). ESTAID Hackathon 2026 project, MVP deadline 2026-03-23.

## Tech Stack

- **Backend:** Python 3.9+ / FastAPI
- **AI:** Anthropic Claude API (Sonnet for generation/eval, Haiku for safety pre-checks)
- **Image:** Hugging Face FLUX.1-schnell (character consistency via Character Sheet + GlobalContext injection)
- **Video:** Fal.ai Kling Video (image-to-video)
- **Validation:** Pydantic v2 + pydantic-settings
- **Storage:** Cloudinary (image upload), SQLite (DB)
- **Deployment:** Railway (backend), Vercel (frontend)

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt

# Run (FastAPI)
uvicorn backend.app.main:app --reload

# Run (CLI — legacy)
python cli.py
```

No test framework or linter is configured yet. `.env` file with `ANTHROPIC_API_KEY`, `HUGGINGFACE_API_KEY`, `FAL_KEY` is required.

## Architecture

### Pipeline Flow

```
유저 입력 → GlobalContext(캐릭터 시트) 생성 → 스토리보드 생성
  ↔ plot_evaluator.full_eval() (C1-C3/C5 + M1-M6) 루프
  → score ≥ 5.0 → Human Eval (H1-H3) → confirm
  → plot_converter.parse_storyboard() → JSON(Scene 12필드) DB 저장
  → compose_cut_prompt(GlobalContext + Scene) → FLUX.1-schnell 이미지 생성
  → 수정 시 diff_scenes() → focused_eval(C2/C5 + M1-M4) → 변경 컷만 재생성
  → Fal.ai Kling 영상 생성
```

### Key Design Principle

**Prompts are separated from code.** `backend/app/prompts/` contains prompt text files that change frequently during calibration. `backend/app/services/` contains stable business logic. This separation is intentional — do not inline prompts into service code.

### Backend Structure

```
backend/app/
├── main.py              — FastAPI 앱, CORS, 라우터 등록
├── api/                 — HTTP 엔드포인트 (11개)
│   ├── plot.py             5개: generate, evaluate, advice, modify, confirm
│   ├── image.py            4개: 단건, 수정, generate-all, modify-by-text
│   └── video.py            2개: 단건, generate-all
├── core/config.py       — Pydantic settings (API keys, model config)
├── db/
│   ├── database.py         SQLite 세션 관리
│   └── models.py           Project, Scene ORM
├── schemas/
│   ├── project.py          PlotRequest, PlotGenerateResponse, PlotEvalResponse 등
│   ├── scene.py            Scene (12필드) + GlobalContext
│   ├── image.py            ImageGenerateAllRequest, ImageModifyByTextRequest
│   ├── video.py            VideoGenerateRequest, VideoGenerateAllRequest
│   └── feedback.py         Feedback (type, detail, target_cuts, free_text)
├── services/
│   ├── claude_client.py    SDK wrapper (caching + retry)
│   ├── plot_generator.py   generate_plot()
│   ├── plot_evaluator.py   full_eval() + focused_eval()
│   ├── plot_advisor.py     generate_advice()
│   ├── plot_converter.py   parse_storyboard(), scenes_to_plain_text(), diff_scenes()
│   ├── character_sheet.py  캐릭터 시트, GlobalContext, compose_cut_prompt()
│   ├── image.py            FLUX.1-schnell + Cloudinary
│   └── video.py            Fal.ai Kling Video
└── prompts/
    ├── system.py           생성 프롬프트 (캐릭터 일관성 강화)
    ├── eval.py             M1~M6 채점 프롬프트
    ├── advisor.py          가이드라인 생성 프롬프트
    └── templates.py        장르별 예시 (kpop/anime/game)
```

### Character Consistency — GlobalContext

캐릭터 일관성의 핵심 메커니즘:
1. `generate_character_sheet()`: Claude 1회 호출 → 상세 캐릭터 외형 묘사 (영어, 100~200단어)
2. `extract_global_context()`: 캐릭터 시트 + art_style(장르 추론) + color_palette(분위기 추론) → GlobalContext
3. `compose_cut_prompt(global_ctx, scene)`: GlobalContext(고정) + Scene(가변) → FLUX 프롬프트
   - **global_ctx.main_character**(캐릭터 시트)가 모든 컷에 동일하게 삽입됨

### Image Modification — diff + focused_eval

이미지 수정 시 전체 재생성 대신 변경 컷만 재생성:
1. `diff_scenes(old, new)`: 9개 필드 비교 → changed_cuts
2. `focused_eval(changed_cuts)`: C2/C5 + M1~M4 (변경컷 + 인접 ±1)
3. 통과 → 변경 컷만 이미지 재생성, 미변경 컷은 기존 URL 보존

### Model Configuration

- Default model: `claude-sonnet-4-20250514`
- Safety pre-check: `claude-haiku-4-5-20251001` (C5 criterion — cheaper than Sonnet)
- Max output tokens: 4,096 / Context window check: 100,000 / Extended thinking: 10,000
- Structured Outputs: `client.messages.create() + tool_choice` (NOT `messages.parse()`)

### Cost Optimization

- Prompt caching: system prompt + rubric use `cache_control: {"type": "ephemeral"}` (90% savings on cache reads)
- Model routing: Haiku for safety checks, Sonnet for generation/evaluation
- diff + focused_eval: 이미지 수정 시 변경 컷만 재생성 (API 호출 2~3회 vs 전체 7~13회)
- Stay under 200K token threshold (input cost doubles above it)

### Evaluation — Code Grader + Model Grader

- Code Grader: C1(구조), C2(필수필드+placeholder), C3(컷수 5~10), C5(안전성/Haiku)
  - C4는 C2에 통합됨
- Model Grader: M1~M6 (Structured Outputs로 JSON 보장)
- Focused Eval: C2/C5 + M1~M4 (M5/M6 제외) — 이미지 수정 후 부분 평가 전용

### Infinite Loop Prevention

3 consecutive failures → offer template inputs. 5 consecutive → option to proceed with warning. 7 consecutive → abort with guidance.

## Spec Documents

Read these before writing code (all in `plot-generation_docements/`):
- `implementation_spec.md` — Phase 1~7 구현 설계, API 엔드포인트, 데이터 스키마
- `folder_structure_guide.md` — 폴더별 역할, 데이터 흐름 다이어그램
- `prompt_eval_criteria.md` — 평가 기준 (C1-C3/C5, M1-M6, H1-H3), Focused Eval, Score UI
- `error_handling.md` — Phase별 에러 전략, Fallback, FastAPI 응답 매핑
- `image.md` — 이미지 파이프라인 (캐릭터 시트, GlobalContext, diff 기반 재생성)
- `video-generate.md` — 영상 파이프라인 (Fal.ai Kling API, 폴링, 에러 처리)

## File Path Warning

**프로젝트 경로에 한글(김진식)이 포함되어 있다.** macOS는 한글을 NFD(자모 분해)로 저장하는데, 도구가 NFC(조합형)로 경로를 전달하면 동일 이름의 복제 폴더가 생성된다. 파일 생성/수정 시 반드시 Bash 도구로 `"$(pwd)/relative/path"` 패턴을 사용할 것. Write/Edit 도구에 한글이 포함된 절대경로를 직접 입력하지 말 것.

## Conventions

- All backend code under `backend/app/`
- All imports use `backend.app.*` prefix
- Pydantic v2 for all data validation (`model_config = {...}`, not `class Config:`)
- Scene schema has 12 fields: cut_number, main_character, sub_character (optional), action, pose, background, era, composition, lighting, mood, story_beat, duration_seconds
- GlobalContext: main_character(캐릭터 시트), sub_character, art_style, era, color_palette
- Storyboard output uses `[Cut N]` pattern for parser compatibility
- Korean language may appear in user-facing strings and documentation
