import time
import requests
import os
from app.core.config import settings

def generate_video_from_fal(prompt: str, image_url: str) -> str:
    """
    [해커톤 쾌속 렌더링] Fal.ai 플랫폼을 통해 최상급 'Kling Video' 모델을 호출합니다.
    폐기된 Luma 엔드포인트 대신, 현재 가장 안정적이고 뛰어난 Kling 모델로 우회합니다.
    """
    print(f"\n🎬 [Video Service] 영상 생성 시작 (엔진: Fal.ai - Kling Video Model)")
    print(f"👉 대상 이미지: {image_url}")

    fal_key = getattr(settings, "FAL_KEY", os.getenv("FAL_KEY"))

    if not fal_key:
        print("⚠️ 경고: .env 파일에 FAL_KEY가 없습니다.")
        return "https://www.w3schools.com/html/mov_bbb.mp4"

    try:
        # 1. Fal.ai 렌더링 작업 제출 (Kling Video 전용 주소로 변경!)
        url = "https://queue.fal.run/fal-ai/kling-video/v1/standard/image-to-video"
        
        headers = {
            "Authorization": f"Key {fal_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "image_url": image_url
        }

        print("⏳ Fal.ai(Kling) 서버에 렌더링 작업을 전송합니다...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"❌ Fal API 에러 발생 ({response.status_code}): {response.text}")
            return "https://www.w3schools.com/html/mov_bbb.mp4"

        data = response.json()
        status_url = data.get("status_url")
        response_url = data.get("response_url")
        
        print(f"🔄 렌더링 작업이 큐에 등록되었습니다! (보통 1~2분 소요)")

        # 2. 결과 대기 (Polling) - 5초마다 확인 (최대 5분 대기)
        for attempt in range(60):
            time.sleep(5)
            
            poll_res = requests.get(status_url, headers=headers)
            if poll_res.status_code != 200:
                continue
                
            poll_data = poll_res.json()
            status = poll_data.get("status")
            
            if status == "COMPLETED":
                # 작업이 완료되면 response_url에서 최종 결과를 가져옵니다.
                final_res = requests.get(response_url, headers=headers)
                final_data = final_res.json()
                
                # 영상 URL 추출 시도 (Fal의 Kling 모델 결과물 경로)
                video_url = final_data.get("video", {}).get("url")
                
                # 만약 video 안에 없으면 그냥 url 속성이나 최상위 요소들을 다 뒤져봅니다.
                if not video_url and "url" in final_data:
                    video_url = final_data["url"]
                
                if video_url:
                    print(f"\n✅ 진짜 AI 영상(Kling) 렌더링 성공!!! 🎉🎉🎉")
                    print(f"🎥 영상 URL: {video_url}")
                    return video_url
                else:
                    print(f"\n⚠️ 작업은 완료되었으나 영상 URL을 찾을 수 없습니다.")
                    return "https://www.w3schools.com/html/mov_bbb.mp4"
                
            elif status == "FAILED":
                print(f"\n❌ Fal.ai 렌더링 실패: {poll_data}")
                return "https://www.w3schools.com/html/mov_bbb.mp4"
                
            else:
                elapsed_time = (attempt + 1) * 5
                print(f"  [{attempt+1}/60] 초고속 렌더링 중... (경과 시간: {elapsed_time}초)")

        print("❌ 영상 생성 시간이 5분을 초과하여 대기를 중단합니다.")
        return "https://www.w3schools.com/html/mov_bbb.mp4"

    except Exception as e:
        print(f"❌ 요청 중 시스템 에러 발생: {str(e)}")
        return "https://www.w3schools.com/html/mov_bbb.mp4"