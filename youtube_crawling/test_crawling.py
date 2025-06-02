import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging, time
from youtube_crawling.longform_crawler import crawl_channel_videos

'''===================== logging 설정 ====================='''
logger = logging.getLogger(__name__)

# ------------------------------------- ⬇️ 크롤링 메인 실행부 ------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # CSV 저장 디렉토리 설정 및 생성
    export_dir = os.path.join(os.getcwd(), "crawling_result_csv")
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
        logger.info(f"📁 CSV 저장 디렉토리 생성: {export_dir}")

    channel_urls = [
        "https://www.youtube.com/@%EC%B9%A1%EC%B4%89",
    ]

    for channel_url in channel_urls:
        try:
            logger.info(f"🚀 채널 크롤링 시작: {channel_url}")
            crawl_channel_videos(channel_url, export_dir)
            logger.info(f"✅ 채널 크롤링 완료: {channel_url}")

        except Exception as e:
            logger.warning(f"❌ 채널 크롤링 중 오류 발생: {channel_url} - {e}")
        
        time.sleep(1)  # 각 채널 간 1초 쉬었다가 다음 채널 실행