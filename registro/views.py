import hashlib
import hmac
import json
import re
import random

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse, Http404, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import RegistrationForm, VipAccessForm
from .models import Registration, Signal, SupportMessage
from .signal_engine import (
    ASSETS,
    TIMEFRAMES,
    MarketDataError,
    evaluate_due_signals,
    get_or_create_signal,
    process_signal_states,
    grouped_assets,
    public_signal_dict,
    strategy_leaderboard,
)
from .telegram import (
    answer_callback_query,
    notify_admin,
    notify_support_message,
    refresh_admin_message,
    send_support_admin_confirmation,
)


VIP_SESSION_KEY = 'vip_registration_public_id'


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


def approved_registration(public_id):
    return get_object_or_404(
        Registration,
        public_id=public_id,
        status=Registration.Status.APPROVED,
    )


def current_vip_registration(request):
    public_id = request.session.get(VIP_SESSION_KEY)
    if not public_id:
        return None
    try:
        return Registration.objects.get(
            public_id=public_id,
            status=Registration.Status.APPROVED,
        )
    except (Registration.DoesNotExist, ValueError):
        request.session.pop(VIP_SESSION_KEY, None)
        return None


def _record_login_attempt(request):
    now = int(timezone.now().timestamp())
    attempts = [ts for ts in request.session.get('vip_login_attempts', []) if now - int(ts) < 600]
    attempts.append(now)
    request.session['vip_login_attempts'] = attempts[-12:]
    return len(attempts)


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


@require_http_methods(['GET', 'POST'])
def vip_login(request):
    current = current_vip_registration(request)
    if current and request.method == 'GET' and not request.GET.get('id'):
        return redirect('registro:signals_dashboard')

    initial_id = (request.GET.get('id') or '').strip()
    form = VipAccessForm(request.POST or None, initial={'quotex_id': initial_id})

    if request.method == 'POST':
        attempts = _record_login_attempt(request)
        if attempts > 10:
            form.add_error(None, 'Demasiados intentos. Espera unos minutos y vuelve a intentarlo.')
        elif form.is_valid():
            quotex_id = form.cleaned_data['quotex_id']
            registration = Registration.objects.filter(
                quotex_id=quotex_id,
                status=Registration.Status.APPROVED,
            ).order_by('-reviewed_at', '-created_at').first()

            if registration:
                request.session.cycle_key()
                request.session[VIP_SESSION_KEY] = str(registration.public_id)
                request.session['vip_login_attempts'] = []
                request.session.set_expiry(60 * 60 * 24 * 14)
                return redirect('registro:signals_dashboard')

            pending = Registration.objects.filter(
                quotex_id=quotex_id,
                status=Registration.Status.PENDING,
            ).exists()
            if pending:
                form.add_error('quotex_id', 'Tu ID todavía está pendiente de validación.')
            else:
                form.add_error('quotex_id', 'Este ID no tiene acceso VIP aprobado.')

    context = common_context()
    context['form'] = form
    return render(request, 'registro/vip_login.html', context)


@require_POST
def vip_logout(request):
    request.session.pop(VIP_SESSION_KEY, None)
    request.session.flush()
    return redirect('registro:vip_login')


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
    access_url = reverse('registro:vip_login')
    return JsonResponse({
        'status': registration.status,
        'status_label': registration.get_status_display(),
        'updated_at': registration.updated_at.isoformat(),
        'vip_url': settings.TELEGRAM_VIP_URL if registration.status == Registration.Status.APPROVED else '',
        'signals_url': (
            f'{access_url}?id={registration.quotex_id}'
            if registration.status == Registration.Status.APPROVED else ''
        ),
    })


def legacy_signals_dashboard(request, public_id):
    registration = approved_registration(public_id)
    request.session.cycle_key()
    request.session[VIP_SESSION_KEY] = str(registration.public_id)
    request.session.set_expiry(60 * 60 * 24 * 14)
    return redirect('registro:signals_dashboard')


