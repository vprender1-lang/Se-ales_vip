from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('registro', '0002_signal_supportmessage')]
    operations = [
        migrations.AddField(model_name='signal', name='is_manual', field=models.BooleanField(default=False, db_index=True, verbose_name='Publicada manualmente')),
        migrations.AlterField(model_name='signal', name='entry_price', field=models.DecimalField(max_digits=20, decimal_places=8, default=0, blank=True)),
        migrations.AddField(model_name='signal', name='scheduled_entry_at', field=models.DateTimeField(null=True, blank=True, db_index=True)),
        migrations.AddField(model_name='signal', name='activated_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='signal', name='execution_entry_price', field=models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)),
    ]
