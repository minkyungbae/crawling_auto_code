# --------- 프로젝트에서 import한 목록 ---------------
from .models import YouTubeVideo, YouTubeProduct
from config import settings
# --------- selenium에서 import한 목록 ---------------
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# --------- webdriver에서 import한 목록 ---------------
from webdriver_manager.chrome import ChromeDriverManager
from contextlib import contextmanager # 드라이버 관리하는 태그
# --------- 그 외 크롤링 코드를 위해 import한 목록 ---------------
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Union, Dict, Optional
from urllib.parse import urlparse, unquote
from slugify import slugify
import pandas as pd
import logging, time, re, json, os, urllib.parse


# ----------------------------- ⬇️ logging 설정 -----------------------------

logger = logging.getLogger(__name__)  # logger.info(), logger.warning()만 써야해용

# --------- driver 한 번으로 정의 ---------------
@contextmanager
def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    # User-Agent 설정
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    logger.info("🟢 ChromeDriver 실행")
    try:
        yield driver
    except Exception as e:
        logger.error(f"❌ WebDriver 예외 발생: {e}", exc_info=True)
        raise
    finally:
        driver.quit()
        logger.info("🛑 ChromeDriver 종료")


# ---------------------- ⬇️ URL 정리하는 함수 추가 ----------------------
def clean_youtube_url(url: str) -> str:
    """YouTube URL을 정리하는 함수"""
    try:
        # URL에서 'watch?v=' 부분이 중복되는지 확인
        if url.count('watch?v=') > 1:
            # 마지막 'watch?v=' 이후의 부분만 가져옴
            video_id = url.split('watch?v=')[-1]
            return f'https://www.youtube.com/watch?v={video_id}'
        return url
    except Exception as e:
        logger.error(f"❌ URL 정리 중 에러 발생: {e}")
        return url


# ----------------------------- ⬇️ 유튜브 채널의 영상 전부 가지고 오는 함수 -----------------------------
def get_all_video_ids(driver, channel_url):
    logger.info(f"🔍 채널 영상 ID 수집 시작: {channel_url}")

    try:
        videos_url = channel_url.rstrip('/') + "/videos"
        driver.get(videos_url)
        time.sleep(5)  # 페이지 로딩을 위한 대기 시간 증가

        video_urls = set()
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        
        SCROLL_PAUSE_TIME = 3
        MAX_RETRIES = 5
        retries = 0

        while True:
            # 스크롤 다운
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)
            
            # 영상 링크 수집
            elements = driver.find_elements(By.CSS_SELECTOR, 'a#video-title-link')
            for elem in elements:
                href = elem.get_attribute("href")
                if href and "watch?v=" in href:
                    # URL 정리 함수 적용
                    cleaned_url = clean_youtube_url(href)
                    video_urls.add(cleaned_url)

            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                retries += 1
                if retries >= MAX_RETRIES:
                    break
            else:
                retries = 0
            last_height = new_height

        video_count = len(video_urls)
        if video_count > 0:
            logger.info(f"✅ 총 {video_count}개의 영상 URL 수집 완료")
        else:
            logger.warning("⚠️ 수집된 영상이 없습니다")

        return list(video_urls)
    except Exception as e:
        logger.error(f"❌ 영상 ID 수집 중 에러 발생: {e}")
        return []

# ----------------------------- ⬇️ element의 text 추출하는 유틸 함수 -----------------------------
def safe_get_text(element, default=""):
    try:
        return element.text.strip()
    except Exception:
        return default


# ---------------------- ⬇️ 조회수 텍스트에서 숫자만 추출 (예: 조회수 1,234회 -> 1234) ----------------------
def parse_view_count(text: str) -> int:
    try:
        if not text:
            return 0
        cleaned = text.replace("조회수", "").replace("회", "").replace(",", "").strip()
        return int(cleaned)
    except ValueError as e:
        logger.warning(f"⚠️ 조회수 파싱 실패: '{text}', 이유: {e}")
        return 0


# ----------------------------- ⬇️ 구독자 수 텍스트를 숫자 형태로 변환 (예: 1.2만명 -> 12000) -----------------------------
def parse_subscriber_count(text: str) -> int:
    try:
        text = text.replace("명", "").replace(",", "").strip()
        if "천" in text:
            return int(float(text.replace("천", "")) * 1_000)
        elif "만" in text:
            return int(float(text.replace("만", "")) * 10_000)
        return int(text)
    except Exception as e:
        logger.warning(f"⚠️ 구독자 수 파싱 실패: '{text}', 이유: {e}")
        return 0


