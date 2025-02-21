
from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.db.models import QuerySet

from core.models import TimeStampedModel


class User(TimeStampedModel, AbstractBaseUser):
    email = models.EmailField(unique=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'

    class Meta(AbstractBaseUser.Meta):
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self) -> str:
        if all([self.first_name, self.last_name]):
            return f'{self.first_name} {self.last_name}'

        return self.email


class Status(models.TextChoices):
    """
    Defines status choices for the Outbox
    """
    SCHEDULED = 'scheduled', 'Scheduled'  # Event is scheduled for processing
    SUCCEEDED = 'succeeded', 'Succeeded'  # Event was successfully processed
    FAILED = 'failed', 'Failed'  # Event failed to be processed


class Outbox(TimeStampedModel):
    """
    Outbox model for storing events before processing
    """
    event_data = models.BinaryField(help_text='Event data pickled')

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text='Status of the event (scheduled, succeeded, failed)',
    )

    @classmethod
    def get_unprocessed_entries(cls, batch_size: int) -> QuerySet:
        """
        Get all unprocessed entries with status 'scheduled'
        """
        filters = {"status": Status.SCHEDULED}
        return cls.objects.filter(**filters).order_by("created_at")[:batch_size]

    @classmethod
    def mark_as_processed(cls, pk_list: list[int]) -> None:
        """
        Method to mark the events as processed
        """
        cls.objects.filter(pk__in=pk_list).update(status=Status.SUCCEEDED)

    def __str__(self) -> str:
        return f"Outbox Entry {self.id}: ({self.status})"
