from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from groups.models import Group
from groups.serializers import SubjectSerializer, TagSerializer
from common.sanitizers import sanitize_text

from .models import CompletedUserRelation, Schedule, ScheduleTagRelation


class GroupBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']


class ScheduleTagRelationSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    tagged_by = PublicUserSerializer(read_only=True)

    class Meta:
        model = ScheduleTagRelation
        fields = ['id', 'tag', 'tagged_by', 'tagged_at']
        read_only_fields = fields


class CompletedUserRelationSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = CompletedUserRelation
        fields = ['id', 'user', 'completed_at']
        read_only_fields = fields


class ScheduleSerializer(serializers.ModelSerializer):
    created_by = PublicUserSerializer(read_only=True)
    subject = SubjectSerializer(read_only=True)
    tags = serializers.SerializerMethodField()
    completed_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            'id', 'title', 'detail', 'start_at', 'deadline', 'is_all_day',
            'subject', 'tags', 'created_by', 'created_at', 'updated_at',
            'completed_by_me',
        ]
        read_only_fields = fields

    def get_tags(self, obj):
        return TagSerializer(
            [rel.tag for rel in obj.tag_relations.select_related('tag').all()],
            many=True,
        ).data

    def get_completed_by_me(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.completed_by.filter(user=request.user).exists()


class ScheduleDetailSerializer(ScheduleSerializer):
    """Extends ScheduleSerializer with full completion list (used in detail view)."""
    completions = CompletedUserRelationSerializer(source='completed_by', many=True, read_only=True)

    class Meta(ScheduleSerializer.Meta):
        fields = ScheduleSerializer.Meta.fields + ['completions']
        read_only_fields = fields


class UpcomingScheduleSerializer(serializers.ModelSerializer):
    group = GroupBriefSerializer(read_only=True)
    subject = SubjectSerializer(read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = ['id', 'title', 'start_at', 'deadline', 'is_all_day', 'group', 'subject', 'tags']
        read_only_fields = fields

    def get_tags(self, obj):
        return TagSerializer(
            [rel.tag for rel in obj.tag_relations.all()],
            many=True,
        ).data


class ScheduleCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    detail = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    start_at = serializers.DateTimeField(required=False, allow_null=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    is_all_day = serializers.BooleanField(required=False, default=False)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def validate_title(self, value):
        return sanitize_text(value)

    def validate_detail(self, value):
        return sanitize_text(value)

    def validate(self, data):
        start = data.get('start_at')
        deadline = data.get('deadline')
        if start and deadline and start > deadline:
            raise serializers.ValidationError(
                {'start_at': '開始日時は終了日時より前に設定してください。'}
            )
        return data


class ScheduleUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    detail = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    start_at = serializers.DateTimeField(required=False, allow_null=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    is_all_day = serializers.BooleanField(required=False)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
    )

    def validate_title(self, value):
        return sanitize_text(value)

    def validate_detail(self, value):
        return sanitize_text(value)

    def validate(self, data):
        schedule = self.context.get('schedule')
        start = data.get('start_at', getattr(schedule, 'start_at', None))
        deadline = data.get('deadline', getattr(schedule, 'deadline', None))
        if start and deadline and start > deadline:
            raise serializers.ValidationError(
                {'start_at': '開始日時は終了日時より前に設定してください。'}
            )
        return data
