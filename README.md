# AI 2차 창작 영상 제작 서비스 — MVP 소프트웨어 설계서

**프로젝트명:** AI 2차 창작 영상 제작 서비스  
**해커톤:** ESTAID Hackathon 2026  
**MVP 마감:** 2026-03-23   

---

## 1. 프로젝트 개요

### 1-1. 서비스 정의

K-pop, 애니, 게임 팬 크리에이터가 짧은 텍스트 아이디어만으로 2차 창작 영상을 제작할 수 있는 AI 기반 영상 제작 플랫폼이다. 영상 편집 경험이 없는 유저도 AI가 생성한 컷씬을 직접 확인하고 수정하여 원하는 결과물을 만들 수 있도록 돕는다.

### 1-2. 핵심 워크플로우

```
유저 프롬프트 입력
       ↓
[1] POST /api/plot → project_id 즉시 반환
       ↓ (BackgroundTasks)
[2] Claude API → 컷씬 구조 JSON (5~10컷) 생성
       ↓ (BackgroundTasks)
[3] 백엔드 조합 로직 → Nano Banana 2 → 컷씬별 초안 이미지 (완료 순서대로 표시)
       ↓
[4] 유저 컷씬 편집 (scene_data 덮어쓰기, "이미지 새로고침" 시 Nano Banana 2 재호출)
       ↓
[5] 유저 최종 Confirm → task_id 즉시 반환
       ↓ (BackgroundTasks)
[6] Claude API → 컷씬별 Veo 2용 자연어 프롬프트 생성 (Unsafe Content 사전 차단)
       ↓ (BackgroundTasks)
[7] Veo 2 → 컷씬별 3~5초 클립 생성 → Cloudinary 업로드
       ↓ (BackgroundTasks, [7] 전체 완료 후)
[8] MoviePy → 클립 순서대로 병합 → 최종 MP4 (15~30초) → Cloudinary 업로드
       ↓
[9] 최종 영상 URL 프론트 표시
```

초안 이미지는 백엔드 조합 로직으로 생성하여 비용을 절감하고, 최종 영상 프롬프트는 Claude가 직접 작성하여 컷씬 이미지와 영상의 시각적 일관성을 보장한다. Nano Banana 2 재호출은 유저가 직접 "이미지 새로고침" 버튼을 누를 때만 발생하여 편집 중 불필요한 비용을 통제한다.

### 1-3. 팀 구성

| 역할 | 인원 | 주요 책임 |
|---|---|---|
| UI/UX | 0명 | 화면 설계 및 프론트엔드 구현 |
| 백엔드 | 2명 | AI API 연동, 데이터 파이프라인, 서버 전체 구현 |

---

## 2. Tech Stack

| 영역 | 기술 | 세부 도구 | 역할 |
|---|---|---|---|
| 프론트엔드 | React + Vite | Vercel (배포) | 컷씬 편집 UI, API 호출, 폴링 처리 |
| 백엔드 | Python + FastAPI | Railway (배포) | AI API 연동, 비동기 파이프라인 |
| 플롯 생성 AI | Anthropic Claude | claude-sonnet-4-20250514 | 프롬프트 → 구조화된 컷씬 JSON 생성 |
| 이미지 생성 AI | Google Gemini | Nano Banana 2 | 컷씬 → 장면 이미지 생성 |
| 영상 생성 AI | Google Gemini | Veo 2 | 이미지 → 영상 클립 생성 (image-to-video) |
| 영상 병합 | MoviePy | Python 라이브러리 | 컷씬별 3~5초 클립을 하나의 MP4로 병합 |
| 파일 저장 | Cloudinary | Python SDK | 이미지/영상 저장 및 공개 URL 제공 |
| 데이터베이스 | SQLite | Railway Volume | 프로젝트 및 컷씬 데이터 저장 |

**주의사항**
- 프론트엔드(Vercel)와 백엔드(Railway)의 도메인이 다르므로 FastAPI에 CORS 미들웨어를 최초 셋업 시 반드시 추가한다.
- Railway 서버 재시작 시 `/tmp` 폴더가 초기화된다. 생성된 이미지와 영상은 즉시 Cloudinary에 업로드해야 한다.

---

## 3. 전체 워크플로우

### 3-1. 단계별 흐름

