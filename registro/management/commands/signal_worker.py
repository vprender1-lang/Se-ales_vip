import logging
import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, close_old_connections

from registro.signal_engine import process_signal_states


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Mantiene automáticamente entradas, vencimientos y resultados de señales.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=float, default=2.0)
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        interval = max(0.8, float(options['interval']))
        limit = max(10, int(options['limit']))
        self.stdout.write(self.style.SUCCESS(
            f'Signal worker activo: intervalo={interval}s, límite={limit}'
        ))

        while True:
            try:
                close_old_connections()
                result = process_signal_states(limit=limit)
                if result.get('activated') or result.get('evaluated'):
                    self.stdout.write(
                        f"signal_worker activated={result.get('activated', 0)} "
                        f"evaluated={result.get('evaluated', 0)} "
                        f"errors={result.get('errors', 0)}"
                    )
            except OperationalError as exc:
                logger.warning('Base de datos ocupada; se reintentará: %s', exc)
            except KeyboardInterrupt:
                self.stdout.write('Signal worker detenido.')
                break
            except Exception:
                logger.exception('Error no fatal en signal_worker')
            finally:
                close_old_connections()

            time.sleep(interval)
