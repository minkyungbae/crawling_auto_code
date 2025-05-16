from .models import YouTubeVideo, YouTubeProduct
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import pandas as pd
from datetime import datetime

def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # API 서버에서는 GUI 없음
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 제품 정보 수집 함수
def get_product_info(soup):
    try:
        product_items = soup.select("ytd-product-item-renderer")
        return len(product_items)
    except Exception:
        return 0

# 메인 크롤링 함수
def collect_video_data(driver, video_id):
    base_url = "https://www.youtube.com/watch?v="
    driver.get(base_url + video_id)
    wait = WebDriverWait(driver, 10)

    # 제목 수집
    try:
        title_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.title')))
        title = title_element.text.strip()
    except Exception:
        title = "제목 수집 실패"

    # 채널명
    try:
        channel_element = driver.find_element(By.CSS_SELECTOR, "ytd-channel-name a")
        channel_name = channel_element.text.strip()
    except Exception:
        channel_name = "채널명 수집 실패"

    # 구독자 수
    try:
        subscriber_element = driver.find_element(By.CSS_SELECTOR, "#owner-sub-count")
        subscriber_count = subscriber_element.text.strip()
    except Exception:
        subscriber_count = "구독자 수 수집 실패"

    # 조회수 및 업로드일
    try:
        view_count_element = driver.find_element(By.CSS_SELECTOR, "span.view-count")
        view_count = view_count_element.text.strip()
    except Exception:
        view_count = "조회수 수집 실패"

    try:
        upload_date_element = driver.find_element(By.CSS_SELECTOR, "#info-strings yt-formatted-string")
        upload_date = upload_date_element.text.strip()
    except Exception:
        upload_date = "업로드일 수집 실패"

    # 스크롤하여 더보기 버튼 클릭
    try:
        time.sleep(1)
        body = driver.find_element(By.TAG_NAME, 'body')
        for _ in range(3):
            body.send_keys(Keys.END)
            time.sleep(1)

        more_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-button#more")))
        driver.execute_script("arguments[0].click();", more_button)
        time.sleep(2)
    except Exception:
        pass  # 더보기 클릭 실패는 무시

    # HTML 파싱
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # 더보기 설명
    try:
        description_element = soup.select_one("#description yt-formatted-string")
        description_text = description_element.get_text(separator="\n").strip()
    except Exception:
        description_text = "설명 수집 실패"

    # 상품 개수
    product_count = get_product_info(soup)

    # DB 저장
    data = {
        "video_id": video_id,
        "title": title,
        "channel_name": channel_name,
        "subscriber_count": subscriber_count,
        "view_count": view_count,
        "upload_date": upload_date,
        "extracted_date": datetime.today().date(),
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "product_count": product_count,
        "description": description_text,
        # 제품 정보
        "product_image_link": None,
        "product_name": "없음",
        "product_price": "0",
        "product_link": None,
    }

    df = pd.DataFrame([data])
    return df


# DB에 저장하는 함수
def save_youtube_data_to_db(dataframe):
    for _, row in dataframe.iterrows():
        video_url = row['video_url']

        # 중복 방지: 영상 링크로 유일성 확인
        if YouTubeVideo.objects.filter(영상_링크=video_url).exists():
            print(f"⚠️ 이미 존재하는 영상입니다: {video_url}")
            continue

        video = YouTubeVideo.objects.create(
            extracted_date=datetime.strptime(str(row['extracted_date']), "%Y%m%d").date(),
            upload_date=datetime.strptime(str(row['upload_date']), "%Y%m%d").date(),
            channel_name=row['channel_name'],
            title=row['title'],
            video_url=video_url,
            subscriber_count=row['subscriber_count'],
            view_count=row['view_count'],
            product_count=row['product_count'],
            description=row['description']
        )

        # 제품 정보 저장
        # 제품 정보 저장
        if pd.notna(row['product_name']) and row['product_name'] != "없음":
            YouTubeProduct.objects.create(
                video=video,
                product_image_link=row.get('product_image_link', None),
                product_name=row['product_name'],
                product_price=row['product_price'],
                product_link=row.get('product_link', None),
            )