| 단계 | 주체 | 처리 내용 | 결과물 |
|---|---|---|---|
| 1. 프롬프트 입력 | 유저 + 프론트엔드 | 유저가 텍스트 아이디어와 장르를 입력하고 생성 요청을 보낸다 | POST 요청 → 백엔드 호출 |
| 2. 컷씬 구조 생성 | 백엔드 + Claude API | Claude가 입력된 아이디어를 기반으로 컷씬 구조 JSON을 생성한다 | 컷씬 목록 → DB 저장 |
| 3. 초안 이미지 생성 | 백엔드 + Nano Banana 2 | 생성된 컷씬 구조를 기반으로 컷씬별 초안 이미지를 1회 자동 생성한다 | 컷씬별 이미지 URL → DB 저장 + 프론트 반환 |
| 4. 컷씬 편집 | 유저 + 프론트엔드 | 유저가 이미지를 보며 각 컷씬을 편집한다. "이미지 새로고침" 버튼을 누르면 수정된 컷씬만 Nano Banana 2를 재호출한다. 만족할 때까지 반복 가능하다 | 수정된 컷씬 데이터 + 재생성 이미지 → DB 저장 |
| 5. 최종 Confirm | 유저 | 유저가 모든 컷씬에 만족하면 최종 Confirm 버튼을 누른다 | 영상 생성 파이프라인 시작 트리거 |
| 6. 영상 생성 | 백엔드 + Veo 2 | Confirm된 컷씬의 최종 이미지를 Veo 2에 전달하여 영상 클립을 자동 생성한다. 백그라운드에서 비동기 처리된다 | 컷씬별 영상 클립 URL → DB 저장 |
| 7. 병합 후 결과 표시 | 프론트엔드 | 생성 완료된 영상 클립을 컷씬 순서대로 병합 후 표시 | 클립 플레이어 화면 |

### 3-2. 편집 단계의 반복 구조

유저는 초안 이미지를 보며 컷씬을 편집한다.

- **직접 수정:** 유저가 편집 도구를 통해 컷씬의 개별 요소(캐릭터, 배경, 구도 등)를 직접 변경한다. 이 경우 이미지는 즉시 바뀌지 않는다.
- **이미지 새로고침:** 필드를 수정한 후 "이미지 새로고침" 버튼을 누르면 해당 컷씬만 Nano Banana 2를 재호출하여 이미지를 업데이트한다. 유저가 버튼을 누를 때만 비용이 발생한다.

Veo 2 호출은 유저가 최종 Confirm을 누른 이후에만 실행된다.

---

## 4. 단계별 기능 상세

### 4-1. 프롬프트 입력 & 컷씬 초안 생성

유저가 입력한 아이디어를 Claude API에 전달하여 컷씬 구조 JSON을 생성하고, 이어서 백엔드 조합 로직이 Nano Banana 2용 프롬프트를 구성하여 컷씬별 초안 이미지를 1회 자동 생성한다. 유저는 처음부터 이미지로 컷씬을 확인할 수 있다.

**Claude API 호출 방식**
- 사용 모델: `claude-sonnet-4-20250514`
- 출력 방식: Structured Output (Pydantic 모델 기반 JSON 스키마 강제). 항상 유효한 JSON이 반환되도록 보장한다.
- 시스템 프롬프트 역할: 2차 창작 크리에이티브 디렉터. 장르별(K-pop / 애니 / 게임) 특성에 맞는 컷씬 구성 규칙을 정의한다.
- 생성 컷 수: 유저 요청에 따라 5~10컷 범위에서 생성한다.
- Claude의 역할은 컷씬 구조 JSON 생성까지이다. 이미지 프롬프트 작성은 백엔드 조합 로직이 담당한다.

**백엔드 조합 로직 (Nano Banana 2 프롬프트 자동 구성)**

Claude가 생성한 컷씬 JSON의 편집 필드들을 백엔드 코드가 조합하여 Nano Banana 2에 전달할 영어 프롬프트 문자열을 구성한다. 유저가 프롬프트를 직접 작성하지 않는다.

조합 규칙은 다음과 같다.
- 프롬프트 앞에 항상 아트 스타일 문자열을 붙여 모든 컷씬의 시각적 일관성을 유지한다.
- 캐릭터 묘사(`main_character`, `sub_character`)를 모든 컷씬 프롬프트에 반복 포함하여 캐릭터 일관성을 유지한다.
- 장르별로 조합 순서와 강조 키워드가 다르다. K-pop은 조명과 패션을 앞에, 애니는 아트 스타일을 앞에, 게임은 구도와 배경을 앞에 배치한다.
- 프롬프트 끝에 항상 퀄리티 modifier를 고정 추가한다: `high quality, detailed, sharp focus`
- 조합된 프롬프트는 DB의 `generated_image_prompt` 컬럼에 저장되며, "이미지 새로고침" 시에도 동일한 조합 로직을 재실행하여 프롬프트를 재구성한다.

