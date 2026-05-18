from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0005_remove_playeranswer_score_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='rewards_processed',
            field=models.BooleanField(default=False),
        ),
    ]
