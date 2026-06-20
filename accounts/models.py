import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, username, password, nickname, email=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        if not nickname:
            raise ValueError('Nickname is required')
        user = self.model(username=username, nickname=nickname, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, nickname, **extra_fields):
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(username, password, nickname, **extra_fields)


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    nickname = models.CharField(max_length=150)
    biography = models.TextField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(default=timezone.now)
    token_version = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['nickname']

    objects = UserManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'

    @classmethod
    def create_for_user(cls, user):
        cls.objects.filter(user=user, is_used=False).delete()
        token = secrets.token_urlsafe(48)
        expires_at = timezone.now() + timedelta(minutes=30)
        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()
