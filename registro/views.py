import hashlib
import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, Http404, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import RegistrationForm
from .models import Registration
from .telegram import (
    answer_callback_query,
    notify_admin,
    refresh_admin_message,
)


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0] if forwarded else request.META.get('REMOTE_ADDR', '')).strip()


def common_context():
    return {
        'affiliate_url': settings.AFFILIATE_URL,
        'quotex_login_url': settings.QUOTEX_LOGIN_URL,
        'telegram_admin_username': settings.TELEGRAM_ADMIN_USERNAME,
        'quotex_partner_bot_url': settings.QUOTEX_PARTNER_BOT_URL,
    }


@require_http_methods(['GET', 'POST'])
def home(request):
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quotex_id = form.cleaned_data['quotex_id']
        existing = Registration.objects.filter(
            quotex_id=quotex_id,
            status__in=[Registration.Status.PENDING, Registration.Status.APPROVED],
        ).first()
        if existing:
            messages.info(request, 'Este ID ya tiene una solicitud activa. Te mostramos su estado.')
            return redirect('registro:status', public_id=existing.public_id)

        registration = form.save(commit=False)
        ip = client_ip(request)
        registration.ip_hash = hashlib.sha256(f'{ip}|{settings.IP_HASH_SALT}'.encode()).hexdigest()
        registration.save()

        ok, _ = notify_admin(registration)
        if ok:
            messages.success(request, 'Solicitud enviada. Tu ID ya fue notificado al administrador por Telegram.')
        else:
            messages.warning(
                request,
                'La solicitud quedó guardada, pero el bot de Telegram todavía necesita su TOKEN para poder avisar al administrador.'
            )
        return redirect('registro:status', public_id=registration.public_id)

    context = common_context()
    context['form'] = form
    return render(request, 'registro/home.html', context)


def status(request, public_id):
    registration = get_object_or_404(Registration, public_id=public_id)
    context = common_context()
    context['registration'] = registration
    context['telegram_message'] = (
        'Hola, vengo de Señales VIP del Latino. '
        f'Mi ID de Quotex es {registration.quotex_id}. '
        f'Mi solicitud es {registration.public_id}. Por favor valida mi registro.'
    )
    context['telegram_vip_url'] = settings.TELEGRAM_VIP_URL
    return render(request, 'registro/status.html', context)


def status_json(request, public_id):
    registration = get_object_or_404(Registration, public_id=public_id)
    return JsonResponse({
        'status': registration.status,
        'status_label': registration.get_status_display(),
        'updated_at': registration.updated_at.isoformat(),
        'vip_url': settings.TELEGRAM_VIP_URL if registration.status == Registration.Status.APPROVED else '',
    })


@require_http_methods(['GET', 'POST'])
def admin_review(request, public_id, action):
    """Ruta web de respaldo para aprobar/rechazar desde navegador."""
    configured = settings.ADMIN_REVIEW_SECRET
    supplied = request.GET.get('key', '') or request.POST.get('key', '')
    if not configured or not hmac.compare_digest(configured, supplied):
        return HttpResponseForbidden('Enlace de revisión no autorizado.')
    if action not in {'aprobar', 'rechazar'}:
        raise Http404

    registration = get_object_or_404(Registration, public_id=public_id)
    if request.method == 'POST':
        registration.status = Registration.Status.APPROVED if action == 'aprobar' else Registration.Status.REJECTED
        registration.reviewed_at = timezone.now()
        registration.save(update_fields=['status', 'reviewed_at', 'updated_at'])
        return render(request, 'registro/review_done.html', {
            'registration': registration,
            'action': action,
        })

    return render(request, 'registro/review_confirm.html', {
        'registration': registration,
        'action': action,
        'key': supplied,
    })


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Recibe los botones Aprobar/Rechazar pulsados en TU bot de Telegram."""
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    supplied = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not secret or not hmac.compare_digest(secret, supplied):
        return HttpResponseForbidden('Webhook no autorizado.')

    try:
        update = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest('JSON inválido.')

    callback = update.get('callback_query')
    if not callback:
        return JsonResponse({'ok': True})

    message = callback.get('message') or {}
    chat = message.get('chat') or {}
    chat_id = str(chat.get('id', ''))
    expected_chat_id = str(settings.TELEGRAM_ADMIN_CHAT_ID)

    # Solo TU chat puede cambiar el estado de una solicitud.
    if not expected_chat_id or chat_id != expected_chat_id:
        answer_callback_query(callback.get('id', ''), 'No autorizado.')
        return JsonResponse({'ok': True})

    data = callback.get('data', '')
    parts = data.split(':', 2)
    if len(parts) != 3 or parts[0] != 'vip' or parts[1] not in {'approve', 'reject'}:
        answer_callback_query(callback.get('id', ''), 'Acción inválida.')
        return JsonResponse({'ok': True})

    action, public_id = parts[1], parts[2]
    try:
        registration = Registration.objects.get(public_id=public_id)
    except (Registration.DoesNotExist, ValueError):
        answer_callback_query(callback.get('id', ''), 'Solicitud no encontrada.')
        return JsonResponse({'ok': True})

    if action == 'approve':
        registration.status = Registration.Status.APPROVED
        result_text = f'✅ ID {registration.quotex_id} aprobado.'
    else:
        registration.status = Registration.Status.REJECTED
        result_text = f'❌ ID {registration.quotex_id} rechazado.'

    registration.reviewed_at = timezone.now()
    registration.save(update_fields=['status', 'reviewed_at', 'updated_at'])

    answer_callback_query(callback.get('id', ''), result_text)
    message_id = message.get('message_id')
    if message_id:
        refresh_admin_message(chat_id, message_id, registration)

    return JsonResponse({'ok': True})
