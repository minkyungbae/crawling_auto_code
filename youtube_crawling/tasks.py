from celery import shared_task
from youtube_crawling.crawler import crawl_channel_videos
import logging, time

logger = logging.getLogger(__name__)

@shared_task
def crawl_channels_task():
    channel_urls = [
        "https://www.youtube.com/@yegulyegul8256",
        "https://www.youtube.com/@%EC%B9%A1%EC%B4%89",
    ]

    for url in channel_urls:
        try:
            logging.info(f"🚀 채널 시작: {url}")
            crawl_channel_videos(url)
            logging.info(f"✅ 채널 완료: {url}")
        except Exception as e:
            logging.error(f"❌ 오류 발생 - {url}: {e}")
        time.sleep(3)
