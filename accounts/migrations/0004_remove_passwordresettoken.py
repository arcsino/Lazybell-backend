from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_email_passwordresettoken'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PasswordResetToken',
        ),
    ]
