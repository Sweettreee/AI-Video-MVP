import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.prompts.eval import (
    get_eval_system_prompt,
    get_eval_user_message,
    get_focused_eval_user_message,
)
from backend.app.services.claude_client import call_claude, call_claude_structured


# ── Structured Outputs 스키마 ──────────────────────────────

class ModelGraderResult(BaseModel):
    M1_image_prompt_quality: float = Field(ge=0, le=10, description="이미지 프롬프트 구체성")
    M2_character_consistency: float = Field(ge=0, le=10, description="캐릭터 일관성")
    M3_story_coherence: float = Field(ge=0, le=10, description="서사 흐름")
    M4_motion_describability: float = Field(ge=0, le=10, description="동작 묘사 구체성")
    M5_genre_adherence: float = Field(ge=0, le=10, description="장르 규칙 준수")
    M6_parseable_intent: float = Field(ge=0, le=10, description="필드 구분 명확성")
    reasoning: str = Field(description="평가 근거 요약")


# ── 평가 결과 ──────────────────────────────────────────────

@dataclass
class EvalResult:
    code_scores: dict[str, float]
    code_average: float
    model_scores: dict[str, float]
    model_average: float
    total_average: float
    passed: bool
    failed_items: list[str]
    previous_total: float | None = None
    model_reasoning: str | None = None


# ── 파서 ───────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "캐릭터", "동작", "포즈", "배경", "시대",
    "구도", "조명", "분위기", "스토리비트", "길이",
]

EMPTY_PATTERN = re.compile(r"^(없음|N/?A|해당\s*없음|-|—|\s*)$", re.IGNORECASE)


def _parse_cuts(plain_text: str) -> list[dict[str, str]]:
    """plain text를 [Cut N] 단위로 분리 → 필드명:값 dict 리스트."""
    raw_cuts = re.split(r"\[Cut \d+\]", plain_text)
    raw_cuts = [c.strip() for c in raw_cuts if c.strip()]

    cuts = []
    for raw in raw_cuts:
        fields = {}
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            for sep in [":", "："]:
                if sep in line:
                    key, _, value = line.partition(sep)
                    fields[key.strip()] = value.strip()
                    break
        cuts.append(fields)

    return cuts


# ── Code Grader (C1~C5) ───────────────────────────────────

def _score_c1(plain_text: str) -> float:
    """C1: [Cut N] 패턴이 일관되게 존재하는가."""
    numbers = re.findall(r"\[Cut (\d+)\]", plain_text)
    if not numbers:
        return 0.0
    actual = [int(n) for n in numbers]
    expected = list(range(1, len(actual) + 1))
    if actual == expected:
        return 10.0
    return 5.0


def _score_c2(cuts: list[dict]) -> float:
    """C2: 각 컷에 필수 필드가 모두 존재하는가. 부분 점수."""
    if not cuts:
        return 0.0
    total = 0
    present = 0
    for cut in cuts:
        for f in REQUIRED_FIELDS:
            total += 1
            if f in cut and cut[f] and not EMPTY_PATTERN.match(cut[f]):
                present += 1
    return round(present / total * 10, 1)


def _score_c3(cuts: list[dict]) -> float:
    """C3: 컷 수가 5~10개 범위인가."""
    n = len(cuts)
    if 5 <= n <= 10:
        return 10.0
    if n == 4 or n == 11:
        return 5.0
    return 0.0


def _score_c5(plain_text: str) -> float:
    """C5: unsafe 표현 검수. Haiku로 저비용 판별."""
    safety_prompt = (
        "당신은 콘텐츠 안전 분류기입니다. "
        "주어진 텍스트에 폭력적, 선정적, 혐오적 표현이 포함되어 있는지 판별합니다. "
        "\"safe\" 또는 \"unsafe\"로만 답하세요."
    )
    result = call_claude(
        system_prompt=safety_prompt,
        user_message=plain_text,
        model=settings.SAFETY_MODEL,
    )
    if "unsafe" in result.lower():
        return 0.0
    return 10.0


def run_code_grader(
    plain_text: str,
    target_cuts: list[int] | None = None,
) -> dict[str, float]:
    """Code Grader 실행.

    target_cuts=None → Full Eval (C1~C5 전체)
    target_cuts 지정 → Focused Eval (C2/C5만, 대상 컷만)
    """
    cuts = _parse_cuts(plain_text)

    if target_cuts is not None:
        target_data = [
            cuts[i] for i in range(len(cuts))
            if (i + 1) in target_cuts
        ]
        return {
            "C2": _score_c2(target_data),
            "C5": _score_c5(plain_text),
        }

    return {
        "C1": _score_c1(plain_text),
        "C2": _score_c2(cuts),
        "C3": _score_c3(cuts),
        "C5": _score_c5(plain_text),
    }


# ── Model Grader (M1~M6) ──────────────────────────────────

