import mimetypes

from django.db import migrations, models


def migrate_profile_avatars_to_db(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')

    for profile in Profile.objects.exclude(avatar='').exclude(avatar__isnull=True).iterator():
        if profile.avatar_data:
            continue

        avatar_field = profile.avatar
        if not avatar_field:
            continue

        try:
            avatar_field.open('rb')
            avatar_bytes = avatar_field.read()
        except Exception:
            continue
        finally:
            try:
                avatar_field.close()
            except Exception:
                pass

        if not avatar_bytes:
            continue

        filename = avatar_field.name.rsplit('/', 1)[-1]
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        if not content_type.startswith('image/'):
            continue

        profile.avatar_data = avatar_bytes
        profile.avatar_content_type = content_type
        profile.avatar_filename = filename
        profile.save(update_fields=['avatar_data', 'avatar_content_type', 'avatar_filename'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_add_premium_lobby_frames'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='avatar_content_type',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='profile',
            name='avatar_data',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='avatar_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(migrate_profile_avatars_to_db, migrations.RunPython.noop),
    ]