# ---------------------- ⬇️ 업로드 날짜 문자열을 'YYYYMMDD' 형식으로 변환 ----------------------
def parse_upload_date(text: str) -> Union[str, None]:
    try:
        if match := re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', text):
            year, month, day = match.groups()
            return f"{year}{int(month):02d}{int(day):02d}"
        elif match := re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text):
            year, month, day = match.groups()
            return f"{year}{int(month):02d}{int(day):02d}"
    except:
        logger.warning(f"⚠️ 날짜를 형식 변환 못했는뎅??")
    return None


# ---------------------- ⬇️ 제품 개수 텍스트에서 숫자 추출 (예: 5개 제품) ----------------------
def parse_product_count(text: str) -> Union[int, None]:
    try:
        if match := re.search(r'(\d+)\s*개\s*제품', text):
            return int(match.group(1))
    except:
        logger.warning(f"⚠️ 제품 개수 못 찾았는뎅??")
    return None

# ---------------------- ⬇️ 더보기 클릭 및 더보기란 텍스트 추출 ----------------------
def click_description(driver) -> str:
    try:
        # 스크롤을 내림으로써 버튼이 로드되도록 유도
        body = driver.find_element(By.TAG_NAME, 'body')
        for _ in range(3):
            body.send_keys(Keys.END)
            time.sleep(1)
        # 더보기 버튼 클릭 시도 (2가지 selector)
        try:
            expand_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#expand"))
            )
            driver.execute_script("arguments[0].click();", expand_button)
            logger.info("더보기 버튼 클릭 성공")
        except Exception:
            logger.info("더보기 버튼 없음 또는 클릭 실패, 무시하고 진행")

        selectors = [
            "#description-text-container",
            "#description-inline-expander"
        ]
        for selector in selectors:
            try:
                elem = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                desc = elem.text.strip()
                if desc:
                    return desc
            except Exception:
                logger.debug(f"'{selector}'로 설명란 추출 실패, 다음 시도")
        logger.warning("더보기란에 설명이 없음")
        return "더보기란에 설명 없음"
        
    except Exception as e:
        logger.error(f"❌ 설명 추출 실패: {e}", exc_info=True)
        return "더보기란에 설명 없음"
    
    
#--------------------------------------- 제품 정보 추출 -------------------------------------
def extract_products_from_dom(soup: BeautifulSoup) -> list[dict]:
    products = []
    try:
        script_tags = soup.find_all("script")
        for tag in script_tags:
            if "var productsData" in tag.text:
                json_text = tag.string.split("var productsData = ")[1].split(";</script>")[0]
                product_data = json.loads(json_text)
                for product in product_data:
                    products.append({
                        "title": product.get("title", "없음"),
                        "url": product.get("url", "없음"),
                        "price": product.get("price", "없음"),
                        "imageUrl": product.get("imageUrl", "없음"),
                    })
                break
    except Exception as e:
        logger.error(f"❌ 제품 정보 추출 중 오류 발생: {e}")
    return products
    

