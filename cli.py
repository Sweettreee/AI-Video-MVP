import re
import sys

from backend.app.prompts.templates import get_template
from backend.app.schemas.feedback import Feedback
from backend.app.services.plot_advisor import generate_advice
from backend.app.services.plot_converter import ParseError, parse_storyboard, save_to_file
from backend.app.services.plot_evaluator import EvalResult, full_eval
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
MAX_FAILURES = 7
TEMPLATE_SUGGEST_AT = 3
CONTINUE_CONFIRM_AT = 5

SCORE_DIRECT_HUMAN_EVAL = 8.0   # 이 이상이면 바로 Human Eval 진입
SCORE_PASS_THRESHOLD = 5.0      # 이 이상이면 통과 (수정 여부 선택 가능)


# ── 입력 수집 ──────────────────────────────────────────────

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
        "genre": "장르", "character": "캐릭터", "mood": "분위기",
        "story": "줄거리", "must_have": "필수 장면", "extra": "추가 요청",
    }
    for key, label in labels.items():
        value = answers.get(key)
        if value:
            print(f"  {label}: {value}")
    print("─" * 50)


def confirm_summary(answers: dict) -> dict:
    while True:
        show_summary(answers)
        print("\n이대로 진행할까요? (y: 생성 / 번호: 항목 수정)")
        for i, (key, _) in enumerate(GUIDE_QUESTIONS, 1):
            label = {
                "genre": "장르", "character": "캐릭터", "mood": "분위기",
                "story": "줄거리", "must_have": "필수 장면", "extra": "추가 요청",
            }[key]
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


# ── 점수 출력 ──────────────────────────────────────────────

def show_eval_result(result: EvalResult) -> None:
    print("\n" + "─" * 50)
    print("[평가 결과]")
    print(f"  코드 점수: {result.code_average} / 10")
    if result.model_scores:
        print(f"  모델 점수: {result.model_average} / 10")
    print(f"  총점: {result.total_average} / 10  (통과 기준: 5.0)")
    if result.failed_items:
        print(f"  미달 항목: {', '.join(result.failed_items)}")
    if result.model_reasoning:
        print(f"\n  [평가 근거]\n  {result.model_reasoning}")
    if result.previous_total is not None:
        delta = round(result.total_average - result.previous_total, 1)
        sign = "+" if delta >= 0 else ""
        print(f"  변화량: {sign}{delta}")
    print("─" * 50)


# ── 템플릿 제안 ────────────────────────────────────────────

def show_template_suggestion(genre: str) -> None:
    template = get_template(genre)
    print("\n" + "=" * 50)
    print("[참고] 아래 예시 형식을 참고해 입력을 수정해보세요:\n")
    labels = {
        "genre": "장르", "character": "캐릭터", "mood": "분위기",
        "story": "줄거리", "must_have": "필수 장면", "extra": "추가 요청",
    }
    for key, label in labels.items():
        value = template.get(key)
        if value:
            print(f"  {label}: {value}")
    print("=" * 50)


# ── Human Eval ─────────────────────────────────────────────

H1_CHECKS = [
    ("H1", "이 스토리보드가 내 팬덤 취향에 맞아요"),
    ("H2", "처음부터 끝까지 읽었을 때 흐름이 자연스러워요"),
    ("H3", "내가 처음에 상상한 내용이 잘 반영되어 있어요"),
]

FEEDBACK_TYPES = {
    "1": ("fan_appeal_mismatch", "캐릭터/분위기가 내 취향이 아니야 (H1)"),
    "2": ("pacing_issue", "흐름이 밋밋하거나 어색해 (H2)"),
    "3": ("input_mismatch", "내가 원한 게 이게 아니야 (H3)"),
}

