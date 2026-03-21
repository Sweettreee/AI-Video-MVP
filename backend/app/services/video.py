import asyncio
import logging

import requests

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class VideoGenerationError(Exception):
    """영상 생성 실패 시 발생하는 예외."""
    pass


async def generate_video_from_fal(prompt: str, image_url: str) -> str:
    """Fal.ai Kling Video 모델로 영상 생성. 비동기 폴링."""
    fal_key = settings.FAL_KEY

    if not fal_key:
        raise VideoGenerationError("FAL_KEY가 설정되지 않았습니다.")

    url = "https://queue.fal.run/fal-ai/kling-video/v1/standard/image-to-video"
    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt, "image_url": image_url}

    try:
        # 1. 렌더링 작업 제출 (블로킹 HTTP를 스레드풀에서 실행)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(url, headers=headers, json=payload, timeout=30),
        )

        if response.status_code not in (200, 202):
            raise VideoGenerationError(
                f"Fal API 에러 ({response.status_code}): {response.text}"
            )

        data = response.json()
        status_url = data.get("status_url")
        response_url = data.get("response_url")

        if not status_url or not response_url:
            raise VideoGenerationError("Fal API 응답에 status_url/response_url이 없습니다.")

        # 2. 비동기 폴링 (asyncio.sleep → 이벤트 루프 해제)
        for attempt in range(60):
            await asyncio.sleep(5)

            poll_res = await loop.run_in_executor(
                None,
                lambda: requests.get(status_url, headers=headers),
            )
            if poll_res.status_code != 200:
                continue

            poll_data = poll_res.json()
            status = poll_data.get("status")

            if status == "COMPLETED":
                final_res = await loop.run_in_executor(
                    None,
                    lambda: requests.get(response_url, headers=headers),
                )
                final_data = final_res.json()

                video_url = final_data.get("video", {}).get("url")
                if not video_url and "url" in final_data:
                    video_url = final_data["url"]

                if video_url:
                    logger.info(f"영상 생성 성공: {video_url}")
                    return video_url
                else:
                    raise VideoGenerationError(
                        "작업 완료되었으나 영상 URL을 찾을 수 없습니다."
                    )

            elif status == "FAILED":
                raise VideoGenerationError(
                    f"Fal.ai 렌더링 실패: {poll_data}"
                )

        raise VideoGenerationError("영상 생성 시간 초과 (5분)")

    except VideoGenerationError:
        raise
    except Exception as e:
        raise VideoGenerationError(f"영상 생성 중 에러: {str(e)}")
