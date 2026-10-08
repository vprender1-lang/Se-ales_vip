import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from .models import Signal


KRAKEN_URL = 'https://api.kraken.com/0/public/OHLC'
KRAKEN_TICKER_URL = 'https://api.kraken.com/0/public/Ticker'
YAHOO_URL = 'https://query2.finance.yahoo.com/v8/finance/chart/{symbol}'
TIMEFRAMES = (1, 5, 15)
SIGNAL_ENTRY_DELAY_SECONDS = 60

ASSETS = {
    'EUR/USD': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'EURUSD=X'},
    'GBP/USD': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'GBPUSD=X'},
    'USD/JPY': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'JPY=X'},
    'AUD/USD': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'AUDUSD=X'},
    'USD/CAD': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'CAD=X'},
    'USD/CHF': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'CHF=X'},
    'NZD/USD': {'category': 'Forex', 'group': 'Principales', 'provider': 'yahoo', 'symbol': 'NZDUSD=X'},
    'EUR/GBP': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'EURGBP=X'},
    'EUR/JPY': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'EURJPY=X'},
    'GBP/JPY': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'GBPJPY=X'},
    'AUD/JPY': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'AUDJPY=X'},
    'EUR/AUD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'EURAUD=X'},
    'GBP/AUD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'GBPAUD=X'},
    'EUR/CAD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'EURCAD=X'},
    'GBP/CAD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'GBPCAD=X'},
    'AUD/CAD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'AUDCAD=X'},
    'CHF/JPY': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'CHFJPY=X'},
    'EUR/CHF': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'EURCHF=X'},
    'GBP/CHF': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'GBPCHF=X'},
    'NZD/JPY': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'NZDJPY=X'},
    'AUD/NZD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'AUDNZD=X'},
    'EUR/NZD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'EURNZD=X'},
    'GBP/NZD': {'category': 'Forex', 'group': 'Cruces', 'provider': 'yahoo', 'symbol': 'GBPNZD=X'},
    'USD/SGD': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'SGD=X'},
    'USD/HKD': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'HKD=X'},
    'USD/TRY': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'TRY=X'},
    'USD/MXN': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'MXN=X'},
    'USD/ZAR': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'ZAR=X'},
    'USD/PLN': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'PLN=X'},
    'USD/NOK': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'NOK=X'},
    'USD/SEK': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'SEK=X'},
    'USD/DKK': {'category': 'Forex', 'group': 'Exóticos', 'provider': 'yahoo', 'symbol': 'DKK=X'},
    'BTC/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'XBTUSD', 'fallback': 'BTC-USD'},
    'ETH/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'ETHUSD', 'fallback': 'ETH-USD'},
    'LTC/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'LTCUSD', 'fallback': 'LTC-USD'},
    'XRP/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'XRPUSD', 'fallback': 'XRP-USD'},
    'BCH/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'BCHUSD', 'fallback': 'BCH-USD'},
    'EOS/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'yahoo', 'symbol': 'EOS-USD'},
    'ADA/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'ADAUSD', 'fallback': 'ADA-USD'},
    'DOT/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'DOTUSD', 'fallback': 'DOT-USD'},
    'LINK/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'LINKUSD', 'fallback': 'LINK-USD'},
    'UNI/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'UNIUSD', 'fallback': 'UNI-USD'},
    'SOL/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'SOLUSD', 'fallback': 'SOL-USD'},
    'AVAX/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'AVAXUSD', 'fallback': 'AVAX-USD'},
    'MATIC/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'yahoo', 'symbol': 'MATIC-USD'},
    'DOGE/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'XDGUSD', 'fallback': 'DOGE-USD'},
    'SHIB/USD': {'category': 'Cripto', 'group': 'Cripto', 'provider': 'kraken', 'symbol': 'SHIBUSD', 'fallback': 'SHIB-USD'},
}

_cache = {}


class MarketDataError(RuntimeError):
    pass


