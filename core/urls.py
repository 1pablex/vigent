from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("rh/colaboradores/", views.rh_colaboradores, name="rh_colaboradores"),
    path("rh/auditoria/", views.rh_auditoria, name="rh_auditoria"),
]