def demo_trader_profiles():
    """100 perfiles DEMO para presentación; nunca se presentan como rendimiento real."""
    first_names = [
        'Mateo','Santiago','Sebastián','Nicolás','Alejandro','Diego','Gabriel','Samuel','Daniel','David',
        'Adrián','Lucas','Martín','Leo','Julián','Emilio','Marco','Iván','Bruno','Thiago',
        'Valentina','Camila','Sofía','Isabella','Lucía','Emma','Victoria','Martina','Daniela','Paula',
        'Renata','Elena','Sara','Julia','Natalia','Andrea','Mía','Carla','Laura','Mariana'
    ]
    last_names = [
        'Mendoza','Castillo','Morales','Navarro','Rojas','Vargas','Herrera','Romero','Guerrero','Santos',
        'Pérez','López','Ramírez','Torres','Flores','Rivera','Cruz','Ortiz','Reyes','Gómez'
    ]
    strategies = ['Tendencia EMA + MACD','Momentum RSI','Confluencia técnica','Ruptura + Momentum','Reversión técnica']
    assets = list(ASSETS.keys())
    today = timezone.localdate()
    presentation_day = ((today.toordinal() - 1) % 4) + 1
    rng = random.Random(f'demo-traders-{today.isoformat()}-day-{presentation_day}')

    names = []
    for first in first_names:
        for last in last_names:
            names.append(f'{first} {last}')
    rng.shuffle(names)

    profiles = []
    for index in range(100):
        capital = rng.randint(80, 2500)
        gain = round(rng.uniform(3.5, 42.0), 2)
        win_rate = round(rng.uniform(58.0, 83.5), 1)
        trades = rng.randint(14, 96)
        profiles.append({
            'rank': index + 1,
            'name': names[index],
            'strategy': rng.choice(strategies),
            'asset': rng.choice(assets),
            'trades': trades,
            'win_rate': win_rate,
            'gain_pct': gain,
            'gain_usd': round(capital * gain / 100, 2),
            'demo': True,
        })

    profiles.sort(key=lambda item: (item['gain_pct'], item['win_rate']), reverse=True)
    for index, item in enumerate(profiles, start=1):
        item['rank'] = index

    return {
        'day': presentation_day,
        'profiles': profiles,
        'top3': profiles[:3],
    }


def daily_trader_profiles():
    demo = demo_trader_profiles()
    return demo['top3']
def signals_dashboard(request):
    registration = current_vip_registration(request)
    if not registration:
        messages.info(request, 'Ingresa tu ID de Quotex aprobado para acceder al motor.')
        return redirect('registro:vip_login')

    try:
        process_signal_states(limit=24)
    except Exception:
        pass

    closed = Signal.objects.exclude(outcome=Signal.Outcome.OPEN)
    summary = closed.aggregate(
        total=Count('id'),
        wins=Count('id', filter=Q(outcome=Signal.Outcome.WIN)),
        losses=Count('id', filter=Q(outcome=Signal.Outcome.LOSS)),
        draws=Count('id', filter=Q(outcome=Signal.Outcome.DRAW)),
    )
    decided = (summary.get('wins') or 0) + (summary.get('losses') or 0)
    summary['accuracy'] = round(((summary.get('wins') or 0) / decided * 100), 1) if decided else None

    context = common_context()
    context.update({
        'registration': registration,
        'assets': list(ASSETS.keys()),
        'asset_groups': grouped_assets(),
        'timeframes': TIMEFRAMES,
        'leaderboard': strategy_leaderboard(),
        'daily_traders': daily_trader_profiles(),
        'demo_traders': demo_trader_profiles(),
        'summary': summary,
        'support_messages': registration.support_messages.all()[:80],
        'reference_payout': settings.SIGNAL_REFERENCE_PAYOUT,
    })
    return render(request, 'registro/signals.html', context)


@require_http_methods(['GET'])
def signal_api(request):
    registration = current_vip_registration(request)
    if not registration:
        return JsonResponse({'ok': False, 'error': 'Sesión VIP expirada. Vuelve a ingresar tu ID.'}, status=401)

    asset = request.GET.get('asset', 'BTC/USD')
    try:
        timeframe = int(request.GET.get('timeframe', '1'))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Temporalidad inválida.'}, status=400)

    if asset not in ASSETS or timeframe not in TIMEFRAMES:
        return JsonResponse({'ok': False, 'error': 'Activo o temporalidad no soportados.'}, status=400)

    try:
        process_signal_states(limit=24)
        signal, analysis = get_or_create_signal(asset, timeframe)
    except MarketDataError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=503)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'No fue posible calcular la señal en este momento.'}, status=503)

    return JsonResponse({
        'ok': True,
        'signal': public_signal_dict(signal, analysis),
        'reference_payout': settings.SIGNAL_REFERENCE_PAYOUT,
        'notice': (
            'La señal se emite ahora y su entrada queda programada 60 segundos después. '
            'El precio de ejecución se captura al comenzar la señal y el resultado se mide al vencer. '
            'Las cotizaciones vienen de fuentes públicas externas y pueden diferir de Quotex. '
            f'El {settings.SIGNAL_REFERENCE_PAYOUT}% es payout de referencia, no una rentabilidad garantizada.'
        ),
    })


