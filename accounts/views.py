import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from common.throttles import LoginRateThrottle, UserSearchRateThrottle

from .models import PasswordResetToken, User
from .serializers import (
    ChangePasswordSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PrivateUserSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UpdateProfileSerializer,
)
from .tokens import CustomRefreshToken

LOGIN_ATTEMPT_KEY = 'login_attempts:{}'
LOGIN_ATTEMPT_LIMIT = getattr(settings, 'LOGIN_ATTEMPT_LIMIT', 5)
LOGIN_ATTEMPT_WINDOW = getattr(settings, 'LOGIN_ATTEMPT_WINDOW', 1800)
REFRESH_COOKIE_NAME = getattr(settings, 'REFRESH_COOKIE_NAME', 'refresh_token')
REFRESH_COOKIE_MAX_AGE = getattr(settings, 'REFRESH_COOKIE_MAX_AGE', 30 * 24 * 60 * 60)


def _set_refresh_cookie(response, refresh_token_str):
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token_str,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
        path='/',
    )


def _clear_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE_NAME, path='/')


def _build_token_response(user):
    refresh = CustomRefreshToken.for_user(user)
    access = refresh.access_token
    return refresh, {
        'access': str(access),
        'user': PrivateUserSerializer(user).data,
    }


def _revoke_all_sessions(user_id: str):
    """Increment token_version to invalidate all existing tokens for this user."""
    User.objects.filter(id=user_id).update(token_version=F('token_version') + 1)
    cache.delete(f'token_version:{user_id}')


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(PrivateUserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        attempt_key = LOGIN_ATTEMPT_KEY.format(username)
        attempts = cache.get(attempt_key, 0)

        if attempts >= LOGIN_ATTEMPT_LIMIT:
            return Response(
                {'error': 'Account locked due to too many failed login attempts. Try again later.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = authenticate(request, username=username, password=password)

        if user is None:
            cache.set(attempt_key, attempts + 1, LOGIN_ATTEMPT_WINDOW)
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'error': 'Account is inactive.'}, status=status.HTTP_401_UNAUTHORIZED)

        cache.delete(attempt_key)
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])

        refresh, data = _build_token_response(user)
        response = Response(data, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_str = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if token_str:
            try:
                token = CustomRefreshToken(token_str)
                token.blacklist()
            except TokenError:
                pass

        response = Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        _clear_refresh_cookie(response)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not token_str:
            return Response({'error': 'Refresh token not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = CustomRefreshToken(token_str)
        except TokenError:
            self._handle_potential_reuse(token_str)
            response = Response(
                {'error': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            return response

        user_id = str(old_refresh.get('user_id', ''))
        token_version = old_refresh.get('token_version', -1)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            response = Response({'error': 'User not found.'}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(response)
            return response

        if not user.is_active:
            response = Response({'error': 'Account is inactive.'}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(response)
            return response

        if token_version != user.token_version:
            response = Response({'error': 'Session has been revoked.'}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(response)
            return response

        old_refresh.blacklist()

        new_refresh = CustomRefreshToken.for_user(user)
        new_access = new_refresh.access_token

        response = Response({'access': str(new_access)}, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, str(new_refresh))
        return response

    def _handle_potential_reuse(self, token_str: str):
        try:
            payload = jwt.decode(token_str, options={'verify_signature': False})
            jti = payload.get('jti')
            user_id = str(payload.get('user_id', ''))

            if jti and user_id:
                if BlacklistedToken.objects.filter(token__jti=jti).exists():
                    _revoke_all_sessions(user_id)
        except Exception:
            pass


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        _revoke_all_sessions(str(user.id))

        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PrivateUserSerializer(request.user).data, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PrivateUserSerializer(request.user).data, status=status.HTTP_200_OK)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserSearchRateThrottle]

    def get(self, request, id):
        try:
            user = User.objects.get(id=id, is_active=True)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(PublicUserSerializer(user).data, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()

        _SAFE_RESPONSE = {'message': 'If the email is registered, a reset link has been sent.'}

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response(_SAFE_RESPONSE)

        token_obj = PasswordResetToken.create_for_user(user)
        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token_obj.token}"

        send_mail(
            subject='Password Reset Request',
            message=(
                f'Click the link below to reset your password:\n\n{reset_url}\n\n'
                'This link expires in 30 minutes. If you did not request a password reset, '
                'please ignore this email.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        return Response(_SAFE_RESPONSE)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        _INVALID = Response(
            {'error': 'Invalid or expired reset token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

        try:
            token_obj = PasswordResetToken.objects.select_related('user').get(
                token=data['token'],
                is_used=False,
            )
        except PasswordResetToken.DoesNotExist:
            return _INVALID

        if not token_obj.is_valid():
            return _INVALID

        user = token_obj.user
        user.set_password(data['new_password'])
        user.save(update_fields=['password'])

        token_obj.is_used = True
        token_obj.save(update_fields=['is_used'])

        _revoke_all_sessions(str(user.id))

        return Response({'message': 'Password has been reset successfully.'})