def grouped_assets():
    groups = [
        ('Forex · Principales', [k for k, v in ASSETS.items() if v['group'] == 'Principales']),
        ('Forex · Cruces', [k for k, v in ASSETS.items() if v['group'] == 'Cruces']),
        ('Forex · Exóticos', [k for k, v in ASSETS.items() if v['group'] == 'Exóticos']),
        ('Criptomonedas', [k for k, v in ASSETS.items() if v['category'] == 'Cripto']),
    ]
    return [{'name': name, 'assets': assets} for name, assets in groups if assets]


def _cached(key, ttl):
    item = _cache.get(key)
    now = time.time()
    if item and now - item[0] < ttl:
        return item[1]
    return None


def _store_cache(key, value):
    _cache[key] = (time.time(), value)
    return value


def _fetch_kraken(symbol, timeframe, limit):
    query = urllib.parse.urlencode({'pair': symbol, 'interval': timeframe})
    req = urllib.request.Request(
        f'{KRAKEN_URL}?{query}',
        headers={'User-Agent': 'SenalesVIPLatino/3.0'},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        payload = json.loads(response.read().decode('utf-8'))

    if payload.get('error'):
        raise MarketDataError('Kraken no devolvió cotización para este activo.')

    result = payload.get('result') or {}
    pair_key = next((k for k in result.keys() if k != 'last'), None)
    if not pair_key:
        raise MarketDataError('Kraken no devolvió velas.')

    return [{
        'time': int(float(row[0])),
        'open': float(row[1]),
        'high': float(row[2]),
        'low': float(row[3]),
        'close': float(row[4]),
        'volume': float(row[6] or 0),
    } for row in result[pair_key][-limit:]]


def _fetch_yahoo(symbol, timeframe, limit):
    interval = f'{int(timeframe)}m'
    range_value = '1d' if int(timeframe) == 1 else '5d'
    query = urllib.parse.urlencode({
        'interval': interval,
        'range': range_value,
        'includePrePost': 'false',
        'events': 'div,splits',
    })
    req = urllib.request.Request(
        f"{YAHOO_URL.format(symbol=urllib.parse.quote(symbol, safe='^=-'))}?{query}",
        headers={'User-Agent': 'Mozilla/5.0 SenalesVIPLatino/3.0', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        payload = json.loads(response.read().decode('utf-8'))

    chart = payload.get('chart') or {}
    if chart.get('error'):
        raise MarketDataError('La fuente de mercado no tiene datos para este activo.')

    results = chart.get('result') or []
    if not results:
        raise MarketDataError('La fuente de mercado no devolvió velas.')

    result = results[0]
    timestamps = result.get('timestamp') or []
    quotes = ((result.get('indicators') or {}).get('quote') or [{}])[0]
    opens = quotes.get('open') or []
    highs = quotes.get('high') or []
    lows = quotes.get('low') or []
    closes = quotes.get('close') or []
    volumes = quotes.get('volume') or []

    candles = []
    for i, ts in enumerate(timestamps):
        try:
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        except IndexError:
            continue
        if None in (o, h, l, c):
            continue
        candles.append({
            'time': int(ts),
            'open': float(o),
            'high': float(h),
            'low': float(l),
            'close': float(c),
            'volume': float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0,
        })
    return candles[-limit:]


def fetch_ohlc(asset='EUR/USD', timeframe=1, limit=220, fresh=False):
    if asset not in ASSETS:
        raise MarketDataError('Activo no soportado.')
    if int(timeframe) not in TIMEFRAMES:
        raise MarketDataError('Temporalidad no soportada.')

    timeframe = int(timeframe)
    key = ('ohlc-v3', asset, timeframe)
    cached = None if fresh else _cached(key, max(8, min(25, timeframe * 4)))
    if cached:
        return cached

    meta = ASSETS[asset]
    candles = None
    source = None

    if meta['provider'] == 'kraken':
        try:
            candles = _fetch_kraken(meta['symbol'], timeframe, limit)
            source = 'Kraken Public Market Data'
        except Exception:
            fallback = meta.get('fallback')
            if fallback:
                candles = _fetch_yahoo(fallback, timeframe, limit)
                source = 'Yahoo Finance public chart data'
    else:
        candles = _fetch_yahoo(meta['symbol'], timeframe, limit)
        source = 'Yahoo Finance public chart data'

    if not candles or len(candles) < 55:
        raise MarketDataError('Aún no hay suficientes velas para calcular una señal fiable.')

    result = {'candles': candles, 'source': source, 'meta': meta}
    return _store_cache(key, result)


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
    gains, losses = [], []
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
    return sum(trs[-period:]) / min(period, len(trs)) if trs else 0.0


def _stochastic(candles, period=14):
    window = candles[-period:]
    low = min(c['low'] for c in window)
    high = max(c['high'] for c in window)
    if high == low:
        return 50.0
    return (window[-1]['close'] - low) / (high - low) * 100


def _bollinger_position(closes, period=20):
    window = closes[-period:]
    mean = statistics.fmean(window)
    std = statistics.pstdev(window) if len(window) > 1 else 0
    if std == 0:
        return 0.0
    return (closes[-1] - mean) / (2 * std)


def _support_resistance(candles, period=20):
    window = candles[-period-1:-1]
    return min(c['low'] for c in window), max(c['high'] for c in window)


def _higher_timeframe_bias(asset, timeframe):
    """Confirma dirección con una temporalidad superior sin bloquear el análisis si la fuente falla."""
    higher = 5 if int(timeframe) == 1 else 15 if int(timeframe) == 5 else None
    if higher is None:
        return 0
    try:
        market = fetch_ohlc(asset, higher, limit=120)
        closes = [c['close'] for c in market['candles']]
        ema9 = _ema_series(closes, 9)[-1]
        ema21 = _ema_series(closes, 21)[-1]
        ema50 = _ema_series(closes, 50)[-1]
        price = closes[-1]
        if price > ema9 > ema21 > ema50:
            return 1
        if price < ema9 < ema21 < ema50:
            return -1
    except Exception:
        return 0
    return 0


def _current_market_price(asset):
    """Obtiene una cotización fresca cuando la entrada/salida se procesa a tiempo."""
    meta = ASSETS[asset]

    if meta['provider'] == 'kraken':
        query = urllib.parse.urlencode({'pair': meta['symbol']})
        req = urllib.request.Request(
            f'{KRAKEN_TICKER_URL}?{query}',
            headers={'User-Agent': 'SenalesVIPLatino/4.0'},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as response:
                payload = json.loads(response.read().decode('utf-8'))
            result = payload.get('result') or {}
            pair_key = next(iter(result), None)
            if pair_key:
                close_values = result[pair_key].get('c') or []
                if close_values:
                    return Decimal(str(close_values[0])), 'Kraken Public Market Data'
        except Exception:
            pass

    try:
        market = fetch_ohlc(asset, 1, limit=120, fresh=True)
        candles = market['candles']
        if candles:
            return Decimal(str(candles[-1]['close'])), market['source']
    except Exception:
        pass

    raise MarketDataError('No fue posible obtener una cotización fresca.')


def _historical_market_price(asset, target_dt):
    """Recupera el precio más cercano sin usar una vela futura al momento objetivo."""
    market = fetch_ohlc(asset, 1, limit=300, fresh=True)
    candles = market['candles']
    target_ts = int(target_dt.timestamp())

    past = [c for c in candles if int(c['time']) <= target_ts]
    if past:
        chosen = max(past, key=lambda c: int(c['time']))
    else:
        chosen = min(candles, key=lambda c: abs(int(c['time']) - target_ts))

    distance = abs(int(chosen['time']) - target_ts)
    if distance > 180:
        raise MarketDataError('No hay una cotización suficientemente cercana al momento de la señal.')
    return Decimal(str(chosen['close'])), market['source']


def _market_price_at(asset, target_dt):
    """
    Si el motor procesa el evento cerca de su hora exacta usa una cotización fresca.
    Si llega tarde tras un reinicio, reconstruye el precio con histórico de 1 minuto.
    """
    lag_seconds = abs((timezone.now() - target_dt).total_seconds())
    if lag_seconds <= 20:
        try:
            return _current_market_price(asset)
        except MarketDataError:
            pass
    return _historical_market_price(asset, target_dt)


def analyze_market(asset, timeframe):
    market = fetch_ohlc(asset, timeframe)
    candles = market['candles']
    source = market['source']
    meta = market['meta']
    closes = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]

    ema9s = _ema_series(closes, 9)
    ema21s = _ema_series(closes, 21)
    ema50s = _ema_series(closes, 50)
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd_series = [a - b for a, b in zip(ema12, ema26)]
    macd_signal = _ema_series(macd_series, 9)

    price = closes[-1]
    ema9, ema21, ema50 = ema9s[-1], ema21s[-1], ema50s[-1]
    rsi = _rsi(closes)
    stochastic = _stochastic(candles)
    bollinger_pos = _bollinger_position(closes)
    macd_hist = macd_series[-1] - macd_signal[-1]
    atr = _atr(candles)
    momentum3 = (price / closes[-4] - 1) * 100 if closes[-4] else 0
    momentum8 = (price / closes[-9] - 1) * 100 if closes[-9] else 0
    support, resistance = _support_resistance(candles)

    nonzero_volumes = [v for v in volumes[-20:] if v and v > 0]
    avg_volume = statistics.fmean(nonzero_volumes) if nonzero_volumes else 0
    volume_ratio = (volumes[-1] / avg_volume) if avg_volume and volumes[-1] else 1.0

    score = 0.0
    reasons = []

    if ema9 > ema21 > ema50:
        score += 2.5
        reasons.append('Tendencia alcista alineada EMA 9/21/50')
    elif ema9 < ema21 < ema50:
        score -= 2.5
        reasons.append('Tendencia bajista alineada EMA 9/21/50')
    elif ema9 > ema21:
        score += 1.2
        reasons.append('EMA 9 por encima de EMA 21')
    elif ema9 < ema21:
        score -= 1.2
        reasons.append('EMA 9 por debajo de EMA 21')

    if macd_hist > 0:
        score += 1.4
        reasons.append('MACD confirma impulso alcista')
    elif macd_hist < 0:
        score -= 1.4
        reasons.append('MACD confirma impulso bajista')

    if 53 <= rsi <= 68:
        score += .9
        reasons.append(f'RSI acompaña al alza ({rsi:.1f})')
    elif 32 <= rsi <= 47:
        score -= .9
        reasons.append(f'RSI acompaña a la baja ({rsi:.1f})')
    elif rsi >= 75:
        score -= .45
        reasons.append('RSI en sobrecompra')
    elif rsi <= 25:
        score += .45
        reasons.append('RSI en sobreventa')

    if stochastic >= 58 and stochastic < 88:
        score += .55
        reasons.append('Estocástico sostiene impulso alcista')
    elif stochastic <= 42 and stochastic > 12:
        score -= .55
        reasons.append('Estocástico sostiene impulso bajista')

    if momentum3 > .035 and momentum8 > 0:
        score += .85
        reasons.append('Momentum corto y medio positivo')
    elif momentum3 < -.035 and momentum8 < 0:
        score -= .85
        reasons.append('Momentum corto y medio negativo')

    if price > resistance:
        score += 1.15
        reasons.append('Ruptura de resistencia reciente')
    elif price < support:
        score -= 1.15
        reasons.append('Ruptura de soporte reciente')

    last = candles[-1]
    body = last['close'] - last['open']
    body_pct = abs(body) / price * 100 if price else 0
    if body_pct > .015:
        score += .35 if body > 0 else -.35
        reasons.append('Última vela confirma dirección')

    if bollinger_pos > .85:
        score -= .25
        reasons.append('Precio cerca de banda superior')
    elif bollinger_pos < -.85:
        score += .25
        reasons.append('Precio cerca de banda inferior')

    if volume_ratio >= 1.20 and nonzero_volumes:
        score += .35 if score > 0 else -.35 if score < 0 else 0
        reasons.append('Volumen superior a su media')

    atr_pct = (atr / price * 100) if price else 0
    if atr_pct > 1.5:
        score *= .86
        reasons.append('Volatilidad alta: señal penalizada')

    higher_bias = _higher_timeframe_bias(asset, timeframe)
    if higher_bias and score:
        if (score > 0 and higher_bias > 0) or (score < 0 and higher_bias < 0):
            score += .8 if score > 0 else -.8
        else:
            score *= .82

    candle_age = max(0, int(time.time()) - int(candles[-1]['time']))
    stale_limit = max(180, int(timeframe) * 180)
    market_fresh = meta['category'] == 'Cripto' or candle_age <= stale_limit

    if not market_fresh:
        direction = Signal.Direction.WAIT
        confidence = 45
        reasons.insert(0, 'Mercado sin cotización reciente')
    else:
        if score >= 4.15:
            direction = Signal.Direction.CALL
        elif score <= -4.15:
            direction = Signal.Direction.PUT
        else:
            direction = Signal.Direction.WAIT
        confidence = int(max(45, min(91, 50 + abs(score) * 6.6)))
        if direction == Signal.Direction.WAIT:
            confidence = min(confidence, 64)

    quality = 'ALTA' if confidence >= 80 and direction != Signal.Direction.WAIT else 'MEDIA' if confidence >= 68 and direction != Signal.Direction.WAIT else 'EN OBSERVACIÓN'

    if abs(ema9 - ema21) > max(atr * .22, price * .00015) and abs(macd_hist) > 0:
        strategy = 'Tendencia EMA + MACD'
    elif (rsi >= 53 or rsi <= 47) and abs(momentum3) >= .035:
        strategy = 'Momentum RSI'
    else:
        strategy = 'Confluencia técnica'

    risk_pct = .5 if atr_pct >= 1 else .75
    if confidence >= 80 and atr_pct < .8:
        risk_pct = 1.0

    return {
        'asset': asset,
        'category': meta['category'],
        'group': meta['group'],
        'timeframe': int(timeframe),
        'direction': direction,
        'score': round(score, 2),
        'confidence': confidence,
        'quality': quality,
        'price': price,
        'strategy': strategy,
        'rsi': round(rsi, 1),
        'stochastic': round(stochastic, 1),
        'bollinger_position': round(bollinger_pos, 2),
        'ema9': ema9,
        'ema21': ema21,
        'ema50': ema50,
        'macd_hist': macd_hist,
        'atr_pct': round(atr_pct, 3),
        'volume_ratio': round(volume_ratio, 2),
        'risk_pct': risk_pct,
        'higher_timeframe_bias': higher_bias,
        'market_fresh': market_fresh,
        'last_candle_at': candles[-1]['time'],
        'reasons': reasons[:6],
        'source': source,
    }


def get_or_create_signal(asset, timeframe):
    timeframe = int(timeframe)
    now = timezone.now()

    existing = Signal.objects.filter(
        asset=asset,
        timeframe=timeframe,
        outcome=Signal.Outcome.OPEN,
    ).order_by('-generated_at').first()
    if existing:
        return existing, None

    analysis = analyze_market(asset, timeframe)
    if analysis['direction'] == Signal.Direction.WAIT:
        return None, analysis

    scheduled_entry_at = now + timedelta(seconds=SIGNAL_ENTRY_DELAY_SECONDS)
    expires_at = scheduled_entry_at + timedelta(minutes=timeframe)
    signal = Signal.objects.create(
        asset=asset,
        timeframe=timeframe,
        strategy=analysis['strategy'],
        direction=analysis['direction'],
        score=analysis['score'],
        confidence=analysis['confidence'],
        entry_price=Decimal(str(analysis['price'])),
        scheduled_entry_at=scheduled_entry_at,
        source=analysis['source'],
        expires_at=expires_at,
    )
    return signal, analysis


def process_signal_states(limit=100):
    """
    Avanza el ciclo de todas las señales abiertas de forma idempotente.
    Puede ejecutarse desde la API y desde el worker sin duplicar activaciones/cierres.
    """
    now = timezone.now()
    activated = 0
    evaluated = 0
    errors = 0

    pending = list(
        Signal.objects.filter(
            outcome=Signal.Outcome.OPEN,
            scheduled_entry_at__isnull=False,
            scheduled_entry_at__lte=now,
            activated_at__isnull=True,
        ).order_by('scheduled_entry_at')[:limit]
    )

    for signal in pending:
        try:
            price, source = _market_price_at(signal.asset, signal.scheduled_entry_at)
        except MarketDataError:
            errors += 1
            continue

        updated = Signal.objects.filter(
            pk=signal.pk,
            outcome=Signal.Outcome.OPEN,
            activated_at__isnull=True,
        ).update(
            execution_entry_price=price,
            activated_at=timezone.now(),
            source=source or signal.source,
        )
        activated += int(bool(updated))

    now = timezone.now()
    due = list(
        Signal.objects.filter(
            outcome=Signal.Outcome.OPEN,
            execution_entry_price__isnull=False,
            expires_at__lte=now,
        ).order_by('expires_at')[:limit]
    )

    for signal in due:
        try:
            exit_price, _ = _market_price_at(signal.asset, signal.expires_at)
        except MarketDataError:
            errors += 1
            continue

        entry = signal.execution_entry_price
        if exit_price == entry:
            outcome = Signal.Outcome.DRAW
        elif signal.direction == Signal.Direction.CALL:
            outcome = Signal.Outcome.WIN if exit_price > entry else Signal.Outcome.LOSS
        else:
            outcome = Signal.Outcome.WIN if exit_price < entry else Signal.Outcome.LOSS

        updated = Signal.objects.filter(
            pk=signal.pk,
            outcome=Signal.Outcome.OPEN,
            execution_entry_price__isnull=False,
        ).update(
            exit_price=exit_price,
            outcome=outcome,
            evaluated_at=timezone.now(),
        )
        evaluated += int(bool(updated))

    return {'activated': activated, 'evaluated': evaluated, 'errors': errors}


def evaluate_due_signals(limit=50):
    return process_signal_states(limit=limit)['evaluated']


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
        output.append({**row, 'accuracy': round(accuracy, 1)})
    return output[:8]


def public_signal_dict(signal, analysis=None):
    now = timezone.now()
    if signal:
        if signal.outcome != Signal.Outcome.OPEN:
            phase = 'closed'
        elif signal.scheduled_entry_at and now < signal.scheduled_entry_at:
            phase = 'scheduled'
        elif signal.execution_entry_price is not None:
            phase = 'active'
        else:
            phase = 'activating'

        return {
            'id': signal.id,
            'asset': signal.asset,
            'timeframe': signal.timeframe,
            'direction': signal.direction,
            'strategy': signal.strategy,
            'confidence': signal.confidence,
            'entry_price': float(signal.entry_price),
            'execution_entry_price': float(signal.execution_entry_price) if signal.execution_entry_price is not None else None,
            'generated_at': signal.generated_at.isoformat(),
            'scheduled_entry_at': signal.scheduled_entry_at.isoformat() if signal.scheduled_entry_at else None,
            'activated_at': signal.activated_at.isoformat() if signal.activated_at else None,
            'expires_at': signal.expires_at.isoformat(),
            'source': signal.source,
            'status': signal.outcome,
            'phase': phase,
            'seconds_to_entry': max(0, int((signal.scheduled_entry_at - now).total_seconds())) if signal.scheduled_entry_at else 0,
            'seconds_to_expiry': max(0, int((signal.expires_at - now).total_seconds())),
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
        'execution_entry_price': None,
        'generated_at': now.isoformat(),
        'scheduled_entry_at': None,
        'activated_at': None,
        'expires_at': None,
        'source': analysis['source'],
        'status': 'wait',
        'phase': 'wait',
        'seconds_to_entry': 0,
        'seconds_to_expiry': 0,
        'analysis': analysis,
    }
