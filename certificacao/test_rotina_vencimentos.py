"""Testes unitários da rotina verificar_vencimentos (RF-10, RN-11, RN-12).

Banco, envio de e-mail (Brevo) e log de auditoria são mocks: o teste verifica
apenas a decisão da rotina de notificar ou não cada certificado.
"""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from auditoria.models import LogSistema
from core.management.commands.verificar_vencimentos import Command

MODULO = "core.management.commands.verificar_vencimentos"


def certificado(dias):
    return SimpleNamespace(
        usuario=SimpleNamespace(email="colab@nortex.com.br"),
        curso=SimpleNamespace(nome="LGPD"),
        dias_para_vencer=dias,
    )


@patch(f"{MODULO}.registrar")
@patch(f"{MODULO}.ExecucaoRotina")
@patch(f"{MODULO}.enviar_alerta_vencimento")
@patch(f"{MODULO}.NotificacaoEnviada")
@patch(f"{MODULO}.Certificado")
class VerificarVencimentosTest(SimpleTestCase):

    def _rodar(self, certificado_mock, notificacao_mock, certificados, ja_notificado=False):
        certificado_mock.objects.select_related.return_value = certificados
        notificacao_mock.objects.filter.return_value.exists.return_value = ja_notificado
        Command(stdout=StringIO()).handle()

    def test_deve_enviar_alerta_quando_certificado_atinge_marco_de_30_dias(
            self, certificado_mock, notificacao_mock, enviar_mock, execucao_mock, _registrar):
        # Arrange
        cert = certificado(30)

        # Act
        self._rodar(certificado_mock, notificacao_mock, [cert])

        # Assert
        enviar_mock.assert_called_once_with(cert.usuario, cert, 30)
        notificacao_mock.objects.create.assert_called_once_with(certificado=cert, marco_dias=30)
        execucao = execucao_mock.objects.create.call_args.kwargs
        self.assertEqual((execucao["notificados"], execucao["sucesso"]), (1, True))

    def test_nao_deve_reenviar_alerta_quando_marco_ja_foi_notificado(
            self, certificado_mock, notificacao_mock, enviar_mock, execucao_mock, _registrar):
        # Act
        self._rodar(certificado_mock, notificacao_mock, [certificado(15)], ja_notificado=True)

        # Assert
        enviar_mock.assert_not_called()
        notificacao_mock.objects.create.assert_not_called()
        self.assertEqual(execucao_mock.objects.create.call_args.kwargs["ignorados"], 1)

    def test_nao_deve_notificar_certificado_vencido_nem_fora_dos_marcos(
            self, certificado_mock, notificacao_mock, enviar_mock, execucao_mock, _registrar):
        # Arrange: vencido ontem (RN-12) e a um dia de distância do marco de 30
        certificados = [certificado(-1), certificado(29), certificado(31)]

        # Act
        self._rodar(certificado_mock, notificacao_mock, certificados)

        # Assert
        enviar_mock.assert_not_called()
        execucao = execucao_mock.objects.create.call_args.kwargs
        self.assertEqual((execucao["avaliados"], execucao["notificados"]), (3, 0))

    def test_deve_registrar_falha_quando_envio_do_email_lanca_excecao(
            self, certificado_mock, notificacao_mock, enviar_mock, execucao_mock, registrar_mock):
        # Arrange
        enviar_mock.side_effect = RuntimeError("Brevo indisponível")

        # Act
        self._rodar(certificado_mock, notificacao_mock, [certificado(7)])

        # Assert
        notificacao_mock.objects.create.assert_not_called()
        self.assertFalse(execucao_mock.objects.create.call_args.kwargs["sucesso"])
        nivel, evento, detalhe = registrar_mock.call_args.args
        self.assertEqual(nivel, LogSistema.Nivel.ERRO)
        self.assertEqual(evento, "Falha ao notificar vencimento")
        self.assertIn("Brevo indisponível", detalhe)
