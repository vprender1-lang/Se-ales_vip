from django import forms
from django.contrib import admin
from django.utils import timezone

from .models import Registration, Signal, SupportMessage


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('quotex_id', 'telegram_username', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('quotex_id', 'telegram_username', 'public_id')
    readonly_fields = ('public_id', 'ip_hash', 'created_at', 'updated_at', 'reviewed_at')
    actions = ('approve_selected', 'reject_selected')

    @admin.action(description='Aprobar solicitudes seleccionadas')
    def approve_selected(self, request, queryset):
        queryset.update(status=Registration.Status.APPROVED, reviewed_at=timezone.now())

    @admin.action(description='Rechazar solicitudes seleccionadas')
    def reject_selected(self, request, queryset):
        queryset.update(status=Registration.Status.REJECTED, reviewed_at=timezone.now())


class ManualSignalForm(forms.ModelForm):
    class Meta:
        model = Signal
        fields = ('asset', 'timeframe', 'direction', 'strategy', 'confidence', 'scheduled_entry_at', 'expires_at', 'entry_price', 'execution_entry_price', 'exit_price', 'outcome')
        help_texts = {
            'scheduled_entry_at': 'Fecha y hora exactas de entrada (zona horaria del sitio).',
            'expires_at': 'Fecha y hora del vencimiento; debe ser posterior a la entrada.',
            'entry_price': 'Opcional. Solo ingresa precios realmente observados; 0 indica no registrado.',
            'confidence': 'Valor manual, no una probabilidad calculada.',
        }

    def clean(self):
        data = super().clean()
        entry, expiry = data.get('scheduled_entry_at'), data.get('expires_at')
        if not entry:
            self.add_error('scheduled_entry_at', 'Indica cuándo comienza la operación.')
        if entry and expiry and expiry <= entry:
            self.add_error('expires_at', 'El vencimiento debe ser después de la entrada.')
        if entry and expiry and data.get('timeframe') and int((expiry-entry).total_seconds()) != data['timeframe']*60:
            self.add_error('expires_at', 'El vencimiento debe coincidir exactamente con la duración seleccionada.')
        if data.get('direction') == Signal.Direction.WAIT:
            self.add_error('direction', 'Publica solamente CALL o PUT.')
        if data.get('outcome') != Signal.Outcome.OPEN and (data.get('execution_entry_price') is None or data.get('exit_price') is None):
            self.add_error('outcome', 'Para cerrar una señal registra precios reales de entrada y salida.')
        return data


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    form = ManualSignalForm
    list_display = ('asset', 'timeframe', 'direction', 'scheduled_entry_at', 'expires_at', 'outcome', 'is_manual')
    list_filter = ('is_manual', 'asset', 'timeframe', 'direction', 'outcome')
    search_fields = ('asset', 'strategy')
    readonly_fields = ('generated_at', 'evaluated_at', 'source', 'is_manual')
    date_hierarchy = 'scheduled_entry_at'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_manual=True)

    def save_model(self, request, obj, form, change):
        obj.is_manual = True
        obj.source = 'Publicación manual del administrador'
        if obj.outcome != Signal.Outcome.OPEN and not obj.evaluated_at:
            obj.evaluated_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('registration', 'sender', 'short_text', 'created_at')
    list_filter = ('sender', 'created_at')
    search_fields = ('registration__quotex_id', 'registration__telegram_username', 'text')
    readonly_fields = ('created_at',)

    @admin.display(description='Mensaje')
    def short_text(self, obj):
        return obj.text[:80]
