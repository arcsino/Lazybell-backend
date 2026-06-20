from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import Group, Subject, Tag, UserGroupRelation
from groups.permissions import has_permission, is_group_member
from common.moderation import ModerationError, check_moderation
from common.webhooks import notify_created_log

from .models import CompletedUserRelation, Schedule, ScheduleTagRelation
from .serializers import (
    ScheduleCreateSerializer,
    ScheduleDetailSerializer,
    ScheduleSerializer,
    ScheduleUpdateSerializer,
    UpcomingScheduleSerializer,
)


class UpcomingScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        user = request.user

        owned_ids = Group.objects.filter(owner=user, is_deleted=False).values_list('id', flat=True)
        joined_ids = UserGroupRelation.objects.filter(
            user=user, status=UserGroupRelation.Status.JOINED
        ).values_list('group_id', flat=True)
        all_group_ids = list(owned_ids) + list(joined_ids)

        completed_ids = CompletedUserRelation.objects.filter(user=user).values_list('schedule_id', flat=True)

        schedules = (
            Schedule.objects.filter(
                group_id__in=all_group_ids,
                is_deleted=False,
                deadline__gte=now,
            )
            .exclude(id__in=completed_ids)
            .select_related('subject', 'group')
            .prefetch_related('tag_relations__tag')
            .order_by('deadline')
        )

        return Response(UpcomingScheduleSerializer(schedules, many=True).data)


def _get_active_group(group_id):
    return get_object_or_404(Group, id=group_id, is_deleted=False)


def _require_member_access(user, group):
    """Return 403 if user is not a member/owner, else None."""
    is_owner = str(group.owner_id) == str(user.id)
    if not is_owner and not is_group_member(user, group):
        return Response({'error': 'You are not a member of this group.'}, status=status.HTTP_403_FORBIDDEN)
    return None


def _resolve_subject(subject_id, group):
    """Resolve subject_id, ensuring it belongs to the same group."""
    if subject_id is None:
        return None
    subject = Subject.objects.filter(id=subject_id, group=group).first()
    if not subject:
        raise ValueError('Subject does not belong to this group.')
    return subject


def _resolve_tags(tag_ids, group):
    """Resolve tag UUIDs, ensuring they all belong to the same group."""
    if not tag_ids:
        return []
    tags = list(Tag.objects.filter(id__in=tag_ids, group=group))
    if len(tags) != len(set(tag_ids)):
        raise ValueError('One or more tags do not belong to this group.')
    return tags


class ScheduleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_member_access(request.user, group)
        if err:
            return err

        schedules = (
            Schedule.objects.filter(group=group, is_deleted=False)
            .select_related('created_by', 'subject')
            .prefetch_related('tag_relations__tag', 'completed_by')
            .order_by('-created_at')
        )
        serializer = ScheduleSerializer(schedules, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, group_id):
        group = _get_active_group(group_id)

        if not has_permission(request.user, group, 'can_edit_schedule'):
            return Response(
                {'error': 'You do not have permission to create schedules.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            check_moderation([t for t in [data.get('title'), data.get('detail')] if t])
            subject = _resolve_subject(data.get('subject_id'), group)
            tags = _resolve_tags(data.get('tag_ids', []), group)
        except ModerationError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            schedule = Schedule.objects.create(
                title=data['title'],
                detail=data.get('detail'),
                start_at=data.get('start_at'),
                deadline=data.get('deadline'),
                is_all_day=data.get('is_all_day', False),
                group=group,
                subject=subject,
                created_by=request.user,
            )
            for tag in tags:
                ScheduleTagRelation.objects.create(
                    schedule=schedule,
                    tag=tag,
                    tagged_by=request.user,
                )

        schedule.refresh_from_db()
        notify_created_log(schedule)
        return Response(
            ScheduleSerializer(schedule, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_schedule(self, group, schedule_id):
        return get_object_or_404(Schedule, id=schedule_id, group=group, is_deleted=False)

    def get(self, request, group_id, schedule_id):
        group = _get_active_group(group_id)
        err = _require_member_access(request.user, group)
        if err:
            return err

        schedule = (
            Schedule.objects.filter(id=schedule_id, group=group, is_deleted=False)
            .select_related('created_by', 'subject')
            .prefetch_related('tag_relations__tag', 'completed_by__user')
            .first()
        )
        if not schedule:
            return Response({'error': 'Schedule not found.'}, status=404)
        return Response(ScheduleDetailSerializer(schedule, context={'request': request}).data)

    def patch(self, request, group_id, schedule_id):
        group = _get_active_group(group_id)
        err = _require_member_access(request.user, group)
        if err:
            return err

        schedule = self._get_schedule(group, schedule_id)

        is_creator = str(schedule.created_by_id) == str(request.user.id)
        if not is_creator and not has_permission(request.user, group, 'can_edit_schedule'):
            return Response(
                {'error': 'You do not have permission to edit this schedule.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ScheduleUpdateSerializer(data=request.data, partial=True, context={'schedule': schedule})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            texts = [
                v for key, current in (('title', schedule.title), ('detail', schedule.detail))
                if key in data and (v := data.get(key)) and v != current
            ]
            check_moderation(texts)
            subject = _resolve_subject(data.get('subject_id', 'SKIP'), group) if 'subject_id' in data else 'SKIP'
            tags = _resolve_tags(data['tag_ids'], group) if 'tag_ids' in data else None
        except ModerationError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if 'title' in data:
                schedule.title = data['title']
            if 'detail' in data:
                schedule.detail = data['detail']
            if 'start_at' in data:
                schedule.start_at = data['start_at']
            if 'deadline' in data:
                schedule.deadline = data['deadline']
            if 'is_all_day' in data:
                schedule.is_all_day = data['is_all_day']
            if subject != 'SKIP':
                schedule.subject = subject
            schedule.save()

            if tags is not None:
                ScheduleTagRelation.objects.filter(schedule=schedule).delete()
                for tag in tags:
                    ScheduleTagRelation.objects.create(
                        schedule=schedule,
                        tag=tag,
                        tagged_by=request.user,
                    )

        return Response(ScheduleSerializer(schedule, context={'request': request}).data)

    def delete(self, request, group_id, schedule_id):
        group = _get_active_group(group_id)
        err = _require_member_access(request.user, group)
        if err:
            return err

        schedule = self._get_schedule(group, schedule_id)

        is_creator = str(schedule.created_by_id) == str(request.user.id)
        if not is_creator and not has_permission(request.user, group, 'can_edit_schedule'):
            return Response(
                {'error': 'You do not have permission to delete this schedule.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        schedule.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScheduleCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id, schedule_id):
        group = _get_active_group(group_id)
        err = _require_member_access(request.user, group)
        if err:
            return err

        schedule = get_object_or_404(Schedule, id=schedule_id, group=group, is_deleted=False)

        if CompletedUserRelation.objects.filter(user=request.user, schedule=schedule).exists():
            return Response({'error': 'Schedule already marked as completed.'}, status=status.HTTP_400_BAD_REQUEST)

        relation = CompletedUserRelation.objects.create(user=request.user, schedule=schedule)
        return Response({'completed_at': relation.completed_at}, status=status.HTTP_201_CREATED)

    def delete(self, request, group_id, schedule_id):
        group = _get_active_group(group_id)
        err = _require_member_access(request.user, group)
        if err:
            return err

        schedule = get_object_or_404(Schedule, id=schedule_id, group=group, is_deleted=False)
        relation = CompletedUserRelation.objects.filter(user=request.user, schedule=schedule).first()

        if not relation:
            return Response({'error': 'Schedule is not marked as completed.'}, status=status.HTTP_400_BAD_REQUEST)

        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
