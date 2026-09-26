from django.urls import path

from . import views

app_name = "contas"

urlpatterns = [
    path("entrar/", views.tela_login, name="login"),
    path("sair/", views.sair, name="logout"),
    path("definir-senha/", views.definir_senha, name="definir_senha"),
    path("verificar-codigo/", views.verificar_codigo, name="verificar_codigo"),
    path("colaboradores/novo/", views.cadastrar_colaborador, name="cadastrar"),
    path("esqueci-senha/", views.esqueci_senha, name="esqueci_senha"),
    path("redefinir-senha/", views.redefinir_senha, name="redefinir_senha"),
    path("aceitar-termo/", views.aceitar_termo, name="aceitar_termo"),
    path("politica-privacidade/", views.ver_politica_privacidade, name="politica_privacidade"),
]