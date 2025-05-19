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


# 제품 수 추출 함수
def get_product_info(soup):
    try:
        product_items = soup.select(".ytd-merch-shelf-item-renderer")
        return len(product_items)
    except Exception:
        return 0
    
"""
구독자 수 표기 방식 변환 함수
"""
def parse_subscriber_count(text):
    match = re.search(r'([\d\.]+)([천만]?)명', text) # 숫자+단위 추출
    if not match:
        return "0" # 매칭 안 되면 0 반환

    number = float(match.group(1)) # 숫자 부분 (정수/소수점 포함)
    unit = match.group(2) # 단위: 천/만

    # 단위에 따라 숫자 변환 
    if unit == '천':
        number *= 1_000
    elif unit == '만':
        number *= 10_000

    return f"{int(number):,}"  # 쉼표 넣은 문자열 반환


# 업로드일, 조회수, 제품 수 추출 함수
def extract_video_info(info_texts: List[str]) -> Tuple[str, Union[str, None], Union[int, None]]:
    youtube_view_count = None
    youtube_upload_date = "업로드 날짜 정보 못 찾음"
    youtube_product_count = None


    for text in info_texts:
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text(separator=' ').strip()

        """
        업로드 날짜 변환 코드(숫자일 시, 한국어 표기일 시)
        """
        if m := re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', text):
            year, month, day = m.groups()
            youtube_upload_date = f"{year}{int(month):02d}{int(day):02d}"
        elif m := re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text):
            year, month, day = m.groups()
            youtube_upload_date = f"{year}{int(month):02d}{int(day):02d}"

        """
        조회수
        """
        if match_views := re.search(r'조회수\s*([\d,]+)회', text):
            youtube_view_count = int(match_views.group(1).replace(',', ''))

        """
        제품 개수
        """
        if match_products := re.search(r'(\d+)\s*개\s*제품', text):
            youtube_product_count = int(match_products.group(1))

    return youtube_view_count, youtube_upload_date, youtube_product_count


