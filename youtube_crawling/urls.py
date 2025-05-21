from django.urls import path
from youtube_crawling.views.longform_views import (
    YoutubeLongFormCrawlAPIView,
    YouTubeVideoOneAPIView,
    )

urlpatterns = [
    path('longform/', YoutubeLongFormCrawlAPIView.as_view()), # 여러 개 영상 크롤링 (C,R,PUT,D)
    path('longform/<str:video_id>/', YouTubeVideoOneAPIView.as_view()), # 특정 영상 한 개 (R,D,PATCH)
]