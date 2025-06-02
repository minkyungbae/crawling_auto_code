# ---------- DRF 관련 라이브러리 ----------
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
# ---------- Swagger 관련 라이브러리 ----------
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
# ---------- 프로젝트 모델 ----------
from ..models import YouTubeVideo
# ---------- 프로젝트 시리얼라이저 ----------
from youtube_crawling.serializers.longform_serializers import YouTubeVideoSerializer
# ---------- 프로젝트 태스크 ----------
from youtube_crawling.longform_crawler import crawl_channel_videos
# ---------- 그 외 라이브러리 ----------
from urllib.parse import urlparse


# ------------------------------------- ⬇️ 크롤링 자동화 딸깍 클래스 -------------------------------
class ChannelCrawlTriggerView(APIView):
    def is_valid_youtube_channel_url(url):
        parsed = urlparse(url)
        return parsed.scheme in ['http', 'https'] and "youtube.com" in parsed.netloc

    # ---------- 자동 크롤링할 유튜브 URL 목록 입력 ----------
    @swagger_auto_schema(
        operation_summary="자동 크롤링할 유튜브 URL 목력 입력",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'channel_url': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description='자동 크롤링할 유튜브 채널 URL 목록을 입력해주세요.',
                ),
            },
            required=['channel_url'],
            example={
                'channel_url': ["", ""]
            }
        ),
        responses={202: '크롤링이 시작되었습니다.'}
    )
    def post(self, request):
        channel_urls = request.data.get("channel_url")
        if not channel_urls or not isinstance(channel_urls, list):
            return Response({"error": "channel_url은 리스트여야 합니다."}, status=400)

        invalid_urls = [url for url in channel_urls if not self.is_valid_youtube_channel_url(url)]
        if invalid_urls:
            return Response({"error": f"유효하지 않은 URL이 있습니다: {invalid_urls}"}, status=400)

        for url in channel_urls:
            save_dir = "./crawling_result_csv"
            crawl_channel_videos.delay(url, save_dir) # <- 크롤링 태스크 실행

        return Response({"message": f"{len(channel_urls)}개의 크롤링이 시작되었습니다."}, status=202)
    
    # ---------- 크롤링한 유튜브 영상 전체 조회 ----------
    @swagger_auto_schema(
        operation_summary="크롤링한 유튜브 영상 전체 조회")
    
    def get(self, request):
        """전체 영상 목록 조회"""
        queryset = YouTubeVideo.objects.all().order_by('-extracted_date')
        serializer = YouTubeVideoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

    # ---------- 크롤링한 유튜브 영상 전체 갱신(재크롤링) ----------
    @swagger_auto_schema(
        operation_summary="자동 크롤링할 유튜브 URL 목록 전체 갱신(재크롤링)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'channel_url': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description='전체를 새로 크롤링할 유튜브 채널 URL 목록을 입력해주세요.',
                ),
            },
            required=['channel_url'],
            example={
                'channel_url': ["", ""]
            }
        ),
        responses={202: '전체 크롤링이 재시작되었습니다.'}
    )
    def put(self, request):
        channel_urls = request.data.get("channel_url")
        if not channel_urls or not isinstance(channel_urls, list):
            return Response({"error": "channel_url은 리스트여야 합니다."}, status=400)

        invalid_urls = [url for url in channel_urls if not self.is_valid_youtube_channel_url(url)]
        if invalid_urls:
            return Response({"error": f"유효하지 않은 URL이 있습니다: {invalid_urls}"}, status=400)

        for url in channel_urls:
            save_dir = "./crawling_result_csv"
            crawl_channel_videos.delay(url, save_dir)

        return Response({"message": f"{len(channel_urls)}개의 크롤링이 재시작되었습니다."}, status=202)


    # ---------- 특정 유튜브 채널 URL의 영상 및 제품 정보 삭제 ----------
    @swagger_auto_schema(
        operation_summary="특정 유튜브 채널 URL의 영상 및 제품 정보 삭제(단일도 가능)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'channel_url': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description='삭제할 유튜브 채널 URL 및 목록을 입력해주세요.',
                ),
            },
            required=['channel_url'],
            example={
                'channel_url': ["", ""]
            }
        ),
        responses={200: '삭제 완료'}
    )
    def delete(self, request):
        channel_urls = request.data.get("channel_url")
        if not channel_urls or not isinstance(channel_urls, list):
            return Response({"error": "channel_url은 리스트여야 합니다."}, status=400)

        invalid_urls = [url for url in channel_urls if not self.is_valid_youtube_channel_url(url)]
        if invalid_urls:
            return Response({"error": f"유효하지 않은 URL이 있습니다: {invalid_urls}"}, status=400)

        deleted_count = 0
        for url in channel_urls:
            videos = YouTubeVideo.objects.filter(video_url=url)
            count = videos.count()
            for video in videos:
                video.delete()  # 관련 YouTubeProduct도 CASCADE로 삭제됨
            deleted_count += count

        return Response({"message": f"총 {deleted_count}개의 영상 및 관련 제품 정보가 삭제되었습니다."}, status=200)
