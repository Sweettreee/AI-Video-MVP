import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

# 현재 파일(config.py) 위치 기준 상위 상위 디렉토리(backend 최상단)의 .env 경로를 찾습니다.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_file = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_file, override=True)
env_config = dotenv_values(env_file)

def get_clean_env(key: str) -> str:
    val = env_config.get(key, "")
    return val.strip() if val else ""

CLOUD_NAME = get_clean_env("CLOUDINARY_CLOUD_NAME")
API_KEY = get_clean_env("CLOUDINARY_API_KEY")
API_SECRET = get_clean_env("CLOUDINARY_API_SECRET")
HF_KEY = get_clean_env("HUGGINGFACE_API_KEY")