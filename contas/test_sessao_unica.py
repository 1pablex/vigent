"""Testes da sessão única por conta e da expiração por inatividade.

Cada Client faz o papel de um computador diferente. Views, middleware, sinal de
login e banco de teste são reais.
"""
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogSistema
from contas.middleware import SessaoUnicaMiddleware

Usuario = get_user_model()


class SessaoUnicaTest(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.pc_fabrica = Client()
        self.notebook = Client()
        self.inicio = reverse("treinamentos:inicio")

    def test_login_em_outro_computador_encerra_a_sessao_anterior(self):
        # Arrange
        self.pc_fabrica.force_login(self.usuario)

        # Act
        self.notebook.force_login(self.usuario)
        resposta = self.pc_fabrica.get(self.inicio)

        # Assert
        self.assertRedirects(resposta, reverse("contas:login"), fetch_redirect_response=False)
        self.assertIn(SessaoUnicaMiddleware.MENSAGEM,
                      [str(m) for m in get_messages(resposta.wsgi_request)])
        self.assertNotIn("_auth_user_id", self.pc_fabrica.session)
        self.assertTrue(LogSistema.objects.filter(
            evento="Sessão encerrada por novo login", usuario=self.usuario).exists())

    def test_ultimo_login_continua_valendo(self):
        # Arrange
        self.pc_fabrica.force_login(self.usuario)
        self.notebook.force_login(self.usuario)

        # Act
        resposta = self.notebook.get(self.inicio)

        # Assert
        self.assertEqual(resposta.status_code, 200)

    def test_aviso_aparece_na_tela_de_login(self):
        # Arrange
        self.pc_fabrica.force_login(self.usuario)
        self.notebook.force_login(self.usuario)

        # Act
        resposta = self.pc_fabrica.get(self.inicio, follow=True)

        # Assert
        self.assertContains(resposta, "acessada em outro dispositivo")

    def test_api_responde_401_em_json_para_a_sessao_encerrada(self):
        # Arrange
        self.usuario.grupo = Usuario.Grupo.RH
        self.usuario.save()
        self.pc_fabrica.force_login(self.usuario)
        self.notebook.force_login(self.usuario)

        # Act
        resposta = self.pc_fabrica.get(reverse("api:conformidade"))

        # Assert
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta.json()["detail"], SessaoUnicaMiddleware.MENSAGEM)

    def test_login_completo_com_2fa_tambem_encerra_a_sessao_anterior(self):
        # Arrange
        self.pc_fabrica.force_login(self.usuario)

        # Act: login real no notebook, com senha e código
        with patch("contas.views.enviar_codigo_verificacao"):
            self.notebook.post(reverse("contas:login"),
                               {"email": "ana@nortex.com.br", "senha": "senha-123"})
        codigo = self.usuario.codigos.latest("data_geracao").codigo
        self.notebook.post(reverse("contas:verificar_codigo"), {"codigo": codigo})

        # Assert
        self.assertEqual(self.notebook.get(self.inicio).status_code, 200)
        self.assertRedirects(self.pc_fabrica.get(self.inicio), reverse("contas:login"),
                             fetch_redirect_response=False)

    def test_trocar_a_senha_provisoria_nao_derruba_a_propria_sessao(self):
        # Arrange: a troca de senha gera uma chave de sessão nova
        self.usuario.senha_provisoria = True
        self.usuario.save()
        self.pc_fabrica.force_login(self.usuario)

        # Act
        self.pc_fabrica.post(reverse("contas:definir_senha"),
                             {"nova1": "senha-nova-456", "nova2": "senha-nova-456"})
        resposta = self.pc_fabrica.get(self.inicio)

        # Assert
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.senha_provisoria)
        self.assertEqual(resposta.status_code, 200)


class ExpiracaoDaSessaoTest(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.client.force_login(self.usuario)
        self.inicio = reverse("treinamentos:inicio")

    def test_configuracao_de_30_minutos_e_fim_ao_fechar_o_navegador(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 30 * 60)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_cookie_de_sessao_nao_fica_salvo_no_computador(self):
        # Act
        resposta = self.client.get(self.inicio)

        # Assert: sem data de expiração, o navegador apaga o cookie ao fechar
        cookie = resposta.cookies[settings.SESSION_COOKIE_NAME]
        self.assertFalse(cookie["expires"])
        self.assertFalse(cookie["max-age"])

    def test_cada_acesso_renova_o_prazo(self):
        # Arrange: sessão perto de expirar
        chave = self.client.session.session_key
        Session.objects.filter(session_key=chave).update(
            expire_date=timezone.now() + timedelta(minutes=1))

        # Act
        self.client.get(self.inicio)

        # Assert
        restante = Session.objects.get(session_key=chave).expire_date - timezone.now()
        self.assertGreater(restante, timedelta(minutes=29))

    def test_sessao_parada_ha_mais_de_30_minutos_exige_novo_login(self):
        # Arrange
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1))

        # Act
        resposta = self.client.get(self.inicio)

        # Assert
        self.assertRedirects(resposta, f"{reverse('contas:login')}?next={self.inicio}",
                             fetch_redirect_response=False)
