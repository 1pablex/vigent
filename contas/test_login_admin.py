"""Login do Django Admin com verificação em duas etapas.

O formulário padrão do Admin (só e-mail e senha) deixa de existir: /admin/login/ leva ao
login do Vigent, que exige o código por e-mail, e depois volta para o Admin.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

Usuario = get_user_model()


class LoginAdminComDoisFatoresTest(TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            email="admin@exemplo.invalid", nome="Administrador", password="senha-admin-123",
            aceite_termo_vigente=True)

    def entrar(self, destino="/admin/contas/termouso/"):
        """Faz o caminho completo: Admin, login do Vigent, código e volta. Devolve o código."""
        resposta = self.client.get(reverse("admin_login"), {"next": destino})
        login = resposta["Location"]
        with patch("contas.views.enviar_codigo_verificacao") as enviar:
            self.client.post(login, {"email": "admin@exemplo.invalid", "senha": "senha-admin-123"})
        return enviar.call_args.args[1]

    def test_login_do_admin_leva_ao_login_do_vigent(self):
        resposta = self.client.get("/admin/login/", {"next": "/admin/"})
        self.assertRedirects(resposta, f"{reverse('contas:login')}?next=%2Fadmin%2F",
                             fetch_redirect_response=False)

    def test_post_direto_no_login_do_admin_nao_autentica(self):
        resposta = self.client.post("/admin/login/?next=/admin/", {
            "username": "admin@exemplo.invalid", "password": "senha-admin-123"})

        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_senha_certa_sem_codigo_nao_entra_no_admin(self):
        self.entrar()
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/",
                             fetch_redirect_response=False)

    def test_depois_do_codigo_volta_para_a_pagina_do_admin(self):
        codigo = self.entrar("/admin/contas/termouso/")

        resposta = self.client.post(reverse("contas:verificar_codigo"), {"codigo": codigo})

        self.assertRedirects(resposta, "/admin/contas/termouso/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin.pk)

    def test_destino_externo_no_login_do_vigent_e_ignorado(self):
        with patch("contas.views.enviar_codigo_verificacao") as enviar:
            self.client.post(f"{reverse('contas:login')}?next=https://site-malicioso.example/",
                             {"email": "admin@exemplo.invalid", "senha": "senha-admin-123"})

        resposta = self.client.post(reverse("contas:verificar_codigo"),
                                    {"codigo": enviar.call_args.args[1]})

        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)

    def test_destino_externo_no_login_do_admin_vira_a_pagina_inicial_do_admin(self):
        resposta = self.client.get("/admin/login/", {"next": "//site-malicioso.example"})
        self.assertRedirects(resposta, f"{reverse('contas:login')}?next=%2Fadmin%2F",
                             fetch_redirect_response=False)

    def test_login_normal_sem_destino_continua_indo_para_o_inicio(self):
        with patch("contas.views.enviar_codigo_verificacao") as enviar:
            self.client.post(reverse("contas:login"),
                             {"email": "admin@exemplo.invalid", "senha": "senha-admin-123"})
        resposta = self.client.post(reverse("contas:verificar_codigo"),
                                    {"codigo": enviar.call_args.args[1]})
        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)
