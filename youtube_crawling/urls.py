from django.urls import path
from .views import views

app_name = 'youtube_crawling'
urlpatterns = [
    path('longform/', views.LongForm.as_views()),
]