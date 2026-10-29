"""Testes de integração das telas de certificado do colaborador.

Views e banco de teste reais; nada é mockado.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from certificacao.models import Certificado
from treinamentos.models import Curso

Usuario = get_user_model()


class CertificadoIntegracaoTest(TestCase):

    def setUp(self):
        self.ana = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.bruno = Usuario.objects.create_user(
            email="bruno@nortex.com.br", nome="Bruno Colaborador", password="senha-123",
            senha_provisoria=False, aceitou_termos=True,
        )
        self.certificado_ana = Certificado.objects.create(
            usuario=self.ana, curso=Curso.objects.create(nome="LGPD na Prática"),
            nota_prova=9, versao_curso=1,
            data_emissao=date(2026, 1, 10), data_validade=date(2027, 1, 10))
        self.certificado_bruno = Certificado.objects.create(
            usuario=self.bruno, curso=Curso.objects.create(nome="NR-10"),
            nota_prova=8, versao_curso=1,
            data_emissao=date(2026, 2, 1), data_validade=date(2027, 2, 1))

    def test_deve_redirecionar_para_login_quando_nao_autenticado(self):
        # Act
        resposta = self.client.get(reverse("certificacao:meus"))

        # Assert
        self.assertRedirects(resposta,
                             f"{reverse('contas:login')}?next={reverse('certificacao:meus')}")

    def test_deve_listar_somente_certificados_do_proprio_usuario(self):
        # Arrange
        self.client.force_login(self.ana)

        # Act
        resposta = self.client.get(reverse("certificacao:meus"))

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["certificados"]), [self.certificado_ana])
        self.assertContains(resposta, "LGPD na Prática")
        self.assertNotContains(resposta, "NR-10")

    def test_deve_exibir_certificado_proprio(self):
        # Arrange
        self.client.force_login(self.ana)

        # Act
        resposta = self.client.get(reverse("certificacao:ver", args=[self.certificado_ana.id]))

        # Assert
        self.assertContains(resposta, "Ana Colaboradora")
        self.assertContains(resposta, "LGPD na Prática")

    def test_deve_retornar_404_ao_abrir_certificado_de_outro_usuario(self):
        # Arrange
        self.client.force_login(self.ana)

        # Act
        resposta = self.client.get(reverse("certificacao:ver", args=[self.certificado_bruno.id]))

        # Assert
        self.assertEqual(resposta.status_code, 404)
