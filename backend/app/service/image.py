import time
import requests
import cloudinary
import cloudinary.uploader

from app.core.config import CLOUD_NAME, API_KEY, API_SECRET, HF_KEY
from app.schemas.image import ImageRequest

# Cloudinary 설정 초기화
cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
    secure=True
)

def backend_compose_prompt(req: ImageRequest) -> str:
    prompt = f"{req.art_style}, {req.main_character} is {req.action}, doing {req.pose}. " \
             f"The background is {req.background} set in {req.era}. " \
             f"Shot in {req.composition} with {req.lighting} lighting. {req.mood} mood. " \
             f"High quality, detailed, sharp focus."
    return prompt

def generate_image_from_hf(prompt: str) -> bytes:
    """허깅페이스 API를 호출하여 이미지를 생성하고 바이트로 반환"""
    if not HF_KEY:
        raise Exception("Hugging Face API 키가 설정되지 않았습니다. .env 파일을 확인하세요!")

    API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_KEY}"}
    max_retries = 5 
    
    for attempt in range(max_retries):
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=60)
        
        if response.status_code == 200:
            print("✅ Hugging Face 이미지 생성 성공!")
            return response.content
        elif response.status_code == 503:
            print(f"💤 허깅페이스 무료 서버 깨우는 중... ({attempt+1}/{max_retries})")
            time.sleep(5)
        else:
            print(f"⚠️ 허깅페이스 API 에러({response.status_code}): {response.text}")
            break
            
    print("프론트엔드 테스트를 위해 더미 이미지를 사용합니다.")
    fallback_url = "https://placehold.co/1024x576/cccccc/000000.png?text=HuggingFace+API+Failed"
    return requests.get(fallback_url).content

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