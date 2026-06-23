from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from common.internal_views import InternalRemindView

urlpatterns = [
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
    path('api/internal/remind/', InternalRemindView.as_view(), name='internal-remind'),
    path('', include('accounts.urls')),
    path('', include('groups.urls')),
    path('', include('schedules.urls')),
]
