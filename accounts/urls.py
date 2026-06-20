from django.urls import path

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    RegisterView,
    UpdateProfileView,
    UserDetailView,
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/refresh/', RefreshView.as_view(), name='auth-refresh'),
    path('auth/reset-password/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('auth/reset-password/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('users/me/', MeView.as_view(), name='me'),
    path('users/me/password/', ChangePasswordView.as_view(), name='change-password'),
    path('users/me/profile/', UpdateProfileView.as_view(), name='update-profile'),
    path('users/<uuid:id>/', UserDetailView.as_view(), name='user-detail'),
]
