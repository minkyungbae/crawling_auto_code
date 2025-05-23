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
from urllib.parse import urlparse, unquote, parse_qsl
from slugify import slugify
import pandas as pd
import logging, time, re, json, os, urllib.parse


# ----------------------------- ⬇️ logging 설정 -----------------------------

logger = logging.getLogger(__name__)  # logger.info(), logger.warning()만 써야해용

# --------- driver 한 번으로 정의 ---------------
@contextmanager
def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")           # 샌드박스 비활성화 (보안 기능 해제)
    options.add_argument("--disable-dev-shm-usage")# 공유 메모리 사용 비활성화
    options.add_argument("--disable-gpu")          # GPU 하드웨어 가속 비활성화
    options.add_argument("--disable-extensions")   # 크롬 확장 프로그램 비활성화
    options.add_argument("--disable-infobars")     # 정보 표시줄 비활성화
    options.add_argument("--start-maximized")      # 브라우저 최대화
    options.add_argument("--disable-notifications")# 알림 비활성화
    options.add_argument('--ignore-certificate-errors')  # 인증서 오류 무시
    options.add_argument('--ignore-ssl-errors')    # SSL 오류 무시
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
        time.sleep(3)  # 페이지 로딩을 위한 대기 시간 증가

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
        # 조회수와 회를 제거하고 숫자와 소수점, 단위(만)만 남김
        cleaned = text.replace("조회수", "").replace("회", "").replace(",", "").strip()
        
        # 백 단위가 있는 경우
        if "천" in cleaned:
            number = float(cleaned.replace("백", ""))
            return int(number * 1000)
        # 만 단위가 있는 경우
        elif "만" in cleaned:
            number = float(cleaned.replace("만", ""))
            return int(number * 10000)
        
        return int(cleaned)
    except ValueError as e:
        logger.warning(f"⚠️ 조회수 파싱 실패: '{text}', 이유: {e}")
        return 0


# ----------------------------- ⬇️ 구독자 수 텍스트를 숫자 형태로 변환 (예: 1.2만명 -> 12000) -----------------------------
def parse_subscriber_count(text: str) -> int:
    try:
        # 구독자와 명을 제거하고 숫자와 소수점, 단위(천, 만)만 남김
        text = text.replace("구독자", "").replace("명", "").replace(",", "").strip()
        
        if "천" in text:
            number = float(text.replace("천", ""))
            return int(number * 1000)
        elif "만" in text:
            number = float(text.replace("만", ""))
            return int(number * 10000)
        
        return int(text)
    except Exception as e:
        logger.warning(f"⚠️ 구독자 수 파싱 실패: '{text}', 이유: {e}")
        return 0


# ---------------------- ⬇️ 날짜를 YYYY-MM-DD 형식으로 변환 ----------------------
def format_date(date_str: str) -> str:
    try:
        if match := re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?', date_str):
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        elif match := re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', date_str):
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        elif match := re.search(r'(\d{4})(\d{2})(\d{2})', date_str):
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"
    except Exception as e:
        logger.warning(f"⚠️ 날짜 형식 변환 실패: {date_str}, 에러: {e}")
    return date_str


