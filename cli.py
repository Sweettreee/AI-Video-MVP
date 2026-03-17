import sys

from backend.app.services.plot_generator import GenerationError, generate_plot

GUIDE_QUESTIONS = [
    ("genre", "어떤 장르의 영상을 만들고 싶으세요?\n  (예: K-pop 뮤비, 애니메이션 액션, 게임 시네마틱, 호러, 로맨스...)"),
    ("character", "주인공은 어떤 모습인가요?\n  (예: 흰 드레스를 입은 여성 아이돌, 검은 갑옷의 기사...)"),
    ("mood", "어떤 분위기를 원하세요?\n  (예: 슬프고 감성적인, 신나고 에너지 넘치는, 어둡고 긴장감 있는...)"),
    ("story", "어떤 이야기가 펼쳐지나요? 간단히 설명해주세요.\n  (예: 빗속에서 마지막 콘서트를 마치고 무대를 떠난다)"),
    ("must_have", "꼭 넣고 싶은 장면이 있나요? (없으면 Enter)\n  (예: 비가 그치는 장면, 폭발 장면...)"),
    ("extra", "기타 추가하고 싶은 내용이 있나요? (없으면 Enter)\n  (예: 컷 전환을 빠르게, 엔딩에 여운을 길게...)"),
]

REQUIRED_KEYS = {"genre", "character", "mood", "story"}


def ask_guide_questions() -> dict:
    answers = {}
    for key, question in GUIDE_QUESTIONS:
        while True:
            print(f"\n{question}")
            answer = input("> ").strip()
            if answer or key not in REQUIRED_KEYS:
                answers[key] = answer if answer else None
                break
            print("이 항목은 필수입니다. 답변을 입력해주세요.")
    return answers


def show_summary(answers: dict) -> None:
    print("\n" + "─" * 50)
    print("[입력 요약]\n")
    labels = {
        "genre": "장르",
        "character": "캐릭터",
        "mood": "분위기",
        "story": "줄거리",
        "must_have": "필수 장면",
        "extra": "추가 요청",
    }
    for key, label in labels.items():
        value = answers.get(key)
        if value:
            print(f"  {label}: {value}")
    print("─" * 50)


def confirm_summary(answers: dict) -> dict:
    """요약을 보여주고 confirm 또는 항목 수정."""
    while True:
        show_summary(answers)
        print("\n이대로 진행할까요? (y: 생성 / 번호: 항목 수정)")
        for i, (key, _) in enumerate(GUIDE_QUESTIONS, 1):
            label = {"genre": "장르", "character": "캐릭터", "mood": "분위기",
                     "story": "줄거리", "must_have": "필수 장면", "extra": "추가 요청"}[key]
            print(f"  {i}. {label}")

        choice = input("> ").strip().lower()

        if choice == "y":
            return answers

        if choice.isdigit() and 1 <= int(choice) <= len(GUIDE_QUESTIONS):
            idx = int(choice) - 1
            key, question = GUIDE_QUESTIONS[idx]
            while True:
                print(f"\n{question}")
                answer = input("> ").strip()
                if answer or key not in REQUIRED_KEYS:
                    answers[key] = answer if answer else None
                    break
                print("이 항목은 필수입니다. 답변을 입력해주세요.")
        else:
            print("y 또는 항목 번호(1~6)를 입력해주세요.")


def main():
    print("=" * 50)
    print("  AI 2차 창작 영상 — 스토리보드 생성기")
    print("=" * 50)

    answers = ask_guide_questions()
    answers = confirm_summary(answers)

    print("\n생성 중...")

    try:
        storyboard = generate_plot(answers)
    except GenerationError as e:
        print(f"\n[오류] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[오류] 예상치 못한 오류가 발생했습니다: {e}")
        sys.exit(1)

    print("\n" + "─" * 50)
    print("[Generated Storyboard]\n")
    print(storyboard)
    print("─" * 50)

    # 수정 루프
    while True:
        print("\n수정하고 싶은 부분이 있나요? (없으면 Enter)")
        modification = input("> ").strip()
        if not modification:
            break

        print("\n수정 반영 중...")
        try:
            storyboard = generate_plot(
                answers,
                previous_storyboard=storyboard,
                modification_request=modification,
            )
        except GenerationError as e:
            print(f"\n[오류] {e}")
            continue
        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류가 발생했습니다: {e}")
            continue

        print("\n" + "─" * 50)
        print("[Modified Storyboard]\n")
        print(storyboard)
        print("─" * 50)

    print("\n스토리보드가 확정되었습니다.")


if __name__ == "__main__":
    main()
