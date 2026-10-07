import json
import urllib.request
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Muestra los chats recientes del bot para encontrar TELEGRAM_ADMIN_CHAT_ID.'

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            self.stderr.write('Configura TELEGRAM_BOT_TOKEN en .env primero.')
            return
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getUpdates', timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        seen = set()
        for update in data.get('result', []):
            msg = update.get('message') or update.get('edited_message') or {}
            chat = msg.get('chat') or {}
            cid = chat.get('id')
            if cid and cid not in seen:
                seen.add(cid)
                self.stdout.write(f"chat_id={cid} | usuario=@{chat.get('username','')} | nombre={chat.get('first_name','')}")
        if not seen:
            self.stdout.write('No hay mensajes. Escríbele primero a tu bot con /start y ejecuta otra vez este comando.')
