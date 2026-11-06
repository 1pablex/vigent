"""Testes da API de indicadores (/api/v1/) e da tela do dashboard do RH (RF-29, RF-30).

Cobrem o controle de acesso (anônimo, colaborador, RH com pendências), o contrato
JSON de cada endpoint, as regras RN-38 (índice), RN-39 (faixas de vencimento),
o histórico da avaliação de reação após reciclagem (RN-30) e o número de consultas.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Alternativa, AvaliacaoReacao, Prova, Questao
from certificacao.models import Certificado
from contas.models import Departamento
from core import services
from core.test_seguranca_endpoints import API_SOMENTE_RH
from treinamentos.models import Aula, Curso, CursoDepartamento, ProgressoAula

Usuario = get_user_model()

INDICADORES = ["api:conformidade", "api:conformidade_departamentos", "api:conformidade_cursos",
               "api:vencimentos", "api:reacao", "api:qualidade"]


def curso_publicado(nome, *departamentos):
    curso = Curso.objects.create(nome=nome, categoria="Compliance")
    Aula.objects.create(curso=curso, ordem=1, titulo="Aula 1")
    questao = Questao.objects.create(prova=Prova.objects.create(curso=curso), ordem=1,
                                     enunciado="Q1?")
    Alternativa.objects.create(questao=questao, letra="A", texto="Certa", correta=True)
    for dep in departamentos:
        CursoDepartamento.objects.create(curso=curso, departamento=dep)
    return curso


class CenarioIndicadores(TestCase):
    """Vendas: 2 colaboradores × 1 curso. Operações: 1 colaborador × 2 cursos."""

    def setUp(self):
        hoje = timezone.localdate()
        self.vendas = Departamento.objects.create(nome="Vendas")
        self.operacoes = Departamento.objects.create(nome="Operações")

        def usuario(email, dep=None, **extra):
            dados = {"senha_provisoria": False, "aceitou_termos": True, **extra}
            return Usuario.objects.create_user(email=email, nome=email.split("@")[0],
                                               password="senha-123", departamento=dep, **dados)

        self.rh = usuario("rh@nortex.com.br", grupo=Usuario.Grupo.RH)
        self.ana = usuario("ana@nortex.com.br", self.vendas)
        self.bia = usuario("bia@nortex.com.br", self.vendas)
        self.caio = usuario("caio@nortex.com.br", self.operacoes)
        self.desligado = usuario("ex@nortex.com.br", self.vendas, is_active=False)

        self.lgpd = curso_publicado("LGPD", self.vendas, self.operacoes)
        self.nr35 = curso_publicado("NR-35", self.operacoes)
        Curso.objects.create(nome="Rascunho", categoria="X")   # não publicado, fica fora

        def cert(usuario, curso, vence_em_dias):
            return Certificado.objects.create(
                usuario=usuario, curso=curso, nota_prova=8, versao_curso=1,
                data_emissao=hoje - timedelta(days=300),
                data_validade=hoje + timedelta(days=vence_em_dias))

        cert(self.ana, self.lgpd, 200)      # em dia
        cert(self.bia, self.lgpd, 10)       # vencendo (faixa 0-30)
        cert(self.caio, self.lgpd, -5)      # vencido
        # caio × NR-35 fica pendente
        cert(self.desligado, self.lgpd, 45)  # desligado: fora dos indicadores

        AvaliacaoReacao.objects.create(usuario=self.ana, curso=self.lgpd,
                                       nota_didatica=8, nota_entendimento=6)
        AvaliacaoReacao.objects.create(usuario=self.bia, curso=self.lgpd,
                                       nota_didatica=10, nota_entendimento=9)

    def get(self, rota):
        return self.client.get(reverse(rota), HTTP_ACCEPT="application/json")


class ControleDeAcessoApiTest(CenarioIndicadores):

    def test_anonimo_recebe_403_em_json_sem_redirecionar(self):
        for rota in API_SOMENTE_RH:
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))   # docs é HTML
                self.assertEqual(resposta.status_code, 403)
                self.assertNotIn("Location", resposta)

    def test_colaborador_recebe_403(self):
        self.client.force_login(self.ana)
        for rota in API_SOMENTE_RH:
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))   # docs é HTML
                self.assertEqual(resposta.status_code, 403)
                if rota in INDICADORES:
                    self.assertEqual(resposta.json(), {"detail": "Acesso restrito ao RH."})

    def test_rh_com_senha_provisoria_recebe_403_em_json(self):
        self.rh.senha_provisoria = True
        self.rh.save()
        self.client.force_login(self.rh)
        resposta = self.get("api:conformidade")
        self.assertEqual(resposta.status_code, 403)
        self.assertIn("senha", resposta.json()["detail"])

    def test_rh_sem_aceite_do_termo_recebe_403_em_json(self):
        self.rh.aceitou_termos = False
        self.rh.save()
        self.client.force_login(self.rh)
        resposta = self.get("api:conformidade")
        self.assertEqual(resposta.status_code, 403)
        self.assertIn("termo", resposta.json()["detail"])

    def test_endpoints_sao_somente_leitura(self):
        self.client.force_login(self.rh)
        for rota in INDICADORES:
            with self.subTest(rota=rota):
                self.assertEqual(self.client.post(reverse(rota)).status_code, 405)

    def test_rh_acessa_documentacao_openapi(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("api:schema")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:docs")).status_code, 200)


class ContratoDosIndicadoresTest(CenarioIndicadores):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.rh)

    def test_indice_geral_conta_em_dia_e_vencendo_como_conformes(self):
        # 4 pares: em dia, vencendo, vencido, pendente -> (1 + 1) / 4 = 50%
        self.assertEqual(self.get("api:conformidade").json(), {
            "percentual": 50, "meta": 90, "total": 4,
            "em_dia": 1, "vencendo": 1, "vencido": 1, "pendente": 1,
        })

    def test_conformidade_por_departamento_do_pior_para_o_melhor(self):
        self.assertEqual(self.get("api:conformidade_departamentos").json(), [
            {"departamento": "Operações", "percentual": 0, "total": 2, "conformes": 0},
            {"departamento": "Vendas", "percentual": 100, "total": 2, "conformes": 2},
        ])

    def test_conformidade_por_curso_mostra_o_gargalo_primeiro(self):
        self.assertEqual(self.get("api:conformidade_cursos").json(), [
            {"curso": "NR-35", "percentual": 0, "total": 1, "conformes": 0},
            {"curso": "LGPD", "percentual": 67, "total": 3, "conformes": 2},
        ])

    def test_vencimentos_por_faixa_ignoram_desligados_e_vencidos(self):
        faixas = self.get("api:vencimentos").json()
        self.assertEqual([(f["faixa"], f["quantidade"]) for f in faixas],
                         [("0 a 30 dias", 1), ("31 a 60 dias", 0), ("61 a 90 dias", 0)])

    def test_reacao_por_curso_separa_didatica_e_entendimento(self):
        self.assertEqual(self.get("api:reacao").json(), [
            {"curso": "LGPD", "media_didatica": 9.0, "media_entendimento": 7.5, "respostas": 2},
        ])

    def test_qualidade_percebida(self):
        self.assertEqual(self.get("api:qualidade").json(), {
            "taxa_conclusao": 75, "nota_media_prova": 8.0, "media_reacao": 8.2,
        })

    def test_matriz_usa_numero_fixo_de_consultas(self):
        # Antes da otimização eram várias consultas por par colaborador × curso.
        with self.assertNumQueries(4):
            services.matriz_conformidade()


class ReacaoHistoricaTest(CenarioIndicadores):
    """RN-30: a reciclagem arquiva a reação, sem tirá-la do indicador."""

    def test_reciclagem_mantem_reacao_no_indicador_e_exige_nova_resposta(self):
        services.reciclar(self.ana, self.lgpd)

        self.assertFalse(services.tem_reacao(self.ana, self.lgpd))
        self.client.force_login(self.rh)
        self.assertEqual(self.get("api:reacao").json()[0]["respostas"], 2)

    def test_reciclagem_e_atomica_e_nao_fica_pela_metade(self):
        # Se arquivar a reação falhar, o progresso já apagado precisa voltar.
        ProgressoAula.objects.create(usuario=self.ana, aula=self.lgpd.aulas.first(),
                                     concluida=True)
        with patch("core.services.AvaliacaoReacao.objects.filter",
                   side_effect=DatabaseError("falha simulada")):
            with self.assertRaises(DatabaseError):
                services.reciclar(self.ana, self.lgpd)

        self.assertTrue(ProgressoAula.objects.filter(usuario=self.ana).exists())

    def test_nova_reacao_do_novo_ciclo_soma_ao_historico(self):
        services.reciclar(self.ana, self.lgpd)
        AvaliacaoReacao.objects.create(usuario=self.ana, curso=self.lgpd,
                                       nota_didatica=9, nota_entendimento=9)

        self.assertTrue(services.tem_reacao(self.ana, self.lgpd))
        self.client.force_login(self.rh)
        self.assertEqual(self.get("api:reacao").json()[0]["respostas"], 3)


class TelaDashboardTest(CenarioIndicadores):

    def test_rh_abre_o_dashboard_com_os_endereços_da_api(self):
        self.client.force_login(self.rh)
        resposta = self.client.get(reverse("core:rh_dashboard"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, reverse("api:conformidade"))
        self.assertContains(resposta, 'id="dash-endpoints"')

    def test_aba_dashboard_substitui_atribuicoes(self):
        self.client.force_login(self.rh)
        resposta = self.client.get(reverse("core:rh_dashboard"))
        self.assertContains(resposta, ">Dashboard</a>")
        self.assertNotContains(resposta, "Atribuições")

    def test_colaborador_e_redirecionado(self):
        self.client.force_login(self.ana)
        self.assertRedirects(self.client.get(reverse("core:rh_dashboard")),
                             reverse("treinamentos:inicio"), fetch_redirect_response=False)
