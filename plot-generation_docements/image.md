# Image Generation — Implementation Spec
> 스토리보드 confirm 후 컷별 이미지 생성 설계서

---

## 1. 목표

confirm된 스토리보드(list[Scene])를 기반으로 캐릭터 일관성이 보장된 컷별 이미지를 생성한다.

### 핵심 문제

이미지 모델(FLUX.1-schnell)은 컷별로 독립 생성하므로, 프롬프트가 조금만 달라져도 완전히 다른 인물이 나온다.

```
문제 시나리오:
  [Cut 1] 캐릭터: 분홍 한복을 입은 공주, 긴 흑발, 비녀   → 인물 A
  [Cut 2] 캐릭터: 공주                                     → 인물 B (다른 사람)
  [Cut 3] 캐릭터: 파란 한복의 공주                          → 인물 C (또 다른 사람)
```

### 해결 전략: 캐릭터 시트 + Global Context

```
해결 후:
  GlobalContext.main_character = "Young Korean princess, early 20s,
    long straight black hair reaching waist with golden binyeo hairpin..."

  [Cut 1] 프롬프트: [캐릭터 시트 전문] + is walking...     → 인물 A
  [Cut 2] 프롬프트: [캐릭터 시트 전문] + is sitting...     → 인물 A (동일)
  [Cut 3] 프롬프트: [캐릭터 시트 전문] + is running...     → 인물 A (동일)
```

---

## 2. 파이프라인

```
/api/plot/confirm
    │  plain text → list[Scene] → DB 저장
    ▼
/api/image/generate-all
    │
    ├─ Step 0: 캐릭터 시트 생성 (Claude 1회 호출)
    │    answers['character'] + scenes[0].main_character
    │    → Claude: 성별, 나이, 헤어, 의상, 체형, 피부, 액세서리, 특징
    │    → character_sheet (영어, 100~200 단어)
    │
    ├─ Step 1: GlobalContext 생성
    │    GlobalContext {
    │      main_character: character_sheet,
    │      sub_character: (있으면 동일 과정),
    │      art_style: 장르에서 추론 (규칙 기반),
    │      era: scenes[0].era,
    │      color_palette: 분위기에서 추론 (규칙 기반),
    │    }
    │
    ├─ Step 2: 컷별 이미지 생성 (N회)
    │    compose_cut_prompt(global_ctx, scene)
    │      → [art_style]. [character_sheet 전문]. is [action], [pose].
    │        Background: [background], set in [era].
    │        Shot composition: [composition]. Lighting: [lighting].
    │        Mood: [mood]. Color palette: [color_palette].
    │      → FLUX.1-schnell → image bytes
    │      → Cloudinary 업로드 → image_url
    │      → DB Scene.draft_image_url 저장
    │
    └─ 응답: { images: [{ cut_number, image_url, image_status }] }
```

---

## 3. 이미지 수정 — diff 기반 부분 재생성

```
/api/image/modify-by-text
    │
    ├─ 1. DB에서 기존 scenes + answers + GlobalContext 로드
    │
    ├─ 2. scenes_to_plain_text(old_scenes) → old_plain_text
    │     generate_plot(answers, previous_storyboard=old_plain, modification=유저 입력)
    │     → new_plain_text
    │
    ├─ 3. parse_storyboard(new_plain_text) → new_scenes
    │
    ├─ 4. diff_scenes(old_scenes, new_scenes) → changed_cuts
    │     비교 대상 9개 필드:
    │       main_character, sub_character, action, pose,
    │       background, era, composition, lighting, mood
    │     (story_beat, duration_seconds는 이미지에 무관하므로 제외)
    │
    ├─ 5. focused_eval(changed_cuts, new_plain_text)
    │     평가 기준: C2/C5 + M1~M4 (변경컷 + 인접 ±1컷)
    │     통과(≥ 5.0) → 6번으로
    │     미통과 → eval_result + failed_items 반환 (프론트에서 가이드 표시)
    │
    ├─ 6. 변경 컷만 이미지 재생성
    │     compose_cut_prompt(global_ctx, changed_scene) → FLUX → Cloudinary
    │     변경 안 된 컷은 기존 image_url 보존
    │
    └─ 응답: { changed_cuts, eval_passed, images: [...] }
```

### 비용 비교

| | 전체 재생성 | diff 기반 부분 재생성 |
|---|---|---|
| 스토리보드 | API 1회 | API 1회 (동일) |
| 평가 | Full Eval (API 1~2회) | Focused Eval (API 0~1회) |
| 이미지 | 5~10회 | 변경 컷만 1~2회 |
| **합계** | **7~13회** | **2~3회** |

