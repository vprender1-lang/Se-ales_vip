# Señales VIP del Latino — Django

Aplicación Django para registrar IDs de Quotex, enviarlos automáticamente al Telegram del administrador y aprobar/rechazar el acceso VIP.

## Lo que ya quedó configurado

- Nombre: **Señales VIP del Latino**.
- Enlace de afiliado: `https://broker-qx.pro/sign-up/?lid=2343139`.
- Banner de Quotex incluido en la portada.
- SQLite como base de datos.
- Formulario con ID de Quotex + usuario de Telegram.
- No solicita contraseña, código SMS, 2FA ni datos bancarios.
- El ID del administrador de Telegram quedó preconfigurado como **7306800842**.
- Cada nueva solicitud se envía automáticamente a tu Telegram mediante tu propio bot.
- El mensaje recibido contiene:
  - ID de Quotex.
  - Usuario de Telegram del solicitante.
  - Número único de solicitud.
  - Botón **Abrir QuotexPartnerBot**.
  - Botón **Aprobar**.
  - Botón **Rechazar**.
- Cuando apruebas/rechazas desde Telegram, Django actualiza el estado del usuario.
- El visitante ve su estado actualizado automáticamente.
- También puedes administrar todo desde `/admin/`.

> Importante: la aplicación no inventa una API de Quotex. La comprobación del referido se hace usando tu acceso autorizado a QuotexPartnerBot/panel y luego tú apruebas o rechazas.

## 1. Instalar en Windows

Descomprime el proyecto y ejecuta:

```bat
run_windows.bat
```

O manualmente:

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre:

```text
http://127.0.0.1:8000/
```

## 2. Crear el bot de Señales VIP del Latino

En Telegram:

1. Abre `@BotFather`.
2. Ejecuta `/newbot`.
3. Crea tu bot.
4. Copia el token.
5. Abre `.env` y coloca:

```env
TELEGRAM_BOT_TOKEN=TU_TOKEN_REAL
TELEGRAM_ADMIN_CHAT_ID=7306800842
```

6. Busca tu nuevo bot en Telegram y pulsa **START / INICIAR** al menos una vez.

Telegram no permite que un bot inicie una conversación privada con una persona que nunca lo ha iniciado.

## 3. Probar que te llegan solicitudes

Con Django funcionando, registra un ID de prueba desde la página.

Debes recibir en Telegram algo parecido a:

```text
🔥 NUEVA SOLICITUD — SEÑALES VIP DEL LATINO

🆔 ID Quotex: 123456789
👤 Telegram: @usuario
🔖 Solicitud: ...
📌 Estado: ⏳ PENDIENTE

1️⃣ Abre QuotexPartnerBot y consulta el ID.
2️⃣ Confirma que pertenece a tus referidos.
3️⃣ Luego pulsa Aprobar o Rechazar aquí.
```

El botón **Abrir QuotexPartnerBot** abre:

```text
https://t.me/QuotexPartnerBot
```

## 4. Hacer funcionar Aprobar/Rechazar desde Telegram

Para que Telegram pueda avisar a Django cuando pulsas un botón, tu página debe estar publicada con **HTTPS**.

En `.env` configura:

```env
PUBLIC_URL=https://tu-dominio.com
TELEGRAM_WEBHOOK_SECRET=una_clave_larga_y_aleatoria
```

Después ejecuta una sola vez:

```bash
python manage.py telegram_set_webhook
```

Desde ese momento:

1. Llega una solicitud a tu Telegram.
2. Pulsas **Abrir QuotexPartnerBot**.
3. Compruebas el ID.
4. Regresas al mensaje.
5. Pulsas **✅ Aprobar** o **❌ Rechazar**.
6. Django cambia el estado inmediatamente.
7. La página del cliente lo detecta automáticamente.

Si cambias de dominio puedes borrar el webhook con:

```bash
python manage.py telegram_delete_webhook
```

y configurarlo nuevamente.

## 5. Panel administrador Django

Crea un usuario administrador:

