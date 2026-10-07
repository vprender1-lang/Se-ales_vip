import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

from django.conf import settings


def _api_call(method, payload):
    """Llama a la Bot API de Telegram sin exponer el token al navegador."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False, 'TELEGRAM_BOT_TOKEN no configurado'

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/{method}',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = json.loads(response.read().decode('utf-8'))
            return bool(body.get('ok')), body
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return False, str(exc)


def _status_text(registration):
    labels = {
        'pending': '⏳ PENDIENTE',
        'approved': '✅ APROBADA',
        'rejected': '❌ RECHAZADA',
    }
    return labels.get(registration.status, registration.status.upper())


def registration_message(registration):
    """Texto compacto que recibe el administrador en Telegram."""
    return '\n'.join([
        '🔥 NUEVA SOLICITUD — SEÑALES VIP DEL LATINO',
        '',
        f'🆔 ID Quotex: {registration.quotex_id}',
        f'👤 Telegram: @{registration.telegram_username}',
        f'🔖 Solicitud: {registration.public_id}',
        f'📅 Fecha: {registration.created_at:%d/%m/%Y %H:%M}',
        f'📌 Estado: {_status_text(registration)}',
        '',
        '1️⃣ Abre QuotexPartnerBot y consulta el ID.',
        '2️⃣ Confirma que pertenece a tus referidos.',
        '3️⃣ Luego pulsa Aprobar o Rechazar aquí.',
        '',
        '⚠️ No apruebes un ID que no hayas verificado.',
    ])


def admin_keyboard(registration):
    """Botones dentro de Telegram. Aprobar/Rechazar usan callback seguro."""
    return {
        'inline_keyboard': [
            [
                {
                    'text': '🔎 Abrir QuotexPartnerBot',
                    'url': settings.QUOTEX_PARTNER_BOT_URL,
                }
            ],
            [
                {
                    'text': '✅ Aprobar',
                    'callback_data': f'vip:approve:{registration.public_id}',
                },
                {
                    'text': '❌ Rechazar',
                    'callback_data': f'vip:reject:{registration.public_id}',
                },
            ],
        ]
    }


def notify_admin(registration):
    chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        return False, 'Telegram no configurado'

    payload = {
        'chat_id': chat_id,
        'text': registration_message(registration),
        'reply_markup': admin_keyboard(registration),
        'disable_web_page_preview': True,
    }
    return _api_call('sendMessage', payload)


def notify_support_message(registration, support_message):
    chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        return False, 'Telegram no configurado'
    text = '\n'.join([
        '💬 SOPORTE — SEÑALES VIP DEL LATINO',
        f'CHAT-ID: {registration.public_id}',
        f'🆔 Quotex: {registration.quotex_id}',
        f'👤 Usuario: @{registration.telegram_username}',
        '',
        support_message.text,
        '',
        '↩️ Responde directamente a ESTE mensaje para contestarle en la web.',
    ])
    return _api_call('sendMessage', {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': True,
    })


def send_support_admin_confirmation(chat_id, text):
    return _api_call('sendMessage', {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': True,
    })


def answer_callback_query(callback_query_id, text):
    return _api_call('answerCallbackQuery', {
        'callback_query_id': callback_query_id,
        'text': text,
        'show_alert': False,
    })


def refresh_admin_message(chat_id, message_id, registration):
    """Actualiza el mensaje original y elimina botones una vez revisado."""
    return _api_call('editMessageText', {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': registration_message(registration),
        'reply_markup': {'inline_keyboard': [[
            {
                'text': '🔎 Abrir QuotexPartnerBot',
                'url': settings.QUOTEX_PARTNER_BOT_URL,
            }
        ]]},
        'disable_web_page_preview': True,
    })


def set_webhook():
    if not settings.PUBLIC_URL:
        return False, 'PUBLIC_URL no configurada'
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        return False, 'TELEGRAM_WEBHOOK_SECRET no configurado'

    webhook_url = f"{settings.PUBLIC_URL.rstrip('/')}/telegram/webhook/"
    return _api_call('setWebhook', {
        'url': webhook_url,
        'secret_token': settings.TELEGRAM_WEBHOOK_SECRET,
        'allowed_updates': ['callback_query', 'message'],
        'drop_pending_updates': True,
    })


def delete_webhook():
    return _api_call('deleteWebhook', {'drop_pending_updates': False})