FEEDBACK_DETAILS = {
    "fan_appeal_mismatch": {
        "1": "character_appearance",
        "2": "mood_background",
        "3": "genre_feel",
        "4": "art_style",
    },
    "pacing_issue": {
        "1": "no_climax",
        "2": "abrupt_transition",
        "3": "monotone",
        "4": "weak_opening_ending",
    },
    "input_mismatch": {
        "1": "missing_scene",
        "2": "unwanted_scene",
        "3": "wrong_character",
        "4": "wrong_setting",
    },
}

DETAIL_LABELS = {
    "fan_appeal_mismatch": [
        "캐릭터 외형/의상이 마음에 안 들어",
        "배경/분위기가 다른 느낌이었으면",
        "장르 느낌이 안 나",
        "전반적인 화풍/스타일이 다르면 좋겠어",
    ],
    "pacing_issue": [
        "클라이맥스/하이라이트가 없어",
        "장면 전환이 갑작스러워",
        "전체적으로 너무 단조로워",
        "시작이나 마무리가 약해",
    ],
    "input_mismatch": [
        "내가 원한 장면이 빠져있어",
        "원하지 않은 장면이 추가됐어",
        "캐릭터가 다르게 나왔어",
        "상황/설정이 내 입력과 달라",
    ],
}


def run_human_eval(storyboard: str, cut_count: int) -> list[Feedback] | None:
    """H1~H3 셀프 체크 → 불만족 시 피드백 funnel → list[Feedback] 반환.

    모두 만족 시 None 반환.
    """
    print("\n" + "=" * 50)
    print("[Human Eval] 아래 항목을 확인해주세요.\n")
    for code, text in H1_CHECKS:
        print(f"  {text}")

    print("\n모두 만족하시나요? (y: 확정 / n: 피드백 입력)")
    if input("> ").strip().lower() == "y":
        return None

    # 피드백 funnel
    feedback_items = []

    # Step 1: 대분류
    print("\n[Step 1] 어디가 아쉬우세요? (복수 선택 가능, 쉼표로 구분)")
    for k, (_, label) in FEEDBACK_TYPES.items():
        print(f"  {k}. {label}")
    choices = [c.strip() for c in input("> ").split(",") if c.strip() in FEEDBACK_TYPES]

    for choice in choices:
        fb_type, _ = FEEDBACK_TYPES[choice]

        # Step 2: 세부
        print(f"\n[Step 2] 구체적으로 어떤 부분인가요?")
        for k, label in enumerate(DETAIL_LABELS[fb_type], 1):
            print(f"  {k}. {label}")
        detail_choice = input("> ").strip()
        detail = FEEDBACK_DETAILS[fb_type].get(detail_choice, "기타")

        # Step 3: 컷 선택
        print(f"\n[Step 3] 어떤 컷이 아쉬웠나요? (번호 입력, 쉼표로 구분 / 없으면 Enter)")
        print(f"  선택 가능: 1~{cut_count}")
        raw_cuts = input("> ").strip()
        target_cuts = []
        if raw_cuts:
            for c in raw_cuts.split(","):
                c = c.strip()
                if c.isdigit() and 1 <= int(c) <= cut_count:
                    target_cuts.append(int(c))

        # Step 4: 자유 입력
        print("\n[Step 4] 추가로 원하는 게 있다면 적어주세요. (없으면 Enter)")
        free_text = input("> ").strip() or None

        feedback_items.append(Feedback(
            feedback_type=fb_type,
            detail=detail,
            target_cuts=target_cuts,
            free_text=free_text,
        ))

    return feedback_items