# ---------------------- ⬇️ 영상 기본 정보: 제목, 채널명, 구독자 수, 조회수, 업로드일, 제품 개수 ----------------------
def base_youtube_info(driver, video_url: str) -> pd.DataFrame:
    logger.info("Crawling video: %s", video_url)
    today_str = datetime.today().strftime('%Y%m%d')

    try:
        driver.get(video_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "description")))
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # 메타데이터 추출
        video_id = video_url.split("v=")[-1]
        # 제목
        title_tag = soup.select_one("h1.title")
        title = title_tag.text.strip() if title_tag else "제목 없음"

        # 채널명
        channel_tag = soup.select_one("ytd-channel-name a")
        channel_name = channel_tag.text.strip() if channel_tag else "채널 없음"

        # 구독자 수
        sub_tag = soup.select_one("yt-formatted-string#owner-sub-count")
        subscriber_count = sub_tag.text.strip() if sub_tag else "구독자 수 없음"

        # 조회수
        view_count_tag = soup.select_one("span.view-count")
        view_count = view_count_tag.text.strip() if view_count_tag else "조회수 없음"

        # 업로드일
        upload_date_tag = soup.select_one("div#info-strings yt-formatted-string")
        upload_date = upload_date_tag.text.strip() if upload_date_tag else "날짜 없음"

        # 설명란
        desc_tag = soup.select_one("yt-formatted-string.content")
        description = desc_tag.text.strip() if desc_tag else "설명 없음"

        # 제품 추출
        products = extract_products_from_dom(soup)
        product_count = len(products)

        # 기본 데이터 세트
        base_data = {
            "youtube_id": video_id,
            "title": title,
            "channel_name": channel_name,
            "subscribers": subscriber_count,
            "view_count": view_count,
            "upload_date": upload_date,
            "extracted_date": today_str,
            "video_url": video_url,
            "description": description,
            "product_count": product_count,
            "products": [],
        }

        if products:
            for p in products:
                base_data["products"].append({
                    "name": p.get("title", ""),
                    "link": p.get("url", ""),
                    "price": p.get("price", None),
                    "image": p.get("imageUrl", None)
                })
        else:
            base_data["products"] = [{
                "product_name": "제품 없음",
                "product_link": None,
                "product_price": None,
                "product_image_link": None
            }]

            
        logger.info(f"✅ 영상 정보 및 제품 {product_count}개 수집 완료")
        return pd.DataFrame([base_data])
    
    except Exception as e:
        logger.error(f"❌ base_youtube_info 예외: {e}", exc_info=True)
        return pd.DataFrame()

# ----------------------------------------------- ⬇️ 유튜브 영상 URL 접속 후 데이터 수집 수행 -----------------------------------------------

def collect_video_data(driver, video_id: str, index: int = None, total: int = None) -> pd.DataFrame:
    # URL 정리
    base_url = clean_youtube_url(f"https://www.youtube.com/watch?v={video_id}")
    
    try:
        driver.get(base_url)
        if index is not None and total is not None:
            logger.info(f"\n📹 ({index}/{total}) 크롤링 중: {video_id}")

        df = base_youtube_info(driver, base_url)

        logger.info(f"📦 수집된 제품 개수: {len(df)}")
        if df.empty:
            logger.warning(f"⚠️ 데이터프레임이 비어 있음: {video_id}")

        return df
    
    except Exception as e:
            logger.error(f"❌ 예외 발생 - collect_video_data(): {video_id} | 에러: {e}")
            return None

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
        logger.info(f"🔁 영상 정보 업데이트 완료: {video_id}")
        return 1

    except YouTubeVideo.DoesNotExist:
        logger.warning(f"❌ 해당 video_id에 대한 영상이 없습니다: {video_id}")
        return 0

# ------------------------------------- ⬇️ 채널 URL에서 고유한 ID 추출 (예: UCxxxx 또는 @handle 형식) ------------------------------
def get_channel_id_from_url(channel_url):
    parsed = urlparse(channel_url)
    parts = parsed.path.strip("/").split("/")
    return parts[-1] if parts else "unknown_channel"

# ------------------------------------- ⬇️ 채널 URL에서 고유한 ID 추출 (예: UCxxxx 또는 @handle 형식) ------------------------------
def get_channel_name(driver, channel_url):
    """
    채널 이름을 YouTube 채널 페이지에서 가져옴.
    """
    driver.get(channel_url)
    driver.implicitly_wait(5)
    try:
        title_element = driver.find_element("xpath", '//meta[@property="og:title"]')
        channel_name = title_element.get_attribute("content")
        return slugify(channel_name)  # 파일명에 사용할 수 있도록 slugify 처리
    except Exception as e:
        logger.warning(f"⚠️ 채널명 추출 실패: {e}")
        return "unknown_channel"
    
# ------------------------------------- ⬇️ 엑셀로 저장하는 함수 ------------------------------
def save_to_excel(df: pd.DataFrame, file_path: str):
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        if file_path.lower().endswith(".xlsx"):
            file_path = file_path[:-5] + f"_{today_str}.xlsx"
        else:
            file_path = file_path + f"_{today_str}.xlsx"

        df.to_excel(file_path, index=False)
        logger.info(f"💾 엑셀 저장 완료: {file_path}")
    except Exception as e:
        logger.error(f"❌ 엑셀 저장 실패: {e}", exc_info=True)

