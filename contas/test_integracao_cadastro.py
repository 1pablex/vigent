"""Testes de integração do cadastro de colaborador e do aceite do termo de uso.

Views, middleware e banco de teste são reais. Só o envio de e-mail pelo Brevo é
substituído por mock, para nenhum teste chamar a API externa.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import LogSistema
from contas.models import Departamento

Usuario = get_user_model()


class CadastroColaboradorIntegracaoTest(TestCase):

    def setUp(self):
        self.enviar_primeiro_acesso = patch("contas.views.enviar_primeiro_acesso").start()
        self.addCleanup(patch.stopall)
        self.departamento = Departamento.objects.create(nome="Vendas")
        self.rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="Rita RH", password="senha-123",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True,
        )
        self.dados = {"nome": "Carlos Pereira", "email": "  Carlos@Nortex.com.br ",
                      "cargo": "Vendedor", "departamento": self.departamento.id}

    def test_deve_cadastrar_colaborador_com_senha_provisoria(self):
        # Arrange
        self.client.force_login(self.rh)

        # Act
        resposta = self.client.post(reverse("contas:cadastrar"), self.dados)

        # Assert (RN-15, RN-32)
        self.assertRedirects(resposta, reverse("core:rh_colaboradores"))
        novo = Usuario.objects.get(email="carlos@nortex.com.br")
        self.assertTrue(novo.matricula)
        self.assertTrue(novo.senha_provisoria)
        self.assertEqual(novo.departamento, self.departamento)
        self.assertEqual(novo.grupo, Usuario.Grupo.COLABORADOR)
        self.enviar_primeiro_acesso.assert_called_once()
        self.assertEqual(self.enviar_primeiro_acesso.call_args.args[0], novo)
        self.assertTrue(LogSistema.objects.filter(evento="Colaborador cadastrado").exists())

    def test_deve_recusar_email_ja_cadastrado(self):
        # Arrange
        self.client.force_login(self.rh)
        self.dados["email"] = "RH@nortex.com.br"

        # Act
        resposta = self.client.post(reverse("contas:cadastrar"), self.dados)

        # Assert
        self.assertContains(resposta, "Já existe conta com este endereço.")
        self.assertEqual(Usuario.objects.count(), 1)
        self.enviar_primeiro_acesso.assert_not_called()

    def test_colaborador_nao_pode_cadastrar(self):
        # Arrange
        colaborador = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.client.force_login(colaborador)

        # Act
        resposta = self.client.post(reverse("contas:cadastrar"), self.dados)

        # Assert
        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)
        self.assertFalse(Usuario.objects.filter(email="carlos@nortex.com.br").exists())
        self.enviar_primeiro_acesso.assert_not_called()


class AceiteTermoIntegracaoTest(TestCase):

    def setUp(self):
        self.colaborador = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            senha_provisoria=False, aceitou_termos=False,
        )
        self.client.force_login(self.colaborador)

    def test_middleware_bloqueia_acesso_sem_aceite_do_termo(self):
        # Act
        resposta = self.client.get(reverse("treinamentos:inicio"))

        # Assert
        self.assertRedirects(resposta, reverse("contas:aceitar_termo"))

    def test_deve_exigir_marcacao_da_caixa_de_aceite(self):
        # Act
        resposta = self.client.post(reverse("contas:aceitar_termo"), {})

        # Assert
        self.assertContains(resposta, "É necessário marcar a caixa de aceite para continuar.")
        self.colaborador.refresh_from_db()
        self.assertFalse(self.colaborador.aceitou_termos)

    def test_deve_registrar_aceite_e_liberar_o_sistema(self):
        # Act
        resposta = self.client.post(reverse("contas:aceitar_termo"), {"aceito": "on"})

        # Assert
        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)
        self.colaborador.refresh_from_db()
        self.assertTrue(self.colaborador.aceitou_termos)
        self.assertIsNotNone(self.colaborador.data_aceite_termos)
        self.assertTrue(LogSistema.objects.filter(evento="Termo de uso aceito").exists())