실제 구현 시 백엔드 f-string 예시는 다음과 같다.

```python
"{art_style}, {main_character} is {action}, doing {pose}. The background is {background} set in {era}. Shot in {composition} with {lighting} lighting. {mood} mood. High quality, detailed, sharp focus."
```

**초안 이미지 생성 방식 (조합 로직 실행 직후 자동 실행)**
- 사용 모델: Nano Banana 2
- 백엔드 조합 로직이 구성한 프롬프트 문자열을 Nano Banana 2에 전달한다.
- 컷씬 수만큼 순차 호출하며, 생성된 이미지는 즉시 Cloudinary에 업로드되고 URL이 DB의 `draft_image_url` 필드에 저장된다.
- 이 단계는 백그라운드로 처리되며, 프론트엔드는 이미지가 완료되는 순서대로 화면에 표시한다.

**컷씬 초안 JSON에 포함되는 필드 (편집 가능 항목)**

해커톤 주제 설명자료의 영상 제작 프레임워크를 기반으로 아래 요소들을 각 컷씬마다 자동 생성한다.

| 필드 | 설명 | 예시 |
|---|---|---|
| `main_character` | 메인 캐릭터 묘사 (외형, 의상 포함) | "검은 단발, 흰 셔츠를 입은 20대 여성" |
| `sub_character` | 보조 캐릭터 묘사 (없을 경우 null) | "회색 후드를 입은 남성" |
| `action` | 캐릭터의 행동 | "무대 위에서 춤을 추고 있다" |
| `pose` | 캐릭터의 포즈 | "한 팔을 들고 고개를 숙인 포즈" |
| `background` | 배경 장소 묘사 | "네온사인이 가득한 도시 골목" |
| `era` | 시대적 배경 | "현대", "1990년대", "미래 도시" |
| `composition` | 구도 | "클로즈업", "풀샷", "버드아이뷰" |
| `lighting` | 조명 | "역광", "스포트라이트", "부드러운 자연광" |
| `mood` | 분위기 | "긴장감", "설렘", "쓸쓸함" |
| `story_beat` | 해당 컷의 서사적 역할 | "주인공이 결심을 굳히는 장면" |

이 필드들은 모두 유저가 편집 단계에서 수정할 수 있다. 필드가 수정된 후 "이미지 새로고침" 버튼을 누르면 수정된 필드들을 조합하여 Nano Banana 2 프롬프트가 재구성되고 이미지가 새로 생성된다.

---

### 4-2. 컷씬 편집 도구

유저가 AI가 생성한 컷씬을 직접 수정할 수 있도록 다양한 편집 도구를 제공한다. 영상 편집 경험이 없는 유저도 쉽게 사용할 수 있도록 각 요소를 선택형 UI로 제공하는 것을 원칙으로 한다.

**편집 도구 목록**

| 도구 | 설명 | UI 방식 |
|---|---|---|
| 캐릭터 편집 | 메인/보조 캐릭터의 외형, 의상, 특징 수정 | 텍스트 입력 |
| 행동 편집 | 캐릭터가 하는 행동 수정 | 텍스트 입력 또는 선택지 제공 |
| 포즈 편집 | 캐릭터의 포즈 수정 | 선택지 제공 (예: 서있기, 앉기, 점프 등) |
| 배경 편집 | 배경 장소 수정 | 텍스트 입력 또는 장르별 추천 목록 |
| 시대 편집 | 시대적 배경 수정 | 드롭다운 선택 |
| 구도 편집 | 카메라 구도 수정 | 선택지 제공 (클로즈업, 풀샷, 버드아이뷰 등) + 용어 설명 더보기 |
| 조명 편집 | 조명 스타일 수정 | 선택지 제공 + 용어 설명 더보기 |
| 분위기 편집 | 전체적인 감정/분위기 수정 | 선택지 제공 + 용어 설명 더보기 |
| 스토리 편집 | 해당 컷의 서사적 역할 수정 | 텍스트 입력 |
| 컷 순서 변경 | 컷씬 순서를 드래그로 재배치 | 드래그 앤 드롭 |
| 컷 추가 | 특정 위치에 새 컷씬 삽입 | 버튼 클릭 → Claude API로 해당 위치의 새 컷씬 자동 생성 |
| 컷 삭제 | 불필요한 컷씬 제거 | 버튼 클릭 |
| AI 재생성 | 특정 컷씬에 대해 수정 방향을 텍스트로 입력하면 Claude API가 해당 컷씬만 다시 생성 | 텍스트 입력 + 버튼 클릭 |

