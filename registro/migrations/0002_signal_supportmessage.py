# Generated manually for Señales VIP del Latino
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('registro', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Signal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset', models.CharField(db_index=True, max_length=20)),
                ('timeframe', models.PositiveSmallIntegerField(db_index=True, default=1)),
                ('strategy', models.CharField(default='Confluencia técnica', max_length=80)),
                ('direction', models.CharField(choices=[('CALL', 'CALL / Alza'), ('PUT', 'PUT / Baja'), ('WAIT', 'Esperar')], max_length=4)),
                ('score', models.FloatField(default=0)),
                ('confidence', models.PositiveSmallIntegerField(default=0)),
                ('entry_price', models.DecimalField(decimal_places=8, max_digits=20)),
                ('exit_price', models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ('source', models.CharField(default='Kraken Public Market Data', max_length=60)),
                ('generated_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('evaluated_at', models.DateTimeField(blank=True, null=True)),
                ('outcome', models.CharField(choices=[('open', 'Abierta'), ('win', 'Ganadora'), ('loss', 'Perdedora'), ('draw', 'Empate')], db_index=True, default='open', max_length=8)),
            ],
            options={'ordering': ['-generated_at']},
        ),
        migrations.CreateModel(
            name='SupportMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender', models.CharField(choices=[('user', 'Usuario'), ('admin', 'Administrador')], max_length=8)),
                ('text', models.TextField(max_length=1200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_messages', to='registro.registration')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.AddIndex(
            model_name='signal',
            index=models.Index(fields=['asset', 'timeframe', '-generated_at'], name='registro_si_asset_a02c3e_idx'),
        ),
        migrations.AddIndex(
            model_name='signal',
            index=models.Index(fields=['outcome', 'expires_at'], name='registro_si_outcome_7142ef_idx'),
        ),
    ]
