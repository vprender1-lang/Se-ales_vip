import json
import math
import time
import urllib.parse
import urllib.request
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from .models import Signal


KRAKEN_URL = 'https://api.kraken.com/0/public/OHLC'
ASSETS = {
    'BTC/USD': 'XBTUSD',
    'ETH/USD': 'ETHUSD',
    'SOL/USD': 'SOLUSD',
    'XRP/USD': 'XRPUSD',
    'LTC/USD': 'LTCUSD',
}
TIMEFRAMES = (1, 5, 15)

_cache = {}


class MarketDataError(RuntimeError):
    pass


def _cached(key, ttl):
    item = _cache.get(key)
    now = time.time()
    if item and now - item[0] < ttl:
        return item[1]
    return None


def _store_cache(key, value):
    _cache[key] = (time.time(), value)
    return value


def fetch_ohlc(asset='BTC/USD', timeframe=1, limit=180):
    if asset not in ASSETS:
        raise MarketDataError('Activo no soportado.')
    if int(timeframe) not in TIMEFRAMES:
        raise MarketDataError('Temporalidad no soportada.')

    timeframe = int(timeframe)
    key = ('ohlc', asset, timeframe)
    cached = _cached(key, max(8, min(25, timeframe * 4)))
    if cached:
        return cached

    query = urllib.parse.urlencode({
        'pair': ASSETS[asset],
        'interval': timeframe,
    })
    req = urllib.request.Request(
        f'{KRAKEN_URL}?{query}',
        headers={'User-Agent': 'SenalesVIPLatino/1.0'},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        raise MarketDataError(f'No se pudo consultar el mercado: {exc}') from exc

    if payload.get('error'):
        raise MarketDataError('Kraken respondió con un error: ' + ', '.join(payload['error']))

    result = payload.get('result') or {}
    pair_key = next((k for k in result.keys() if k != 'last'), None)
    if not pair_key:
        raise MarketDataError('La fuente de mercado no devolvió velas.')

    rows = result[pair_key][-limit:]
    candles = []
    for row in rows:
        candles.append({
            'time': int(float(row[0])),
            'open': float(row[1]),
            'high': float(row[2]),
            'low': float(row[3]),
            'close': float(row[4]),
            'volume': float(row[6]),
        })
    if len(candles) < 40:
        raise MarketDataError('Aún no hay suficientes velas para calcular la señal.')
    return _store_cache(key, candles)


def _ema_series(values, period):
    if not values:
        return []
    k = 2 / (period + 1)
    out = [float(values[0])]
    for value in values[1:]:
        out.append(float(value) * k + out[-1] * (1 - k))
    return out


def _rsi(values, period=14):
    if len(values) <= period:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        current = candles[i]
        prev_close = candles[i - 1]['close']
        trs.append(max(
            current['high'] - current['low'],
            abs(current['high'] - prev_close),
            abs(current['low'] - prev_close),
        ))
    if not trs:
        return 0.0
    return sum(trs[-period:]) / min(period, len(trs))


def analyze_market(asset, timeframe):
    candles = fetch_ohlc(asset, timeframe)
    closes = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]

    ema9_series = _ema_series(closes, 9)
    ema21_series = _ema_series(closes, 21)
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd_series = [a - b for a, b in zip(ema12, ema26)]
    macd_signal = _ema_series(macd_series, 9)

    price = closes[-1]
    ema9 = ema9_series[-1]
    ema21 = ema21_series[-1]
    rsi = _rsi(closes, 14)
    macd_hist = macd_series[-1] - macd_signal[-1]
    atr = _atr(candles, 14)
    momentum = (price / closes[-4] - 1) * 100 if closes[-4] else 0
    avg_volume = sum(volumes[-20:]) / min(20, len(volumes))
    volume_ratio = volumes[-1] / avg_volume if avg_volume else 1.0

    score = 0.0
    reasons = []

    if ema9 > ema21:
        score += 2.0
        reasons.append('EMA 9 por encima de EMA 21')
    elif ema9 < ema21:
        score -= 2.0
        reasons.append('EMA 9 por debajo de EMA 21')

    if macd_hist > 0:
        score += 1.35
        reasons.append('MACD con impulso alcista')
    elif macd_hist < 0:
        score -= 1.35
        reasons.append('MACD con impulso bajista')

    if 52 <= rsi <= 69:
        score += 1.0
        reasons.append(f'RSI favorable al alza ({rsi:.1f})')
    elif 31 <= rsi <= 48:
        score -= 1.0
        reasons.append(f'RSI favorable a la baja ({rsi:.1f})')
    elif rsi >= 74:
        score -= .55
        reasons.append(f'RSI en sobrecompra ({rsi:.1f})')
    elif rsi <= 26:
        score += .55
        reasons.append(f'RSI en sobreventa ({rsi:.1f})')

    if momentum > .04:
        score += .75
        reasons.append('Momentum reciente positivo')
    elif momentum < -.04:
        score -= .75
        reasons.append('Momentum reciente negativo')

    if volume_ratio >= 1.18:
        score += .35 if score > 0 else -.35 if score < 0 else 0
        reasons.append('Volumen por encima de su media')

    atr_pct = (atr / price * 100) if price else 0
    if atr_pct > 1.4:
        score *= .88
        reasons.append('Volatilidad elevada: señal penalizada')

    if score >= 3.15:
        direction = Signal.Direction.CALL
    elif score <= -3.15:
        direction = Signal.Direction.PUT
    else:
        direction = Signal.Direction.WAIT

    confidence = int(max(45, min(89, 49 + abs(score) * 8)))
    if direction == Signal.Direction.WAIT:
        confidence = min(confidence, 62)

    if abs(ema9 - ema21) > max(atr * .25, price * .0002) and abs(macd_hist) > 0:
        strategy = 'Tendencia EMA + MACD'
    elif (rsi >= 52 or rsi <= 48) and abs(momentum) >= .04:
        strategy = 'Momentum RSI'
    else:
        strategy = 'Confluencia técnica'

    risk_pct = .5 if atr_pct >= 1 else .75
    if confidence >= 78 and atr_pct < .8:
        risk_pct = 1.0

    return {
        'asset': asset,
        'timeframe': int(timeframe),
        'direction': direction,
        'score': round(score, 2),
        'confidence': confidence,
        'price': price,
        'strategy': strategy,
        'rsi': round(rsi, 1),
        'ema9': ema9,
        'ema21': ema21,
        'macd_hist': macd_hist,
        'atr_pct': round(atr_pct, 3),
        'volume_ratio': round(volume_ratio, 2),
        'risk_pct': risk_pct,
        'reasons': reasons[:5],
        'source': 'Kraken Public Market Data',
    }


