"""Testes de autenticação: RN-27 (senha provisória) e RN-35 (força bruta)."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from auditoria.models import LogSistema
from contas.models import Departamento

Usuario = get_user_model()


class AutenticacaoTestCase(TestCase):
    def setUp(self):
        self.departamento = Departamento.objects.create(nome="Vendas")
        self.colaborador = Usuario.objects.create_user(
            email="teste@nortex.com.br", nome="Colaborador Teste",
            password="senha-correta-123", cargo="Analista",
            departamento=self.departamento, senha_provisoria=False,
        )

    def test_login_com_credenciais_corretas(self):
        resposta = self.client.post(reverse("contas:login"), {
            "email": "teste@nortex.com.br", "senha": "senha-correta-123",
        })
        self.assertTrue(resposta.wsgi_request.user.is_authenticated)

    def test_login_com_senha_errada(self):
        resposta = self.client.post(reverse("contas:login"), {
            "email": "teste@nortex.com.br", "senha": "senha-errada",
        })
        self.assertIn("inválidos", resposta.content.decode())
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)

    def test_email_normalizado_no_login(self):
        """RN-26 — maiúsculo/espaço não deveriam impedir o login."""
        resposta = self.client.post(reverse("contas:login"), {
            "email": "  TESTE@Nortex.COM.BR  ", "senha": "senha-correta-123",
        })
        self.assertTrue(resposta.wsgi_request.user.is_authenticated)

    def test_rn27_senha_provisoria_redireciona_para_definir_senha(self):
        Usuario.objects.create_user(
            email="novo@nortex.com.br", nome="Novo Colaborador",
            password="Provisoria@2026", cargo="Estagiário",
            departamento=self.departamento, senha_provisoria=True,
        )
        resposta = self.client.post(reverse("contas:login"), {
            "email": "novo@nortex.com.br", "senha": "Provisoria@2026",
        }, follow=True)
        self.assertRedirects(resposta, reverse("contas:definir_senha"))

    def test_rn27_middleware_bloqueia_outras_paginas_com_senha_provisoria(self):
        Usuario.objects.create_user(
            email="preso@nortex.com.br", nome="Preso",
            password="Provisoria@2026", cargo="Estagiário",
            departamento=self.departamento, senha_provisoria=True,
        )
        self.client.login(username="preso@nortex.com.br", password="Provisoria@2026")
        resposta = self.client.get(reverse("treinamentos:inicio"), follow=True)
        self.assertRedirects(resposta, reverse("contas:definir_senha"))

    def test_rn27_definir_senha_libera_acesso(self):
        usuario = Usuario.objects.create_user(
            email="troca@nortex.com.br", nome="Troca Senha",
            password="Provisoria@2026", cargo="Estagiário",
            departamento=self.departamento, senha_provisoria=True,
        )
        self.client.login(username="troca@nortex.com.br", password="Provisoria@2026")
        self.client.post(reverse("contas:definir_senha"), {
            "nova1": "senha-nova-123", "nova2": "senha-nova-123",
        })
        usuario.refresh_from_db()
        self.assertFalse(usuario.senha_provisoria)
        resposta = self.client.get(reverse("treinamentos:inicio"))
        self.assertEqual(resposta.status_code, 200)

    def test_rn35_bloqueio_apos_cinco_tentativas(self):
        for _ in range(5):
            self.client.post(reverse("contas:login"), {
                "email": "teste@nortex.com.br", "senha": "senha-errada",
            })
        resposta = self.client.post(reverse("contas:login"), {
            "email": "teste@nortex.com.br", "senha": "senha-correta-123",
        })
        self.assertIn("Muitas tentativas", resposta.content.decode())
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)
        self.assertTrue(
            LogSistema.objects.filter(evento="Login bloqueado").exists())