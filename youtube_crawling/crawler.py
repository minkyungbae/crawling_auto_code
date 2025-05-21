from .models import YouTubeVideo, YouTubeProduct
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Tuple, Union, Dict
import pandas as pd
import logging
import time
import json
import re

logger = logging.getLogger(__name__)  # 모듈 전용 로거 생성

def crawl_youtube():
    logger.info("유튜브 크롤링을 시작합니다.")
    logger.warning("테스트 경고 메시지입니다.")
    logger.info("유튜브 크롤링을 완료했습니다.")



# ----------------------------- ⬇️ 파싱 함수(업로드일 날짜 표기, 조회수, 제품 수) -----------------------------

def parse_subscriber_count(text: str) -> str:
    """구독자 수 텍스트를 숫자 형태로 변환 (예: 1.2만명 -> 12000)"""
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

# ---------------------- ⬇️ 업로드 날짜 문자열을 'YYYYMMDD' 형식으로 변환 ----------------------
def parse_upload_date(text: str) -> Union[str, None]:

    if m := re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', text):
        year, month, day = m.groups()
        return f"{year}{int(month):02d}{int(day):02d}"
    elif m := re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text):
        year, month, day = m.groups()
        return f"{year}{int(month):02d}{int(day):02d}"
    return None

# ---------------------- ⬇️ 조회수 텍스트에서 숫자만 추출 (예: 조회수 1,234회 -> 1234) ----------------------
def parse_view_count(text: str) -> Union[int, None]:

    if match := re.search(r'조회수\s*([\d,]+)회', text):
        return int(match.group(1).replace(',', ''))
    return None


# ---------------------- ⬇️ 제품 개수 텍스트에서 숫자 추출 (예: 5개 제품) ----------------------
def parse_product_count(text: str) -> Union[int, None]:

    if match := re.search(r'(\d+)\s*개\s*제품', text):
        return int(match.group(1))
    return None

# ---------------------- ⬇️ 조회수, 업로드일, 제품 개수 파싱 ----------------------
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


# ---------------------- ⬇️ 영상 기본 정보: 제목, 채널명, 구독자 수 ----------------------

def extract_basic_video_info(driver) -> Tuple[str, str, str]:

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


# ---------------------- ⬇️ 더보기 클릭 및 더보기란 텍스트 추출 ----------------------
def click_show_more_and_get_description(driver) -> str:

    try:
        body = driver.find_element(By.TAG_NAME, 'body')
        for _ in range(3):  # 스크롤을 내려서 '더보기' 버튼 나오게 유도
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

    except Exception as e:
        logging.error(f"❌ 더보기 버튼 클릭 실패: {e}")

    try:
        description = driver.find_element(By.ID, "description-inline-expander").text
        if not description.strip():
            description = "더보기란에 설명 없음"
    except Exception:
        description = "더보기란에 설명 없음"

    return description

