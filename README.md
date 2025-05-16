# Auto Youtube LongForm Crawling
특정 시간에 크롤링이 작동되도록 설계한 프로젝트입니다.

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

# 폴더 구조
```
crawling_auto_code
├─ config/              # 프로젝트 설정 폴더
├─ manage.py
├─ requirements.txt     # 패키지
└─ youtube_crawling     # 주된 기능 폴더
   ├─ models.py
   ├─ serializers
   ├─ tests.py
   ├─ urls.py
   └─ views
      └─ longform_views.py

```