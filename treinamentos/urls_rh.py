from django.urls import path

from . import views_rh

app_name = "cursos_rh"

urlpatterns = [
    path("", views_rh.lista, name="lista"),
    path("novo/", views_rh.novo, name="novo"),
    path("<int:curso_id>/", views_rh.editar, name="editar"),
    path("<int:curso_id>/aulas/nova/", views_rh.aula_nova, name="aula_nova"),
    path("<int:curso_id>/aulas/<int:aula_id>/", views_rh.aula_editar, name="aula_editar"),
    path("<int:curso_id>/aulas/<int:aula_id>/excluir/", views_rh.aula_excluir, name="aula_excluir"),
    path("<int:curso_id>/aulas/<int:aula_id>/slides/novo/", views_rh.slide_novo,
         name="slide_novo"),
    path("<int:curso_id>/aulas/<int:aula_id>/slides/<int:slide_id>/", views_rh.slide_editar,
         name="slide_editar"),
    path("<int:curso_id>/aulas/<int:aula_id>/slides/<int:slide_id>/excluir/",
         views_rh.slide_excluir, name="slide_excluir"),
    path("<int:curso_id>/questoes/nova/", views_rh.questao_nova, name="questao_nova"),
    path("<int:curso_id>/questoes/<int:questao_id>/", views_rh.questao_editar,
         name="questao_editar"),
    path("<int:curso_id>/questoes/<int:questao_id>/excluir/", views_rh.questao_excluir,
         name="questao_excluir"),
]
