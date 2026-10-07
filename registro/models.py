import uuid
from django.db import models


class Registration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        APPROVED = 'approved', 'Aprobado'
        REJECTED = 'rejected', 'Rechazado'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    quotex_id = models.CharField('ID de Quotex', max_length=20, db_index=True)
    telegram_username = models.CharField('Usuario de Telegram', max_length=32)
    status = models.CharField('Estado', max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    accepted_review = models.BooleanField('Aceptó revisión', default=False)
    adult_confirmed = models.BooleanField('Confirmó mayoría de edad', default=False)
    admin_notes = models.TextField('Notas del administrador', blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, editable=False)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)
    reviewed_at = models.DateTimeField('Revisado', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Solicitud VIP'
        verbose_name_plural = 'Solicitudes VIP'

    def __str__(self):
        return f'{self.quotex_id} - @{self.telegram_username} - {self.get_status_display()}'
