from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json, logging

logger = logging.getLogger(__name__)

def setup_periodic_tasks():
    try:
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=10, # 10분 간격
            period=IntervalSchedule.MINUTES,
        )

        task_name = 'crawl_channels_task_every_10min'
        task_path = 'youtube_crawling.tasks.crawl_channels_task'

        if not PeriodicTask.objects.filter(name=task_name).exists():
            PeriodicTask.objects.create(
                interval=schedule,
                name=task_name,
                task=task_path,
                args=json.dumps([]),
            )
            logger.info(f"✅ 주기 작업 '{task_name}' 등록 완료")
        else:
            logger.info(f"⚠️ 주기 작업 '{task_name}' 이미 존재함 (건너뜀)")
    except Exception as e:
        logger.error(f"❌ 주기 작업 등록 중 오류 발생: {e}")

setup_periodic_tasks()
