import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('groups', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('detail', models.TextField(blank=True, null=True)),
                ('start_at', models.DateTimeField(blank=True, null=True)),
                ('deadline', models.DateTimeField(blank=True, null=True)),
                ('is_all_day', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_schedules', to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='groups.group')),
                ('subject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='schedules', to='groups.subject')),
            ],
            options={
                'db_table': 'schedules',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CompletedUserRelation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('completed_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='completed_schedules', to=settings.AUTH_USER_MODEL)),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='completed_by', to='schedules.schedule')),
            ],
            options={
                'db_table': 'completed_user_relations',
                'unique_together': {('user', 'schedule')},
            },
        ),
        migrations.CreateModel(
            name='ScheduleTagRelation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tagged_at', models.DateTimeField(auto_now_add=True)),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tag_relations', to='schedules.schedule')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedule_relations', to='groups.tag')),
                ('tagged_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tagged_schedules', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'schedule_tag_relations',
                'unique_together': {('schedule', 'tag')},
            },
        ),
    ]
