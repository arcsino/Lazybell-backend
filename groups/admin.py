from django.contrib import admin

from .models import (
    Group,
    GroupRole,
    InvitedGroupRelation,
    RolePermission,
    Subject,
    Tag,
    UserGroupRelation,
    UserRoleRelation,
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_private', 'is_deleted', 'created_at']
    list_filter = ['is_private', 'is_deleted']
    search_fields = ['name', 'owner__username']
    readonly_fields = ['id', 'created_at', 'deleted_at']


@admin.register(UserGroupRelation)
class UserGroupRelationAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'status', 'joined_at']
    list_filter = ['status']
    search_fields = ['user__username', 'group__name']
    readonly_fields = ['id']


@admin.register(GroupRole)
class GroupRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'group']
    search_fields = ['name', 'group__name']
    readonly_fields = ['id']


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'can_invite_user', 'can_remove_member', 'can_manage_role',
                    'can_edit_group', 'can_edit_schedule', 'can_manage_subject', 'can_manage_tag']
    readonly_fields = ['id']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'group']
    search_fields = ['name', 'group__name']
    readonly_fields = ['id']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'group']
    search_fields = ['name', 'group__name']
    readonly_fields = ['id']


admin.site.register(InvitedGroupRelation)
admin.site.register(UserRoleRelation)
