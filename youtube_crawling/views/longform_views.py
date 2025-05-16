from rest_framework import viewsets
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from ..models import YouTubeVideo, YouTubeProduct
from youtube_crawling.serializers.video_ids_serializers import YouTubeVideoSerializer
from youtube_crawling.crawler import collect_video_data  # selenium 함수 임포트
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class YoutubeLongFormCrawlAPIView(APIView):

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'video_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description='크롤링할 유튜브 영상 ID 리스트',
                ),
            },
            required=['video_ids'],
            example={
                'video_ids': [
                    'dQw4w9WgXcQ',
                    '9bZkp7q19f0',
                    '3JZ_D3ELwOQ'
                ]
            }
        )
    )
    
    def post(self, request):
        video_ids = request.data.get("video_ids", [])
        if not video_ids:
            return Response({"error": "video_ids를 제공해주세요."}, status=400)

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        saved_results = []

        for vid in video_ids:
            try:
                df = collect_video_data(driver, vid)
                for _, row in df.iterrows():
                    # 중복 방지
                    if YouTubeVideo.objects.filter(video_id=vid).exists():
                        continue
                    
                    video = YouTubeVideo.objects.create(
                        video_id=vid,
                        title=row['영상 제목'],
                        channel_name=row['채널명'],
                        subscriber_count=row['구독자 수'],
                        upload_date=row['영상 업로드일'],
                        extracted_date=row['추출일'],
                        video_url=row['영상 링크'],
                        view_count=row['조회수'],
                        product_count=row['포함된 제품 개수'],
                        description=row['더보기란 설명'],
                    )

                    YouTubeProduct.objects.create(
                        video=video,
                        product_image_link=row['제품 이미지 링크'],
                        product_name=row['제품명'],
                        product_price=row['제품 가격(원)'],
                        product_link=row['제품 구매 링크'],
                    )
                    saved_results.append(video)
            except Exception as e:
                print(f"{vid} 처리 중 오류: {e}")
                continue

        driver.quit()
        return Response({"message": f"{len(saved_results)}개 영상 저장 완료"}, status=status.HTTP_201_CREATED)

class YouTubeVideoViewSet(viewsets.ModelViewSet):
    queryset = YouTubeVideo.objects.all().order_by('-extracted_date')
    serializer_class = YouTubeVideoSerializer

