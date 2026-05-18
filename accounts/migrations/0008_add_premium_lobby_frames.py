from django.db import migrations


def add_premium_frames(apps, schema_editor):
    ShopItem = apps.get_model('accounts', 'ShopItem')

    frames = [
        {
            'name': 'Mythic Frame',
            'description': 'A legendary ranked border with violet energy and gold highlights.',
            'item_type': 'frame',
            'price': 560,
            'css_class': 'mythic-frame',
            'is_active': True,
        },
        {
            'name': 'Starlight Frame',
            'description': 'A celestial border with polished silver light and star shimmer.',
            'item_type': 'frame',
            'price': 520,
            'css_class': 'starlight-frame',
            'is_active': True,
        },
        {
            'name': 'Tempest Frame',
            'description': 'A storm-charged border with blue lightning and arcane glow.',
            'item_type': 'frame',
            'price': 490,
            'css_class': 'tempest-frame',
            'is_active': True,
        },
        {
            'name': 'Obsidian Frame',
            'description': 'A dark elite border with void aura and magenta embers.',
            'item_type': 'frame',
            'price': 540,
            'css_class': 'obsidian-frame',
            'is_active': True,
        },
    ]

    for frame in frames:
        ShopItem.objects.update_or_create(
            name=frame['name'],
            defaults=frame,
        )


def remove_premium_frames(apps, schema_editor):
    ShopItem = apps.get_model('accounts', 'ShopItem')
    ShopItem.objects.filter(
        css_class__in=[
            'mythic-frame',
            'starlight-frame',
            'tempest-frame',
            'obsidian-frame',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_profile_experience_points_profile_level'),
    ]

    operations = [
        migrations.RunPython(add_premium_frames, remove_premium_frames),
    ]
