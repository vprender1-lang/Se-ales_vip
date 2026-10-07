import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('quotex_id', models.CharField(db_index=True, max_length=20, verbose_name='ID de Quotex')),
                ('telegram_username', models.CharField(max_length=32, verbose_name='Usuario de Telegram')),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('approved', 'Aprobado'), ('rejected', 'Rechazado')], db_index=True, default='pending', max_length=10, verbose_name='Estado')),
                ('accepted_review', models.BooleanField(default=False, verbose_name='Aceptó revisión')),
                ('adult_confirmed', models.BooleanField(default=False, verbose_name='Confirmó mayoría de edad')),
                ('admin_notes', models.TextField(blank=True, verbose_name='Notas del administrador')),
                ('ip_hash', models.CharField(blank=True, editable=False, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Revisado')),
            ],
            options={'verbose_name': 'Solicitud VIP', 'verbose_name_plural': 'Solicitudes VIP', 'ordering': ['-created_at']},
        ),
    ]
