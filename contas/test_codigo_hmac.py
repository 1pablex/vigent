"""Código de verificação guardado só como HMAC e credenciais mascaradas na auditoria.

Quem lê o banco não encontra o código 2FA nem a senha provisória em texto: nem na tabela
de códigos nem no registro dos e-mails enviados. O titular continua recebendo os valores
reais por e-mail. O envio pelo Brevo é substituído por mock.
"""
import importlib
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from auditoria.models import EmailEnviado
from contas.models import CodigoVerificacao
from core.correio import MASCARA, enviar_codigo_redefinicao, enviar_codigo_verificacao, enviar_primeiro_acesso
from core.services import gerar_codigo_verificacao

Usuario = get_user_model()


class CodigoGuardadoComoHmacTest(TestCase):

    def setUp(self):
        self.ana = Usuario.objects.create_user(email="ana@exemplo.invalid", nome="Ana", password="x")
        self.bia = Usuario.objects.create_user(email="bia@exemplo.invalid", nome="Bia", password="x")

    def test_banco_guarda_so_o_hmac(self):
        registro, codigo = gerar_codigo_verificacao(self.ana)

        registro.refresh_from_db()
        self.assertRegex(codigo, r"^\d{6}$")
        self.assertEqual(len(registro.codigo_hash), 64)
        self.assertNotIn(codigo, registro.codigo_hash)
        self.assertFalse(hasattr(registro, "codigo"))

    def test_confere_aceita_o_codigo_certo_e_recusa_os_demais(self):
        registro, codigo = gerar_codigo_verificacao(self.ana)

        self.assertTrue(registro.confere(codigo))
        self.assertFalse(registro.confere("000000" if codigo != "000000" else "111111"))
        self.assertFalse(registro.confere(""))
        self.assertFalse(registro.confere(None))

    def test_mesmo_codigo_gera_hash_diferente_para_cada_usuario(self):
        self.assertNotEqual(CodigoVerificacao.calcular_hash(self.ana.pk, "123456"),
                            CodigoVerificacao.calcular_hash(self.bia.pk, "123456"))

    def test_hash_depende_da_secret_key(self):
        hash_atual = CodigoVerificacao.calcular_hash(self.ana.pk, "123456")
        with override_settings(SECRET_KEY="outra-chave-que-o-atacante-nao-tem"):
            self.assertNotEqual(CodigoVerificacao.calcular_hash(self.ana.pk, "123456"), hash_atual)

    def test_login_completo_funciona_com_o_codigo_enviado(self):
        self.ana.set_password("senha-correta-123")
        self.ana.senha_provisoria = False
        self.ana.aceitou_termos = True
        self.ana.save()

        with patch("contas.views.enviar_codigo_verificacao") as enviar:
            self.client.post(reverse("contas:login"),
                             {"email": "ana@exemplo.invalid", "senha": "senha-correta-123"})
        resposta = self.client.post(reverse("contas:verificar_codigo"),
                                    {"codigo": enviar.call_args.args[1]})

        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)


class CredencialMascaradaNaAuditoriaTest(TestCase):

    def setUp(self):
        self.ana = Usuario.objects.create_user(email="ana@empresa.com.br", nome="Ana", password="x")

    def enviar(self, funcao, segredo):
        with patch("core.correio.Brevo") as brevo:
            registro = funcao(self.ana, segredo)
        enviado = brevo.return_value.transactional_emails.send_transac_email.call_args.kwargs
        return registro, enviado["html_content"]

    def test_codigo_de_verificacao(self):
        registro, html = self.enviar(enviar_codigo_verificacao, "482913")

        self.assertIn("482913", html)                       # o titular recebe o código
        self.assertNotIn("482913", registro.corpo)          # a auditoria não guarda
        self.assertIn(f"é: {MASCARA}", registro.corpo)

    def test_codigo_de_redefinicao(self):
        registro, html = self.enviar(enviar_codigo_redefinicao, "731045")

        self.assertIn("731045", html)
        self.assertNotIn("731045", registro.corpo)

    def test_senha_provisoria_do_primeiro_acesso(self):
        registro, html = self.enviar(enviar_primeiro_acesso, "Xy7kP2qLm9")

        self.assertIn("Xy7kP2qLm9", html)
        self.assertNotIn("Xy7kP2qLm9", EmailEnviado.objects.get(pk=registro.pk).corpo)
        self.assertIn(f"Senha provisória: {MASCARA}", registro.corpo)


class MigracaoMascaraRegistrosAntigosTest(TestCase):
    """A migração 0002 da auditoria mascara as credenciais gravadas antes da correção."""

    def test_mascara_credenciais_e_preserva_o_resto(self):
        migracao = importlib.import_module("auditoria.migrations.0002_mascara_credenciais_emails")
        antigos = [
            EmailEnviado.objects.create(
                tipo="Primeiro acesso", destinatario="a@exemplo.invalid", assunto="Credenciais",
                corpo="Matrícula: 0007\nSenha provisória: Ab12Cd34Ef\n\nAcesse o Vigent."),
            EmailEnviado.objects.create(
                tipo="Código de verificação", destinatario="a@exemplo.invalid", assunto="Código",
                corpo="Olá.\n\nSeu código de verificação é: 123456\n\nVálido por 5 minutos."),
            EmailEnviado.objects.create(
                tipo="Redefinição de senha", destinatario="a@exemplo.invalid", assunto="Senha",
                corpo="Seu código de redefinição é: 654321\n"),
            EmailEnviado.objects.create(
                tipo="Alerta de vencimento", destinatario="a@exemplo.invalid", assunto="Vence",
                corpo="Seu certificado vence em 30 dias, em 17/12/2026."),
        ]

        migracao.mascarar(apps, None)

        corpos = [EmailEnviado.objects.get(pk=e.pk).corpo for e in antigos]
        self.assertEqual(corpos[0], f"Matrícula: 0007\nSenha provisória: {MASCARA}\n\nAcesse o Vigent.")
        self.assertEqual(corpos[1], f"Olá.\n\nSeu código de verificação é: {MASCARA}\n\nVálido por 5 minutos.")
        self.assertEqual(corpos[2], f"Seu código de redefinição é: {MASCARA}\n")
        self.assertEqual(corpos[3], "Seu certificado vence em 30 dias, em 17/12/2026.")