**용어 설명 더보기 (입문자 친화 UI)**

영상 제작 경험이 없는 유저에게 생소할 수 있는 용어에는 각 선택지 옆에 "더보기" 버튼을 제공한다. 버튼을 누르면 해당 용어의 의미와 어떤 느낌의 장면에 어울리는지를 짧은 텍스트와 예시로 설명하는 패널이 펼쳐진다. 설명을 읽지 않아도 서비스 이용에 지장이 없도록 기본은 접힌 상태로 표시된다.

더보기 설명이 제공되는 필드와 설명 예시는 아래와 같다.

| 필드 | 용어 예시 | 더보기 설명 예시 |
|---|---|---|
| 구도 | 클로즈업 | 인물의 얼굴이나 손 등 특정 부위를 크게 담는 방식. 감정을 강조하고 싶을 때 사용 |
| 구도 | 버드아이뷰 | 새가 위에서 내려다보는 시점. 인물이 작게 보이고 배경이 넓게 펼쳐져 웅장한 느낌을 줌 |
| 구도 | 풀샷 | 인물의 전신이 모두 보이는 구도. 의상이나 동작 전체를 보여주고 싶을 때 사용 |
| 조명 | 역광 | 인물 뒤에서 빛이 비춰 실루엣이 강조되는 방식. 드라마틱하고 감성적인 느낌을 줌 |
| 조명 | 스포트라이트 | 무대 조명처럼 인물에만 집중적으로 빛이 비추는 방식. K-pop 공연 장면에 잘 어울림 |
| 조명 | 자연광 | 햇빛처럼 부드럽고 자연스러운 조명. 일상적이고 따뜻한 분위기를 만들 때 사용 |
| 분위기 | 긴장감 | 무언가 일어날 것 같은 팽팽한 느낌. 결전 전날 밤이나 대결 직전 장면에 어울림 |
| 분위기 | 설렘 | 두근거리고 기분이 좋은 느낌. 처음 만남이나 고백 장면에 어울림 |
| 분위기 | 쓸쓸함 | 혼자이거나 무언가를 잃은 듯한 느낌. 이별이나 회상 장면에 어울림 |

**편집 시 비용 정책**
- 유저가 필드를 직접 수정하는 경우: AI API 호출 없음. 비용 발생 없음.
- "이미지 새로고침" 버튼을 누르는 경우: 해당 컷씬 1개에 대해 Nano Banana 2만 호출. 유저가 버튼을 누를 때만 비용 발생.
- Veo 2 호출은 오직 최종 Confirm 이후에만 발생한다.

---

### 4-3. 최종 Confirm & 영상 생성

유저가 최종 Confirm을 누르면 두 단계가 순서대로 실행된다. 먼저 Claude API가 각 컷씬의 최종 확정 데이터를 바탕으로 Veo 2용 고품질 프롬프트를 작성하고, 이어서 Veo 2가 해당 프롬프트와 컷씬 이미지를 사용하여 영상 클립을 생성한다. 이미지는 편집 단계에서 이미 생성되어 있으므로 Nano Banana 2는 호출되지 않는다.

**Confirm 시점에 일어나는 일**

1. 프론트엔드가 백엔드에 영상 생성 요청을 보낸다.
2. 백엔드는 `task_id`를 즉시 반환하고, 파이프라인을 백그라운드에서 시작한다.
3. 프론트엔드는 `task_id`를 사용하여 3~5초 간격으로 진행 상태를 폴링한다.

