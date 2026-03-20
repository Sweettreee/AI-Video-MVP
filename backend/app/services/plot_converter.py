import json
import os
import re
from datetime import datetime

from backend.app.schemas.scene import Scene


class ParseError(Exception):
    pass


# ── plain text → Scene 리스트 ──────────────────────────────

def parse_storyboard(plain_text: str) -> list[Scene]:
    """plain text 스토리보드 → Scene 리스트.

    파싱 실패 시 ParseError(컷 번호, 필드명) 포함 raise.
    """
    raw_cuts = re.split(r"\[Cut (\d+)\]", plain_text)
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
                duration_seconds=fields.get("길이", "5.0"),
            )
        except Exception as e:
            raise ParseError(f"[Cut {cut_number}] 파싱 오류: {e}")

        scenes.append(scene)

    return scenes


def save_to_file(scenes: list[Scene], project_id: str | None = None) -> str:
    """Scene 리스트 → output/scene_<YYYYMMDD_HHMMSS>.json 저장.

    저장 실패 시 JSON을 터미널에 출력하고 경로 대신 빈 문자열 반환.
    """
    if project_id is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scene_{timestamp}.json"
    else:
        filename = f"{project_id}.json"

    data = [s.model_dump() for s in scenes]
    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    try:
        os.makedirs("output", exist_ok=True)
        path = f"output/{filename}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return path
    except OSError:
        print("\n[파일 저장 실패] 아래 JSON을 직접 복사해주세요:\n")
        print(json_str)
        return ""


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
            f"조명: {s.lighting}\n"
            f"분위기: {s.mood}\n"
            f"스토리비트: {s.story_beat}\n"
            f"길이: {s.duration_seconds}"
        )
        parts.append(block)

    return "\n\n".join(parts)