```bash
python manage.py createsuperuser
```

Luego abre:

```text
http://127.0.0.1:8000/admin/
```

Desde ahí también puedes buscar por ID, ver pendientes y aprobar/rechazar solicitudes.

## 6. Enlace VIP

Cuando tengas tu grupo o canal privado, coloca su invitación en `.env`:

```env
TELEGRAM_VIP_URL=https://t.me/+TU_INVITACION_PRIVADA
```

Ese botón solo se muestra al usuario cuando su solicitud está **APROBADA**.

## 7. Configuración recomendada al publicar

```env
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com,https://www.tu-dominio.com
PUBLIC_URL=https://tu-dominio.com
```

Usa una `DJANGO_SECRET_KEY`, `TELEGRAM_WEBHOOK_SECRET`, `ADMIN_REVIEW_SECRET` e `IP_HASH_SALT` largas y distintas.

## Seguridad

- `TELEGRAM_BOT_TOKEN` permanece únicamente en el servidor.
- Nunca se imprime el token en HTML o JavaScript.
- El webhook valida el secreto enviado por Telegram.
- Solo el chat administrador `7306800842` puede ejecutar los callbacks de aprobar/rechazar.
- El ID de Quotex se trata como identificador; nunca se piden credenciales de la cuenta.
- `.env` está excluido de Git mediante `.gitignore`.


## Motor de señales VIP

Después de aprobar una solicitud, el usuario recibe acceso a:

- Panel privado vinculado al UUID de su solicitud aprobada.
- Señales técnicas para 1, 5 y 15 minutos.
- Activos iniciales: BTC/USD, ETH/USD, SOL/USD, XRP/USD y LTC/USD.
- Fuente de mercado pública: Kraken.
- Confluencia con EMA 9/21, RSI 14, MACD, momentum, volumen y ATR.
- Puntuación heurística de confianza (no es una probabilidad garantizada).
- Gestión de riesgo con calculadora de exposición y límite máximo de 2%.
- Historial de señales cerradas y precisión direccional.
- Ranking basado únicamente en resultados medidos; no se generan ganancias ni traders falsos.
- Chat de soporte web conectado a tu Telegram.

### Chat de soporte por Telegram

Cuando un usuario aprobado escribe en el chat del panel:

1. El mensaje se guarda en Django.
2. Tu bot te envía el mensaje a `TELEGRAM_ADMIN_CHAT_ID=7306800842`.
3. En Telegram, usa **Responder** sobre ese mensaje y escribe tu respuesta.
4. El webhook guarda tu respuesta como administrador.
5. El panel del usuario la muestra automáticamente.

Para recibir también mensajes (además de los botones Aprobar/Rechazar), vuelve a registrar el webhook después de desplegar:

```bash
python manage.py telegram_set_webhook
```

`start.sh` intenta ejecutar este comando automáticamente en cada despliegue si el token, la URL pública y el secreto están configurados.

### Variables necesarias en Render

```env
TELEGRAM_BOT_TOKEN=TOKEN_REAL_DE_BOTFATHER
TELEGRAM_ADMIN_CHAT_ID=7306800842
TELEGRAM_WEBHOOK_SECRET=UNA_CLAVE_LARGA_Y_ALEATORIA
TELEGRAM_VIP_URL=https://t.me/+TU_INVITACION_PRIVADA
```

En Render, `PUBLIC_URL` se puede omitir porque la aplicación toma `RENDER_EXTERNAL_HOSTNAME` automáticamente.

### Nota sobre Quotex y datos de mercado

El motor no necesita la contraseña de Quotex. Las señales actuales se calculan con datos públicos de Kraken, por lo que la cotización puede diferir de la mostrada por Quotex. La precisión almacenada es una medición direccional del motor, no una garantía de rentabilidad ni una reproducción del P&L del broker.

Existe software de terceros que intenta conectarse a Quotex mediante APIs no oficiales, pero esta aplicación no guarda credenciales del broker ni depende de ellas para funcionar.