**Claude API 호출 방식 (Veo 2 프롬프트 생성)**
- 사용 모델: `claude-sonnet-4-6`
- 백엔드가 최종 확정된 모든 컷씬의 `scene_data`를 하나의 컨텍스트로 묶어 Claude에게 전달한다.
- Claude는 각 컷씬마다 Veo 2에 최적화된 자연어 서술형 영어 프롬프트를 작성한다. 캐릭터 묘사, 행동, 배경, 구도, 조명, 분위기, 카메라 무빙을 모두 포함한 완성형 문장으로 출력한다.
- 컷씬 이미지에서 유저가 확인한 시각적 결과물이 영상에서도 동일하게 구현되도록, scene_data의 모든 필드를 빠짐없이 프롬프트에 반영하도록 시스템 프롬프트에 명시한다.
- **Unsafe Content 사전 차단:** 시스템 프롬프트에 "절대로 폭력적, 유혈, 선정적, 혐오적 단어나 표현을 포함하지 말 것"을 강력하게 지시한다. Veo 2는 안전하지 않은 콘텐츠가 감지되면 생성을 강제 거부하므로, 이 단계에서 사전 차단하여 Veo 2 생성 실패와 불필요한 재호출로 인한 토큰 낭비를 함께 예방한다.
- 출력 방식: 컷씬 ID를 키로 하는 JSON 형태로 각 컷씬의 프롬프트를 반환한다.

**Veo 2 호출 방식**
- 사용 모델: `veo-2.0-generate-001`
- 각 컷씬의 최종 확정 이미지(`draft_image_url`)를 첫 번째 프레임으로 사용하는 image-to-video 방식으로 호출한다.
- Claude가 작성한 해당 컷씬의 프롬프트를 전달한다.
- 클립 길이는 컷씬의 `duration_seconds` 필드를 따른다 (3~8초).
- 생성된 클립은 즉시 Cloudinary에 업로드되고 URL이 DB의 `clip_video_url` 필드에 저장된다.

---

### 4-4. 최종 영상 병합 (Video Stitching)

모든 컷씬 클립 생성이 완료되면 백엔드가 MoviePy를 사용하여 클립들을 하나의 완성된 영상으로 병합한다.

**병합 처리 방식**
1. 전체 컷씬의 `clip_video_url`을 Cloudinary에서 순서대로 다운로드한다.
2. MoviePy로 컷씬 번호 순서에 맞게 클립을 이어 붙인다.
3. 최종 `final_video.mp4` (15~30초)를 생성하여 Cloudinary에 업로드한다.
4. 반환된 URL을 `projects.final_video_url`에 저장하고 프론트엔드에 전달한다.

병합 실패 시(`merge_failed`)에는 병합을 한번 재시도하고 최종 실패 시 개별 클립 URL 목록(`clip_video_url`)을 제공한다.

---

## 5. 컷씬 데이터 구조

컷씬 1개를 나타내는 데이터 구조이다. 편집 가능 필드와 시스템 관리 필드로 구분된다.

### 5-1. 편집 가능 필드 (유저가 수정할 수 있는 항목)

| 필드명 | 타입 | 설명 |
|---|---|---|
| `main_character` | string | 메인 캐릭터 묘사 |
| `sub_character` | string \| null | 보조 캐릭터 묘사 |
| `action` | string | 캐릭터의 행동 |
| `pose` | string | 캐릭터의 포즈 |
| `background` | string | 배경 장소 묘사 |
| `era` | string | 시대적 배경 |
| `composition` | string | 카메라 구도 |
| `lighting` | string | 조명 스타일 |
| `mood` | string | 분위기 |
| `story_beat` | string | 해당 컷의 서사적 역할 |
| `duration_seconds` | float | 목표 클립 길이 (3.0~8.0초) |

### 5-2. 시스템 관리 필드 (자동 생성, 유저 수정 불가)

| 필드명 | 타입 | 설명 |
|---|---|---|
| `id` | string (UUID) | 컷씬 고유 식별자 |
| `project_id` | string (UUID) | 소속 프로젝트 ID |
| `scene_number` | integer | 컷 순서 번호 |
| `generated_image_prompt` | string | 편집 필드들을 조합하여 자동 생성된 Nano Banana 2용 프롬프트. 이미지 생성 시마다 재구성된다 |
| `draft_image_url` | string \| null | 현재 확정된 Cloudinary 이미지 URL. 초안 생성 또는 이미지 새로고침 시 업데이트된다 |
| `veo2_prompt` | string \| null | Claude가 작성한 Veo 2용 프롬프트. Confirm 이후 생성된다 |
| `clip_video_url` | string \| null | Cloudinary 영상 클립 URL. Confirm 이후 생성된다 (final_video_url과 구분) |
| `image_status` | string | 이미지 생성 상태: pending / generating / done / failed |
| `video_status` | string | 영상 클립 생성 상태: pending / generating / done / failed |

