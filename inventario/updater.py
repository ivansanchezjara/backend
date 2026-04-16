from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

def update_vencimientos_job():
    """Execution of the procesar_vencimientos management command in background"""
    try:
        logger.info("Starting background job to process expirations...")
        call_command('procesar_vencimientos')
        logger.info("Done processing expirations.")
    except Exception as e:
        logger.error(f"Error processing expirations: {e}")

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    
    # Check every day at midnight (or every couple hours if you prefer)
    # We will set it to run once a day at 00:01
    from apscheduler.triggers.cron import CronTrigger
    
    scheduler.add_job(
        update_vencimientos_job,
        trigger=CronTrigger(hour="00", minute="01"), # Runs at 00:01 every day
        id="update_vencimientos",
        max_instances=1,
        replace_existing=True,
    )
    
    register_events(scheduler)
    scheduler.start()
    logger.info("APScheduler started: Processing expirations every day at 00:01")
