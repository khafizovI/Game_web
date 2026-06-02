from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_profile_avatar_storage'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='avatar',
        ),
    ]