---

## 6. DB 스키마

### 6-1. projects 테이블

프로젝트 1건을 나타낸다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `id` | TEXT (UUID) | 프로젝트 고유 식별자 |
| `user_prompt` | TEXT | 유저가 처음 입력한 원본 아이디어 텍스트 |
| `genre` | TEXT | 선택된 장르: kpop / anime / game |
| `art_style` | TEXT | Claude가 결정한 전체 아트 스타일 문자열. 모든 컷씬에 공통 적용 |
| `status` | TEXT | 전체 작업 상태 (status 값 정의 참조) |
| `progress` | INTEGER | 영상 생성 진행률 0~100. Confirm 이후에만 변화 |
| `current_stage` | TEXT | 현재 처리 단계 문자열 (예: "이미지 생성 중 2/4") |
| `final_video_url` | TEXT \| null | MoviePy 병합 완료 후 저장되는 최종 MP4 URL |
| `created_at` | DATETIME | 프로젝트 생성 시각 |
| `confirmed_at` | DATETIME \| null | 유저가 최종 Confirm을 누른 시각 |

**status 값 정의**

| 값 | 의미 |
|---|---|
| `draft` | POST /api/plot 수신 직후. Claude API 호출 대기 또는 진행 중 |
| `generating_images` | Claude 완료 후 Nano Banana 2 백그라운드 호출 진행 중 |
| `editing` | 전체 컷씬 이미지 생성 완료. 유저 편집 중 |
| `editing_with_errors` | 일부 컷씬 이미지 생성 실패. 성공한 컷씬으로 편집 진입 허용 |
| `confirmed` | 유저가 최종 Confirm을 누른 상태. Veo 2 대기 중 |
| `processing` | Claude(Veo 2 프롬프트) + Veo 2 호출 백그라운드 진행 중 |
| `merging` | 전체 클립 완료 → MoviePy 병합 진행 중 |
| `completed` | 병합 완료. `final_video_url` 존재 |
| `completed_with_errors` | 일부 컷씬 영상 생성 실패. 병합 스킵, 성공한 클립만 표시 |
| `merge_failed` | 개별 클립은 정상이나 MoviePy 병합 실패. `clip_video_url` 목록으로 fallback 제공 |
| `failed` | 전체 컷씬 실패 또는 Claude 타임아웃으로 처리 불가 |

### 6-2. scenes 테이블

컷씬 1개를 나타낸다. 하나의 프로젝트는 여러 scene을 가진다.

편집 가능 필드 10개(섹션 5-1)는 `scene_data` JSON 컬럼 하나에 묶어서 저장한다. 이 필드들은 개별적으로 쿼리할 필요가 없고 유저 편집 시 통째로 읽고 쓰는 단위이기 때문이다. 향후 필드가 추가되거나 변경되더라도 DB 마이그레이션 없이 JSON 구조만 수정하면 된다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `id` | TEXT (UUID) | 컷씬 고유 식별자 |
| `project_id` | TEXT | 소속 프로젝트 ID (외래키) |
| `scene_number` | INTEGER | 컷 순서 번호. 순서 변경 시 업데이트된다 |
| `scene_data` | TEXT (JSON) | 편집 가능 필드 전체를 JSON으로 저장. 섹션 5-1의 필드 구조를 따른다 |
| `generated_image_prompt` | TEXT \| null | 편집 필드 조합으로 자동 생성된 Nano Banana 2용 프롬프트. 이미지 생성 시마다 재구성된다 |
| `draft_image_url` | TEXT \| null | 현재 확정된 Cloudinary 이미지 URL. 초안 또는 새로고침 시 업데이트된다 |
| `veo2_prompt` | TEXT \| null | Claude가 작성한 Veo 2용 프롬프트. Confirm 이후 생성된다 |
| `clip_video_url` | TEXT \| null | Cloudinary 영상 클립 URL. Confirm 이후 생성된다 (`final_video_url`과 구분) |
| `image_status` | TEXT | 이미지 생성 상태: pending / generating / done / failed |
| `video_status` | TEXT | 영상 클립 생성 상태: pending / generating / done / failed |

> `scene_data`는 수정 시 항상 UPDATE(덮어쓰기)한다. Undo 기능은 구현하지 않으며, edit_history 테이블도 존재하지 않는다. 구현 복잡도를 낮추기 위한 의도적 결정이다. 프론트엔드 React state로 세션 내 임시 되돌리기는 허용 가능하다.

