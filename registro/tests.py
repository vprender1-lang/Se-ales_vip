from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import Signal
from .signal_engine import (
    SIGNAL_ENTRY_DELAY_SECONDS,
    get_or_create_signal,
    process_signal_states,
    public_signal_dict,
)


class SignalLifecycleTests(TestCase):
    @patch('registro.signal_engine.analyze_market')
    def test_signal_is_issued_now_but_enters_sixty_seconds_later(self, analyze):
        analyze.return_value = {
            'asset': 'EUR/USD',
            'timeframe': 1,
            'direction': Signal.Direction.CALL,
            'score': 5.2,
            'confidence': 84,
            'price': 1.10000,
            'strategy': 'Tendencia EMA + MACD',
            'source': 'Test market',
        }

        before = timezone.now()
        signal, analysis = get_or_create_signal('EUR/USD', 1)
        after = timezone.now()

        self.assertIsNotNone(signal)
        self.assertEqual(signal.direction, Signal.Direction.CALL)
        expected_min = before + timedelta(seconds=SIGNAL_ENTRY_DELAY_SECONDS)
        expected_max = after + timedelta(seconds=SIGNAL_ENTRY_DELAY_SECONDS)
        self.assertGreaterEqual(signal.scheduled_entry_at, expected_min)
        self.assertLessEqual(signal.scheduled_entry_at, expected_max)
        self.assertEqual(signal.expires_at, signal.scheduled_entry_at + timedelta(minutes=1))
        self.assertIsNone(signal.execution_entry_price)
        self.assertIsNone(signal.activated_at)

        public = public_signal_dict(signal, analysis)
        self.assertEqual(public['phase'], 'scheduled')
        self.assertGreaterEqual(public['seconds_to_entry'], 58)
        self.assertLessEqual(public['seconds_to_entry'], 60)

    @patch('registro.signal_engine._market_price_at')
    def test_signal_activates_then_closes_as_win(self, market_price):
        now = timezone.now()
        signal = Signal.objects.create(
            asset='EUR/USD',
            timeframe=1,
            strategy='Confluencia técnica',
            direction=Signal.Direction.CALL,
            score=5.0,
            confidence=82,
            entry_price=Decimal('1.09900'),
            scheduled_entry_at=now - timedelta(minutes=2),
            expires_at=now - timedelta(minutes=1),
            source='Test market',
        )
        market_price.side_effect = [
            (Decimal('1.10000'), 'Test market'),
            (Decimal('1.10100'), 'Test market'),
        ]

        result = process_signal_states(limit=10)
        signal.refresh_from_db()

        self.assertEqual(result['activated'], 1)
        self.assertEqual(result['evaluated'], 1)
        self.assertEqual(signal.execution_entry_price, Decimal('1.10000'))
        self.assertEqual(signal.exit_price, Decimal('1.10100'))
        self.assertEqual(signal.outcome, Signal.Outcome.WIN)
        self.assertIsNotNone(signal.activated_at)
        self.assertIsNotNone(signal.evaluated_at)

    @patch('registro.signal_engine._market_price_at')
    def test_put_signal_closes_as_loss_when_price_rises(self, market_price):
        now = timezone.now()
        signal = Signal.objects.create(
            asset='GBP/USD',
            timeframe=5,
            strategy='Momentum RSI',
            direction=Signal.Direction.PUT,
            score=-5.0,
            confidence=81,
            entry_price=Decimal('1.25000'),
            scheduled_entry_at=now - timedelta(minutes=6),
            expires_at=now - timedelta(minutes=1),
            source='Test market',
        )
        market_price.side_effect = [
            (Decimal('1.25000'), 'Test market'),
            (Decimal('1.25100'), 'Test market'),
        ]

        process_signal_states(limit=10)
        signal.refresh_from_db()
        self.assertEqual(signal.outcome, Signal.Outcome.LOSS)