#--------------------------------------- 제품 정보를 json으로 찾아서 갖고 오기 -------------------------------------
def extract_products_from_json(driver) -> list:
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    html_text = soup.prettify()

    def extract_json_block(text: str, key: str) -> str:
        """
        JSON 배열 블록을 중괄호/대괄호 균형으로 안전하게 추출
        """
        pattern = rf'"{key}":\s*(\[[\s\S]*?\])'
        match = re.search(pattern, text)
        if not match:
            return None

        start = match.start(1)
        stack = []
        for i in range(start, len(text)):
            if text[i] == '[':
                stack.append('[')
            elif text[i] == ']':
                stack.pop()
                if not stack:
                    return text[start:i+1]
        return None

    products_json_text = extract_json_block(html_text, "productsData")
    if not products_json_text:
        logging.warning("⚠️ productsData 블록 없음: 이 영상에는 제품 정보가 포함되지 않았을 수 있습니다.")
        return []

    try:
        products = json.loads(products_json_text)
    except json.JSONDecodeError as e:
        logging.error(f"❌ JSON 파싱 오류: {e}")
        with open("error_products.json", "w", encoding="utf-8") as f:
            f.write(products_json_text)
        return []

    extracted = []

    for i, item in enumerate(products):
        renderer = item.get("productListItemRenderer", {})

        # ⬇️ 제품명
        product_name = renderer.get("title", {}).get("simpleText")
        if product_name:
            product_name = product_name.lstrip() # 맨 앞 공백만 제거


        # ⬇️ 가격
        price_info = renderer.get("price")
        price = price_info.get("simpleText") if isinstance(price_info, dict) else price_info
        if price:
            price = price.replace(",", "").replace("₩", "").strip()


        # ⬇️ 판매처 찾기
        commands = renderer.get("onClickCommand", {}) \
            .get("commandExecutorCommand", {}) \
            .get("commands", [])

        merchant_link = None
        for cmd in commands:
            url = cmd.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url")
            if url:
                merchant_link = url
                break

        # ⬇️ HTML에서 판매처 링크를 보완 추출
        if not merchant_link:
            descriptions = soup.select("div.product-item-description")
            if i < len(descriptions):
                merchant_text = descriptions[i].get_text(strip=True)
                if merchant_text:
                    # http 없는 링크 처리
                    merchant_link = (
                        "https://" + merchant_text if not merchant_text.startswith("http") else merchant_text
                    )
        
        # ⬇️ 제품 사진 찾기
        thumbnails = renderer.get("thumbnail", {}).get("thumbnails", [])

        # 256px 제품 사진이 없을 경우 첫 번째 이미지 fallback
        image_url = None
        for thumb in thumbnails:
            if thumb.get("width") == 256:
                image_url = thumb.get("url")
                break
        if not image_url and thumbnails:
            image_url = thumbnails[0].get("url")

        logging.info(f"✅ 상품 {i+1}: {product_name}, 가격: {price}, 판매처: {merchant_link}, 이미지: {image_url}")
        extracted.append({
            "product_name": product_name,
            "product_price": price,
            "product_link": merchant_link,
            "product_image_link": image_url,
        })

    return extracted