# ---------------------- ⬇️ 설명란의 불필요한 줄바꿈 제거 ----------------------
def clean_description(text: str) -> str:
    if not text:
        return ""
    # 연속된 줄바꿈을 하나로 통일
    text = re.sub(r'\n\s*\n', '\n', text)
    # 앞뒤 공백 제거
    return text.strip()


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
def extract_products_from_dom(driver, soup: BeautifulSoup) -> list[dict]:
    products = []
    try:
        # 250522 제품 섹션 찾기 (여러 선택자 시도)
        product_sections = []
        section_selectors = [
            "ytd-merch-shelf-renderer",
            "ytd-product-metadata-badge-renderer",
            "ytd-product-item-renderer",
            "#product-shelf",
            "#items.ytd-merch-shelf-renderer",
            "ytd-merch-shelf-item-renderer",
            "#content ytd-metadata-row-container-renderer",
            "#product-list",
            ".product-list",
            ".product-shelf"
        ]
        
        for selector in section_selectors:
            sections = soup.select(selector)
            if sections:
                product_sections.extend(sections)
                logger.info(f"제품 섹션 찾음: {selector}")
                
        if not product_sections:
            logger.warning("제품 섹션을 찾을 수 없습니다.")
            return products

        # 오른쪽 화살표 버튼이 있는지 확인하고 클릭
        right_arrow_selectors = [
            "#right-arrow-container",
            "#right-arrow",
            "div.arrow.center-aligned",
            "yt-icon[icon='yt-icons:chevron_right']",
            ".arrow.style-scope.ytd-merch-shelf-renderer",
            "#navigation-buttons button[aria-label*='다음']",
            "#navigation-buttons button[aria-label*='Next']"
        ]

        max_clicks = 10  # 무한 루프 방지
        clicks = 0
        
        while clicks < max_clicks:
            # 현재 보이는 모든 제품 정보 추출
            for section in product_sections:
                try:
                    # 제품 아이템 찾기
                    item_selectors = [
                        "ytd-merch-shelf-item-renderer",
                        ".product-item",
                        ".ytd-merch-product-renderer",
                        "ytd-product-item-renderer",
                        ".product-shelf-item"
                    ]
                    
                    items = []
                    for selector in item_selectors:
                        items.extend(section.select(selector))
                    
                    for item in items:
                        product_info = {}
                        
                        # 제품 링크 및 기본 정보
                        link_selectors = [
                            "a.yt-simple-endpoint",
                            "a[href*='redirect']",
                            "a[href*='shopping']",
                            "a[target='_blank']",
                            ".product-link",
                            ".ytd-merch-product-renderer a",
                            "a.product-item-link",
                            "a[data-url]",
                            "a[data-sessionlink]",
                            "ytd-button-renderer a"
                        ]
                        
                        for selector in link_selectors:
                            if link_elem := item.select_one(selector):
                                href = link_elem.get("href") or link_elem.get("data-url")
                                if href:
                                    if "redirect" in href:
                                        try:
                                            parsed = urlparse(href)
                                            query_params = dict(parse_qsl(parsed.query))
                                            if 'q' in query_params:
                                                href = query_params['q']
                                            elif 'url' in query_params:
                                                href = query_params['url']
                                        except:
                                            pass
                                    product_info["url"] = href if href.startswith("http") else f"https://www.youtube.com{href}"
                                    break

                        # 제품명
                        title_selectors = [
                            ".product-item-title",
                            "span#video-title",
                            "yt-formatted-string.ytd-merch-product-renderer",
                            "a#title",
                            "span[id='title']",
                            ".product-title",
                            ".ytd-merch-product-renderer-title",
                            "div[class*='title']",
                            ".small-item-hide.product-item-title"
                        ]
                        
                        for selector in title_selectors:
                            if title_elem := item.select_one(selector):
                                if title_text := title_elem.get_text(strip=True):
                                    product_info["title"] = title_text
                                    break

                        # 가격
                        price_selectors = [
                            ".product-item-price",
                            "span#price",
                            "span.price",
                            "yt-formatted-string#price",
                            ".ytd-merch-product-renderer-price",
                            ".product-price",
                            ".product-item-price-wrapper .product-item-price",
                            "div[class*='price']"
                        ]
                        
                        for selector in price_selectors:
                            if price_elem := item.select_one(selector):
                                if price_text := price_elem.get_text(strip=True):
                                    product_info["price"] = price_text
                                    break

                        # 이미지 URL
                        img_selectors = [
                            "img#img",
                            "img.ytd-merch-product-renderer-thumbnail",
                            "yt-img-shadow img",
                            ".product-image img",
                            ".product-item-image img",
                            "img[class*='product']",
                            "img[alt]",
                            ".style-scope.yt-img-shadow",
                            "img.style-scope",
                            "img[src*='i.ytimg.com']",
                            "img[data-thumb]"
                        ]
                        
                        for selector in img_selectors:
                            if img_elem := item.select_one(selector):
                                # 여러 속성에서 이미지 URL 찾기
                                src = (img_elem.get("src") or 
                                      img_elem.get("data-thumb") or 
                                      img_elem.get("data-src"))
                                
                                if src:
                                    # 상대 URL을 절대 URL로 변환
                                    if src.startswith("//"):
                                        src = f"https:{src}"
                                    elif not src.startswith(("http://", "https://")):
                                        src = f"https://www.youtube.com{src}"
                                    
                                    product_info["imageUrl"] = src
                                    break

                        # 판매처
                        merchant_selectors = [
                            ".product-item-merchant-text",
                            ".product-merchant",
                            ".merchant-name",
                            "div[class*='merchant']",
                            ".product-item-merchant div",
                            ".product-item-merchant-text:first-child"
                        ]
                        
                        for selector in merchant_selectors:
                            if merchant_elem := item.select_one(selector):
                                if merchant_text := merchant_elem.get_text(strip=True):
                                    product_info["merchant"] = merchant_text.replace("!", "").strip()
                                    break

                        if product_info.get("title"):  # 최소한 제품명은 있어야 함
                            if product_info not in products:  # 중복 제품 방지
                                products.append(product_info)
                                logger.info(f"제품 추출 성공: {product_info['title']}")

                except Exception as e:
                    logger.warning(f"개별 제품 파싱 중 오류: {e}")
                    continue

            # 다음 제품을 보기 위해 오른쪽 화살표 클릭 시도
            arrow_clicked = False
            for selector in right_arrow_selectors:
                try:
                    arrow = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    driver.execute_script("arguments[0].click();", arrow)
                    logger.info("오른쪽 화살표 클릭 성공")
                    arrow_clicked = True
                    time.sleep(2)  # 새로운 제품이 로드될 때까지 대기
                    break
                except:
                    continue

            if not arrow_clicked:
                logger.info("더 이상 표시할 제품이 없습니다")
                break

            clicks += 1
            # 페이지 소스 업데이트
            soup = BeautifulSoup(driver.page_source, "html.parser")
                
    except Exception as e:
        logger.error(f"❌ 제품 정보 추출 중 오류 발생: {e}")
        
    logger.info(f"총 {len(products)}개의 제품 추출 완료")
    return products
    

