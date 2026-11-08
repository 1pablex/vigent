"""Testes de integração do limite de tentativas nos códigos de verificação.

Após 5 erros o código é invalidado e o usuário precisa solicitar outro, tanto no
segundo fator do login (RN-25) quanto na redefinição de senha. O envio pelo Brevo
é substituído por mock.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogSistema
from contas.models import CodigoVerificacao

Usuario = get_user_model()


def codigo_errado(certo):
    return "000000" if certo != "000000" else "111111"


class LimiteTentativasDoisFatoresTest(TestCase):

    def setUp(self):
        patch("contas.views.enviar_codigo_verificacao").start()
        self.addCleanup(patch.stopall)
        self.usuario = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-correta-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.client.post(reverse("contas:login"), {
            "email": "ana@nortex.com.br", "senha": "senha-correta-123"})
        self.codigo = CodigoVerificacao.objects.get(usuario=self.usuario)

    def errar(self, vezes):
        for _ in range(vezes):
            resposta = self.client.post(reverse("contas:verificar_codigo"),
                                        {"codigo": codigo_errado(self.codigo.codigo)})
        return resposta

    def test_deve_informar_tentativas_restantes(self):
        # Act
        resposta = self.errar(4)

        # Assert
        self.assertContains(resposta, "Código incorreto. Tentativas restantes: 1.")
        self.codigo.refresh_from_db()
        self.assertEqual(self.codigo.tentativas_erradas, 4)

    def test_deve_bloquear_codigo_apos_cinco_erros_mesmo_com_valor_certo(self):
        # Arrange
        self.errar(5)

        # Act
        resposta = self.client.post(reverse("contas:verificar_codigo"),
                                    {"codigo": self.codigo.codigo})

        # Assert
        self.assertContains(resposta, "Código bloqueado após 5 tentativas incorretas.")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.codigo.refresh_from_db()
        self.assertEqual(self.codigo.tentativas_erradas, 5)
        self.assertFalse(self.codigo.utilizado)
        self.assertEqual(LogSistema.objects.filter(
            evento="Código de verificação bloqueado", usuario=self.usuario).count(), 1)

    def passar_intervalo_de_reenvio(self):
        CodigoVerificacao.objects.filter(usuario=self.usuario).update(
            data_geracao=timezone.now() - timedelta(minutes=5, seconds=1))

    def test_novo_codigo_solicitado_libera_o_login(self):
        # Arrange
        self.errar(5)
        self.passar_intervalo_de_reenvio()
        self.client.post(reverse("contas:verificar_codigo"), {"reenviar": "1"})
        novo = CodigoVerificacao.objects.filter(usuario=self.usuario).latest("data_geracao")

        # Act
        resposta = self.client.post(reverse("contas:verificar_codigo"), {"codigo": novo.codigo})

        # Assert
        self.assertNotEqual(novo.pk, self.codigo.pk)
        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)


    def test_reenvio_antes_de_5_minutos_e_recusado(self):
        # Act
        resposta = self.client.post(reverse("contas:verificar_codigo"), {"reenviar": "1"})

        # Assert
        self.assertContains(resposta, "Aguarde 5 minutos para pedir um novo código.")
        self.assertEqual(CodigoVerificacao.objects.filter(usuario=self.usuario).count(), 1)

    def test_reenvio_informa_o_tempo_que_falta(self):
        # Arrange: código gerado há 3 min e 30 s
        CodigoVerificacao.objects.filter(usuario=self.usuario).update(
            data_geracao=timezone.now() - timedelta(minutes=3, seconds=30))

        # Act
        resposta = self.client.post(reverse("contas:verificar_codigo"), {"reenviar": "1"})

        # Assert
        self.assertContains(resposta, "Aguarde 2 minutos para pedir um novo código.")

    def test_reenvio_depois_de_5_minutos_gera_novo_codigo(self):
        # Arrange
        self.passar_intervalo_de_reenvio()

        # Act
        resposta = self.client.post(reverse("contas:verificar_codigo"), {"reenviar": "1"})

        # Assert
        self.assertContains(resposta, "Um novo código foi enviado.")
        self.assertEqual(CodigoVerificacao.objects.filter(usuario=self.usuario).count(), 2)


class LimiteTentativasRedefinicaoSenhaTest(TestCase):

    def setUp(self):
        patch("contas.views.enviar_codigo_redefinicao").start()
        self.addCleanup(patch.stopall)
        self.usuario = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-antiga-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.client.post(reverse("contas:esqueci_senha"), {"email": "ana@nortex.com.br"})
        self.codigo = CodigoVerificacao.objects.get(usuario=self.usuario)

    def redefinir(self, codigo):
        return self.client.post(reverse("contas:redefinir_senha"), {
            "codigo": codigo, "nova1": "senha-nova-456", "nova2": "senha-nova-456"})

    def test_deve_bloquear_redefinicao_apos_cinco_erros_mesmo_com_valor_certo(self):
        # Arrange
        for _ in range(5):
            self.redefinir(codigo_errado(self.codigo.codigo))

        # Act
        resposta = self.redefinir(self.codigo.codigo)

        # Assert
        self.assertContains(resposta, "Código bloqueado após 5 tentativas incorretas.")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("senha-antiga-123"))
        self.assertFalse(self.usuario.check_password("senha-nova-456"))

    def test_novo_codigo_solicitado_permite_redefinir(self):
        # Arrange
        for _ in range(5):
            self.redefinir(codigo_errado(self.codigo.codigo))
        self.client.post(reverse("contas:esqueci_senha"), {"email": "ana@nortex.com.br"})
        novo = CodigoVerificacao.objects.filter(usuario=self.usuario).latest("data_geracao")

        # Act
        resposta = self.redefinir(novo.codigo)

        # Assert
        self.assertRedirects(resposta, reverse("contas:login"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("senha-nova-456"))

    def test_senha_invalida_nao_consome_tentativa(self):
        # Act: senhas diferentes são recusadas antes de conferir o código
        self.client.post(reverse("contas:redefinir_senha"), {
            "codigo": codigo_errado(self.codigo.codigo), "nova1": "senha-nova-456",
            "nova2": "outra-senha-789"})

        # Assert
        self.codigo.refresh_from_db()
        self.assertEqual(self.codigo.tentativas_erradas, 0)
