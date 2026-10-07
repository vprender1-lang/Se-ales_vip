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


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('asset', 'timeframe', 'direction', 'strategy', 'confidence', 'entry_price', 'outcome', 'generated_at')
    list_filter = ('asset', 'timeframe', 'direction', 'outcome', 'strategy')
    search_fields = ('asset', 'strategy')
    readonly_fields = ('generated_at', 'evaluated_at')
    date_hierarchy = 'generated_at'


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('registration', 'sender', 'short_text', 'created_at')
    list_filter = ('sender', 'created_at')
    search_fields = ('registration__quotex_id', 'registration__telegram_username', 'text')
    readonly_fields = ('created_at',)

    @admin.display(description='Mensaje')
    def short_text(self, obj):
        return obj.text[:80]
