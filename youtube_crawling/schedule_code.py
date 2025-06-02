import logging
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from datetime import datetime
import pytz

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def setup_periodic_tasks():
    try:
        # 현재 시간을 KST로 확인
        kst = pytz.timezone('Asia/Seoul')
        current_time = datetime.now(kst)
        logger.info(f"현재 서버 시간: {current_time}")

        """
        =====================================
        '*' <- 이거는 매일을 의미!
        ⬇ 여기서 시간, 날짜, 월 등등 수정하면 돼유 ⬇
        =====================================
        """
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='17', # 한국 시간
            day_of_week='*', # 매일 -> 0 ~ 6 (일 ~ 토)
            day_of_month='*', # 매일 -> 1 ~ 31
            month_of_year='*', # 매월 -> 1 ~ 12
            timezone=pytz.timezone('Asia/Seoul')
        )
    
        if created:
            logger.info("새로운 Crontab 스케줄이 생성되었습니다. (KST 17:00 실행)")
        else:
            logger.info("기존 Crontab 스케줄을 사용합니다. (KST 17:00 실행)")

        task_name = 'youtube_daily_crawling_task'
        task, task_created = PeriodicTask.objects.get_or_create(
            name=task_name,
            defaults={
                'crontab': schedule,
                'task': 'youtube_crawling.tasks.crawl_channels_task',
                'enabled': True,
            }
        )

        if task_created:
            logger.info(f"새로운 Periodic Task가 생성되었습니다: {task_name}")
        else:
            # 기존 태스크가 있다면 스케줄 업데이트
            task.crontab = schedule
            task.enabled = True
            task.save()
            logger.info(f"기존 Periodic Task가 업데이트되었습니다: {task_name}")

        return True

    except Exception as e:
        logger.error(f"스케줄 생성 중 오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    setup_periodic_tasks()
