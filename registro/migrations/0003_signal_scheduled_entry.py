from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('registro', '0002_signal_supportmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='signal',
            name='scheduled_entry_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='signal',
            name='activated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='signal',
            name='execution_entry_price',
            field=models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True),
        ),
    ]
