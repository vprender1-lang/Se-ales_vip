from django.urls import path
from . import views

app_name = 'registro'

urlpatterns = [
    path('', views.home, name='home'),
    path('solicitud/<uuid:public_id>/', views.status, name='status'),
    path('solicitud/<uuid:public_id>/estado.json', views.status_json, name='status_json'),
    path('revision/<uuid:public_id>/<str:action>/', views.admin_review, name='admin_review'),
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
]
