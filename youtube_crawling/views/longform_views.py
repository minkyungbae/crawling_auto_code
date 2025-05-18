from rest_framework import viewsets
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from ..models import YouTubeVideo, YouTubeProduct
from youtube_crawling.serializers.video_ids_serializers import YouTubeVideoSerializer, ProductSerializer
from youtube_crawling.crawler import collect_video_data, save_youtube_data_to_db
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
                    description='크롤링할 유튜브 영상 ID 리스트를 입력해주세요.',
                ),
            },
            required=['video_ids'],
            example={
                'video_ids': [
                    'id 1',
                    'id 2',
                    'id 3'
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
        options.add_argument('user-agent=Mozilla/5.0')  # User-Agent 추가
        
        saved_count = 0
        failed_ids = []

        with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:

            for vid in video_ids:
                try:
                    df = collect_video_data(driver, vid)
                    count = save_youtube_data_to_db(df)
                    saved_count += count
                except Exception as e:
                    print(f"[❌ 오류] {vid} 처리 중: {e}")
                    failed_ids.append(vid)
                    continue

        return Response({
            "message": f"{saved_count}개 영상 저장 완료",
            "failed_ids": failed_ids
        }, status=status.HTTP_201_CREATED)

class YouTubeVideoViewSet(viewsets.ModelViewSet):
    queryset = YouTubeVideo.objects.all().order_by('-extracted_date')
    serializer_class = YouTubeVideoSerializer

class YouTubeProductViewSet(viewsets.ModelViewSet):
    queryset = YouTubeProduct.objects.all().order_by('video')
    serializer_class = ProductSerializer

