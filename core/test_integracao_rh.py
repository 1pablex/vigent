"""Testes de integração do painel do RH (RF-11, RF-12, RN-19).

Views, services e banco de teste são reais. Só o envio de e-mail pelo Brevo é
substituído por mock, para nenhum teste chamar a API externa.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import ExecucaoRotina, LogSistema
from avaliacoes.models import Alternativa, AvaliacaoReacao, Prova, Questao
from contas.models import Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, ProgressoAula

Usuario = get_user_model()


class PainelRhIntegracaoTest(TestCase):

    def setUp(self):
        self.departamento = Departamento.objects.create(nome="Vendas")
        self.rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="Rita RH", password="senha-123",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True,
        )
        self.colaborador = Usuario.objects.create_user(
            email="maria@nortex.com.br", nome="Maria Souza", password="senha-123",
            departamento=self.departamento, senha_provisoria=False, aceitou_termos=True,
        )
        Usuario.objects.create_user(
            email="joao@nortex.com.br", nome="João Lima", password="senha-123",
            departamento=self.departamento, senha_provisoria=False, aceitou_termos=True,
        )
        self.curso = Curso.objects.create(nome="LGPD na Prática", categoria="Compliance")
        CursoDepartamento.objects.create(curso=self.curso, departamento=self.departamento)
        self.aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")
        questao = Questao.objects.create(prova=Prova.objects.create(curso=self.curso),
                                         ordem=1, enunciado="Q1?")
        Alternativa.objects.create(questao=questao, letra="A", texto="Certa", correta=True)

        self.client.force_login(self.rh)

    def test_colaborador_nao_acessa_painel_do_rh(self):
        # Arrange
        self.client.force_login(self.colaborador)

        # Act
        resposta = self.client.get(reverse("core:rh_colaboradores"))

        # Assert
        self.assertRedirects(resposta, reverse("treinamentos:inicio"))

    def test_deve_filtrar_colaboradores_pela_busca(self):
        # Act
        resposta = self.client.get(reverse("core:rh_colaboradores"), {"busca": "maria"})

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["colaboradores"]), [self.colaborador])
        self.assertContains(resposta, "Maria Souza")
        self.assertNotContains(resposta, "João Lima")

    def test_deve_filtrar_auditoria_por_nivel(self):
        # Arrange
        LogSistema.objects.create(nivel=LogSistema.Nivel.WARN, evento="Evento de alerta")
        LogSistema.objects.create(nivel=LogSistema.Nivel.INFO, evento="Evento informativo")

        # Act
        resposta = self.client.get(reverse("core:rh_auditoria"), {"nivel": "WARN"})

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Evento de alerta")
        self.assertNotContains(resposta, "Evento informativo")
        self.assertEqual(resposta.context["total_warn"], 1)

    def test_deve_calcular_conformidade_dos_colaboradores(self):
        # Act
        resposta = self.client.get(reverse("core:rh_conformidade"))

        # Assert: 2 colaboradores de Vendas, nenhum certificado emitido (RN-14)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["kpis"],
                         {"em_dia": 0, "vencendo": 0, "vencido": 0, "pendente": 2})
        self.assertContains(resposta, "Maria Souza")

    def test_deve_executar_rotinas_de_vencimento_e_expurgo(self):
        # Act
        resposta = self.client.post(reverse("core:rh_conformidade"), {"rodar_rotina": "1"})

        # Assert
        self.assertRedirects(resposta, reverse("core:rh_conformidade"))
        self.assertTrue(ExecucaoRotina.objects.exists())

    @patch("core.views.enviar_notificacao_reciclagem")
    def test_deve_reiniciar_treinamento_e_notificar_colaborador(self, enviar_notificacao):
        # Arrange
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula, concluida=True)
        AvaliacaoReacao.objects.create(usuario=self.colaborador, curso=self.curso,
                                       nota_didatica=8, nota_entendimento=8)

        # Act
        resposta = self.client.post(
            reverse("core:rh_reciclagem", args=[self.colaborador.id, self.curso.id]))

        # Assert (RN-19)
        self.assertRedirects(resposta, reverse("core:rh_conformidade"))
        self.assertFalse(ProgressoAula.objects.filter(usuario=self.colaborador).exists())
        self.assertFalse(AvaliacaoReacao.objects.filter(usuario=self.colaborador).exists())
        enviar_notificacao.assert_called_once_with(self.colaborador, self.curso)
        self.assertTrue(LogSistema.objects.filter(
            evento="Reciclagem solicitada pelo RH", usuario=self.rh).exists())

    @patch("core.views.enviar_notificacao_reciclagem")
    def test_reciclagem_via_get_nao_altera_dados(self, enviar_notificacao):
        # Arrange
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula, concluida=True)

        # Act
        resposta = self.client.get(
            reverse("core:rh_reciclagem", args=[self.colaborador.id, self.curso.id]))

        # Assert
        self.assertRedirects(resposta, reverse("core:rh_conformidade"))
        self.assertTrue(ProgressoAula.objects.filter(usuario=self.colaborador).exists())
        enviar_notificacao.assert_not_called()
