from django.core.management.base import BaseCommand, CommandError
from registro.telegram import set_webhook


class Command(BaseCommand):
    help = 'Configura el webhook de Telegram para los botones Aprobar/Rechazar.'

    def handle(self, *args, **options):
        ok, result = set_webhook()
        if not ok:
            raise CommandError(f'No se pudo configurar el webhook: {result}')
        self.stdout.write(self.style.SUCCESS('Webhook de Telegram configurado correctamente.'))
        self.stdout.write(str(result))
