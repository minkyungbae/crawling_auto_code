from django.urls import path
from youtube_crawling.views.longform_api_views import ChannelCrawlTriggerView

urlpatterns = [
    path('', ChannelCrawlTriggerView.as_view()), # 유튜브 채널에 있는 영상 크롤링 (POST,GET,PUT,DELETE)
]