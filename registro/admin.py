from django.contrib import admin
from django.utils import timezone
from .models import Registration


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
