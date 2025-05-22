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
from typing import List, Union, Dict
from urllib.parse import urlparse
from slugify import slugify
import pandas as pd
import logging, time, re, json, os, urllib.parse


# ----------------------------- ⬇️ logging 설정 -----------------------------

logger = logging.getLogger(__name__)  # logger.info(), logger.warning()만 써야해용

def crawl_youtube():
    logger.info("유튜브 크롤링을 시작합니다.")
    logger.warning("테스트 경고 메시지입니다.")
    logger.info("유튜브 크롤링을 완료했습니다.")


# --------- driver 한 번으로 정의 ---------------
@contextmanager
def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 크롬 창 띄우지 않는 기능(주석처리하면 창 띄워져요)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
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


# ----------------------------- ⬇️ 유튜브 채널의 영상 전부 가지고 오는 함수 -----------------------------

def get_all_video_ids(driver, channel_url) -> List[str]:
    logger.info(f"🔍 채널 영상 ID 수집 시작: {channel_url}")

    try:
        driver.get(channel_url + '/videos')
        time.sleep(2)

        video_ids = set()
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        
        # 스크롤 3번 했는데도 새로고침 안 되면 스크롤 멈춤
        scroll_retries = 3 
        retry_count = 0

        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.documentElement.scrollHeight")

            if new_height == last_height:
                retry_count += 1
                if retry_count >= scroll_retries:
                    logger.info("⚠️ 더 이상 스크롤할 콘텐츠 없음")
                    break
            else:
                retry_count = 0
            last_height = new_height

        soup = BeautifulSoup(driver.page_source, "html.parser")
        video_elements = soup.select("a#video-title")

        video_ids = []
        for element in video_elements:
            href = element.get("href", "")
            if "v=" in href:
                video_id = href.split("v=")[-1].split("&")[0]
                video_ids.append(video_id)
            else:
                logger.warning(f"⚠️ href 형식 이상: {href}")

        logger.info(f"✅ 총 영상 ID {len(video_ids)}개 수집 완료")
        return video_ids
            
    except Exception as e:
        logger.error(f"❌ get_all_video_ids 예외 발생: {e}", exc_info=True)
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
    except ValueError:
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
        title = safe_get_text(soup.select_one("h1.title")) or "제목 수집 실패"
        channel_name = safe_get_text(soup.select_one("#channel-name")) or "채널명 수집 실패"
        subscriber_text = safe_get_text(soup.select_one("#owner-sub-count"))
        subscriber_count = parse_subscriber_count(subscriber_text) if subscriber_text else "구독자 수 수집 실패"
        view_text = safe_get_text(soup.select_one(".view-count"))
        view_count = parse_view_count(view_text)
        upload_date = safe_get_text(soup.select_one("#info-strings yt-formatted-string"))
        description = safe_get_text(soup.select_one("#description"))

        # 기본 데이터 세트
        base_data = {
            "video_id": video_id,
            "title": title,
            "channel_name": channel_name,
            "subscriber_count": subscriber_count,
            "view_count": view_count,
            "upload_date": upload_date,
            "extracted_date": today_str,
            "video_url": video_url,
            "description": description
        }
        # 제품 추출
        products = extract_products_from_dom(soup)
        product_count = len(products)

        if products > 0:
            # 제품 각각에 메타데이터 병합
            full_data = [{**base_data, 
                        "product_name": p.get("title", ""), 
                        "product_link": p.get("url", ""),
                        "product_price": None,
                        "product_image_link": None,
                        "product_count": product_count} for p in products]

        else:
            full_data = [{**base_data,
                        "product_name": "제품 없음",
                        "product_link": None,
                        "product_price": None,
                        "product_image_link": None,
                        "product_count": 0}]
            
        logger.info(f"✅ 영상 정보 및 제품 {product_count}개 수집 완료")
        return pd.DataFrame(full_data)
    
    except Exception as e:
        logger.error(f"❌ base_youtube_info 예외: {e}", exc_info=True)
        return pd.DataFrame()

