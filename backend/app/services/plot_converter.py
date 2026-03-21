import re

from backend.app.schemas.scene import Scene


class ParseError(Exception):
    pass


def _parse_duration(raw: str) -> float:
    """길이 필드에서 숫자만 추출. Claude가 '5초', '약 5' 등을 출력해도 안전하게 파싱."""
    import re as _re
    m = _re.search(r"[\d.]+", str(raw))
    value = float(m.group()) if m else 5.0
    return max(3.0, min(8.0, value))  # Scene 스키마 범위 3.0~8.0 강제



# ── plain text → Scene 리스트 ──────────────────────────────

def parse_storyboard(plain_text: str) -> list[Scene]:
    """plain text 스토리보드 → Scene 리스트.

    파싱 실패 시 ParseError(컷 번호, 필드명) 포함 raise.
    """
    raw_cuts = re.split(r"\[\s*Cut\s+(\d+)\s*\]", plain_text)
    # split 결과: ["", "1", "...cut1 body...", "2", "...cut2 body...", ...]
    if len(raw_cuts) < 3:
        raise ParseError("스토리보드에서 [Cut N] 패턴을 찾을 수 없습니다.")

    scenes = []
    # 인덱스 1, 3, 5... = 컷 번호 / 2, 4, 6... = 컷 본문
    for i in range(1, len(raw_cuts) - 1, 2):
        cut_number = int(raw_cuts[i])
        body = raw_cuts[i + 1].strip()

        fields: dict[str, str] = {}
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            for sep in [":", "："]:
                if sep in line:
                    key, _, value = line.partition(sep)
                    fields[key.strip()] = value.strip()
                    break

        # 캐릭터 필드 분리 (main / sub)
        char_raw = fields.get("캐릭터", "")
        if "/" in char_raw:
            main_char, sub_char = [c.strip() for c in char_raw.split("/", 1)]
        else:
            main_char, sub_char = char_raw, None

        # Scene 생성 (Pydantic 검증)
        try:
            scene = Scene(
                cut_number=cut_number,
                main_character=main_char,
                sub_character=sub_char,
                action=fields.get("동작", ""),
                pose=fields.get("포즈", ""),
                background=fields.get("배경", ""),
                era=fields.get("시대", ""),
                composition=fields.get("구도", ""),
                lighting=fields.get("조명", ""),
                mood=fields.get("분위기", ""),
                story_beat=fields.get("스토리비트", ""),
                duration_seconds=_parse_duration(fields.get("길이", "5.0")),
                camera_angle=fields.get("카메라앵글", ""),
                expression=fields.get("표정", ""),
                foreground=fields.get("전경", ""),
            )
        except Exception as e:
            raise ParseError(f"[Cut {cut_number}] 파싱 오류: {e}")

        scenes.append(scene)

    return scenes



# ── Scene 리스트 → plain text ──────────────────────────────

def scenes_to_plain_text(scenes: list[Scene]) -> str:
    """Scene 리스트 → [Cut N] plain text 복원.

    이미지 수정 시 generate_plot()의 previous_storyboard로 전달하는 용도.
    라벨:값 1:1 대응이므로 정보 손실 없음.
    """
    parts = []
    for s in scenes:
        char_line = s.main_character
        if s.sub_character:
            char_line += f" / {s.sub_character}"

        block = (
            f"[Cut {s.cut_number}]\n"
            f"캐릭터: {char_line}\n"
            f"동작: {s.action}\n"
            f"포즈: {s.pose}\n"
            f"배경: {s.background}\n"
            f"시대: {s.era}\n"
            f"구도: {s.composition}\n"
            f"카메라앵글: {s.camera_angle}\n"
            f"표정: {s.expression}\n"
            f"전경: {s.foreground}\n"
            f"조명: {s.lighting}\n"
            f"분위기: {s.mood}\n"
            f"스토리비트: {s.story_beat}\n"
            f"길이: {s.duration_seconds}"
        )
        parts.append(block)

    return "\n\n".join(parts)


# ── Scene diff — 변경된 컷 번호 반환 ──────────────────────

_DIFF_FIELDS = (
    "main_character", "sub_character", "action", "pose",
    "background", "era", "composition", "lighting", "mood",
    "camera_angle", "expression", "foreground",
)


def diff_scenes(old: list[Scene], new: list[Scene]) -> list[int]:
    """이전/이후 Scene 리스트를 비교하여 변경된 컷 번호 반환.

    비교 대상: 이미지에 영향을 주는 9개 필드 (_DIFF_FIELDS).
    story_beat, duration_seconds는 이미지 생성에 무관하므로 제외.

    컷 수가 달라진 경우(추가/삭제) → 전체 컷 번호 반환 (전체 재생성).
    """
    if len(old) != len(new):
        return [s.cut_number for s in new]

    old_map = {s.cut_number: s for s in old}
    changed = []

    for new_scene in new:
        old_scene = old_map.get(new_scene.cut_number)
        if old_scene is None:
            changed.append(new_scene.cut_number)
            continue

        for field in _DIFF_FIELDS:
            if getattr(old_scene, field) != getattr(new_scene, field):
                changed.append(new_scene.cut_number)
                break

    return changed
