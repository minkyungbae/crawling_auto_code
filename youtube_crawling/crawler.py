from .models import YouTubeVideo, YouTubeProduct
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import time
import re
from typing import List, Tuple, Union


# ----------------------------- 파싱 함수 -----------------------------

def parse_subscriber_count(text):
    match = re.search(r'([\d\.]+)([천만]?)명', text)
    if not match:
        return "0"

    number = float(match.group(1))
    unit = match.group(2)

    if unit == '천':
        number *= 1_000
    elif unit == '만':
        number *= 10_000

    return f"{int(number):,}"


def parse_upload_date(text: str) -> Union[str, None]:
    if m := re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', text):
        year, month, day = m.groups()
        return f"{year}{int(month):02d}{int(day):02d}"
    elif m := re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text):
        year, month, day = m.groups()
        return f"{year}{int(month):02d}{int(day):02d}"
    return None


def parse_view_count(text: str) -> Union[int, None]:
    if match := re.search(r'조회수\s*([\d,]+)회', text):
        return int(match.group(1).replace(',', ''))
    return None


def parse_product_count(text: str) -> Union[int, None]:
    if match := re.search(r'(\d+)\s*개\s*제품', text):
        return int(match.group(1))
    return None


def extract_video_info(info_texts: List[str]) -> Tuple[Union[int, None], str, Union[int, None]]:
    view_count = None
    upload_date = "업로드 날짜 정보 못 찾음"
    product_count = None

    for raw in info_texts:
        soup = BeautifulSoup(raw, 'html.parser')
        text = soup.get_text(separator=' ').strip()

        view_count = view_count or parse_view_count(text)
        upload_date = parse_upload_date(text) or upload_date
        product_count = product_count or parse_product_count(text)

    return view_count, upload_date, product_count


# ---------------------- 수집 기능 분리 ----------------------

def extract_basic_video_info(driver):
    try:
        title = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.style-scope.ytd-watch-metadata yt-formatted-string"))
        ).text.strip()
    except Exception:
        title = "제목 수집 실패"

    try:
        channel_name = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "yt-formatted-string#text a.yt-simple-endpoint"))
        ).text.strip()
    except Exception:
        channel_name = "채널명 수집 실패"

    try:
        subscriber_text = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#owner-sub-count"))
        ).text.strip()
        subscriber_count = parse_subscriber_count(subscriber_text)
    except Exception:
        subscriber_count = "구독자 수 수집 실패"

    return title, channel_name, subscriber_count


def click_show_more_and_get_description(driver):
    try:
        body = driver.find_element(By.TAG_NAME, 'body')
        for _ in range(3):
            body.send_keys(Keys.END)
            time.sleep(1)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "description-inline-expander"))
        )

        expand_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-button#expand"))
        )
        driver.execute_script("arguments[0].click();", expand_button)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "description-inline-expander")))

    except Exception:
        pass

    try:
        description = driver.find_element(By.ID, "description-inline-expander").text
        if not description.strip():
            description = "더보기란에 설명 없음"
    except Exception:
        description = "더보기란에 설명 없음"

    return description


def extract_products_and_metadata(driver, video_id, title, channel_name, subscriber_count, description):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    info_texts = [span.get_text(strip=True) for span in soup.select("span.style-scope.yt-formatted-string.bold") if span.get_text(strip=True)]

    view_count, upload_date, product_count = extract_video_info(info_texts)
    today_str = datetime.today().strftime('%Y%m%d')
    base_url = f"https://www.youtube.com/watch?v={video_id}"

    product_info_list = []
    product_data = {
        "video_id": video_id,
        "title": title,
        "channel_name": channel_name,
        "subscriber_count": subscriber_count,
        "view_count": view_count,
        "upload_date": upload_date,
        "extracted_date": today_str,
        "video_url": base_url,
        "product_count": product_count,
        "description": description,
    }

    try:
        products = soup.select("ytd-merch-shelf-renderer")
        print(f"  - 🛍️ 제품 블록 개수: {len(products)}")

        for i, p in enumerate(products):
            try:
                image_tag_wrapper = p.find(attrs={'class': 'product-item-image style-scope ytd-merch-shelf-item-renderer no-transition'})
                image_tag = image_tag_wrapper.find(attrs={'class': 'style-scope yt-img-shadow'}) if image_tag_wrapper else None
                image_url = image_tag.get("src") if image_tag and hasattr(image_tag, "get") else None

                product_name_tag = p.find(attrs={'class': 'small-item-hide product-item-title style-scope ytd-merch-shelf-item-renderer'})
                product_name = product_name_tag.text.strip() if product_name_tag else None

                price_tag = p.find(attrs={'class': 'product-item-price style-scope ytd-merch-shelf-item-renderer'})
                price = price_tag.text.replace("₩", "").strip() if price_tag else None

                merchant_tag = p.find(attrs={'class': 'product-item-description style-scope ytd-merch-shelf-item-renderer'})
                merchant = merchant_tag.text if merchant_tag else None

                print(f"    • 상품 {i+1}: {product_name} | 가격: {price} | 판매처: {merchant}")

                product_info_list.append({**product_data,
                    "product_image_link": image_url,
                    "product_name": product_name,
                    "product_price": price,
                    "product_link": merchant})

            except Exception as e:
                print(f"    ⚠️ 상품 파싱 실패: {e}")

        if not products:
            print("  - ⚠️ 상품 없음 → 기본 정보만 저장")
            product_info_list.append({**product_data,
                "product_image_link": None,
                "product_name": None,
                "product_price": None,
                "product_link": None})

    except Exception as e:
        print(f"  - ⚠️ 전체 상품 정보 파싱 실패: {e}")
        product_info_list.append({**product_data,
            "product_image_link": None,
            "product_name": None,
            "product_price": None,
            "product_link": None})

    return pd.DataFrame(product_info_list)


# ---------------------- 메인 진입 함수 ----------------------

def collect_video_data(driver, video_id, index=None, total=None):
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    driver.get(base_url)

    if index is not None and total is not None:
        print(f"\n📹 ({index}/{total}) 크롤링 중: {video_id}")

    title, channel_name, subscriber_count = extract_basic_video_info(driver)
    print(f"  - 제목: {title} | 채널: {channel_name} | 구독자: {subscriber_count}")

    description = click_show_more_and_get_description(driver)
    df = extract_products_and_metadata(driver, video_id, title, channel_name, subscriber_count, description)

    return df


# ---------------------- DB 저장 함수 ----------------------

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
        subscriber_count=row['subscriber_count'],
        video_url=row['video_url'],
        title=row['title'],
        view_count=row['view_count'],
        product_count=row['product_count'],
        description=row['description']
    )

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