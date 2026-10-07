from django.core.management.base import BaseCommand, CommandError
from registro.telegram import delete_webhook


class Command(BaseCommand):
    help = 'Elimina el webhook actual del bot de Telegram.'

    def handle(self, *args, **options):
        ok, result = delete_webhook()
        if not ok:
            raise CommandError(f'No se pudo eliminar el webhook: {result}')
        self.stdout.write(self.style.SUCCESS('Webhook eliminado correctamente.'))
        self.stdout.write(str(result))
