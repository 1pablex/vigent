"""Testes unitários das regras de negócio de core/services.py.

Rodam em SimpleTestCase (sem banco): as dependências de persistência e de log
são substituídas por mocks, e os dados de entrada são objetos em memória.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core import services
from treinamentos.models import Curso

HOJE = date(2026, 10, 9)


@patch("core.services.registrar")
@patch("core.services.timezone.localdate", return_value=HOJE)
@patch("core.services.Certificado")
@patch("core.services.tem_reacao", return_value=True)
class EmitirCertificadoTest(SimpleTestCase):
    """RN-08 (reação + nota mínima) e RN-21 (versão do curso gravada no certificado)."""

    def setUp(self):
        self.usuario = MagicMock(name="usuario")
        self.curso = Curso(nome="NR-35 Trabalho em Altura", nota_minima=Decimal("7.0"),
                           validade_meses=12, versao=2)

    def _create_devolve_os_dados(self, certificado_mock):
        certificado_mock.objects.create.side_effect = lambda **dados: SimpleNamespace(**dados)

    def test_deve_emitir_certificado_com_versao_e_validade_quando_aprovado(
            self, _tem_reacao, certificado_mock, _hoje, registrar_mock):
        # Arrange
        self._create_devolve_os_dados(certificado_mock)

        # Act
        cert = services.emitir_certificado(self.usuario, self.curso, nota=9)

        # Assert
        certificado_mock.objects.create.assert_called_once_with(
            usuario=self.usuario, curso=self.curso, nota_prova=9, versao_curso=2,
            data_emissao=HOJE, data_validade=date(2027, 10, 9),
        )
        self.assertEqual(cert.data_validade, date(2027, 10, 9))
        registrar_mock.assert_called_once()

    def test_deve_lancar_excecao_quando_nao_ha_avaliacao_de_reacao(
            self, tem_reacao_mock, certificado_mock, _hoje, registrar_mock):
        # Arrange
        tem_reacao_mock.return_value = False

        # Act / Assert
        with self.assertRaisesMessage(ValueError, "exige avaliação de reação registrada"):
            services.emitir_certificado(self.usuario, self.curso, nota=10)
        certificado_mock.objects.create.assert_not_called()
        registrar_mock.assert_not_called()

    def test_deve_lancar_excecao_quando_nota_abaixo_da_minima(
            self, _tem_reacao, certificado_mock, _hoje, _registrar):
        # Act / Assert
        with self.assertRaisesMessage(ValueError, "Nota inferior à mínima exigida"):
            services.emitir_certificado(self.usuario, self.curso, nota=Decimal("6.9"))
        certificado_mock.objects.create.assert_not_called()

    def test_deve_emitir_certificado_quando_nota_igual_a_minima(
            self, _tem_reacao, certificado_mock, _hoje, _registrar):
        # Arrange
        self._create_devolve_os_dados(certificado_mock)

        # Act
        cert = services.emitir_certificado(self.usuario, self.curso, nota=Decimal("7.0"))

        # Assert
        self.assertEqual(cert.nota_prova, Decimal("7.0"))
        certificado_mock.objects.create.assert_called_once()


def linhas_do_departamento(nome, total, em_dia):
    """Monta linhas da matriz de conformidade (RF-11) em memória."""
    departamento = SimpleNamespace(nome=nome) if nome else None
    usuario = SimpleNamespace(departamento=departamento)
    return [{"usuario": usuario, "situacao": "EM DIA" if i < em_dia else "VENCIDO"}
            for i in range(total)]


class ConformidadePorDepartamentoTest(SimpleTestCase):
    """RF-12: percentual em dia por departamento, com faixa de cor do painel do RH."""

    def test_deve_calcular_percentual_e_ordenar_do_pior_para_o_melhor(self):
        # Arrange
        linhas = (linhas_do_departamento("Vendas", total=4, em_dia=4)
                  + linhas_do_departamento("Operações", total=4, em_dia=1))

        # Act
        resultado = services.conformidade_por_departamento(linhas)

        # Assert
        self.assertEqual(resultado, [
            {"departamento": "Operações", "percentual": 25, "cor": "var(--red)"},
            {"departamento": "Vendas", "percentual": 100, "cor": "var(--green)"},
        ])

    def test_deve_agrupar_colaborador_sem_departamento_em_grupo_proprio(self):
        # Arrange
        linhas = linhas_do_departamento(None, total=2, em_dia=1)

        # Act
        resultado = services.conformidade_por_departamento(linhas)

        # Assert
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["departamento"], "Sem departamento")
        self.assertEqual(resultado[0]["percentual"], 50)

    def test_deve_trocar_a_cor_exatamente_nas_fronteiras_de_90_e_50_por_cento(self):
        # Arrange: (colaboradores em dia de 100, cor esperada)
        casos = [
            (90, "var(--green)"),
            (89, "var(--amber)"),
            (50, "var(--amber)"),
            (49, "var(--red)"),
        ]
        for em_dia, cor in casos:
            with self.subTest(percentual=em_dia):
                linhas = linhas_do_departamento("Vendas", total=100, em_dia=em_dia)

                # Act
                resultado = services.conformidade_por_departamento(linhas)

                # Assert
                self.assertEqual(resultado[0]["percentual"], em_dia)
                self.assertEqual(resultado[0]["cor"], cor)

    def test_deve_retornar_lista_vazia_e_kpis_zerados_quando_nao_ha_linhas(self):
        # Act
        departamentos = services.conformidade_por_departamento([])
        kpis = services.kpis_conformidade([])

        # Assert
        self.assertEqual(departamentos, [])
        self.assertEqual(kpis, {"em_dia": 0, "vencendo": 0, "vencido": 0, "pendente": 0})
