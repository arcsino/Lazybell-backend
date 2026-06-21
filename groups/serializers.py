from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from common.sanitizers import sanitize_text
from common.webhooks import validate_discord_url

from .models import (
    Group,
    GroupRole,
    GroupWebhook,
    InvitedGroupRelation,
    RolePermission,
    Subject,
    Tag,
    UserGroupRelation,
    UserRoleRelation,
)


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['name', 'description', 'is_private', 'max_members']
        extra_kwargs = {
            'description': {'required': False, 'allow_null': True},
            'max_members': {'required': False, 'allow_null': True},
        }

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)


class GroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['name', 'description', 'is_private', 'max_members']
        extra_kwargs = {
            'name': {'required': False},
            'description': {'required': False, 'allow_null': True},
            'is_private': {'required': False},
            'max_members': {'required': False, 'allow_null': True},
        }

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)


class GroupSerializer(serializers.ModelSerializer):
    owner = PublicUserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'is_private', 'max_members', 'owner', 'member_count', 'is_member', 'created_at']
        read_only_fields = fields

    def get_member_count(self, obj):
        return obj.member_relations.filter(status=UserGroupRelation.Status.JOINED).count()

    def get_is_member(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        if str(obj.owner_id) == str(user.id):
            return True
        return obj.member_relations.filter(user=user, status=UserGroupRelation.Status.JOINED).exists()


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = [
            'can_invite_user',
            'can_remove_member',
            'can_manage_role',
            'can_edit_group',
            'can_edit_schedule',
            'can_manage_subject',
            'can_manage_tag',
            'can_manage_webhook',
        ]


class GroupRoleSerializer(serializers.ModelSerializer):
    permission = RolePermissionSerializer(read_only=True)

    class Meta:
        model = GroupRole
        fields = ['id', 'name', 'permission']
        read_only_fields = ['id']


class GroupRoleCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    permission = RolePermissionSerializer()

    def validate_name(self, value):
        group = self.context['group']
        if GroupRole.objects.filter(name=value, group=group).exists():
            raise serializers.ValidationError('A role with this name already exists in the group.')
        return sanitize_text(value)


class GroupRoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    permission = RolePermissionSerializer(required=False)

    def validate_name(self, value):
        return sanitize_text(value)


class MemberRelationSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = UserGroupRelation
        fields = ['id', 'user', 'status', 'joined_at', 'roles']
        read_only_fields = fields

    def get_roles(self, obj):
        roles = GroupRole.objects.filter(
            userrelations__user=obj.user,
            group=obj.group,
        ).only('id', 'name')
        return [{'id': str(r.id), 'name': r.name} for r in roles]


class InviteSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)
    invited_by = PublicUserSerializer(read_only=True)

    class Meta:
        model = InvitedGroupRelation
        fields = ['id', 'group', 'invited_by', 'created_at']
        read_only_fields = fields


class GroupPendingInviteSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    invited_by = PublicUserSerializer(read_only=True)

    class Meta:
        model = InvitedGroupRelation
        fields = ['id', 'user', 'invited_by', 'created_at']
        read_only_fields = fields


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']
        read_only_fields = ['id']

    def validate_name(self, value):
        return sanitize_text(value)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'priority']
        read_only_fields = ['id', 'priority']

    def validate_name(self, value):
        return sanitize_text(value)


class TagReorderSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)


class AssignRoleSerializer(serializers.Serializer):
    role_id = serializers.UUIDField()


class WebhookSerializer(serializers.ModelSerializer):
    created_by = PublicUserSerializer(read_only=True)
    updated_by = PublicUserSerializer(read_only=True)

    class Meta:
        model = GroupWebhook
        fields = ['id', 'webhook_type', 'name', 'created_by', 'updated_by', 'created_at', 'updated_at']
        read_only_fields = fields


class WebhookCreateSerializer(serializers.Serializer):
    webhook_type = serializers.ChoiceField(choices=GroupWebhook.WebhookType.choices)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    url = serializers.CharField()

    def validate_url(self, value):
        if not validate_discord_url(value):
            raise serializers.ValidationError(
                'Invalid Discord webhook URL. Expected format: '
                'https://discord.com/api/webhooks/{id}/{token}'
            )
        return value


class WebhookUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    url = serializers.CharField(required=False)

    def validate_url(self, value):
        if not validate_discord_url(value):
            raise serializers.ValidationError(
                'Invalid Discord webhook URL. Expected format: '
                'https://discord.com/api/webhooks/{id}/{token}'
            )
        return value
