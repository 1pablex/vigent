"""Testes de integração: views (HTTP) + services + banco de teste.

Cada teste monta o próprio cenário no setUp; o Django cria um banco de teste
descartável e o destrói ao final, sem tocar no banco de desenvolvimento.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from avaliacoes.models import Alternativa, AvaliacaoReacao, Prova, Questao
from certificacao.models import Certificado
from contas.models import Departamento
from core import services
from treinamentos.models import Aula, Curso, CursoDepartamento, ProgressoAula

Usuario = get_user_model()


class FluxoTreinamentoIntegracaoTest(TestCase):

    def setUp(self):
        self.departamento = Departamento.objects.create(nome="Vendas")
        self.colaborador = Usuario.objects.create_user(
            email="colab@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            departamento=self.departamento, senha_provisoria=False, aceitou_termos=True,
        )
        self.curso = Curso.objects.create(
            nome="LGPD na Prática", categoria="Compliance",
            nota_minima=7, max_tentativas=3, validade_meses=12,
        )
        CursoDepartamento.objects.create(curso=self.curso, departamento=self.departamento)
        self.aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")

        prova = Prova.objects.create(curso=self.curso)
        self.respostas_certas = {}
        for ordem in (1, 2):
            questao = Questao.objects.create(prova=prova, ordem=ordem, enunciado=f"Q{ordem}?")
            certa = Alternativa.objects.create(questao=questao, letra="A", texto="Certa",
                                               correta=True)
            Alternativa.objects.create(questao=questao, letra="B", texto="Errada")
            self.respostas_certas[f"q{questao.id}"] = str(certa.id)

        self.client.force_login(self.colaborador)

    def test_deve_listar_curso_do_departamento_como_nao_iniciado(self):
        # Act
        resposta = self.client.get(reverse("treinamentos:inicio"))

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "LGPD na Prática")
        self.assertContains(resposta, "NÃO INICIADO")

    def test_deve_retornar_404_ao_abrir_curso_inexistente(self):
        # Act
        resposta = self.client.get(reverse("treinamentos:abrir", args=[999999]))

        # Assert
        self.assertContains(resposta, "Not Found", status_code=404)
        self.assertFalse(self.colaborador.presencas.exists())

    def test_deve_persistir_certificados_e_recuperar_o_mais_recente(self):
        # Arrange
        Certificado.objects.create(
            usuario=self.colaborador, curso=self.curso, nota_prova=8, versao_curso=1,
            data_emissao=date(2024, 1, 10), data_validade=date(2025, 1, 10))
        recente = Certificado.objects.create(
            usuario=self.colaborador, curso=self.curso, nota_prova=9.5, versao_curso=2,
            data_emissao=date(2025, 2, 1), data_validade=date(2026, 2, 1))

        # Act
        vigente = services.certificado_vigente(self.colaborador, self.curso)

        # Assert
        self.assertEqual(vigente.pk, recente.pk)
        self.assertEqual(vigente.versao_curso, 2)
        self.assertEqual(Certificado.objects.filter(usuario=self.colaborador).count(), 2)

    def test_deve_emitir_certificado_ao_aprovar_na_prova_e_exibir_em_dia(self):
        # Arrange: conteúdo concluído e avaliação de reação respondida (RN-06/RN-23)
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula, concluida=True)
        AvaliacaoReacao.objects.create(usuario=self.colaborador, curso=self.curso,
                                       nota_didatica=9, nota_entendimento=8)

        # Act
        resposta = self.client.post(
            reverse("avaliacoes:prova", args=[self.curso.id]), self.respostas_certas)
        lista = self.client.get(reverse("treinamentos:inicio"))

        # Assert
        self.assertContains(resposta, "Aprovado")
        certificado = Certificado.objects.get(usuario=self.colaborador, curso=self.curso)
        self.assertEqual(certificado.nota_prova, 10)
        self.assertEqual(certificado.situacao, "EM DIA")
        self.assertContains(resposta, f"válido até {certificado.data_validade:%d/%m/%Y}")
        self.assertContains(lista, "EM DIA")


class ReciclagemRhIntegracaoTest(TestCase):

    def test_deve_retornar_404_ao_solicitar_reciclagem_de_colaborador_inexistente(self):
        # Arrange
        rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="Rita RH", password="senha-123",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True,
        )
        curso = Curso.objects.create(nome="NR-10", categoria="Segurança")
        self.client.force_login(rh)

        # Act
        resposta = self.client.post(reverse("core:rh_reciclagem", args=[999999, curso.id]))

        # Assert
        self.assertContains(resposta, "Not Found", status_code=404)
