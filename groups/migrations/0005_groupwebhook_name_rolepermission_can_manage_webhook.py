from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0004_groupwebhook'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupwebhook',
            name='name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterUniqueTogether(
            name='groupwebhook',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='rolepermission',
            name='can_manage_webhook',
            field=models.BooleanField(default=False),
        ),
    ]
