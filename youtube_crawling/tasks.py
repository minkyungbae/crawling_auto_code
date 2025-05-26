from celery import shared_task
from youtube_crawling.crawler import crawl_channel_videos
import logging, time, datetime, urllib.parse, os

logger = logging.getLogger(__name__)

@shared_task
def crawl_channels_task():
    channel_urls = [
        "https://www.youtube.com/@%EC%B9%A1%EC%B4%89",
    ]
    export_dir = "./crawling_result_csv/"
    os.makedirs(export_dir, exist_ok=True)

    today_str = datetime.datetime.now().strftime("%Y%m%d")

    for url in channel_urls:
        try:
            logger.info(f"🚀 채널 시작: {url}")

            # 채널 이름 추출 및 디코딩
            raw_channel_name = urllib.parse.unquote(url.split("/")[-1])
            format_channel_name = "".join(
                c for c in raw_channel_name.replace(" ", "_") if c.isalnum() or c in ('_',)
            ).rstrip()
            
            # 크롤링 시작 전 충분한 대기 시간 확보
            logger.info("⏳ 페이지 로딩 대기 중...")
            time.sleep(5)  # 5초로 증가
            
            crawl_channel_videos(url, export_dir, format_channel_name)
            
            logger.info(f"✅ 채널 완료: {url}")
            
            # 다음 채널 크롤링 전 대기
            logger.info("⏳ 다음 채널 크롤링 전 대기 중...")
            time.sleep(5)  # 5초로 증가
            
        except Exception as e:
            logger.error(f"❌ 오류 발생 - {url}: {e}")
            logger.error("상세 에러:", exc_info=True)
