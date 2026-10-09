"""Testes de autenticação: RN-18 (2FA), RN-27 (senha provisória) e RN-35 (força bruta).

O envio do código pelo Brevo é substituído por mock: nenhum teste chama a API real.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import LogSistema
from contas.models import CodigoVerificacao, Departamento

Usuario = get_user_model()


class AutenticacaoTestCase(TestCase):
    def setUp(self):
        self.enviar_codigo = patch("contas.views.enviar_codigo_verificacao").start()
        self.addCleanup(patch.stopall)
        self.departamento = Departamento.objects.create(nome="Vendas")
        self.colaborador = Usuario.objects.create_user(
            email="teste@nortex.com.br", nome="Colaborador Teste",
            password="senha-correta-123", cargo="Analista",
            departamento=self.departamento, senha_provisoria=False,
        )

    def test_login_com_credenciais_corretas_envia_codigo_e_aguarda_segundo_fator(self):
        resposta = self.client.post(reverse("contas:login"), {
            "email": "teste@nortex.com.br", "senha": "senha-correta-123",
        })
        self.assertRedirects(resposta, reverse("contas:verificar_codigo"))
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)
        codigo = CodigoVerificacao.objects.get(usuario=self.colaborador)
        self.enviar_codigo.assert_called_once_with(self.colaborador, codigo)

    def test_rn18_codigo_correto_conclui_login_e_invalida_o_codigo(self):
        self.client.post(reverse("contas:login"), {
            "email": "teste@nortex.com.br", "senha": "senha-correta-123",
        })
        codigo = CodigoVerificacao.objects.get(usuario=self.colaborador)

        resposta = self.client.post(reverse("contas:verificar_codigo"),
                                    {"codigo": codigo.codigo})

        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.colaborador.pk)
        codigo.refresh_from_db()
        self.assertTrue(codigo.utilizado)

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
        self.assertRedirects(resposta, reverse("contas:verificar_codigo"))
        self.assertEqual(self.client.session["pre_2fa_usuario_id"], self.colaborador.pk)

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

    def test_rn27_definir_senha_libera_e_segue_para_aceite_do_termo(self):
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
        # Saiu do bloqueio da senha provisória; o próximo passo obrigatório é o aceite LGPD.
        resposta = self.client.get(reverse("treinamentos:inicio"))
        self.assertRedirects(resposta, reverse("contas:aceitar_termo"))

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