import logging
import time

import requests
import cloudinary
import cloudinary.uploader

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

DEFAULT_NEGATIVE_PROMPT = (
    "portrait, headshot, close-up face only, plain background, "
    "white background, passport photo, ID photo, mugshot, "
    "blurry, low quality, text, watermark"
)


def generate_image_from_hf(prompt: str, negative_prompt: str | None = None) -> bytes:
    """허깅페이스 API를 호출하여 이미지를 생성하고 바이트로 반환"""
    if not settings.HUGGINGFACE_API_KEY:
        raise Exception("Hugging Face API 키가 설정되지 않았습니다. .env 파일을 확인하세요!")

    API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}
    max_retries = 5

    neg = negative_prompt or DEFAULT_NEGATIVE_PROMPT
    payload = {
        "inputs": prompt,
        "parameters": {"negative_prompt": neg},
    }

    for attempt in range(max_retries):
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            logger.info("이미지 생성 성공")
            return response.content
        elif response.status_code == 503:
            logger.warning(f"HF 서버 웜업 중... ({attempt+1}/{max_retries})")
            time.sleep(5)
        elif response.status_code == 429:
            wait = min(2 ** attempt, 30)
            logger.warning(f"HF 429 rate limit, {wait}초 대기... ({attempt+1}/{max_retries})")
            time.sleep(wait)
        else:
            logger.error(f"HF API 에러({response.status_code}): {response.text}")
            break

    raise Exception("HuggingFace 이미지 생성 실패: 모든 재시도 소진")

def upload_to_cloudinary(image_bytes: bytes) -> str:
    """Cloudinary에 이미지를 업로드하고 URL을 반환"""
    retries = 3
    for attempt in range(retries):
        try:
            result = cloudinary.uploader.upload(
                image_bytes,
                folder="estaid_hackathon",
                resource_type="image"
            )
            return result["secure_url"]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise Exception(f"Cloudinary 업로드 실패: {str(e)}")