---

## 4. 구현 파일

| 파일 | 역할 |
|------|------|
| `schemas/scene.py` — `GlobalContext` | main_character, sub_character, art_style, era, color_palette |
| `schemas/image.py` — `ImageGenerateAllRequest` | { project_id } |
| `schemas/image.py` — `ImageModifyByTextRequest` | { project_id, modification_request } |
| `services/character_sheet.py` — `generate_character_sheet()` | Claude 1회 호출 → 상세 캐릭터 시트 (영어) |
| `services/character_sheet.py` — `extract_global_context()` | 캐릭터 시트 + 화풍/색감 추론 → GlobalContext |
| `services/character_sheet.py` — `compose_cut_prompt()` | GlobalContext + Scene → 이미지 프롬프트 (캐릭터 시트 강제 삽입) |
| `services/image.py` — `generate_image_from_hf()` | FLUX.1-schnell Inference API 호출 |
| `services/image.py` — `upload_to_cloudinary()` | Cloudinary 업로드 → URL 반환 |
| `services/plot_converter.py` — `diff_scenes()` | old/new Scene 비교 → 변경 컷 번호 반환 |
| `api/image.py` — `/generate-all` | 프로젝트 전체 이미지 일괄 생성 |
| `api/image.py` — `/modify-by-text` | 텍스트 수정 → diff → focused_eval → 부분 재생성 |
| `db/models.py` — `Project.global_context_json` | GlobalContext JSON 저장 컬럼 |

---

## 5. 화풍/색감 추론 규칙

### art_style (장르 → 화풍)

| 장르 키워드 | art_style |
|---|---|
| kpop, k-pop, 아이돌, 뮤직비디오 | K-pop music video style, vibrant colors, high fashion, studio lighting |
| anime, 애니, 애니메이션 | anime cel-shading style, bold outlines, expressive features |
| game, 게임, 시네마틱 | cinematic game trailer style, photorealistic, dramatic lighting |
| 기타 | high quality, detailed, cinematic |

### color_palette (분위기 → 색감)

| 분위기 키워드 | color_palette |
|---|---|
| 슬프, melancholy | cool blue, muted tones, soft shadows |
| 감성 | warm golden, soft pastel, gentle gradients |
| 신나, energetic | bright saturated, neon accents, high contrast |
| 어두, dark | dark moody, deep shadows, desaturated |
| epic | cinematic warm-cool contrast, volumetric lighting |
| tense | high contrast, cold tones, sharp shadows |
| 기타 | natural balanced tones |

---

## 6. 캐릭터 시트 생성 프롬프트

시스템 프롬프트에서 요구하는 항목:
- Gender and age
- Hair: length, color, style, accessories
- Face: eye shape, eye color, nose, lips, skin tone
- Body: height impression, build
- Outfit: top (color, material, details), bottom, shoes
- Accessories: jewelry, weapons, props
- Distinctive features: scars, tattoos, markings

제약:
- 영어로 작성 (이미지 모델 호환)
- 100~200 단어 분량
- 모호한 표현 금지 ("예쁜", "멋진" → 구체적 묘사)
- 서브 캐릭터가 있으면 별도 문단 분리

---

## 7. 에러 처리

| 에러 | 처리 |
|---|---|
| GlobalContext 생성 실패 | 스토리보드는 반환, global_context_json = null |
| FLUX API 503 (웜업) | 5초 대기 후 최대 5회 재시도 |
| FLUX API 기타 에러 | 해당 컷 실패 처리, 나머지 컷 계속 진행 |
| Cloudinary 업로드 실패 | 2초 대기 후 최대 3회 재시도 |
| diff_scenes 후 변경 없음 | "변경된 컷이 없습니다" 반환 |
| focused_eval 미통과 | eval_result + failed_items 반환 (프론트에서 가이드 표시) |
| focused_eval 자체 에러 | full_eval로 폴백 |

---

## 8. 한계 및 향후 개선

### 현재 한계
- FLUX.1-schnell은 텍스트→이미지 전용 (IP-Adapter 미지원)
- 동일한 프롬프트를 넣어도 매번 다른 얼굴/체형이 생성될 수 있음
- 캐릭터 시트로 텍스트 수준 일관성은 확보하지만, 픽셀 수준 일관성은 보장 불가

### 향후 개선 방향
- 참조 이미지 기반 모델 (SDXL + IP-Adapter, 또는 Fal.ai 이미지 생성 API)
- 첫 컷 이미지를 reference로 사용하는 img2img 접근
