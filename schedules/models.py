import uuid

from django.db import models
from django.utils import timezone


class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    detail = models.TextField(null=True, blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    subject = models.ForeignKey(
        'groups.Subject',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='schedules',
    )
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='created_schedules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'schedules'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])


class ScheduleTagRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='tag_relations',
    )
    tag = models.ForeignKey(
        'groups.Tag',
        on_delete=models.CASCADE,
        related_name='schedule_relations',
    )
    tagged_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='tagged_schedules',
    )
    tagged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'schedule_tag_relations'
        unique_together = [('schedule', 'tag')]


class CompletedUserRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='completed_schedules',
    )
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='completed_by',
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'completed_user_relations'
        unique_together = [('user', 'schedule')]
