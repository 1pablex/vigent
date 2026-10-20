from django.urls import path

from . import views

app_name = "certificacao"

urlpatterns = [
    path("meus/", views.meus_certificados, name="meus"),
    path("<int:certificado_id>/", views.ver_certificado, name="ver"),
]