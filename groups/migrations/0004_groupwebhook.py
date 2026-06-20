import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0003_alter_tag_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GroupWebhook',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('webhook_type', models.CharField(
                    choices=[('remind', 'Remind'), ('created_log', 'Created Log')],
                    max_length=20,
                )),
                ('encrypted_url', models.CharField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webhooks',
                    to='groups.group',
                )),
                ('created_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='created_webhooks',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='updated_webhooks',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'group_webhooks',
                'unique_together': {('group', 'webhook_type')},
            },
        ),
    ]