#--------------------------------------- 제품 정보 추출 -------------------------------------
def extract_products_from_dom(soup) -> List[Dict]:
    script_tag = soup.find("script", string=lambda s: s and "var ytInitialData" in s)
    if not script_tag:
        logger.warning("⚠️ ytInitialData 스크립트 태그 없음")
        return []
    
    try:
        json_text = script_tag.string.split("var ytInitialData =")[-1].rsplit("};", 1)[0] + "}"
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.warning("⚠️ ytInitialData JSON 파싱 실패")
        return []
    
    products = []
    try:
        contents = data["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"]
        for item in contents:
            section = item.get("itemSectionRenderer", {}).get("contents", [{}])[0]
            sponsor = section.get("videoDescriptionSponsorSectionRenderer")
            if sponsor:
                for prod in sponsor.get("sponsorSection", {}).get("products", []):
                    title = prod.get("title", {}).get("runs", [{}])[0].get("text", "")
                    url = prod.get("navigationEndpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
                    if title and url:
                        products.append({"title": title, "url": url})
        return products
    except Exception as e:
        logger.warning(f"⚠️ 제품 데이터 추출 실패: {e}")
        return []


# ----------------------------------------------- ⬇️ 유튜브 영상 URL 접속 후 데이터 수집 수행 -----------------------------------------------

def collect_video_data(driver, video_id: str, index: int = None, total: int = None) -> pd.DataFrame:
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    
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


# -------------------------------------------- ⬇️ DB(sqlite) 저장 함수 ---------------------------------------- 
def save_youtube_data_to_db(df: pd.DataFrame) -> int:
    if df.empty:
        logger.warning("❌ 저장할 데이터프레임이 비어 있습니다.")
        return 0
    
    # 영상은 video_id 기준으로 1개, 제품은 여러 개
    video_data = df.iloc[0]

    try:

        video, created = YouTubeVideo.objects.get_or_create(
            video_id=video_data["video_id"],
            defaults={
                "extracted_date": video_data["extracted_date"],
                "video_url": video_data["video_url"],
                "title": video_data["title"],
                "channel_name": video_data["channel_name"],
                "subscriber_count": video_data["subscriber_count"],
                "view_count": video_data["view_count"],
                "upload_date": video_data["upload_date"],
                "description": video_data["description"]
            }
        )
        if not created:
            logger.info("⚠️ 이미 존재하는 영상 id입니다: %s", video.video_id)
            return 0

        for _, row in df.iterrows():
            YouTubeProduct.objects.get_or_create(
                video=video,
                url=row["product_link"],
                defaults={
                    "title": row["product_name"],
                    "price": row.get("product_price"),
                    "image_url": row.get("product_image_link")
                }
            )

        logger.info("📹 영상 및 제품 저장 완료: %s", video.video_id)
        return len(df)
    
    except Exception as e:
        logger.error(f"❌ DB 저장 실패: {e}", exc_info=True)
        return 0
    
# ------------------------------------- ⬇️ 엑셀/CSV 저장 함수 ------------------------------
def export_videos_to_csv(file_path="youtube_videos.csv"):
    videos = YouTubeVideo.objects.all().prefetch_related("product_set")
    rows = []
    for video in videos:
        for product in video.product_set.all():
            rows.append({
                "video_id": video.video_id,
                "title": video.title,
                "channel_name": video.channel_name,
                "view_count": video.view_count,
                "upload_date": video.upload_date,
                "product_title": product.title,
                "product_url": product.url,
                "product_price": product.price,
                "product_image_link": product.image_url
            })
    df = pd.DataFrame(rows)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    logger.info("Exported video and product data to CSV: %s", file_path)


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
def save_to_db(df: pd.DataFrame):
    from django.db import transaction

    if df.empty:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return

    with transaction.atomic():
        video_cache = {}  # video_id 별로 video 객체 캐싱
        
        for _, row in df.iterrows():
            video_id = row["video_id"]

            if video_id not in video_cache:
                video_obj, created = YouTubeVideo.objects.update_or_create(
                    video_id=video_id,
                    defaults={
                        "extracted_date": row["extracted_date"],
                        "upload_date": row["upload_date"],
                        "channel_name": row["channel_name"],
                        "subscriber_count": row["subscriber_count"],
                        "title": row["title"],
                        "view_count": row["view_count"],
                        "video_url": row["video_url"],
                        "product_count": row.get("product_count", ""),
                        "description": row["description"],
                    }
                )
                video_cache[video_id] = video_obj
                if created:
                    logger.info(f"DB 저장 완료: {video_obj.video_id}")
                else:
                    logger.info(f"DB 업데이트 완료: {video_obj.video_id}")
            else:
                video_obj = video_cache[video_id]

            # 제품 저장
            product_name = row.get("product_name")
            if product_name:
                YouTubeProduct.objects.update_or_create(
                    video=video_obj,
                    product_name=product_name,
                    defaults={
                        "product_price": row.get("product_price", ""),
                        "product_image_link": row.get("product_image_link", ""),
                        "product_link": row.get("product_link", ""),
                    }
                )

# ------------------------------------- ⬇️ 유튜브 채널의 전체 크롤링을 실행하는 함수 ------------------------------
def crawl_channel_videos(channel_url: str, save_path: str):
    with create_driver() as driver:
        video_ids = get_all_video_ids(driver, channel_url)
        logger.info(f"총 {len(video_ids)}개 영상 크롤링 시작")
        all_data = pd.DataFrame()

        for idx, vid in enumerate(video_ids, 1):
            video_url = f"https://www.youtube.com/watch?v={vid}"
            df = base_youtube_info(driver, video_url)
            if not df.empty:
                all_data = pd.concat([all_data, df], ignore_index=True)
            else:
                logger.warning(f"⚠️ 영상 크롤링 실패: {video_url}")
            logger.info(f"진행: {idx}/{len(video_ids)}")

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
