from django.apps import AppConfig

class YoutubeCrawlingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'youtube_crawling'

    def ready(self):
        from . import schedule_code
        schedule_code.setup_periodic_tasks()