# ── 메인 루프 ──────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  AI 2차 창작 영상 — 스토리보드 생성기")
    print("=" * 50)

    answers = ask_guide_questions()
    answers = confirm_summary(answers)

    fail_count = 0
    previous_storyboard = None
    modification = None
    previous_advice = None
    result = None

    # ── Plot Generation 루프 ───────────────────────────────
    while True:
        print("\n생성 중...")

        try:
            storyboard = generate_plot(answers, previous_storyboard, modification)
        except GenerationError as e:
            print(f"\n[오류] {e}")
            fail_count += 1
        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류가 발생했습니다: {e}")
            fail_count += 1
        else:
            print("\n" + "─" * 50)
            print("[생성된 스토리보드]\n")
            print(storyboard)

            print("\n평가 중...")
            previous_total = result.total_average if result else None
            result = full_eval(storyboard, previous_total=previous_total)
            show_eval_result(result)

            if result.total_average >= SCORE_DIRECT_HUMAN_EVAL:
                # 8점 이상 → 바로 Human Eval 진입
                break

            if result.total_average >= SCORE_PASS_THRESHOLD:
                # 5~7.9점 → 약점 요약 + 유저 선택
                print("\n기준은 통과했지만 보완할 수 있는 항목이 있습니다.")
                if result.failed_items:
                    print(f"  약점 항목: {', '.join(result.failed_items)}")
                print("\nHuman Eval을 진행하시겠습니까? (y: 진행 / n: 추가 수정)")
                if input("> ").strip().lower() != "n":
                    break
                # n → 추가 수정 진행 (아래 fail 로직으로)

            fail_count += 1
            previous_storyboard = storyboard

            print("\n개선 가이드라인 생성 중...")
            advice = generate_advice(storyboard, result, previous_advice=previous_advice)
            previous_advice = advice
            print("\n[개선 방향]\n")
            print(advice)

        if fail_count >= MAX_FAILURES:
            print("\n생성에 반복적으로 실패했습니다. 다른 아이디어로 새로 시작해주세요.")
            sys.exit(1)

        if fail_count == TEMPLATE_SUGGEST_AT:
            show_template_suggestion(answers.get("genre", ""))

        if fail_count == CONTINUE_CONFIRM_AT:
            print(f"\n{fail_count}회 연속 실패했습니다. 계속 시도하시겠습니까? (y/n)")
            if input("> ").strip().lower() != "y":
                print("종료합니다.")
                sys.exit(0)

        print("\n수정사항을 입력해주세요. (Enter: 그대로 재시도)")
        modification = input("> ").strip() or None

    # ── Human Eval 루프 ────────────────────────────────────
    cut_count = len(re.findall(r"\[Cut \d+\]", storyboard))

    while True:
        feedback = run_human_eval(storyboard, cut_count)

        if feedback is None:
            # 만족 → JSON 변환 + 저장
            print("\nJSON으로 변환 중...")
            try:
                scenes = parse_storyboard(storyboard)
            except ParseError as e:
                print(f"\n[오류] {e}")
                print("스토리보드를 다시 생성합니다.")
                break

            path = save_to_file(scenes)
            if path:
                print(f"\n스토리보드가 저장되었습니다: {path}")
            print("\n완료! 이미지 생성 단계로 넘어갈 수 있습니다. (Phase 5)")
            break

        # 불만족 → 피드백 기반 가이드라인 + 재생성
        feedback_dicts = [f.model_dump() for f in feedback]
        print("\n개선 가이드라인 생성 중...")
        advice = generate_advice(storyboard, result, feedback=feedback_dicts, previous_advice=previous_advice)
        previous_advice = advice
        print("\n[개선 방향]\n")
        print(advice)

        print("\n수정사항을 입력해주세요.")
        modification = input("> ").strip() or None

        print("\n재생성 중...")
        try:
            storyboard = generate_plot(answers, storyboard, modification)
        except GenerationError as e:
            print(f"\n[오류] {e}")
            continue

        print("\n" + "─" * 50)
        print("[수정된 스토리보드]\n")
        print(storyboard)

        print("\n재평가 중...")
        previous_total = result.total_average if result else None
        result = full_eval(storyboard, previous_total=previous_total)
        show_eval_result(result)
        cut_count = len(re.findall(r"\[Cut \d+\]", storyboard))

        if not result.passed:
            print("\n수정 후 점수가 기준에 미달합니다. 추가 수정이 필요합니다.")
            # Human Eval 루프 최상단으로 돌아가서 재평가 유도


if __name__ == "__main__":
    main()