---

## 7. 비동기 처리 구조

비동기 처리가 필요한 구간은 두 곳이다. 첫 번째는 컷씬 생성 + 초안 이미지 생성 단계(프롬프트 입력 직후)이고, 두 번째는 영상 생성 단계(Confirm 이후)이다.

### 7-1. 초안 이미지 생성 처리 흐름 (프롬프트 입력 직후)

| 순서 | 동작 | 상세 설명 |
|---|---|---|
| 1 | 즉시 응답 | POST /api/plot 수신 즉시 `project_id`를 반환한다 (100ms 이내). Claude 호출은 BackgroundTasks로 처리한다. `project.status = draft` |
| 2 | Claude 백그라운드 호출 | FastAPI BackgroundTasks가 Claude API를 호출하여 컷씬 구조 JSON을 생성한다. 타임아웃 30초. 초과 시 `project.status = failed` |
| 3 | 이미지 백그라운드 생성 | Claude 완료 직후 `project.status = generating_images`로 변경하고 Nano Banana 2 호출을 컷씬 수만큼 순차 실행한다. 실패 시 최대 3회 재시도(5초 간격, exponential backoff). Cloudinary 업로드 실패 시 최대 3회 재시도(2초 간격) |
| 4 | 컷씬별 상태 업데이트 | 각 컷씬 완료 시 `draft_image_url` DB 저장, `image_status = done`. 재시도 소진 시 `image_status = failed` |
| 5 | 프론트엔드 폴링 | `/api/scenes/status/{project_id}`를 3~5초마다 호출. `image_status=done` 컷씬은 즉시 이미지 카드로 표시, `pending/generating`은 로딩 스켈레톤, `failed`는 에러 카드 + 컷씬별 재시도 버튼 |
| 6 | 상태 집계 | 전체 완료 시 `project.status = editing`. 일부 실패 시 `project.status = editing_with_errors`(성공 컷씬으로 편집 진입 허용). 전체 실패 시 `project.status = failed` |

### 7-2. 영상 생성 처리 흐름 (Confirm 이후)

| 순서 | 동작 | 상세 설명 |
|---|---|---|
| 1 | 즉시 응답 | Confirm 요청 수신 즉시 `task_id`를 반환하고 `project.status = confirmed`로 변경한다 |
| 2 | Claude API 호출 | 백그라운드에서 모든 컷씬의 최종 `scene_data`를 묶어 Claude에게 전달하여 Veo 2용 고품질 프롬프트를 일괄 생성한다. 타임아웃 30초 |
| 3 | Veo 2 클립 생성 | 컷씬별 `draft_image_url`과 Claude 프롬프트를 Veo 2에 전달하여 영상 클립을 순차 생성한다. 타임아웃 300초/클립. 실패 시 최대 2회 재시도(30초 간격). 완료 클립은 즉시 Cloudinary 업로드 → `clip_video_url` DB 저장 |
| 4 | 상태 업데이트 | 각 클립 완료 시 `video_status = done`, `progress` + `current_stage` 업데이트. 재시도 소진 시 `video_status = failed` |
| 5 | 상태 집계 | 전체 완료 시 `project.status = merging` → MoviePy 병합 시작. 일부 실패 시 `project.status = completed_with_errors`(성공 클립만 표시, 병합 스킵). 전체 실패 시 `project.status = failed` |
| 6 | 영상 병합 | MoviePy가 전체 `clip_video_url`을 다운로드하여 순서대로 병합 → `final_video.mp4` → Cloudinary 업로드 → `projects.final_video_url` 저장 |
| 7 | 완료 처리 | 병합 성공 시 `project.status = completed`. 병합 실패 시 `project.status = merge_failed` (개별 클립 URL 제공) |

### 7-3. 에러 처리 정책

| 대상 | 재시도 횟수 | 재시도 간격 | 타임아웃 |
|---|---|---|---|
| Claude API | 2회 | 3초 | 30초 |
| Nano Banana 2 | 3회 | 5초 (exponential backoff) | 60초 |
| Veo 2 | 2회 | 30초 | 300초 |
| Cloudinary 업로드 | 3회 | 2초 (linear) | 30초 |

