import structlog
from celery import shared_task
from sentry_sdk import capture_exception, start_transaction

from core.outbox_processor import process_outbox_batch

logger = structlog.get_logger(__name__)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def push_to_clickhouse() -> None:
    try:
        with start_transaction(op="task", name="push_to_clickhouse"):
            processed = process_outbox_batch(batch_size=1000)
            if processed:
                logger.info("Successfully pushed events to ClickHouse", event_count=processed)
    except Exception as e:
        capture_exception(e)
        logger.error("Failed to push events to ClickHouse", error=str(e))
        raise
