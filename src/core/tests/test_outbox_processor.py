import json
from collections.abc import Generator

import msgpack
import pytest
from clickhouse_connect.driver import Client
from django.conf import settings
from django.utils import timezone

from core.outbox_processor import process_outbox_batch
from users.models import Outbox, Status

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def create_outbox_entries() -> list[Outbox]:
    entries = []
    for i in range(3):
        entry = Outbox.objects.create(
            event_data=msgpack.packb((
                'test_event_happened',
                {'__datetime__': True, 'as_str': timezone.now().strftime("%Y%m%dT%H:%M:%S.%f%z")},
                'Test',
                json.dumps({"important_value": f"Value{i}", "other_value": i}),
            )),
            status=Status.SCHEDULED,
        )
        entries.append(entry)
    return entries


@pytest.fixture(autouse=True)
def f_clean_up_event_log(f_ch_client: Client) -> Generator:
    f_ch_client.query(f'TRUNCATE TABLE {settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}')
    yield


def test_process_outbox_batch(create_outbox_entries, f_ch_client: Client) -> None:  # noqa ARG001
    processed_count = process_outbox_batch(batch_size=2)

    assert processed_count == 2

    processed_entries = Outbox.objects.filter(status=Status.SUCCEEDED)
    assert processed_entries.count() == 2

    remaining_entries = Outbox.objects.filter(status=Status.SCHEDULED)
    assert remaining_entries.count() == 1

    log = f_ch_client.query("SELECT * FROM default.event_log WHERE event_type = 'test_event_happened'")
    assert len(log.result_rows) == 2


def test_skip_failed_behavior(create_outbox_entries) -> None:  # noqa ARG001
    # check for skip FAILED
    event = Outbox.objects.filter(status=Status.SCHEDULED).first()
    event.status = Status.FAILED
    event.save()

    processed_count = process_outbox_batch(batch_size=3)

    assert processed_count == 2
