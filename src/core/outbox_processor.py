from datetime import datetime

import msgpack
import structlog
from django.db import transaction

from core.event_log_client import EventLogClient
from users.models import Outbox

logger = structlog.get_logger(__name__)


def decode_datetime(obj: dict) -> datetime:
    if '__datetime__' in obj:
        obj = datetime.strptime(obj["as_str"], "%Y%m%dT%H:%M:%S.%f%z")
    return obj


def process_outbox_batch(batch_size: int = 1000) -> int:
    """
    Processes a batch of outbox events:
      - Sends the events in batch to ClickHouse.
      - Marks the events as processed (status = 'succeeded') in a single transaction.

    Returns:
        Number of events processed.
    """
    processed_count = 0

    with transaction.atomic():
        # Lock up to batch_size events in SCHEDULED status (skip locked to avoid deadlocks)
        events = Outbox.get_unprocessed_entries(batch_size)
        if not events:
            return 0

        data = [
            msgpack.unpackb(event.event_data, object_hook=decode_datetime, raw=False)
            for event in events
        ]

        with EventLogClient.init() as client:
            # Insert data into ClickHouse
            client.insert(data=data)

        # Mark events as processed only after successful insertion
        event_ids = [event.id for event in events]
        Outbox.mark_as_processed(event_ids)

        processed_count = len(event_ids)
        logger.info("Processed outbox batch", processed_count=processed_count)

    return processed_count
