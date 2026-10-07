from django.urls import path
from . import views

app_name = 'registro'

urlpatterns = [
    path('', views.home, name='home'),
    path('acceso/', views.vip_login, name='vip_login'),
    path('salir/', views.vip_logout, name='vip_logout'),
    path('solicitud/<uuid:public_id>/', views.status, name='status'),
    path('solicitud/<uuid:public_id>/estado.json', views.status_json, name='status_json'),
    path('senales/', views.signals_dashboard, name='signals_dashboard'),
    path('senales/<uuid:public_id>/', views.legacy_signals_dashboard, name='legacy_signals_dashboard'),
    path('api/senales/', views.signal_api, name='signal_api'),
    path('api/senales/historial/', views.signal_history_api, name='signal_history_api'),
    path('api/soporte/', views.support_api, name='support_api'),
    path('revision/<uuid:public_id>/<str:action>/', views.admin_review, name='admin_review'),
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
]