# ------------------------------------- ⬇️ DB에 저장하는 함수 ------------------------------
def save_to_db(data: dict):
    from django.db import transaction

    if data.empty:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return
    
    failed_ids = []

    with transaction.atomic():
        try:
            # DataFrame의 첫 번째 행을 딕셔너리로 변환
            data_dict = data.iloc[0].to_dict()
            video_id = data_dict.get("youtube_id")
            if not video_id:
                logger.warning("⚠️ video_id 없음, 저장 불가")
                return
            
            video_data = {
                "extracted_date": data_dict.get("extracted_date"),
                "upload_date": data_dict.get("upload_date"),
                "channel_name": data_dict.get("channel_name"),
                "subscriber_count": data_dict.get("subscribers"),
                "title": data_dict.get("title"),
                "view_count": data_dict.get("view_count"),
                "video_url": data_dict.get("video_url"),
                "product_count": data_dict.get("product_count", 0),
                "description": data_dict.get("description"),
            }

            video_obj = YouTubeVideo.objects.filter(video_id=video_id).first()

            if video_obj:
                # 변경된 필드가 있는지 확인
                has_changes = any(
                    getattr(video_obj, field) != value
                    for field, value in video_data.items()
                )
                if has_changes:
                    for field, value in video_data.items():
                        setattr(video_obj, field, value)
                    video_obj.save()
                    logger.info(f"DB 업데이트 완료: {video_id}")
                else:
                    logger.info(f"변경 없음: {video_id}")
            else:
                video_obj = YouTubeVideo.objects.create(video_id=video_id, **video_data)
                logger.info(f"DB 저장 완료: {video_id}")

            # 제품 저장
            products = data_dict.get("products", [])
            for p in products:
                YouTubeProduct.objects.update_or_create(
                    video=video_obj,
                    product_name=p.get("product_name", "제품 없음"),
                    defaults={
                        "product_price": p.get("product_price", None),
                        "product_image_link": p.get("product_image_link", None),
                        "product_link": p.get("product_link", None),
                    }
                )

        except Exception as e:
            logger.error(f"❌ 저장 실패 - video_id: {video_id} | 에러: {e}")
            failed_ids.append(video_id)
        
    # 실패한 video_id 파일로 저장
    if failed_ids:
        with open("logs/failed_ids.txt", "w") as f:
            for vid in failed_ids:
                f.write(f"{vid}\n")
        logger.warning(f"⚠️ 저장 실패한 video_id {len(failed_ids)}개 저장 완료: failed_ids.txt")


# ------------------------------------- ⬇️ 유튜브 채널의 전체 크롤링을 실행하는 함수 ------------------------------
def crawl_channel_videos(channel_url: str, save_path: str):
    with create_driver() as driver:
        video_ids = get_all_video_ids(driver, channel_url)

        total = len(video_ids)
        if total == 0:
            logger.warning("❌ 채널에서 수집된 영상 ID가 없습니다.")
            return
        
        logger.info(f"총 {total}개 영상 크롤링 시작")
        all_data = pd.DataFrame()

        for i, video_id in enumerate(video_ids, start=1):
            try:
                df = collect_video_data(driver, video_id, i, total)
                if df is not None and not df.empty:
                    save_to_db(df)
            except Exception as e:
                logger.error(f"❌ 영상 크롤링 중 에러 발생: {video_id}, 에러: {e}", exc_info=True)

        if not all_data.empty:
            save_to_db(all_data)
            save_to_excel(all_data, save_path)
        else:
            logger.warning("⚠️ 크롤링 결과 데이터 없음")


# 메인 실행부
if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    channel_urls = [
        "https://www.youtube.com/@yegulyegul8256",
        "https://www.youtube.com/@%EC%B9%A1%EC%B4%89",
    ]
    
    export_dir = "exports"
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    for channel_url in channel_urls:
        try:
            logger.info(f"🚀 채널 크롤링 시작: {channel_url}")

            today_str = datetime.datetime.now().strftime("%Y%m%d")
            channel_name = urllib.parse.unquote(channel_url.split("/")[-1])
            save_path = os.path.join(export_dir,f"{channel_name}_{today_str}.xlsx")

            crawl_channel_videos(channel_url, save_path)
            logger.info(f"✅ 채널 크롤링 완료: {channel_url}")

        except Exception as e:
            logger.warning(f"❌ 채널 크롤링 중 오류 발생: {channel_url} - {e}")
        
        time.sleep(3)  # 🔽 각 채널 간 3초 쉬었다가 다음 채널 실행
