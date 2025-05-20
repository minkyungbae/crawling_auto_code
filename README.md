# Auto Youtube LongForm Crawling
특정 시간에 크롤링이 자동으로 작동되도록 설계한 프로젝트입니다.

# 기능
- YouTube 동영상 데이터 자동 수집
- Selenium을 이용한 웹 크롤링
- 수집된 데이터 Django DB(SQLite) 저장
- REST API 제공

# 기술 스택
- Python
- DRF(Django REST Framework)
- Selenium
- BeautifulSoup4
- Pandas
- SQLite3
- Celery / Celery beat

# 설치 및 사용
**1. Download Repository**
```
git clone https://github.com/minkyungbae/crawling_auto_code.git
```
**2. 가상환경 생성 및 활성화**
<br>
**2.1. 가상환경 생성**
```
python -m venv env
```
**2.2. 가상환경 실행**
<br>
**2.2.1. MacOS**
```
source env/bin/activate
```
**2.2.2. Window**
```
./env/Scripts/activate
```
**3. 패키지 설치**
```
pip install -r requirements.txt
```
**4. 데이터베이스 마이그레이션**
```
python manage.py migrate
```
**5. 서버 실행**
```
python manage.py runserver
```

# 폴더 구조
```
crawling_auto_code
├─ config/              # 프로젝트 설정 폴더
├─ manage.py
├─ requirements.txt     # 패키지
├─ youtube_crawling     # 주된 기능 폴더
│  ├─ models.py
│  ├─ serializers       # serializer 관리 폴더
│  │  ├─ __init__.py
│  │  └─ video_ids_serializers.py
│  ├─ tests.py
│  ├─ crawler.py        # 주요 크롤링 기능 코드 파일
│  ├─ urls.py
│  ├─views             # view 관리 폴더
│     └─ longform_views.py  # 크콜링 작동 옵션 설정한 코드 파일
└─ youtube_product_html.txt # 사용되고 있는 html 디버깅한 파일
```