# 메인 크롤링 함수
def collect_video_data(driver, video_id):
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    driver.get(base_url)
    wait = WebDriverWait(driver, 10)
    
    """
    제목
    """
    try:
        element = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.style-scope.ytd-watch-metadata yt-formatted-string"))
    )
        title = element.text.strip()
    except Exception as e:
        title = "제목 수집 실패"
        print("Error:", e)
    print("제목:", title)

    """
    채널명
    """
    try:
        element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "yt-formatted-string#text a.yt-simple-endpoint"))
    )
        channel_name = element.text.strip()
    except Exception:
        channel_name = "채널명 수집 실패"

    """
    구독자 수
    """
    try:
        element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#owner-sub-count"))
    )
        subscriber_text = element.text.strip()
        subscriber_count = parse_subscriber_count(subscriber_text)
    except Exception:
        subscriber_count = "구독자 수 수집 실패"

    """
    스크롤하여 더보기 버튼 클릭
    """
    try:
        time.sleep(1)
        body = driver.find_element(By.TAG_NAME, 'body')
        for _ in range(3):
            body.send_keys(Keys.END)
            time.sleep(1)

        # '더보기' 버튼이 포함된 설명 섹션이 로드될 때까지 최대 20초 대기
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "description-inline-expander"))
        )
        # '더보기' 버튼이 클릭 가능 상태가 될 때까지 최대 10초 대기
        expand_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-button#expand"))
        )
        # JavaScript를 사용하여 '더보기' 버튼 클릭 (Selenium 기본 클릭으로 안 되는 경우 대비)
        driver.execute_script("arguments[0].click();", expand_button)

        # 클릭 후 콘텐츠가 로드될 시간을 조금 기다림
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "description-inline-expander")))
        
    except Exception as e:
        print("더보기 버튼 클릭 실패:", e)

    """
    HTML 파싱
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser') # 조회수, 업로드일, 제품 수 추출
    spans = soup.select("span.style-scope.yt-formatted-string.bold")
    info_texts = [span.get_text(strip=True) for span in spans if span.get_text(strip=True)] # 공백 제외하고 실제 텍스트만 

    """
    더보기 설명란 들고 오기
    """
    try:
        description = driver.find_element(By.ID, "description-inline-expander").text
        # 설명이 비어있을 경우, 기본 메시지로 대체
        if not description.strip():
            description = "더보기란에 설명 없음"
            
    except Exception as e:
        # 설명란 찾기 실패 또는 텍스트 추출 중 에러 발생 시
        print("더보기 클릭 또는 설명 추출 실패:", e)
        description = "더보기란에 설명 없음" 

    """
    여러 제품 수집
    """
    product_info_list = []

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".product-item.style-scope.ytd-merch-shelf-item-renderer"))) # 제품 정보가 담긴 요소가 페이지에 로드될 때까지 대기
        product_elements = soup.select(".product-item.style-scope.ytd-merch-shelf-item-renderer") # 상품 영역(여러 개일 수 있음) 요소들을 모두 가져오기
        
        """
        제품 이미지 링크, 제품명, 제품 가격, 제품 구매 링크
        """
        for product in product_elements:
            product_img_link = None

            try:
                product_img_link = product.find_element(By.CSS_SELECTOR, "#img").get_attribute("src")
                product_name = product.find_element(By.CSS_SELECTOR, ".product-item-title").text.strip()
                product_price = product.find_element(By.CSS_SELECTOR, ".product-item-price").text.replace("₩", "").strip()
                link_raw = product.find_element(By.CSS_SELECTOR, ".product-item-description").text.strip()
                product_link = link_raw if not link_raw.startswith("http") else link_raw


            except Exception as inner_e:
                print("🔸 일부 제품 정보 추출 실패:", inner_e)
            # try:
            #     """이미지 링크부터 시도"""
            #     img_shadow = product.select_one("yt-img-shadow")
            #     if img_shadow:
            #         product_img = img_shadow.select_one("img#img")

            #         if product_img:
            #             # src, data-src, srcset 속성 중 하나 추출
            #             product_img_link = product_img.get('src') or product_img.get('data-src') or product_img.get('srcset') or None

            #             if not product_img_link:
            #                 style = img_shadow.get('style', '')
            #                 match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
            #                 product_img_link = match.group(1) if match else None

            #         else:
            #             print(f"⚠️ 제품 {idx} : img#img 태그 없음")
            #     else:
            #         print(f"⚠️ 제품 {idx} : yt-img-shadow 태그 없음")
            # except Exception as e:
            #     print(f"❌ 제품 {idx}: 이미지 추출 실패 - {e}")
            
            # # 디버깅
            # print(f"제품 {idx} 최종 이미지 링크: {product_img_link}")

            # """제품명, 제품 가격, 제품 구매 링크"""
            # try:
            #     product_name = product.select_one(".product-item-title").text.strip()
            #     product_price = product.select_one(".product-item-price").text.replace("₩", "").strip()
            #     link_raw = product.select_one(".product-item-description").text.strip()
            #     product_link = link_raw if link_raw.startswith("http") else f"http://{link_raw}"

                # 조회수, 업로드일, 제품 개수 들고오기
                youtube_view_count, youtube_upload_date, youtube_product_count = extract_video_info(info_texts)

                # 추출일 날짜 문자열(YYYYMMDD)
                today_str_four = datetime.today().strftime('%Y%m%d')

                """
                의미있는 값일 시, 저장
                """
                if any([product_img_link, product_name, product_price, product_link]):
                    product_info_list.append({
                        "video_id": video_id,
                        "title": title,
                        "channel_name": channel_name,
                        "subscriber_count": subscriber_count,
                        "view_count": youtube_view_count,
                        "upload_date": youtube_upload_date,
                        "extracted_date": today_str_four,
                        "video_url": base_url,
                        "product_count": youtube_product_count,
                        "description": description,
                        'product_image_link': product_img_link,
                        "product_name": product_name,
                        "product_price": product_price,
                        "product_link": product_link,
                    })

            except Exception as inner_e:
                print("🔸 일부 제품 정보 추출 실패:", inner_e)

        if not product_info_list:
                """
                제품이 없을 경우에도 영상 정보는 저장
                """
                youtube_view_count, youtube_upload_date, youtube_product_count = extract_video_info(info_texts)
                today_str_four = datetime.today().strftime('%Y%m%d')
                product_info_list.append({
                    "video_id": video_id,
                    "title": title,
                    "channel_name": channel_name,
                    "subscriber_count": subscriber_count,
                    "view_count": youtube_view_count,
                    "upload_date": youtube_upload_date,
                    "extracted_date": today_str_four,
                    "video_url": base_url,
                    "product_count": 0,
                    "description": description,
                    "product_name": None,
                    "product_price": None,
                    "product_link": None,
                    "product_image_link": None,
                })
            
    except Exception as e:
        print("제품 정보 추출 실패:", e)

    return pd.DataFrame(product_info_list)


"""
DB에 저장하는 함수
"""
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

    """
    여러 제품 저장
    """
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

