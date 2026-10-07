from django.urls import path
from . import views

app_name = 'registro'

urlpatterns = [
    path('', views.home, name='home'),
    path('solicitud/<uuid:public_id>/', views.status, name='status'),
    path('solicitud/<uuid:public_id>/estado.json', views.status_json, name='status_json'),
    path('senales/<uuid:public_id>/', views.signals_dashboard, name='signals_dashboard'),
    path('api/senales/<uuid:public_id>/', views.signal_api, name='signal_api'),
    path('api/soporte/<uuid:public_id>/', views.support_api, name='support_api'),
    path('revision/<uuid:public_id>/<str:action>/', views.admin_review, name='admin_review'),
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
]
