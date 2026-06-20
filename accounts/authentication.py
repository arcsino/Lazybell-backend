from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CustomJWTAuthentication(JWTAuthentication):
    """
    Extends standard JWT auth with token_version validation.
    When all sessions are revoked (e.g., on token reuse detection),
    token_version is incremented and all existing tokens are rejected.
    """

    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)

        token_version = validated_token.get('token_version')
        if token_version is None:
            return validated_token

        user_id = str(validated_token.get('user_id', ''))
        cache_key = f'token_version:{user_id}'
        cached_version = cache.get(cache_key)

        if cached_version is None:
            from accounts.models import User
            try:
                user = User.objects.only('token_version', 'is_active').get(id=user_id)
            except User.DoesNotExist:
                raise InvalidToken('User not found')

            if not user.is_active:
                raise InvalidToken('User account is inactive')

            cached_version = user.token_version
            cache.set(cache_key, cached_version, 300)

        if token_version != cached_version:
            raise InvalidToken('Session has been revoked')

        return validated_token
