# Video Generation — Implementation Spec
> 컷별 이미지 → 영상 변환 설계서

---

## 1. 목표

이미지 생성이 완료된 컷별 이미지를 영상 클립으로 변환한다.
현재는 Fal.ai Kling Video를 사용하며, 최종 목표는 Veo 2 전환이다.

---

## 2. 파이프라인

```
/api/image/generate-all (또는 modify-by-text) 완료
    │  각 Scene에 draft_image_url + generated_image_prompt 저장됨
    ▼
/api/video (단건) 또는 /api/video/generate-all (일괄)
    │
    ├─ Step 1: DB에서 Scene 로드
    │    - draft_image_url (이미지 URL — 첫 프레임 고정)
    │    - generated_image_prompt (동작 프롬프트)
    │
    ├─ Step 2: Fal.ai Kling API 호출
    │    POST https://queue.fal.run/fal-ai/kling-video/v1/standard/image-to-video
    │    {
    │      "prompt": generated_image_prompt,
    │      "image_url": draft_image_url
    │    }
    │
    ├─ Step 3: 비동기 폴링 (5초 간격, 최대 5분)
    │    GET status_url → COMPLETED / FAILED / IN_QUEUE
    │    COMPLETED → GET response_url → video.url
    │
    ├─ Step 4: DB 업데이트
    │    Scene.clip_video_url = video_url
    │    Scene.veo2_prompt = generated_image_prompt
    │    Scene.video_status = "done"
    │
    └─ 응답: { scene_id, video_url, video_status }
```

---

## 3. API 엔드포인트

### POST /api/video — 단건 영상 생성

| 필드 | 타입 | 설명 |
|------|------|------|
| scene_id | string | 대상 Scene ID |

**전제 조건:**
- Scene에 `draft_image_url`과 `generated_image_prompt`가 존재해야 함
- 이미지 미생성 시 400 에러

**응답:**
```json
{
  "scene_id": "abc123",
  "video_url": "https://fal.ai/...",
  "video_status": "done"
}
```

### POST /api/video/generate-all — 전체 영상 일괄 생성

| 필드 | 타입 | 설명 |
|------|------|------|
| project_id | string | 대상 프로젝트 ID |

**동작:**
- 프로젝트의 모든 Scene을 scene_number 순으로 순회
- 이미지가 없는 Scene은 `skipped`로 표시
- 개별 실패 시 해당 Scene만 `failed`, 나머지 계속 진행
- 완료 후 `Project.current_stage = "videos_generated"`

**응답:**
```json
{
  "project_id": "xyz789",
  "videos": [
    { "scene_id": "a1", "cut_number": 1, "video_url": "https://...", "video_status": "done" },
    { "scene_id": "a2", "cut_number": 2, "video_status": "skipped", "reason": "이미지 미생성" },
    { "scene_id": "a3", "cut_number": 3, "video_status": "failed", "error": "Fal API timeout" }
  ]
}
```

---

## 4. 구현 파일

| 파일 | 역할 |
|------|------|
| `schemas/video.py` — `VideoGenerateRequest` | { scene_id } |
| `schemas/video.py` — `VideoGenerateAllRequest` | { project_id } |
| `services/video.py` — `generate_video_from_fal()` | Fal.ai Kling API 호출 + 폴링 + URL 반환 |
| `api/video.py` — `POST /` | 단건 영상 생성 |
| `api/video.py` — `POST /generate-all` | 전체 영상 일괄 생성 |

---

## 5. Fal.ai Kling Video API 상세

### 요청

```
POST https://queue.fal.run/fal-ai/kling-video/v1/standard/image-to-video
Headers:
  Authorization: Key {FAL_KEY}
  Content-Type: application/json
Body:
  { "prompt": "...", "image_url": "..." }
```

### 응답 (큐 등록)

```json
{
  "status_url": "https://queue.fal.run/.../status",
  "response_url": "https://queue.fal.run/.../response"
}
```

### 폴링 (status_url)

| status | 의미 | 처리 |
|--------|------|------|
| IN_QUEUE | 대기 중 | 5초 후 재확인 |
| COMPLETED | 완료 | response_url에서 결과 가져오기 |
| FAILED | 실패 | fallback URL 반환 |

### 결과 (response_url)

```json
{
  "video": {
    "url": "https://fal.ai/generated/..."
  }
}
```

### 폴링 설정

| 설정 | 값 |
|------|------|
| 폴링 간격 | 5초 |
| 최대 대기 | 300초 (60회 × 5초) |
| 타임아웃 시 | fallback URL 반환 |

---

## 6. 에러 처리

> `VideoGenerationError` — `services/video.py`에 정의된 전용 예외 클래스. 모든 실패 경로에서 이 예외를 raise하며, fallback URL 반환 방식은 사용하지 않는다.

| 에러 | 처리 |
|------|------|
| FAL_KEY 미설정 | `VideoGenerationError` raise → 단건 500 / 일괄 해당 Scene `failed` |
| Fal API 제출 실패 (비200) | `VideoGenerationError` raise → 단건 500 / 일괄 해당 Scene `failed` |
| 폴링 중 FAILED | `VideoGenerationError` raise → 단건 500 / 일괄 해당 Scene `failed` |
| 5분 초과 타임아웃 | `VideoGenerationError` raise → 단건 500 / 일괄 해당 Scene `failed` |
| 네트워크/시스템 에러 | `VideoGenerationError` wrap → 단건 500 / 일괄 해당 Scene `failed` |
| Scene에 이미지 없음 | 단건: 400 에러 / 일괄: skipped 처리 |
| Project 미존재 | 404 에러 |
| Scene 없음 | 400 에러 |

### 일괄 생성 시 에러 격리

`generate-all`에서 개별 Scene 실패가 전체를 중단하지 않는다:
- 이미지 미생성 Scene → `skipped`
- `VideoGenerationError` 발생 Scene → `video_status = "failed"` DB 저장 후 계속
- 성공 Scene → `video_status = "done"`
- 모든 Scene 처리 후 일괄 commit

---

## 7. DB 스키마 (Scene 테이블 관련 컬럼)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| draft_image_url | String | 이미지 생성 후 저장된 URL (영상 생성의 입력) |
| generated_image_prompt | Text | compose_cut_prompt() 결과 (동작 프롬프트로 재사용) |
| clip_video_url | String | 생성된 영상 URL |
| veo2_prompt | Text | 영상 생성에 사용된 프롬프트 |
| video_status | String | done / skipped / failed |

---

## 8. 현재 상태 및 향후 계획

### 현재 (해커톤 MVP)
- **엔진:** Fal.ai Kling Video (image-to-video)
- **방식:** 동기 폴링 (서버 대기)
- **비용:** Fal.ai 유료 API 키 필요
- **품질:** 1~2분 소요, 표준 화질

### 향후 전환 목표
- **엔진:** Google Veo 2
- **방식:** 비동기 처리 (웹훅 또는 큐)
- **개선 사항:**
  - 더 높은 영상 품질
  - 더 긴 클립 길이 지원
  - 카메라 무브먼트 프롬프트 지원

### FFmpeg 병합 (미구현)
- 모든 컷 영상 생성 완료 후 `cut_1.mp4 + cut_2.mp4 + ... → final.mp4`
- MoviePy 또는 FFmpeg CLI 활용 예정
- 컷 간 트랜지션 (fade, dissolve) 추가 가능
