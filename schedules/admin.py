from django.contrib import admin

from .models import CompletedUserRelation, Schedule, ScheduleTagRelation


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['title', 'group', 'created_by', 'start_at', 'deadline', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'is_all_day']
    search_fields = ['title', 'group__name', 'created_by__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']


@admin.register(ScheduleTagRelation)
class ScheduleTagRelationAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'tag', 'tagged_by', 'tagged_at']
    readonly_fields = ['id', 'tagged_at']


@admin.register(CompletedUserRelation)
class CompletedUserRelationAdmin(admin.ModelAdmin):
    list_display = ['user', 'schedule', 'completed_at']
    readonly_fields = ['id', 'completed_at']
