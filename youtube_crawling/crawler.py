from .models import YouTubeVideo, YouTubeProduct
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime

# 제품 정보 수집 함수
def get_product_info(soup):
    try:
        product_items = soup.select("ytd-product-item-renderer")
        return len(product_items)
    except Exception:
        return 0


# 메인 크롤링 함수
def collect_video_data(driver, video_id):
    base_url = "https://www.youtube.com/watch?v={video_id}"
    driver.get(base_url)
    wait = WebDriverWait(driver, 10)

    # 제목 수집
    try:
        title = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.title'))).text.strip()
    except Exception:
        title = "제목 수집 실패"

    # 채널명
    try:
        channel_name = driver.find_element(By.CSS_SELECTOR, "ytd-channel-name a").text.strip()
    except Exception:
        channel_name = "채널명 수집 실패"

    # 구독자 수
    try:
        subscriber_count = driver.find_element(By.CSS_SELECTOR, "#owner-sub-count").text.strip()
    except Exception:
        subscriber_count = "구독자 수 수집 실패"

    # 조회수 및 업로드일
    try:
        view_count_element = driver.find_element(By.CSS_SELECTOR, "span.view-count")
        view_count = view_count_element.text.strip()
    except Exception:
        view_count = "조회수 수집 실패"

    try:
        upload_date = driver.find_element(By.CSS_SELECTOR, "#info-strings yt-formatted-string").text.strip()
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
        description_text = soup.select_one("#description yt-formatted-string").get_text(separator="\n").strip
    except Exception:
        description_text = "설명 수집 실패"

    # 여러 제품 수집
    product_items = soup.select("ytd-product-item-renderer")
    rows = []

    if product_items:
        for product in product_items:
            try:
                name = product.select_one("yt-formatted-string").text.strip()
            except:
                name = "이름 수집 실패"

            try:
                price = product.select_one("#price").text.strip()
            except:
                price = "가격 수집 실패"

            try:
                link = product.select_one("a")["href"]
            except:
                link = None

            try:
                image = product.select_one("img")["src"]
            except:
                image = None
    
            rows.append({
                    "video_id": video_id,
                    "title": title,
                    "channel_name": channel_name,
                    "subscriber_count": subscriber_count,
                    "view_count": view_count,
                    "upload_date": upload_date,
                    "extracted_date": datetime.today().date(),
                    "video_url": base_url,
                    "product_count": len(product_items),
                    "description": description_text,
                    "product_name": name,
                    "product_price": price,
                    "product_link": link,
                    "product_image_link": image,
                })

    else:
        # 제품이 없을 경우에도 영상 정보는 저장
        rows.append({
            "video_id": video_id,
            "title": title,
            "channel_name": channel_name,
            "subscriber_count": subscriber_count,
            "view_count": view_count,
            "upload_date": upload_date,
            "extracted_date": datetime.today().date(),
            "video_url": base_url,
            "product_count": 0,
            "description": description_text,
            "product_name": None,
            "product_price": None,
            "product_link": None,
            "product_image_link": None,
        })
    return pd.DataFrame(rows)


# DB에 저장하는 함수
def save_youtube_data_to_db(dataframe):
    if dataframe.empty:
        return 0

    video_id = dataframe.iloc[0]['video_id']

    if YouTubeVideo.objects.filter(video_id=video_id).exists():
        print(f"⚠️ 이미 존재하는 영상 id입니다: {video_id}")
        return 0
    

    row = dataframe.iloc[0]
    video = YouTubeVideo.objects.create(
        video_id=video_id,
        extracted_date=row['extracted_date'],
        upload_date=row['upload_date'],
        channel_name=row['channel_name'],
        title=row['title'],
        video_url=row['video_url'],
        subscriber_count=row['subscriber_count'],
        view_count=row['view_count'],
        product_count=row['product_count'],
        description=row['description']
    )

    # 여러 제품 저장
    for _, row in dataframe.iterrows():
        if pd.notna(row['product_name']) and row['product_name']:
            YouTubeProduct.objects.create(
                video=video,
                product_image_link=row.get('product_image_link'),
                product_name=row['product_name'],
                product_price=row['product_price'],
                product_link=row.get('product_link'),
            )

    return 1
