"""Testes unitários da situação do certificado (RN-13).

SimpleTestCase não abre conexão com o banco: qualquer consulta faria o teste falhar.
A data de "hoje" é fixada com mock para o resultado não depender do relógio.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from certificacao.models import Certificado

HOJE = date(2026, 10, 9)


def certificado_vencendo_em(dias):
    return Certificado(data_emissao=HOJE - timedelta(days=365),
                       data_validade=HOJE + timedelta(days=dias))


@patch("certificacao.models.timezone.localdate", return_value=HOJE)
class SituacaoCertificadoTest(SimpleTestCase):

    def test_deve_retornar_em_dia_quando_validade_esta_distante(self, _hoje):
        # Arrange
        certificado = certificado_vencendo_em(90)

        # Act
        situacao = certificado.situacao

        # Assert
        self.assertEqual(situacao, "EM DIA")
        self.assertEqual(certificado.dias_para_vencer, 90)

    def test_deve_retornar_vencido_quando_validade_ja_passou(self, _hoje):
        # Arrange
        certificado = certificado_vencendo_em(-10)

        # Act
        situacao = certificado.situacao

        # Assert
        self.assertEqual(situacao, "VENCIDO")

    def test_deve_classificar_corretamente_nas_fronteiras_de_30_e_0_dias(self, _hoje):
        # Arrange: (dias até o vencimento, situação esperada)
        casos = [
            (-1, "VENCIDO"),
            (0, "VENCENDO"),
            (30, "VENCENDO"),
            (31, "EM DIA"),
        ]
        for dias, esperada in casos:
            with self.subTest(dias=dias):
                # Act
                situacao = certificado_vencendo_em(dias).situacao

                # Assert
                self.assertEqual(situacao, esperada)
