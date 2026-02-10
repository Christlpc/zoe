# apps/whatsapp_bot/urls.py
from django.urls import path
from . import views

app_name = 'whatsapp_bot'

urlpatterns = [
    path('webhook/', views.whatsapp_webhook, name='webhook'),
    path('reset-session/', views.reset_session, name='reset_session'),
    path('sessions/', views.sessions_actives, name='sessions_actives'),
]