# ---------------------- ⬇️ 영상 기본 정보: 제목, 채널명, 구독자 수, 조회수, 업로드일, 제품 개수 ----------------------
def base_youtube_info(driver, video_url: str) -> pd.DataFrame:
    logger.info("Crawling video: %s", video_url)
    today_str = datetime.today().strftime('%Y%m%d')

    try:
        driver.get(video_url)
        # 페이지 로딩 대기 시간
        time.sleep(3)
        
        # 페이지 스크롤을 여러 번 수행하여 동적 컨텐츠 로드
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, window.scrollY + 500);")
            time.sleep(2)
        
        wait = WebDriverWait(driver, 20)
        
        # 250523 더보기 버튼 클릭 시도 (여러 셀렉터 시도)
        expand_button_selectors = [
            "tp-yt-paper-button#expand",
            "#expand",
            "#expand-button",
            "#more",
            "ytd-button-renderer#more",
            "ytd-expander#description [aria-label='더보기']",
            "ytd-expander[description-collapsed] #expand"
        ]
        
        for selector in expand_button_selectors:
            try:
                more_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                driver.execute_script("arguments[0].click();", more_button)
                logger.info(f"더보기 버튼 클릭 성공: {selector}")
                time.sleep(3)  # 더보기 클릭 후 컨텐츠 로드 대기
                break
            except:
                continue
                
        # 250523 제품 섹션 선택지 추가
        product_selectors = [
            "ytd-product-metadata-badge-renderer",
            "ytd-merch-shelf-renderer",
            "ytd-product-item-renderer",
            "#product-shelf",
            "#product-list",
            "ytd-merch-product-renderer",
            "#product-items",
            ".product-item",
            "#content ytd-metadata-row-container-renderer",
            "ytd-metadata-row-renderer",
            "#product-section"
        ]
        
        for selector in product_selectors:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                logger.info(f"제품 섹션 찾음: {selector}")
                break
            except:
                continue
        
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # 메타데이터 추출
        video_id = video_url.split("v=")[-1]
        
        # 250522 제목 (여러 선택자 시도)
        title_selectors = [
            "h1.title yt-formatted-string",
            "h1.title",
            "#title h1",
            "#container h1.style-scope.ytd-watch-metadata"
        ]
        title = None
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title:
                    break
        title = title or "제목 없음"
        logger.info(f"제목: {title}")

        # 250522채널명 (여러 선택자 시도)
        channel_selectors = [
            "ytd-channel-name yt-formatted-string#text a",
            "ytd-channel-name a",
            "#channel-name a"
        ]
        channel_name = None
        for selector in channel_selectors:
            channel_tag = soup.select_one(selector)
            if channel_tag:
                channel_name = channel_tag.text.strip()
                break
        channel_name = channel_name or "채널 없음"

        # 250522 구독자 수
        sub_selectors = [
            "yt-formatted-string#owner-sub-count",
            "#subscriber-count"
        ]
        subscriber_count = None
        for selector in sub_selectors:
            sub_tag = soup.select_one(selector)
            if sub_tag:
                subscriber_count = sub_tag.text.strip()
                break
        subscriber_count = subscriber_count or "구독자 수 없음"

        # 250522 조회수
        view_selectors = [
            "span.view-count",
            "#view-count",
            "ytd-video-view-count-renderer"
        ]
        view_count = None
        for selector in view_selectors:
            view_tag = soup.select_one(selector)
            if view_tag:
                view_count = view_tag.text.strip()
                break
        view_count = view_count or "조회수 없음"

        # 250522 업로드일
        date_selectors = [
            "#info-strings yt-formatted-string",
            "#upload-info .date",
            "ytd-video-primary-info-renderer yt-formatted-string.ytd-video-primary-info-renderer:not([id])"
        ]
        upload_date = None
        for selector in date_selectors:
            date_tag = soup.select_one(selector)
            if date_tag:
                upload_date = date_tag.text.strip()
                break
        upload_date = upload_date or "날짜 없음"

        # 250522 설명란
        desc_selectors = [
            "ytd-expander#description yt-formatted-string",
            "#description",
            "#description-inline-expander",
            "#description-text-container"
        ]
        description = None
        for selector in desc_selectors:
            desc_tag = soup.select_one(selector)
            if desc_tag:
                description = desc_tag.text.strip()
                if description:
                    break
        description = description or "설명 없음"
        logger.info(f"설명 길이: {len(description)} 글자")

        # 250522 제품 추출
        products = extract_products_from_dom(driver, soup)
        product_count = len(products)

        # 기본 데이터 세트
        base_data = []
        
        # 250523
        if products:
            # 각 제품별로 row 생성
            for product in products:
                row_data = {
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
                    "product_name": product.get("title", ""),
                    "product_price": product.get("price", ""),
                    "product_image_url": product.get("imageUrl", ""),
                    "product_url": product.get("url", ""),
                    "product_merchant": product.get("merchant", "")
                }
                base_data.append(row_data)
        else:
            # 제품이 없는 경우 기본 정보만 저장
            base_data.append({
                "youtube_id": video_id,
                "title": title,
                "channel_name": channel_name,
                "subscribers": subscriber_count,
                "view_count": view_count,
                "upload_date": upload_date,
                "extracted_date": today_str,
                "video_url": video_url,
                "description": description,
                "product_count": 0,
                "product_name": "",
                "product_price": "",
                "product_image_url": "",
                "product_url": "",
                "product_merchant": ""
            })

        logger.info(f"✅ 영상 정보 및 제품 {product_count}개 수집 완료")
        return pd.DataFrame(base_data)
    
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
                product, created = YouTubeProduct.objects.update_or_create(
                    video=video,
                    product_name=row.get('title', '제품 없음'),
                    defaults={
                        "product_price": row.get('price'),
                        "product_image_link": row.get('imageUrl'),
                        "product_link": row.get('url')
                    }
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
def save_to_db(data: pd.DataFrame):
    """DataFrame을 DB에 저장하는 함수"""
    if data is None or data.empty:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return 0

    from django.db import transaction
    saved_count = 0
    
    try:
        with transaction.atomic():
            # DataFrame의 각 행을 처리
            for _, row in data.iterrows():
                video_id = row.get("youtube_id")
                if not video_id:
                    logger.warning("⚠️ video_id 없음, 건너뜁니다")
                    continue

                # 날짜 형식 변환
                extracted_date = format_date(row.get("extracted_date", ""))
                upload_date = format_date(row.get("upload_date", ""))
                
                # 구독자 수와 조회수를 정수로 변환
                subscriber_count = parse_subscriber_count(row.get("subscribers", "0"))
                view_count = parse_view_count(row.get("view_count", "0"))
                
                # 설명란 정리
                description = clean_description(row.get("description", ""))
                
                # 비디오 데이터 생성 또는 업데이트
                video_obj, created = YouTubeVideo.objects.update_or_create(
                    video_id=video_id,
                    defaults={
                        "extracted_date": extracted_date,
                        "upload_date": upload_date,
                        "channel_name": row.get("channel_name"),
                        "subscriber_count": subscriber_count,
                        "title": row.get("title"),
                        "view_count": view_count,
                        "video_url": row.get("video_url"),
                        "product_count": row.get("product_count", 0),
                        "description": description,
                    }
                )

                # 250523 제품 정보가 있는 경우에만 저장
                if row.get("product_name"):
                    YouTubeProduct.objects.create(
                        video=video_obj,
                        product_name=row.get("product_name", ""),
                        product_price=row.get("product_price", ""),
                        product_image_link=row.get("product_image_url", ""),
                        product_link=row.get("product_url", ""),
                        product_merchant=row.get("product_merchant", "")
                    )
                    logger.info(f"✅ 제품 정보 저장 완료 (video_id: {video_id})")
                else:
                    # 250523 제품이 없는 경우도 빈 값으로 저장
                    YouTubeProduct.objects.create(
                        video=video_obj,
                        product_name="",
                        product_price="",
                        product_image_link="",
                        product_link="",
                        product_merchant=""
                    )
                    logger.info(f"⚠️ 제품 없는 채로 정보 저장 완료 (video_id: {video_id})")
                saved_count += 1

    except Exception as e:
        logger.error(f"❌ DB 저장 중 에러 발생: {e}")
        return 0

    return saved_count

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
        
        time.sleep(1)  # 각 채널 간 1초 쉬었다가 다음 채널 실행
