import uuid

from django.db import models
from django.utils import timezone


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_private = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    max_members = models.PositiveIntegerField(null=True, blank=True)
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='owned_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'groups'

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])


class UserGroupRelation(models.Model):
    class Status(models.TextChoices):
        JOINED = 'joined', 'Joined'
        REQUEST_PENDING = 'request_pending', 'Request Pending'
        REJECTED = 'rejected', 'Rejected'
        BANNED = 'banned', 'Banned'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='group_relations',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='member_relations',
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_group_relations'
        unique_together = [('user', 'group')]

    def approve(self):
        self.status = self.Status.JOINED
        self.joined_at = timezone.now()
        self.save(update_fields=['status', 'joined_at'])


class InvitedGroupRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='received_invites',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='invites',
    )
    invited_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='sent_invites',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invited_group_relations'
        unique_together = [('user', 'group')]


class GroupRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='roles',
    )

    class Meta:
        db_table = 'group_roles'
        unique_together = [('name', 'group')]

    def __str__(self):
        return f'{self.group.name} / {self.name}'


class RolePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.OneToOneField(
        GroupRole,
        on_delete=models.CASCADE,
        related_name='permission',
    )
    can_invite_user = models.BooleanField(default=False)
    can_remove_member = models.BooleanField(default=False)
    can_manage_role = models.BooleanField(default=False)
    can_edit_group = models.BooleanField(default=False)
    can_edit_schedule = models.BooleanField(default=False)
    can_manage_subject = models.BooleanField(default=False)
    can_manage_tag = models.BooleanField(default=False)
    can_manage_webhook = models.BooleanField(default=False)

    class Meta:
        db_table = 'role_permissions'


class UserRoleRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='role_relations',
    )
    role = models.ForeignKey(
        GroupRole,
        on_delete=models.CASCADE,
        related_name='userrelations',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='assigned_roles',
    )

    class Meta:
        db_table = 'user_role_relations'
        unique_together = [('user', 'role')]


class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='subjects',
    )

    class Meta:
        db_table = 'subjects'

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#6B7280')
    priority = models.PositiveIntegerField(default=0)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='tags',
    )

    class Meta:
        db_table = 'tags'
        unique_together = [('name', 'group')]
        ordering = ['priority', 'name']

    def __str__(self):
        return self.name


class GroupWebhook(models.Model):
    class WebhookType(models.TextChoices):
        REMIND = 'remind', 'Remind'
        CREATED_LOG = 'created_log', 'Created Log'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='webhooks',
    )
    webhook_type = models.CharField(max_length=20, choices=WebhookType.choices)
    name = models.CharField(max_length=100, blank=True, default='')
    encrypted_url = models.CharField(max_length=500)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='created_webhooks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='updated_webhooks',
    )

    class Meta:
        db_table = 'group_webhooks'

    def __str__(self):
        return f'{self.group.name} / {self.webhook_type}'
