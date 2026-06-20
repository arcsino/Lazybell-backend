from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tag',
            name='color',
            field=models.CharField(default='#6B7280', max_length=7),
        ),
        migrations.AddField(
            model_name='tag',
            name='priority',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
