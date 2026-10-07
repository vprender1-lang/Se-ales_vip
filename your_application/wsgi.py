# Compatibilidad con el comando antiguo de Render:
# gunicorn your_application.wsgi
from config.wsgi import application

__all__ = ["application"]
