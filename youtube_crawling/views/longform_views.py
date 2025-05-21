from rest_framework import viewsets
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from ..models import YouTubeVideo, YouTubeProduct
from youtube_crawling.serializers.video_ids_serializers import YouTubeVideoSerializer, ProductSerializer
from youtube_crawling.crawler import collect_video_data, save_youtube_data_to_db, update_youtube_data_to_db

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
                'video_ids': ['id 1', 'id 2','id 3']
            }
        ),
        responses={201: '성공적으로 저장된 영상 개수와 실패한 ID 리스트 반환'}
    )
    
# ------------------------------------- API POST 함수(성공한 동영상 수, 실패한 영상 id 출력)-------------------------------
    def post(self, request):
        video_ids = request.data.get("video_ids", [])
        if not video_ids:
            return Response({"error": "video_ids를 제공해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('user-agent=Mozilla/5.0')  # User-Agent 추가
        
        saved_count = 0
        failed_ids = []

        with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:

            for index, vid in enumerate(video_ids, start=1):
                try:
                    df = collect_video_data(driver, vid, index=index, total=len(video_ids))
                    saved_count += save_youtube_data_to_db(df)
                except Exception as e:
                    print(f"[❌ 오류] {vid} 처리 중: {e}")
                    failed_ids.append(vid)

        return Response({
            "message": f"{saved_count}개 영상 저장 완료",
            "failed_ids": failed_ids
        }, status=status.HTTP_201_CREATED)
    
# ------------------------------------- API GET 함수(전체 영상 목록 조회)-------------------------------
    def get(self, request):
        """전체 영상 목록 조회"""
        queryset = YouTubeVideo.objects.all()
        serializer = YouTubeVideoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# ------------------------------------- API DELETE 함수(영상 id로 삭제)-------------------------------
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'video_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description='삭제할 유튜브 영상 ID 리스트',
                ),
            },
            required=['video_ids'],
            example={
                'video_ids': ['id1', 'id2']
            }
        ),
        responses={200: '삭제된 영상 수'}
    )
    def delete(self, request):
        video_ids = request.data.get("video_ids", [])
        if not video_ids:
            return Response({"error": "video_ids를 제공해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = YouTubeVideo.objects.filter(video_id__in=video_ids).delete()
        return Response({"message": f"{deleted}개 영상 삭제 완료"}, status=status.HTTP_200_OK)
    
# ------------------------------------- API PUT 함수(영상 id로 삭제)-------------------------------
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'video_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='수정할 유튜브 영상 ID',
                ),
            },
            required=['video_id'],
            example={'video_id': 'id1'}
        ),
        responses={200: '수정 성공 or 실패 메시지'}
    )
    def put(self, request):
        video_id = request.data.get("video_id")
        if not video_id:
            return Response({"error": "video_id를 제공해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('user-agent=Mozilla/5.0')

        try:
            with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
                df = collect_video_data(driver, video_id)
                update_youtube_data_to_db(df)  # 기존 DB 업데이트하는 함수로 구현해야 함
            return Response({"message": f"{video_id} 업데이트 완료"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"{video_id} 업데이트 실패: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class YouTubeVideoViewSet(viewsets.ModelViewSet):
    queryset = YouTubeVideo.objects.all().order_by('-extracted_date')
    serializer_class = YouTubeVideoSerializer

class YouTubeProductViewSet(viewsets.ModelViewSet):
    queryset = YouTubeProduct.objects.all().order_by('video')
    serializer_class = ProductSerializer

    