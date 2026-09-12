"""Testes das regras de negócio implementadas em services.py."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from avaliacoes.models import Alternativa, AvaliacaoReacao, Prova, Questao, RespostaProva
from certificacao.models import Certificado
from contas.models import Departamento
from core import services
from treinamentos.models import Aula, AtribuicaoManual, Curso, CursoDepartamento, ProgressoAula

Usuario = get_user_model()


class ServicosTestCase(TestCase):
    def setUp(self):
        self.dep_vendas = Departamento.objects.create(nome="Vendas")
        self.dep_operacoes = Departamento.objects.create(nome="Operações")

        self.colaborador = Usuario.objects.create_user(
            email="colab@nortex.com.br", nome="Colaborador", password="123456",
            departamento=self.dep_vendas,
        )
        self.rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="RH", password="123456",
            departamento=self.dep_operacoes, grupo=Usuario.Grupo.RH,
        )

        self.curso = Curso.objects.create(
            nome="Curso Teste", categoria="Compliance",
            nota_minima=7, max_tentativas=3, validade_meses=12,
        )
        self.aula1 = Aula.objects.create(curso=self.curso, ordem=1, titulo="Aula 1")
        self.aula2 = Aula.objects.create(curso=self.curso, ordem=2, titulo="Aula 2")

        self.prova = Prova.objects.create(curso=self.curso)
        self.questao1 = Questao.objects.create(prova=self.prova, ordem=1, enunciado="Q1?")
        self.alt1_certa = Alternativa.objects.create(
            questao=self.questao1, letra="A", texto="Certa", correta=True)
        self.alt1_errada = Alternativa.objects.create(
            questao=self.questao1, letra="B", texto="Errada", correta=False)

        self.questao2 = Questao.objects.create(prova=self.prova, ordem=2, enunciado="Q2?")
        self.alt2_certa = Alternativa.objects.create(
            questao=self.questao2, letra="A", texto="Certa", correta=True)
        self.alt2_errada = Alternativa.objects.create(
            questao=self.questao2, letra="B", texto="Errada", correta=False)

    #RN-02: visibilidade de cursos
    def test_rn02_curso_visivel_por_departamento(self):
        CursoDepartamento.objects.create(curso=self.curso, departamento=self.dep_vendas)
        self.assertIn(self.curso, services.cursos_do_usuario(self.colaborador))

    def test_rn02_curso_visivel_por_atribuicao_individual(self):
        outro_curso = Curso.objects.create(nome="Só pra ele", categoria="X")
        AtribuicaoManual.objects.create(
            curso=outro_curso, usuario=self.colaborador, atribuido_por=self.rh)
        self.assertIn(outro_curso, services.cursos_do_usuario(self.colaborador))

    def test_rn02_curso_sem_vinculo_fica_invisivel(self):
        self.assertNotIn(self.curso, services.cursos_do_usuario(self.colaborador))

    #RN-04: curso rascunho
    def test_rn04_curso_sem_prova_nao_publicado(self):
        curso_sem_prova = Curso.objects.create(nome="Incompleto", categoria="X")
        Aula.objects.create(curso=curso_sem_prova, ordem=1, titulo="Só uma aula")
        self.assertFalse(curso_sem_prova.publicado)

    def test_rn04_curso_completo_publicado(self):
        self.assertTrue(self.curso.publicado)

    #RN-05: presença única
    def test_rn05_presenca_registrada_uma_unica_vez(self):
        _, criada1 = services.registrar_presenca(self.colaborador, self.curso)
        _, criada2 = services.registrar_presenca(self.colaborador, self.curso)
        self.assertTrue(criada1)
        self.assertFalse(criada2)
        self.assertEqual(self.curso.presencas.filter(usuario=self.colaborador).count(), 1)

    #RN-23: progressão de etapas
    def test_rn23_etapa_1_enquanto_conteudo_incompleto(self):
        self.assertEqual(services.etapa_atual(self.colaborador, self.curso), 1)

    def test_rn23_etapa_2_apos_conteudo_completo(self):
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula1, concluida=True)
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula2, concluida=True)
        self.assertEqual(services.etapa_atual(self.colaborador, self.curso), 2)

    def test_rn23_etapa_3_apos_reacao_registrada(self):
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula1, concluida=True)
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula2, concluida=True)
        AvaliacaoReacao.objects.create(
            usuario=self.colaborador, curso=self.curso,
            nota_didatica=9, nota_entendimento=9)
        self.assertEqual(services.etapa_atual(self.colaborador, self.curso), 3)

    #RN-08: certificado exige reação e nota mínima
    def test_rn08_certificado_recusa_sem_reacao(self):
        with self.assertRaises(ValueError):
            services.emitir_certificado(self.colaborador, self.curso, nota=9)

    def test_rn08_certificado_recusa_nota_abaixo_da_minima(self):
        AvaliacaoReacao.objects.create(
            usuario=self.colaborador, curso=self.curso,
            nota_didatica=9, nota_entendimento=9)
        with self.assertRaises(ValueError):
            services.emitir_certificado(self.colaborador, self.curso, nota=6)

    def test_rn08_e_rn21_certificado_emitido_com_dados_corretos(self):
        AvaliacaoReacao.objects.create(
            usuario=self.colaborador, curso=self.curso,
            nota_didatica=9, nota_entendimento=9)
        cert = services.emitir_certificado(self.colaborador, self.curso, nota=9)
        self.assertEqual(cert.versao_curso, self.curso.versao)
        self.assertEqual(
            cert.data_validade,
            date(cert.data_emissao.year + 1, cert.data_emissao.month, cert.data_emissao.day))

    #RN-09/RN-20: correção da prova
    def test_rn09_corrigir_prova_calcula_nota_e_grava_tentativa(self):
        marcadas = {str(self.questao1.id): str(self.alt1_certa.id),
                    str(self.questao2.id): str(self.alt2_certa.id)}
        nota, aprovado, reciclou = services.corrigir_prova(
            self.colaborador, self.curso, marcadas)
        self.assertEqual(nota, 10)
        self.assertTrue(aprovado)
        self.assertFalse(reciclou)
        self.assertEqual(
            RespostaProva.objects.filter(usuario=self.colaborador).count(), 1)

    def test_rn09_segunda_tentativa_incrementa_numero(self):
        marcadas_erradas = {str(self.questao1.id): str(self.alt1_errada.id),
                            str(self.questao2.id): str(self.alt2_errada.id)}
        services.corrigir_prova(self.colaborador, self.curso, marcadas_erradas)
        services.corrigir_prova(self.colaborador, self.curso, marcadas_erradas)
        ultima = RespostaProva.objects.filter(usuario=self.colaborador).latest("id")
        self.assertEqual(ultima.numero_tentativa, 2)

    #RN-19: reciclagem após esgotar tentativas
    def test_rn19_reciclagem_apos_esgotar_tentativas(self):
        marcadas_erradas = {str(self.questao1.id): str(self.alt1_errada.id),
                            str(self.questao2.id): str(self.alt2_errada.id)}
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula1, concluida=True)
        AvaliacaoReacao.objects.create(
            usuario=self.colaborador, curso=self.curso,
            nota_didatica=8, nota_entendimento=8)

        #curso.max_tentativas = 3 — as duas primeiras não devem reciclar
        _, aprovado1, reciclou1 = services.corrigir_prova(
            self.colaborador, self.curso, marcadas_erradas)
        _, aprovado2, reciclou2 = services.corrigir_prova(
            self.colaborador, self.curso, marcadas_erradas)
        self.assertFalse(reciclou1)
        self.assertFalse(reciclou2)

        #a terceira ainda errada, deve reciclar
        _, aprovado3, reciclou3 = services.corrigir_prova(
            self.colaborador, self.curso, marcadas_erradas)
        self.assertFalse(aprovado3)
        self.assertTrue(reciclou3)

        #confirma que tudo foi zerado de verdade
        self.assertEqual(services.tentativas(self.colaborador, self.curso), 0)
        self.assertFalse(services.tem_reacao(self.colaborador, self.curso))
        self.assertFalse(
            ProgressoAula.objects.filter(usuario=self.colaborador, aula__curso=self.curso).exists())

    #RN-13/RN-14: situação de conformidade
    def test_rn14_sem_certificado_situacao_pendente(self):
        sit, cert = services.situacao(self.colaborador, self.curso)
        self.assertEqual(sit, "PENDENTE")
        self.assertIsNone(cert)

    def test_rn13_situacao_calculada_a_partir_da_data_de_validade(self):
        AvaliacaoReacao.objects.create(
            usuario=self.colaborador, curso=self.curso,
            nota_didatica=9, nota_entendimento=9)
        cert = services.emitir_certificado(self.colaborador, self.curso, nota=9)
        sit, _ = services.situacao(self.colaborador, self.curso)
        self.assertEqual(sit, "EM DIA")
        self.assertEqual(cert.situacao, "EM DIA")