import re
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import msgpack
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.base_model import Model
from users.models import Outbox, Status


def to_snake_case(event_name: str) -> str:
    """Converts a string to snake_case."""
    result = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', event_name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', result).lower()


F = TypeVar('F', bound=Callable[..., Any])


def publish_event(func: F) -> F:
    """
    This decorator will publish an event after the function execution.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Model:  # noqa ANN003
        with transaction.atomic():
            event = func(self, *args, **kwargs)

            if event.result:
                event_type = to_snake_case(event.result.__class__.__name__)
                event_context = event.result.model_dump_json()
            else:
                event_type = 'error'
                event_context = event.error

            event_time_encoded  = {'__datetime__': True, 'as_str': timezone.now().strftime("%Y%m%dT%H:%M:%S.%f")}
            event_data = (
                event_type,
                event_time_encoded,
                settings.ENVIRONMENT,
                event_context,
            )

            # Publishing the event to Outbox
            Outbox.objects.create(event_data=msgpack.packb(event_data), status=Status.SCHEDULED)

            return event

    return wrapper
