from django.urls import path

from . import views

app_name = "avaliacoes"

urlpatterns = [
    path("curso/<int:curso_id>/reacao/", views.reacao, name="reacao"),
    path("curso/<int:curso_id>/prova/", views.prova, name="prova"),
]