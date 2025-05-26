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
            crawl_channel_videos(url, export_dir, format_channel_name)
            
            logger.info(f"✅ 채널 완료: {url}")
        except Exception as e:
            logger.error(f"❌ 오류 발생 - {url}: {e}")
        time.sleep(3)
