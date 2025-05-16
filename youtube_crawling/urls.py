from django.urls import path, include
from youtube_crawling.views.longform_views import YoutubeLongFormCrawlAPIView
from rest_framework.routers import DefaultRouter
from .views.longform_views import YouTubeVideoViewSet

router = DefaultRouter()
router.register(r'youtube-videos', YouTubeVideoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

urlpatterns = [
    path('longform/', YoutubeLongFormCrawlAPIView.as_view()),
]