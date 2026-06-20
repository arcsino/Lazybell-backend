import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_private', models.BooleanField(default=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('max_members', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_groups', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'groups',
            },
        ),
        migrations.CreateModel(
            name='GroupRole',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roles', to='groups.group')),
            ],
            options={
                'db_table': 'group_roles',
                'unique_together': {('name', 'group')},
            },
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('can_invite_user', models.BooleanField(default=False)),
                ('can_remove_member', models.BooleanField(default=False)),
                ('can_manage_role', models.BooleanField(default=False)),
                ('can_edit_group', models.BooleanField(default=False)),
                ('can_edit_schedule', models.BooleanField(default=False)),
                ('can_manage_subject', models.BooleanField(default=False)),
                ('can_manage_tag', models.BooleanField(default=False)),
                ('role', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='permission', to='groups.grouprole')),
            ],
            options={
                'db_table': 'role_permissions',
            },
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subjects', to='groups.group')),
            ],
            options={
                'db_table': 'subjects',
            },
        ),
        migrations.CreateModel(
            name='InvitedGroupRelation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invites', to='groups.group')),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_invites', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_invites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'invited_group_relations',
                'unique_together': {('user', 'group')},
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='groups.group')),
            ],
            options={
                'db_table': 'tags',
                'unique_together': {('name', 'group')},
            },
        ),
        migrations.CreateModel(
            name='UserGroupRelation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('joined', 'Joined'), ('request_pending', 'Request Pending'), ('rejected', 'Rejected'), ('banned', 'Banned')], max_length=20)),
                ('joined_at', models.DateTimeField(blank=True, null=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_relations', to='groups.group')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_relations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_group_relations',
                'unique_together': {('user', 'group')},
            },
        ),
        migrations.CreateModel(
            name='UserRoleRelation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('assigned_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assigned_roles', to=settings.AUTH_USER_MODEL)),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='userrelations', to='groups.grouprole')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_relations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_role_relations',
                'unique_together': {('user', 'role')},
            },
        ),
    ]
