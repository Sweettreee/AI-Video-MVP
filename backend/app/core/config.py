from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- 팀원 담당: Claude (Anthropic) API 설정 ---
    ANTHROPIC_API_KEY: str = "" # .env에 없으면 일단 빈 문자열로 처리 (에러 방지)
    MODEL: str = "claude-sonnet-4-20250514"
    SAFETY_MODEL: str = "claude-haiku-4-5-20251001"
    MAX_TOKENS: int = 4096
    MAX_INPUT_TOKENS: int = 100000
    THINKING_BUDGET: int = 10000
    SDK_MAX_RETRIES: int = 3

    # --- 내 담당: 이미지 생성 및 클라우드(Cloudinary) 설정 ---
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    HUGGINGFACE_API_KEY: str = ""

    # .env 파일을 자동으로 찾아서 위 변수들에 쏙쏙 넣어줍니다!
    model_config = {"env_file": ".env", "extra": "ignore"}

# 이 settings 객체 하나만 다른 곳에서 import해서 쓰면 됩니다.
settings = Settings()