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


class Signal(models.Model):
    class Direction(models.TextChoices):
        CALL = 'CALL', 'CALL / Alza'
        PUT = 'PUT', 'PUT / Baja'
        WAIT = 'WAIT', 'Esperar'

    class Outcome(models.TextChoices):
        OPEN = 'open', 'Abierta'
        WIN = 'win', 'Ganadora'
        LOSS = 'loss', 'Perdedora'
        DRAW = 'draw', 'Empate'

    asset = models.CharField(max_length=20, db_index=True)
    timeframe = models.PositiveSmallIntegerField(default=1, db_index=True)
    strategy = models.CharField(max_length=80, default='Confluencia técnica')
    direction = models.CharField(max_length=4, choices=Direction.choices)
    score = models.FloatField(default=0)
    confidence = models.PositiveSmallIntegerField(default=0)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    scheduled_entry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    execution_entry_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    source = models.CharField(max_length=60, default='Kraken Public Market Data')
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=8, choices=Outcome.choices, default=Outcome.OPEN, db_index=True)

    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['asset', 'timeframe', '-generated_at']),
            models.Index(fields=['outcome', 'expires_at']),
        ]

    def __str__(self):
        return f'{self.asset} {self.timeframe}m {self.direction} {self.generated_at:%Y-%m-%d %H:%M}'


class SupportMessage(models.Model):
    class Sender(models.TextChoices):
        USER = 'user', 'Usuario'
        ADMIN = 'admin', 'Administrador'

    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='support_messages')
    sender = models.CharField(max_length=8, choices=Sender.choices)
    text = models.TextField(max_length=1200)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.registration.quotex_id} - {self.sender} - {self.created_at:%Y-%m-%d %H:%M}'
