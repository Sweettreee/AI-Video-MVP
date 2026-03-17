from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Claude (Anthropic) API 설정
    ANTHROPIC_API_KEY: str
    MODEL: str = "claude-sonnet-4-20250514"
    SAFETY_MODEL: str = "claude-haiku-4-5-20251001"
    MAX_TOKENS: int = 4096
    MAX_INPUT_TOKENS: int = 100000
    THINKING_BUDGET: int = 10000
    SDK_MAX_RETRIES: int = 3

    # 이미지 생성 및 Cloudinary 설정
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    HUGGINGFACE_API_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
