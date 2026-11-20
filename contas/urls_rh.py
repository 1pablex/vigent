"""Rotas da aba "Termo de uso" do painel do RH (RN-33)."""
from django.urls import path

from . import views_termo

app_name = "termo_rh"

urlpatterns = [
    path("", views_termo.lista, name="lista"),
    path("nova-versao/", views_termo.nova, name="nova"),
    path("<int:termo_id>/", views_termo.ver, name="ver"),
]
