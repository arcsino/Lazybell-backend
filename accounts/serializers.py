import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from common.sanitizers import sanitize_text

from .models import User


def validate_password_strength(password):
    if len(password) < 8:
        raise serializers.ValidationError('Password must be at least 8 characters.')
    if not re.search(r'[A-Za-z]', password):
        raise serializers.ValidationError('Password must contain at least one letter.')
    if not re.search(r'[0-9]', password):
        raise serializers.ValidationError('Password must contain at least one digit.')
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{}|;:\'",.<>?/`~\\]', password):
        raise serializers.ValidationError('Password must contain at least one special character.')
    return password


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'nickname', 'biography']
        extra_kwargs = {
            'biography': {'required': False, 'allow_null': True},
        }

    def validate_password(self, value):
        return validate_password_strength(value)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already in use.')
        return value

    def validate_nickname(self, value):
        return sanitize_text(value)

    def validate_biography(self, value):
        return sanitize_text(value)

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            nickname=validated_data['nickname'],
            biography=validated_data.get('biography'),
        )


class PublicUserSerializer(serializers.ModelSerializer):
    """Minimal user info returned in public-facing endpoints."""

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'biography', 'registered_at']
        read_only_fields = fields


class PrivateUserSerializer(serializers.ModelSerializer):
    """Full user info for the authenticated user themselves."""

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'biography', 'last_login_at', 'registered_at']
        read_only_fields = fields


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['nickname', 'biography']

    def validate_nickname(self, value):
        return sanitize_text(value)

    def validate_biography(self, value):
        return sanitize_text(value)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        return validate_password_strength(value)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_new_password(self, value):
        return validate_password_strength(value)
