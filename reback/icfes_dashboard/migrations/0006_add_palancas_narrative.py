from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icfes_dashboard', '0005_ensure_mlanalisisia_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='mlanalisisia',
            name='palancas_narrative',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
    ]