def get_or_create_signal(asset, timeframe):
    timeframe = int(timeframe)
    now = timezone.now()
    active = Signal.objects.filter(
        asset=asset,
        timeframe=timeframe,
        outcome=Signal.Outcome.OPEN,
        expires_at__gt=now,
    ).exclude(direction=Signal.Direction.WAIT).first()
    if active:
        return active, None

    analysis = analyze_market(asset, timeframe)
    if analysis['direction'] == Signal.Direction.WAIT:
        return None, analysis

    signal = Signal.objects.create(
        asset=asset,
        timeframe=timeframe,
        strategy=analysis['strategy'],
        direction=analysis['direction'],
        score=analysis['score'],
        confidence=analysis['confidence'],
        entry_price=Decimal(str(analysis['price'])),
        source=analysis['source'],
        expires_at=now + timedelta(minutes=timeframe),
    )
    return signal, analysis


def evaluate_due_signals(limit=50):
    due = list(
        Signal.objects.filter(
            outcome=Signal.Outcome.OPEN,
            expires_at__lte=timezone.now(),
        ).exclude(direction=Signal.Direction.WAIT)[:limit]
    )
    updated = 0
    for signal in due:
        try:
            candles = fetch_ohlc(signal.asset, signal.timeframe)
            exit_price = Decimal(str(candles[-1]['close']))
        except MarketDataError:
            continue

        entry = signal.entry_price
        if exit_price == entry:
            outcome = Signal.Outcome.DRAW
        elif signal.direction == Signal.Direction.CALL:
            outcome = Signal.Outcome.WIN if exit_price > entry else Signal.Outcome.LOSS
        else:
            outcome = Signal.Outcome.WIN if exit_price < entry else Signal.Outcome.LOSS

        signal.exit_price = exit_price
        signal.outcome = outcome
        signal.evaluated_at = timezone.now()
        signal.save(update_fields=['exit_price', 'outcome', 'evaluated_at'])
        updated += 1
    return updated


def strategy_leaderboard():
    rows = (
        Signal.objects.exclude(outcome=Signal.Outcome.OPEN)
        .values('strategy')
        .annotate(
            total=Count('id'),
            wins=Count('id', filter=Q(outcome=Signal.Outcome.WIN)),
            losses=Count('id', filter=Q(outcome=Signal.Outcome.LOSS)),
            draws=Count('id', filter=Q(outcome=Signal.Outcome.DRAW)),
        )
        .order_by('-wins', '-total')
    )
    output = []
    for row in rows:
        decided = row['wins'] + row['losses']
        accuracy = (row['wins'] / decided * 100) if decided else 0
        output.append({
            **row,
            'accuracy': round(accuracy, 1),
        })
    return output[:8]


def public_signal_dict(signal, analysis=None):
    if signal:
        return {
            'id': signal.id,
            'asset': signal.asset,
            'timeframe': signal.timeframe,
            'direction': signal.direction,
            'strategy': signal.strategy,
            'confidence': signal.confidence,
            'entry_price': float(signal.entry_price),
            'generated_at': signal.generated_at.isoformat(),
            'expires_at': signal.expires_at.isoformat(),
            'source': signal.source,
            'status': signal.outcome,
            'analysis': analysis or {},
        }
    return {
        'id': None,
        'asset': analysis['asset'],
        'timeframe': analysis['timeframe'],
        'direction': Signal.Direction.WAIT,
        'strategy': analysis['strategy'],
        'confidence': analysis['confidence'],
        'entry_price': analysis['price'],
        'generated_at': timezone.now().isoformat(),
        'expires_at': None,
        'source': analysis['source'],
        'status': 'wait',
        'analysis': analysis,
    }
