from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('registro', '0003_signal_scheduled_entry')]

    operations = [
        migrations.AddField(
            model_name='signal',
            name='is_manual',
            field=models.BooleanField(default=False, db_index=True, verbose_name='Publicada manualmente'),
        ),
        migrations.AlterField(
            model_name='signal',
            name='entry_price',
            field=models.DecimalField(max_digits=20, decimal_places=8, default=0, blank=True),
        ),
    ]
