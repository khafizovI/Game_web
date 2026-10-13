from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0012_pet_inventoryitem_profile_selected_avatar_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='subscription_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='subscription_tier',
            field=models.CharField(
                choices=[('free', 'Free'), ('pro', 'Pro'), ('premium', 'Premium'), ('vip', 'VIP')],
                default='free',
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name='TeacherAIUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('count', models.PositiveIntegerField(default=0)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='ai_usages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date'],
                'unique_together': {('user', 'date')},
            },
        ),
    ]
