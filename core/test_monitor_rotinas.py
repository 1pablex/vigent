"""Monitoramento das rotinas diárias (RN-35): aviso ao Healthchecks.io e alerta no painel.

Nenhum teste acessa a internet: o envio HTTP é substituído por mock.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, call, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import ExecucaoRotina, LogSistema
from core import monitor
from core.services import rotinas_atrasadas

Usuario = get_user_model()
URL = "https://hc-ping.com/00000000-0000-0000-0000-000000000000"


def resposta_ok():
    resposta = MagicMock(status=200)
    resposta.__enter__.return_value = resposta
    return resposta


class AvisoAoMonitorTest(TestCase):

    @override_settings(MONITOR_ROTINAS_URL="")
    def test_sem_endereco_nao_envia_nada(self):
        with patch("core.monitor.urllib.request.urlopen") as urlopen:
            self.assertFalse(monitor.avisar("sucesso"))
        urlopen.assert_not_called()

    @override_settings(MONITOR_ROTINAS_URL=URL)
    def test_endereco_de_cada_estado(self):
        with patch("core.monitor.urllib.request.urlopen", return_value=resposta_ok()) as urlopen:
            for estado in ("inicio", "sucesso", "falha"):
                self.assertTrue(monitor.avisar(estado, "resumo"))

        enderecos = [c.args[0].full_url for c in urlopen.call_args_list]
        self.assertEqual(enderecos, [URL + "/start", URL, URL + "/fail"])
        self.assertTrue(all(c.args[0].method == "POST" for c in urlopen.call_args_list))
        self.assertEqual(urlopen.call_args.args[0].data, b"resumo")

    @override_settings(MONITOR_ROTINAS_URL="http://hc-ping.com/sem-https")
    def test_recusa_endereco_sem_https(self):
        with patch("core.monitor.urllib.request.urlopen") as urlopen:
            self.assertFalse(monitor.avisar("sucesso"))
        urlopen.assert_not_called()
        self.assertTrue(LogSistema.objects.filter(evento__contains="monitor").exists())

    @override_settings(MONITOR_ROTINAS_URL=URL)
    def test_monitor_fora_do_ar_nao_derruba_a_rotina_e_nao_vaza_o_endereco(self):
        with patch("core.monitor.urllib.request.urlopen", side_effect=OSError("sem rede")):
            self.assertFalse(monitor.avisar("sucesso"))

        log = LogSistema.objects.get(evento="Falha ao avisar o monitor das rotinas")
        self.assertEqual(log.nivel, LogSistema.Nivel.WARN)
        self.assertNotIn("hc-ping.com", log.detalhe)


class ComandoRodarRotinasTest(TestCase):

    def rodar(self):
        call_command("rodar_rotinas", stdout=StringIO())

    def test_roda_as_duas_rotinas_e_avisa_inicio_e_sucesso(self):
        with patch("core.monitor.avisar") as avisar:
            self.rodar()

        self.assertEqual([c.args[0] for c in avisar.call_args_list], ["inicio", "sucesso"])
        self.assertIn("expurgar_reidentificacoes", avisar.call_args.args[1])
        self.assertEqual(
            sorted(ExecucaoRotina.objects.values_list("rotina", flat=True)),
            ["expurgar_reidentificacoes", "verificar_vencimentos"])

    def test_falha_no_expurgo_avisa_falha_e_termina_com_erro(self):
        with patch("core.monitor.avisar") as avisar, \
             patch("core.management.commands.expurgar_reidentificacoes.expurgar_reidentificacoes",
                   side_effect=RuntimeError("banco indisponível")):
            with self.assertRaises(CommandError):
                self.rodar()

        self.assertEqual(avisar.call_args_list[-1].args[0], "falha")
        self.assertIn("expurgar_reidentificacoes", avisar.call_args_list[-1].args[1])
        # a outra rotina rodou mesmo assim
        self.assertTrue(ExecucaoRotina.objects.filter(rotina="verificar_vencimentos",
                                                      sucesso=True).exists())

    def test_erro_inesperado_numa_rotina_nao_impede_a_outra(self):
        with patch("core.monitor.avisar") as avisar, \
             patch("core.management.commands.verificar_vencimentos.certificados_monitorados",
                   side_effect=RuntimeError("falha inesperada")):
            with self.assertRaises(CommandError):
                self.rodar()

        self.assertEqual(avisar.call_args_list[0], call("inicio"))
        self.assertEqual(avisar.call_args_list[-1].args[0], "falha")
        self.assertTrue(ExecucaoRotina.objects.filter(rotina="expurgar_reidentificacoes").exists())


class RotinasAtrasadasTest(TestCase):

    def execucao(self, rotina, horas_atras, sucesso=True):
        e = ExecucaoRotina.objects.create(rotina=rotina, sucesso=sucesso)
        ExecucaoRotina.objects.filter(pk=e.pk).update(
            data_hora=timezone.now() - timedelta(hours=horas_atras))

    def test_nunca_executadas_aparecem_como_atrasadas(self):
        self.assertEqual([r for r, _ in rotinas_atrasadas()],
                         ["verificar_vencimentos", "expurgar_reidentificacoes"])

    def test_execucoes_recentes_nao_geram_alerta(self):
        self.execucao("verificar_vencimentos", 3)
        self.execucao("expurgar_reidentificacoes", 3)
        self.assertEqual(rotinas_atrasadas(), [])

    def test_execucao_mais_antiga_que_26_horas_gera_alerta(self):
        self.execucao("verificar_vencimentos", 3)
        self.execucao("expurgar_reidentificacoes", 27)
        self.assertEqual([r for r, _ in rotinas_atrasadas()], ["expurgar_reidentificacoes"])

    def test_execucao_com_falha_nao_conta_como_feita(self):
        self.execucao("verificar_vencimentos", 3)
        self.execucao("expurgar_reidentificacoes", 3, sucesso=False)
        self.assertEqual([r for r, _ in rotinas_atrasadas()], ["expurgar_reidentificacoes"])


class AlertaNoPainelTest(TestCase):

    def setUp(self):
        rh = Usuario.objects.create_user(
            email="rh@exemplo.invalid", nome="RH Teste", password="x",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True)
        self.client.force_login(rh)

    def test_painel_mostra_alerta_quando_rotina_esta_atrasada(self):
        resposta = self.client.get(reverse("core:rh_conformidade"))
        self.assertContains(resposta, "Rotinas diárias atrasadas.")
        self.assertContains(resposta, "Expurgo do cofre de reidentificação")

    def test_painel_sem_alerta_depois_de_rodar_as_rotinas(self):
        with patch("core.monitor.avisar"):
            call_command("rodar_rotinas", stdout=StringIO())
        resposta = self.client.get(reverse("core:rh_conformidade"))
        self.assertNotContains(resposta, "Rotinas diárias atrasadas.")