@require_http_methods(['GET'])
def signal_history_api(request):
    registration = current_vip_registration(request)
    if not registration:
        return JsonResponse({'ok': False, 'error': 'Sesión VIP expirada.'}, status=401)

    try:
        process_signal_states(limit=100)
    except Exception:
        pass

    asset = (request.GET.get('asset') or '').strip()
    try:
        timeframe = int(request.GET.get('timeframe', '0') or 0)
    except ValueError:
        timeframe = 0

    qs = Signal.objects.all()
    if asset in ASSETS:
        qs = qs.filter(asset=asset)
    if timeframe in TIMEFRAMES:
        qs = qs.filter(timeframe=timeframe)

    recent = list(qs.order_by('-generated_at')[:10])
    now = timezone.now()
    items = []
    for signal in recent:
        remaining = max(0, int((signal.expires_at - now).total_seconds()))
        items.append({
            'id': signal.id,
            'asset': signal.asset,
            'timeframe': signal.timeframe,
            'direction': signal.direction,
            'strategy': signal.strategy,
            'confidence': signal.confidence,
            'entry_price': float(signal.entry_price),
            'execution_entry_price': float(signal.execution_entry_price) if signal.execution_entry_price is not None else None,
            'exit_price': float(signal.exit_price) if signal.exit_price is not None else None,
            'outcome': signal.outcome,
            'outcome_label': signal.get_outcome_display(),
            'generated_at': signal.generated_at.isoformat(),
            'scheduled_entry_at': signal.scheduled_entry_at.isoformat() if signal.scheduled_entry_at else None,
            'activated_at': signal.activated_at.isoformat() if signal.activated_at else None,
            'expires_at': signal.expires_at.isoformat(),
            'evaluated_at': signal.evaluated_at.isoformat() if signal.evaluated_at else None,
            'remaining_seconds': remaining,
            'phase': (
                'closed' if signal.outcome != Signal.Outcome.OPEN
                else 'scheduled' if signal.scheduled_entry_at and now < signal.scheduled_entry_at
                else 'active' if signal.execution_entry_price is not None
                else 'activating'
            ),
        })

    closed = [item for item in items if item['outcome'] in {'win', 'loss', 'draw'}]
    decided = [item for item in closed if item['outcome'] in {'win', 'loss'}]
    wins = sum(1 for item in decided if item['outcome'] == 'win')
    accuracy = round((wins / len(decided) * 100), 1) if decided else None

    return JsonResponse({
        'ok': True,
        'signals': items,
        'recent_accuracy': accuracy,
        'closed_count': len(closed),
    })


@require_http_methods(['GET', 'POST'])
def support_api(request):
    registration = current_vip_registration(request)
    if not registration:
        return JsonResponse({'ok': False, 'error': 'Sesión VIP expirada.'}, status=401)

    if request.method == 'GET':
        data = [{
            'sender': item.sender,
            'text': item.text,
            'created_at': item.created_at.isoformat(),
        } for item in registration.support_messages.all()[:120]]
        return JsonResponse({'ok': True, 'messages': data})

    text = (request.POST.get('message') or '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Escribe un mensaje.'}, status=400)
    if len(text) > 1200:
        return JsonResponse({'ok': False, 'error': 'El mensaje es demasiado largo.'}, status=400)

    last = registration.support_messages.filter(sender=SupportMessage.Sender.USER).order_by('-created_at').first()
    if last and (timezone.now() - last.created_at).total_seconds() < 3:
        return JsonResponse({'ok': False, 'error': 'Espera unos segundos antes de enviar otro mensaje.'}, status=429)

    item = SupportMessage.objects.create(
        registration=registration,
        sender=SupportMessage.Sender.USER,
        text=text,
    )
    notify_support_message(registration, item)
    return JsonResponse({
        'ok': True,
        'message': {
            'sender': item.sender,
            'text': item.text,
            'created_at': item.created_at.isoformat(),
        },
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


def _support_reply_from_telegram(message, chat_id):
    """Si el admin responde a una notificación de soporte, refleja la respuesta en la web."""
    reply_to = message.get('reply_to_message') or {}
    original_text = reply_to.get('text') or ''
    match = re.search(r'CHAT-ID:\s*([0-9a-fA-F-]{36})', original_text)
    text = (message.get('text') or '').strip()
    if not match or not text or text.startswith('/start'):
        return False

    try:
        registration = Registration.objects.get(
            public_id=match.group(1),
            status=Registration.Status.APPROVED,
        )
    except (Registration.DoesNotExist, ValueError):
        return False

    SupportMessage.objects.create(
        registration=registration,
        sender=SupportMessage.Sender.ADMIN,
        text=text[:1200],
    )
    send_support_admin_confirmation(
        chat_id,
        f'✅ Respuesta enviada a @{registration.telegram_username} en el chat web.',
    )
    return True


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Recibe validaciones y respuestas de soporte desde TU bot de Telegram."""
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    supplied = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not secret or not hmac.compare_digest(secret, supplied):
        return HttpResponseForbidden('Webhook no autorizado.')

    try:
        update = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest('JSON inválido.')

    expected_chat_id = str(settings.TELEGRAM_ADMIN_CHAT_ID)

    incoming_message = update.get('message')
    if incoming_message:
        chat = incoming_message.get('chat') or {}
        chat_id = str(chat.get('id', ''))
        if expected_chat_id and chat_id == expected_chat_id:
            _support_reply_from_telegram(incoming_message, chat_id)
        return JsonResponse({'ok': True})

    callback = update.get('callback_query')
    if not callback:
        return JsonResponse({'ok': True})

    message = callback.get('message') or {}
    chat = message.get('chat') or {}
    chat_id = str(chat.get('id', ''))

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