#--------------------------------------- ⬇️ product 추출 -------------------------------------
def extract_products_and_metadata(driver, video_id: str, title: str, channel_name: str, subscriber_count: str, description: str) -> List[Dict]:
    """
    영상 페이지 전체 HTML을 파싱하여 제품 정보 및 메타데이터 추출 후 DataFrame 반환
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    info_texts = [span.get_text(strip=True) for span in soup.select("span.style-scope.yt-formatted-string.bold") if span.get_text(strip=True)]
    
    # ----------------------------디버깅 확인하기 ------------------------------------
    # with open("youtube_product_html.txt", "w", encoding="utf-8") as f:
    #     f.write(soup.prettify())
    # print("HTML 구조가 'youtube_product_html.txt' 파일에 저장되었습니다.")
    # ----------------------------디버깅 확인하기 끝 ------------------------------------

    view_count, upload_date, product_count = extract_video_info(info_texts)
    today_str = datetime.today().strftime('%Y%m%d') # 오늘 날짜(YYYYmmdd)
    base_url = f"https://www.youtube.com/watch?v={video_id}" # 기본 유튜브 영상 틀

    # 페이지 렌더링 대기
    time.sleep(5)

    product_count = product_count or 0
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
        product_info_list = []
        extracted_products = extract_products_from_json(driver)

        for product in extracted_products:
            product_info_list.append({**product_data, **product})

        if not product_info_list:
            product_info_list.append({
                **product_data,
                "product_image_link": None,
                "product_name": "해당 영상에 포함된 제품 없음",
                "product_price": None,
                "product_link": None
                })
        return pd.DataFrame(product_info_list)
    
    except Exception as e:
        logging.error(f"[❌ 예외 발생] {video_id} 처리 중: {e}")

        return [{
            **product_data,
            "product_image_link": None,
            "product_name": "해당 영상에 포함된 제품 없음",
            "product_price": None,
            "product_link": None
        }]
    
    # return pd.DataFrame(product_info_list)


# ----------------------------------------------- ⬇️ 메인 진입 함수 -----------------------------------------------

def collect_video_data(driver, video_id: str, index: int = None, total: int = None) -> pd.DataFrame:
    """
    유튜브 영상 URL 접속 후 데이터 수집 수행
    """
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    driver.get(base_url)

    if index is not None and total is not None:
        logging.info(f"\n📹 ({index}/{total}) 크롤링 중: {video_id}")

    title, channel_name, subscriber_count = extract_basic_video_info(driver)
    logging.info(f"  - 제목: {title} | 채널: {channel_name} | 구독자: {subscriber_count}")

    description = click_show_more_and_get_description(driver)
    df = extract_products_and_metadata(driver, video_id, title, channel_name, subscriber_count, description)

    return df


# -------------------------------------------- ⬇️ DB(sqlite) 저장 함수 ----------------------------------------

def save_youtube_data_to_db(dataframe: pd.DataFrame) -> int:

    if dataframe.empty:
        return 0

    video_id = dataframe.iloc[0]['video_id']

    if YouTubeVideo.objects.filter(video_id=video_id).exists():
        logging.warning(f"⚠️ 이미 존재하는 영상 id입니다: {video_id}")
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

    # 빈 값일 때
    for _, row in dataframe.iterrows():
        product_name = row.get('product_name')

        # 빈 값 처리
        if not product_name or pd.isna(product_name) or product_name.strip() == "":
            product_name = "영상에 포함된 제품 정보 없음"
        
        product_image_link = row.get('product_image_link')
        if not product_image_link or pd.isna(product_image_link) or product_image_link.strip() == "":
            product_image_link = "영상에 포함된 제품 정보 없음"
        
        product_price = row.get('product_price')
        if not product_price or pd.isna(product_price) or product_price.strip() == "":
            product_price = "영상에 포함된 제품 정보 없음"
        
        product_link = row.get('product_link')
        if not product_link or pd.isna(product_link) or product_link.strip() == "":
            product_link = None
            
        YouTubeProduct.objects.create(
            video=video,
            product_image_link=row.get('product_image_link'),
            product_name=product_name,
            product_price=row.get('product_price'),
            product_link=row.get('product_link'),
        )
    logging.info(f"✅ 영상 및 제품 정보 저장 완료: {video_id}")
    return 1

# ------------------------------------- ⬇️ 크롤링된 유튜브 영상을 조회하고 수정하는 코드 ------------------------------
def update_youtube_data_to_db(dataframe: pd.DataFrame) -> int:
    if dataframe.empty:
        return 0

    video_id = dataframe.iloc[0]['video_id']
    
    try:
        video = YouTubeVideo.objects.get(video_id=video_id)
        row = dataframe.iloc[0]

        # 기존 영상 정보 업데이트
        video.extracted_date = row['extracted_date']
        video.upload_date = row['upload_date']
        video.channel_name = row['channel_name']
        video.subscriber_count = row['subscriber_count']
        video.video_url = row['video_url']
        video.title = row['title']
        video.view_count = row['view_count']
        video.product_count = row['product_count']
        video.description = row['description']
        video.save()

        # 기존 제품 정보 삭제 후 새로 저장
        video.products.all().delete()

        # pd.DataFrame == dataframe
        for _, row in dataframe.iterrows():
            product_name = row.get('product_name')
            if product_name and pd.notna(product_name):
                YouTubeProduct.objects.create(
                    video=video,
                    product_image_link=row.get('product_image_link'),
                    product_name=product_name,
                    product_price=row.get('product_price'),
                    product_link=row.get('product_link'),
                )
        logging.info(f"🔁 영상 정보 업데이트 완료: {video_id}")
        return 1

    except YouTubeVideo.DoesNotExist:
        logging.error(f"❌ 해당 video_id에 대한 영상이 없습니다: {video_id}")
        return 0

