from django.urls import path

from . import views

app_name = "treinamentos"

urlpatterns = [
    path("", views.meus_treinamentos, name="inicio"),
    path("curso/<int:curso_id>/abrir/", views.abrir_curso, name="abrir"),
    path("curso/<int:curso_id>/", views.curso, name="curso"),
]