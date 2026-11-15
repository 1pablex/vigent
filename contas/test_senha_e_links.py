"""RN-28 (senha mínima de 8 caracteres) e link do site nos e-mails de acesso.

O envio pelo Brevo é substituído por mock: o teste lê o corpo que seria enviado.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from auditoria.models import EmailEnviado
from contas.models import CodigoVerificacao
from core.correio import _html, enviar_primeiro_acesso

Usuario = get_user_model()
SITE = "https://vigent.exemplo.invalid"


class SenhaMinimaPrimeiroAcessoTest(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="novo@nortex.com.br", nome="Novo Colaborador", password="Provisoria@2026",
            senha_provisoria=True)
        self.client.force_login(self.usuario)

    def definir(self, senha):
        return self.client.post(reverse("contas:definir_senha"), {"nova1": senha, "nova2": senha})

    def test_recusa_senha_com_7_caracteres(self):
        resposta = self.definir("abc1234")
        self.assertContains(resposta, "A senha deve ter ao menos 8 caracteres.")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.senha_provisoria)

    def test_aceita_senha_com_8_caracteres(self):
        self.definir("abc12345")
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.senha_provisoria)
        self.assertTrue(self.usuario.check_password("abc12345"))

    def test_tela_informa_o_minimo(self):
        resposta = self.client.get(reverse("contas:definir_senha"))
        self.assertContains(resposta, 'minlength="8"', count=2)
        self.assertContains(resposta, "mínimo de 8 caracteres")


class SenhaMinimaRedefinicaoTest(TestCase):

    def setUp(self):
        patch("contas.views.enviar_codigo_redefinicao").start()
        self.addCleanup(patch.stopall)
        self.usuario = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-antiga-123",
            senha_provisoria=False, aceitou_termos=True)
        self.client.post(reverse("contas:esqueci_senha"), {"email": "ana@nortex.com.br"})
        self.codigo = CodigoVerificacao.objects.get(usuario=self.usuario).codigo

    def redefinir(self, senha):
        return self.client.post(reverse("contas:redefinir_senha"),
                                {"codigo": self.codigo, "nova1": senha, "nova2": senha})

    def test_recusa_senha_com_7_caracteres(self):
        resposta = self.redefinir("abc1234")
        self.assertContains(resposta, "A senha deve ter ao menos 8 caracteres.")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("senha-antiga-123"))

    def test_aceita_senha_com_8_caracteres(self):
        self.assertRedirects(self.redefinir("abc12345"), reverse("contas:login"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("abc12345"))


@override_settings(SITE_URL=SITE)
class LinkDoSiteNosEmailsTest(TestCase):
    """O e-mail para .invalid é só registrado: o corpo gravado é o que seria enviado."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="link@exemplo.invalid", nome="Teste Link", password="qualquer-123")

    def test_primeiro_acesso_traz_o_link_de_login(self):
        enviar_primeiro_acesso(self.usuario, "Provisoria@2026")
        corpo = EmailEnviado.objects.get(tipo="Primeiro acesso").corpo
        self.assertIn(f"Acesse o Vigent em: {SITE}{reverse('contas:login')}", corpo)


class HtmlDoEmailTest(TestCase):

    def test_endereco_vira_link_clicavel(self):
        html = _html(f"Acesse o Vigent em: {SITE}/conta/entrar/")
        self.assertIn(f'<a href="{SITE}/conta/entrar/">{SITE}/conta/entrar/</a>', html)

    def test_tags_no_texto_nao_viram_html(self):
        html = _html("Olá, <script>alert(1)</script> Ana")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
