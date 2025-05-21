from django.urls import path, include
from youtube_crawling.views.longform_views import (
    YoutubeLongFormCrawlAPIView,
    YouTubeVideoViewSet,
    YouTubeProductViewSet
    )

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'youtube-videos', YouTubeVideoViewSet)
router.register(r'youtube-products', YouTubeProductViewSet)

urlpatterns = [
    path('', include(router.urls)), # ViewSet API (GET, POST, PUT, DELETE 등 자동 라우팅)
    path('longform/', YoutubeLongFormCrawlAPIView.as_view()), # POST /longform/ => 크롤링
]