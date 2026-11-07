"""Comando carregar_dados_demonstracao: base grande de colaboradores para o dashboard."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from auditoria.models import EmailEnviado
from contas.models import Departamento, Usuario
from core import services
from core.correio import enviar_notificacao_reciclagem
from treinamentos.models import Curso

SEED = {"email__endswith": "@exemplo.invalid"}


def rodar(*args):
    call_command("carregar_dados_demonstracao", *args, stdout=StringIO())


@override_settings(DEBUG=True)
class SeedDemonstracaoTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        with override_settings(DEBUG=True):
            rodar()

    def test_cria_60_colaboradores_com_as_quatro_situacoes(self):
        self.assertEqual(Usuario.objects.filter(**SEED).count(), 60)
        kpis = services.kpis_conformidade(services.matriz_conformidade())
        for situacao in ("em_dia", "vencendo", "vencido", "pendente"):
            with self.subTest(situacao=situacao):
                self.assertGreater(kpis[situacao], 0)

    def test_departamentos_tem_perfis_diferentes(self):
        por_dep = {d["departamento"]: d["percentual"] for d in
                   services.conformidade_por_departamento(services.matriz_conformidade())}
        self.assertGreaterEqual(por_dep["Vendas"], 90)     # acima da meta
        self.assertLess(por_dep["Sala Limpa"], 50)         # crítico

    def test_preenche_as_tres_faixas_de_vencimento(self):
        faixas = services.vencimentos_por_faixa(services.matriz_conformidade())
        self.assertTrue(all(f["quantidade"] > 0 for f in faixas))

    def test_rodar_de_novo_recria_sem_duplicar_e_com_os_mesmos_numeros(self):
        antes = services.indice_conformidade(services.matriz_conformidade())
        rodar()
        self.assertEqual(Usuario.objects.filter(**SEED).count(), 60)
        self.assertEqual(services.indice_conformidade(services.matriz_conformidade()), antes)

    def test_limpar_remove_so_a_seed(self):
        rodar("--limpar")
        self.assertFalse(Usuario.objects.filter(**SEED).exists())
        self.assertTrue(Usuario.objects.filter(email="ricardo.lima@nortex.com.br").exists())
        self.assertFalse(Departamento.objects.filter(nome__in=["Financeiro", "TI"]).exists())
        self.assertTrue(Curso.objects.filter(nome="LGPD - Proteção de Dados").exists())


class ProtecoesDaSeedTest(TestCase):

    @override_settings(DEBUG=False)
    def test_nao_roda_sem_debug_para_proteger_producao(self):
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            rodar()
        self.assertFalse(Usuario.objects.exists())

    def test_email_para_dominio_invalid_nao_sai_pelo_brevo(self):
        usuario = Usuario.objects.create_user(email="teste@exemplo.invalid", nome="Teste")
        curso = Curso.objects.create(nome="LGPD", categoria="X")

        with patch("core.correio.Brevo") as brevo:
            enviar_notificacao_reciclagem(usuario, curso)

        brevo.assert_not_called()
        registro = EmailEnviado.objects.get()
        self.assertFalse(registro.entregue)
        self.assertIn(".invalid", registro.erro)
