# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 2차 창작 영상 제작 서비스 — a backend service for generating AI fan-content video storyboards from text prompts (K-pop, anime, game genres). ESTAID Hackathon 2026 project, MVP deadline 2026-03-23.

## Tech Stack

- **Backend:** Python 3.9+ / FastAPI
- **AI:** Anthropic Claude API (Sonnet for generation/eval, Haiku for safety pre-checks)
- **Image/Video (planned):** Google Gemini Nano Banana 2 (image gen), Veo 2 (image→video)
- **Validation:** Pydantic v2 + pydantic-settings
- **Video Processing (planned):** MoviePy, Cloudinary SDK
- **Deployment:** Railway (backend), Vercel (frontend)

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt

# Run (CLI MVP)
python cli.py

# Run (FastAPI - future)
uvicorn backend.app.main:app --reload
```

No test framework or linter is configured yet. `.env` file with `ANTHROPIC_API_KEY` is required.

## Architecture

### Pipeline Flow

User text input → **plot_generator** (Claude generates [Cut N] storyboard) → **plot_evaluator** (Code Grader C1-C5 + Model Grader M1-M6) → score < 5.0 triggers **plot_advisor** (improvement guidance) → loop back to generator. Score ≥ 8.0 → **human evaluation** (H1-H3) → **plot_converter** (plain text → JSON) → image/video generation pipeline.

### Key Design Principle

**Prompts are separated from code.** `backend/app/prompts/` contains prompt text files that change frequently during calibration. `backend/app/services/` contains stable business logic. This separation is intentional — do not inline prompts into service code.

### Backend Structure

- `backend/app/core/config.py` — Pydantic settings (API keys, model config, token limits)
- `backend/app/services/` — Business logic: `claude_client.py` (SDK wrapper w/ caching + retry), `plot_generator.py`, `plot_evaluator.py`, `plot_advisor.py`, `plot_converter.py`
- `backend/app/prompts/` — `system.py`, `eval.py`, `advisor.py`, `templates.py` (genre-specific examples)
- `backend/app/schemas/` — Pydantic models: `project.py`, `scene.py` (11 fields per cut), `feedback.py`

### Model Configuration

- Default model: `claude-sonnet-4-20250514`
- Safety pre-check: `claude-haiku-4-5-20251001` (C5 criterion — cheaper than Sonnet)
- Max output tokens: 4,096 / Context window check: 100,000 / Extended thinking: 10,000

### Cost Optimization

- Prompt caching: system prompt + rubric use `cache_control: {"type": "ephemeral"}` (90% savings on cache reads)
- Model routing: Haiku for safety checks, Sonnet for generation/evaluation
- Stay under 200K token threshold (input cost doubles above it)

### Infinite Loop Prevention

3 consecutive failures → offer template inputs. 5 consecutive → option to proceed with warning. Persistent → abort with guidance.

## Spec Documents

Read these before writing code:
- `implementation_spec.md` — Phase breakdown, file interfaces, prompt design, data schemas
- `folder_structure_guide.md` — Per-folder purpose and data flow rationale
- `prompt_eval_criteria.md` — All grading criteria (C1-C5, M1-M6, H1-H3), score thresholds, UI specs
- `error_handling.md` — Error strategies by phase, fallback mechanisms

## File Path Warning

**프로젝트 경로에 한글(김진식)이 포함되어 있다.** macOS는 한글을 NFD(자모 분해)로 저장하는데, 도구가 NFC(조합형)로 경로를 전달하면 동일 이름의 복제 폴더가 생성된다. 파일 생성/수정 시 반드시 Bash 도구로 `"$(pwd)/relative/path"` 패턴을 사용할 것. Write/Edit 도구에 한글이 포함된 절대경로를 직접 입력하지 말 것.

## Conventions

- All backend code under `backend/app/`
- Pydantic for all data validation and serialization
- Scene schema has 11 required fields: character, action, pose, background, era, composition, lighting, mood, story_beat, duration_seconds, cut_number
- Storyboard output uses `[Cut N]` pattern for parser compatibility
- Korean language may appear in user-facing strings and documentation
