from backend.app.schemas.scene import GlobalContext, Scene
from backend.app.core.config import settings
from backend.app.services.claude_client import call_claude

# ── 장르 → 화풍 매핑 ──────────────────────────────────────

_ART_STYLE_MAP = {
    "kpop": "K-pop music video style, vibrant colors, high fashion, studio lighting",
    "k-pop": "K-pop music video style, vibrant colors, high fashion, studio lighting",
    "아이돌": "K-pop music video style, vibrant colors, high fashion, studio lighting",
    "뮤직비디오": "K-pop music video style, vibrant colors, high fashion, studio lighting",
    "anime": "anime cel-shading style, bold outlines, expressive features",
    "애니": "anime cel-shading style, bold outlines, expressive features",
    "애니메이션": "anime cel-shading style, bold outlines, expressive features",
    "game": "cinematic game trailer style, photorealistic, dramatic lighting",
    "게임": "cinematic game trailer style, photorealistic, dramatic lighting",
    "시네마틱": "cinematic game trailer style, photorealistic, dramatic lighting",
}

_COLOR_PALETTE_MAP = {
    "슬프": "cool blue, muted tones, soft shadows",
    "감성": "warm golden, soft pastel, gentle gradients",
    "melancholy": "cool blue, muted tones, soft shadows",
    "신나": "bright saturated, neon accents, high contrast",
    "energetic": "bright saturated, neon accents, high contrast",
    "어두": "dark moody, deep shadows, desaturated",
    "dark": "dark moody, deep shadows, desaturated",
    "epic": "cinematic warm-cool contrast, volumetric lighting",
    "tense": "high contrast, cold tones, sharp shadows",
}


def _infer_art_style(genre: str) -> str:
    """장르 키워드에서 화풍 추론."""
    genre_lower = genre.lower()
    for keyword, style in _ART_STYLE_MAP.items():
        if keyword in genre_lower:
            return style
    return "high quality, detailed, cinematic"


def _infer_color_palette(mood: str) -> str:
    """분위기 키워드에서 색감 추론."""
    mood_lower = mood.lower()
    for keyword, palette in _COLOR_PALETTE_MAP.items():
        if keyword in mood_lower:
            return palette
    return "natural balanced tones"


# ── 캐릭터 시트 생성 ──────────────────────────────────────

_CHARACTER_SHEET_SYSTEM = """\
<role>
당신은 이미지 생성 AI를 위한 캐릭터 외형 명세서 작성자입니다.
주어진 캐릭터 정보를 바탕으로, 이미지 생성 모델이 매번 동일한 인물을 그릴 수 있도록
구체적이고 재현 가능한 외형 묘사를 영어로 작성합니다.
</role>

<output_format>
아래 항목을 모두 포함하여 한 문단의 영어 텍스트로 작성하세요.
- Gender and age
- Hair: length, color, style, accessories (hairpins, ribbons, etc.)
- Face: eye shape, eye color, nose, lips, skin tone
- Body: height impression, build
- Outfit: top (color, material, details), bottom (color, material), shoes
- Accessories: jewelry, weapons, props
- Distinctive features: scars, tattoos, markings, aura, etc.
</output_format>

<constraints>
- 모호한 표현 금지: "예쁜", "멋진" 대신 구체적 묘사
- 영어로 작성 (이미지 모델 호환)
- 100~200 단어 분량
- 서브 캐릭터가 있으면 별도 문단으로 분리하여 작성
</constraints>"""


def generate_character_sheet(
    answers: dict,
    scenes: list[Scene],
) -> str:
    """유저 입력 + 첫 컷 캐릭터 묘사를 기반으로 상세 캐릭터 시트 생성.

    Claude 1회 호출. 결과는 영어 텍스트로, 모든 컷 프롬프트에 그대로 삽입된다.
    """
    # 첫 컷의 캐릭터 묘사를 참고 정보로 활용
    first_scene = scenes[0] if scenes else None
    first_char = first_scene.main_character if first_scene else ""
    first_sub = first_scene.sub_character if first_scene else None

    user_parts = [
        f"캐릭터 원본 입력: {answers.get('character', '')}",
        f"장르: {answers.get('genre', '')}",
        f"분위기: {answers.get('mood', '')}",
        f"첫 컷 캐릭터 묘사: {first_char}",
    ]
    if first_sub:
        user_parts.append(f"서브 캐릭터 묘사: {first_sub}")

    user_message = "\n".join(user_parts)
    user_message += "\n\n위 정보를 바탕으로 캐릭터 시트를 작성해주세요."

    return call_claude(
        system_prompt=_CHARACTER_SHEET_SYSTEM,
        user_message=user_message,
        cache_system=True,
    )