def run_model_grader(
    plain_text: str,
    target_cuts: list[int] | None = None,
) -> ModelGraderResult | None:
    """Model Grader 실행. Structured Outputs. 실패 시 None."""
    system = get_eval_system_prompt()

    if target_cuts is not None:
        user_msg = get_focused_eval_user_message(plain_text, target_cuts)
    else:
        user_msg = get_eval_user_message(plain_text)

    return call_claude_structured(
        system_prompt=system,
        user_message=user_msg,
        output_schema=ModelGraderResult,
        cache_system=True,
    )


# ── Full Eval ──────────────────────────────────────────────

def full_eval(
    plain_text: str,
    previous_total: float | None = None,
) -> EvalResult:
    """최초 생성 시 전체 평가. C1~C5 + M1~M6."""
    code_scores = run_code_grader(plain_text)
    code_avg = sum(code_scores.values()) / len(code_scores)

    # Code 평균 5.0 미만 → Model Grader 실행 안 함
    if code_avg < 5.0:
        failed = [k for k, v in code_scores.items() if v < 5.0]
        return EvalResult(
            code_scores=code_scores,
            code_average=round(code_avg, 1),
            model_scores={},
            model_average=0.0,
            total_average=round(code_avg / 2, 1),
            passed=False,
            failed_items=failed,
            previous_total=previous_total,
        )

    # Model Grader 실행
    model_result = run_model_grader(plain_text)

    if model_result is None:
        # API 실패 → Code 점수만으로 판단
        failed = [k for k, v in code_scores.items() if v < 5.0]
        return EvalResult(
            code_scores=code_scores,
            code_average=round(code_avg, 1),
            model_scores={},
            model_average=0.0,
            total_average=round(code_avg, 1),
            passed=code_avg >= 5.0,
            failed_items=failed,
            previous_total=previous_total,
        )

    model_scores = {
        "M1": model_result.M1_image_prompt_quality,
        "M2": model_result.M2_character_consistency,
        "M3": model_result.M3_story_coherence,
        "M4": model_result.M4_motion_describability,
        "M5": model_result.M5_genre_adherence,
        "M6": model_result.M6_parseable_intent,
    }
    model_avg = sum(model_scores.values()) / len(model_scores)
    total = (code_avg + model_avg) / 2

    all_scores = {**code_scores, **model_scores}
    failed = [k for k, v in all_scores.items() if v < 5.0]

    return EvalResult(
        code_scores=code_scores,
        code_average=round(code_avg, 1),
        model_scores=model_scores,
        model_average=round(model_avg, 1),
        total_average=round(total, 1),
        passed=total >= 5.0,
        failed_items=failed,
        previous_total=previous_total,
        model_reasoning=model_result.reasoning,
    )


# ── Focused Eval ───────────────────────────────────────────

def focused_eval(
    changed_cuts: list[int],
    plain_text: str,
    previous_total: float | None = None,
) -> EvalResult:
    """이미지 수정 후 부분 평가. 변경 컷 + 인접 ±1, C2/C5 + M1~M4."""
    # 대상 컷 계산
    target_set = set()
    for c in changed_cuts:
        target_set.update([c - 1, c, c + 1])
    target_set.discard(0)
    target_cuts = sorted(target_set)

    # Code Grader: C2/C5만
    code_scores = run_code_grader(plain_text, target_cuts=target_cuts)
    code_avg = sum(code_scores.values()) / len(code_scores)

    if code_avg < 5.0:
        failed = [k for k, v in code_scores.items() if v < 5.0]
        return EvalResult(
            code_scores=code_scores,
            code_average=round(code_avg, 1),
            model_scores={},
            model_average=0.0,
            total_average=round(code_avg / 2, 1),
            passed=False,
            failed_items=failed,
            previous_total=previous_total,
        )

    # Model Grader: M1~M4만 사용 (M5/M6은 프롬프트에서 0 반환 지시)
    model_result = run_model_grader(plain_text, target_cuts=target_cuts)

    if model_result is None:
        failed = [k for k, v in code_scores.items() if v < 5.0]
        return EvalResult(
            code_scores=code_scores,
            code_average=round(code_avg, 1),
            model_scores={},
            model_average=0.0,
            total_average=round(code_avg, 1),
            passed=code_avg >= 5.0,
            failed_items=failed,
            previous_total=previous_total,
        )

    # M1~M4만 집계 (M5/M6 제외)
    model_scores = {
        "M1": model_result.M1_image_prompt_quality,
        "M2": model_result.M2_character_consistency,
        "M3": model_result.M3_story_coherence,
        "M4": model_result.M4_motion_describability,
    }
    model_avg = sum(model_scores.values()) / len(model_scores)
    total = (code_avg + model_avg) / 2

    all_scores = {**code_scores, **model_scores}
    failed = [k for k, v in all_scores.items() if v < 5.0]

    return EvalResult(
        code_scores=code_scores,
        code_average=round(code_avg, 1),
        model_scores=model_scores,
        model_average=round(model_avg, 1),
        total_average=round(total, 1),
        passed=total >= 5.0,
        failed_items=failed,
        previous_total=previous_total,
        model_reasoning=model_result.reasoning,
    )