일부 컷씬만 실패한 경우 전체를 취소하지 않는다. 성공한 컷씬은 그대로 유지하고, 실패한 컷씬만 개별 재시도 버튼을 제공한다. 전체 재시도는 제공하지 않아 성공한 컷씬의 API 비용이 중복 발생하지 않도록 한다.

---

## 8. 프론트엔드 화면 구조

### Step 1 — 프롬프트 입력 화면

유저가 텍스트 아이디어와 장르(K-pop / 애니 / 게임)를 입력하는 화면이다. "컷씬 생성하기" 버튼을 누르면 `project_id`를 즉시 받고 Step 2 화면으로 이동하여 폴링을 시작한다. Claude와 Nano Banana 2 호출은 백그라운드에서 처리되며 `project.status`에 따라 로딩 메시지가 변경된다.

| project.status | 표시 메시지 |
|---|---|
| `draft` | "스토리를 구성하고 있어요..." |
| `generating_images` | "장면 이미지를 그리고 있어요 (N/M)" |
| `editing` | 편집 UI 활성화 |
| `editing_with_errors` | 편집 UI 활성화 + 실패 컷씬 에러 카드 표시 |
| `failed` | "생성에 실패했어요. 다시 시도해주세요" + 재시도 버튼 |

### Step 2 — 컷씬 편집 화면

생성된 컷씬이 이미지 카드 형태로 표시된다. `image_status`에 따라 각 카드의 상태가 구분된다.

| image_status | 카드 표시 |
|---|---|
| `pending` / `generating` | 로딩 스켈레톤 |
| `done` | 이미지 + 편집 UI 활성화 (즉시 편집 가능) |
| `failed` | 에러 카드 + 해당 컷씬 재시도 버튼 |

각 카드에는 이미지와 함께 모든 편집 가능 필드가 표시된다. 유저는 필드를 직접 수정하거나 "이미지 새로고침" 버튼을 눌러 수정된 내용을 이미지에 반영할 수 있다. AI 재생성을 요청하면 컷씬 구조와 이미지가 함께 새로 생성된다. 수정된 내용은 DB에 즉시 덮어쓰기로 저장되며 Undo 기능은 제공되지 않는다.

영상 제작 용어가 생소한 입문자를 위해 구도, 조명, 분위기 항목에는 각 선택지 옆에 "더보기" 버튼이 제공된다. 기본 상태는 접혀 있으며 클릭 시 용어 설명과 장면 예시 패널이 펼쳐진다.

컷씬의 순서를 드래그 앤 드롭으로 변경하거나 컷을 추가 및 삭제할 수 있다. 화면 하단의 "최종 확인 및 영상 생성" 버튼을 누르면 다음 단계로 진행한다.

### Step 3 — 영상 생성 진행 화면

Confirm 이후 영상 클립을 생성하는 동안 표시되는 화면이다. 현재 처리 중인 컷씬 번호와 전체 진행률이 진행 바 형태로 실시간 표시된다. `project.status`에 따라 화면 전환이 결정된다.

| project.status | 동작 |
|---|---|
| `processing` | 진행 바 + "영상 클립 생성 중 N/M" |
| `merging` | 진행 바 + "최종 영상을 완성하고 있어요..." |
| `completed` | Step 4(결과 화면)로 이동 |
| `completed_with_errors` | Step 4로 이동 + 실패 컷씬 안내 메시지 |
| `merge_failed` | Step 4로 이동 + "병합에 실패했어요. 개별 클립을 확인해주세요" |
| `failed` | "영상 생성에 실패했어요." + 전체 재시도 버튼 |

### Step 4 — 결과 화면

`projects.final_video_url`이 존재하면 병합된 최종 영상(15~30초)을 메인으로 표시한다. 그 아래에 컷씬별 개별 클립(`clip_video_url`)도 함께 표시하여 개별 재생과 다운로드가 가능하다. `merge_failed` 상태라면 최종 영상 없이 개별 클립 목록만 표시된다. `video_status=failed` 컷씬은 "이 장면은 생성에 실패했어요" 메시지와 해당 컷씬 재시도 버튼을 표시한다.

### 공통 UI 요소

- **로딩 인디케이터:** AI 처리가 진행 중인 모든 상황에서 로딩 상태를 명확히 표시한다.
- **반응형 레이아웃:** 모바일 환경에서도 사용 가능하도록 반응형으로 구성한다.

---

*본 설계서는 MVP 개발 진행에 따라 지속적으로 업데이트된다.*  