# ── 캐릭터 시트 압축 (프롬프트용) ─────────────────────────

_CONDENSE_SYSTEM = """\
Extract the 3-5 most visually distinctive features from this character description.
Output: single comma-separated English phrase, max 30 words.
Focus on: hair (color+style), outfit (main color+type), one unique accessory or feature.
Example: "waist-length black hair with golden hairpin, pink silk hanbok dress, silver bracelet"
Do NOT include generic traits like "young woman" or "medium build"."""


def condense_character_sheet(full_sheet: str) -> str:
    """전체 캐릭터 시트(100-200 words) → 핵심 시각 특징(20-30 words).

    Haiku 1회 호출. 프로젝트당 1회만 실행.
    실패 시 첫 문장으로 폴백.
    """
    try:
        result = call_claude(
            system_prompt=_CONDENSE_SYSTEM,
            user_message=full_sheet,
            model=settings.SAFETY_MODEL,  # Haiku — 저비용
        )
        # 30단어 이내로 강제
        words = result.strip().split()
        if len(words) > 35:
            result = " ".join(words[:30])
        return result.strip()
    except Exception:
        # 폴백: 첫 문장만 사용
        first_sentence = full_sheet.split(".")[0]
        return first_sentence[:200]


# ── GlobalContext 추출 ─────────────────────────────────────

def extract_global_context(
    answers: dict,
    scenes: list[Scene],
) -> GlobalContext:
    """캐릭터 시트 생성 + 장르/분위기에서 화풍·색감 추론 → GlobalContext 반환.

    Claude 호출: 1회 (캐릭터 시트 생성).
    화풍/색감은 규칙 기반 추론 (API 호출 없음).
    """
    character_sheet = generate_character_sheet(answers, scenes)
    condensed = condense_character_sheet(character_sheet)

    era = scenes[0].era if scenes else "modern"

    return GlobalContext(
        main_character=character_sheet,
        condensed_character=condensed,
        sub_character=None,  # 서브 캐릭터는 시트 내부에 포함
        art_style=_infer_art_style(answers.get("genre", "")),
        era=era,
        color_palette=_infer_color_palette(answers.get("mood", "")),
    )


# ── 컷별 이미지 프롬프트 조합 ──────────────────────────────

def compose_cut_prompt(global_ctx: GlobalContext, scene: Scene) -> str:
    """GlobalContext(고정) + Scene(컷별 가변) → 이미지 생성 프롬프트.

    장면 중심 프롬프트: 구도/행동/배경을 우선 배치하고,
    캐릭터는 압축된 핵심 특징(condensed_character)만 삽입.
    scene.main_character는 무시하고, GlobalContext의 캐릭터 정보를 사용한다.
    """
    # 카메라앵글: 빈 값이면 "eye level" 기본값
    angle = scene.camera_angle.strip() if scene.camera_angle else "eye level"
    # 표정: 빈 값이면 생략
    expression_part = f", {scene.expression}" if scene.expression.strip() else ""
    # 전경: "없음" 또는 빈 값이면 생략
    foreground_part = (
        f"{scene.foreground} in foreground, "
        if scene.foreground.strip() and scene.foreground.strip() != "없음"
        else ""
    )
    # 압축 캐릭터 사용 (하위 호환: 없으면 전체 시트 폴백)
    char_desc = global_ctx.condensed_character or global_ctx.main_character

    parts = [
        # 1. 프레임 선언 + 샷 타입 (FLUX 최우선 토큰)
        f"cinematic storyboard cut, {scene.composition} {angle}",

        # 2. 캐릭터+행동 통합 (캐릭터를 행동과 연결하여 초상화 방지)
        f"{foreground_part}{char_desc} {scene.action}{expression_part}",

        # 3. 배경 환경 (장면감 확보)
        f"{scene.background}, {global_ctx.era}",

        # 4. 화풍 + 조명 + 분위기
        f"{global_ctx.art_style}, {scene.lighting} lighting, {scene.mood}",

        # 5. 색감 + 품질 태그
        f"{global_ctx.color_palette}, cinematic depth of field",
    ]

    return ". ".join(parts)
