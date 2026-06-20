from django.urls import path

from .views import ScheduleCompleteView, ScheduleDetailView, ScheduleListCreateView, UpcomingScheduleView

urlpatterns = [
    path('users/me/upcoming-schedules/', UpcomingScheduleView.as_view(), name='upcoming-schedules'),
    path('groups/<uuid:group_id>/schedules/', ScheduleListCreateView.as_view(), name='schedule-list-create'),
    path('groups/<uuid:group_id>/schedules/<uuid:schedule_id>/', ScheduleDetailView.as_view(), name='schedule-detail'),
    path(
        'groups/<uuid:group_id>/schedules/<uuid:schedule_id>/complete/',
        ScheduleCompleteView.as_view(),
        name='schedule-complete',
    ),
]
