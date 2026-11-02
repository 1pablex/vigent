"""Testes de integração das telas do RH para cadastro de cursos, aulas, slides e prova.

Views, formulários, services e banco de teste são reais; nada é mockado.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import LogSistema
from avaliacoes.models import Alternativa, Prova, Questao
from contas.models import Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, SlideAula

Usuario = get_user_model()


def dados_curso(**extra):
    dados = {"nome": "LGPD na Prática", "categoria": "Compliance", "carga_horaria": "4 horas",
             "validade_meses": 12, "nota_minima": 7, "max_tentativas": 3}
    dados.update(extra)
    return dados


def dados_aula(ordem=1, titulo="Introdução", slides=(), iniciais=0):
    """Monta o POST da aula com o formset de slides (prefixo "slides")."""
    dados = {"ordem": ordem, "titulo": titulo,
             "slides-TOTAL_FORMS": len(slides), "slides-INITIAL_FORMS": iniciais,
             "slides-MIN_NUM_FORMS": 0, "slides-MAX_NUM_FORMS": 1000}
    for i, slide in enumerate(slides):
        for campo, valor in slide.items():
            dados[f"slides-{i}-{campo}"] = valor
    return dados


def dados_questao(enunciado="O que a LGPD protege?", correta="A", ordem=1, **alternativas):
    dados = {"ordem": ordem, "enunciado": enunciado, "correta": correta,
             "alt_A": "Dados pessoais", "alt_B": "Patentes", "alt_C": "", "alt_D": "", "alt_E": ""}
    dados.update(alternativas)
    return dados


class GestaoCursosBase(TestCase):

    def setUp(self):
        self.vendas = Departamento.objects.create(nome="Vendas")
        self.financeiro = Departamento.objects.create(nome="Financeiro")
        self.rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="Rita RH", password="senha-123",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True,
        )
        self.colaborador = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            departamento=self.vendas, senha_provisoria=False, aceitou_termos=True,
        )
        self.client.force_login(self.rh)

    def criar_curso(self):
        curso = Curso.objects.create(nome="NR-10", categoria="Segurança")
        CursoDepartamento.objects.create(curso=curso, departamento=self.vendas)
        return curso


class AcessoGestaoCursosTest(GestaoCursosBase):

    def test_deve_redirecionar_para_login_quando_nao_autenticado(self):
        # Arrange
        self.client.logout()

        # Act
        resposta = self.client.get(reverse("cursos_rh:lista"))

        # Assert
        self.assertRedirects(resposta,
                             f"{reverse('contas:login')}?next={reverse('cursos_rh:lista')}")

    def test_colaborador_nao_acessa_nem_altera_cursos(self):
        # Arrange
        curso = self.criar_curso()
        self.client.force_login(self.colaborador)

        # Act
        lista = self.client.get(reverse("cursos_rh:lista"))
        edicao = self.client.post(reverse("cursos_rh:editar", args=[curso.id]),
                                  dados_curso(nome="Alterado"))

        # Assert
        self.assertRedirects(lista, reverse("treinamentos:inicio"))
        self.assertRedirects(edicao, reverse("treinamentos:inicio"))
        curso.refresh_from_db()
        self.assertEqual(curso.nome, "NR-10")

    def test_deve_listar_cursos_com_situacao_de_publicacao(self):
        # Arrange
        self.criar_curso()

        # Act
        resposta = self.client.get(reverse("cursos_rh:lista"))

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "NR-10")
        self.assertContains(resposta, "Rascunho")


class CadastroCursoTest(GestaoCursosBase):

    def test_deve_criar_curso_vinculado_aos_departamentos(self):
        # Act
        resposta = self.client.post(reverse("cursos_rh:novo"),
                                    dados_curso(departamentos=[self.vendas.id, self.financeiro.id]))

        # Assert
        curso = Curso.objects.get(nome="LGPD na Prática")
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[curso.id]))
        self.assertEqual(float(curso.nota_minima), 7.0)
        self.assertEqual(
            set(curso.departamentos.values_list("departamento__nome", flat=True)),
            {"Vendas", "Financeiro"})
        self.assertFalse(curso.publicado)
        self.assertTrue(LogSistema.objects.filter(evento="Curso cadastrado", usuario=self.rh).exists())

    def test_deve_recusar_nota_minima_acima_de_dez(self):
        # Act
        resposta = self.client.post(reverse("cursos_rh:novo"), dados_curso(nota_minima=11))

        # Assert
        self.assertContains(resposta, "A nota mínima deve ficar entre 0 e 10.")
        self.assertFalse(Curso.objects.exists())

    def test_deve_atualizar_dados_e_departamentos(self):
        # Arrange
        curso = self.criar_curso()

        # Act
        resposta = self.client.post(reverse("cursos_rh:editar", args=[curso.id]),
                                    dados_curso(nome="NR-10 Reciclagem",
                                                departamentos=[self.financeiro.id]))

        # Assert
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[curso.id]))
        curso.refresh_from_db()
        self.assertEqual(curso.nome, "NR-10 Reciclagem")
        self.assertEqual(list(curso.departamentos.values_list("departamento", flat=True)),
                         [self.financeiro.id])


class CadastroAulaTest(GestaoCursosBase):

    def setUp(self):
        super().setUp()
        self.curso = self.criar_curso()

    def test_deve_criar_aula_com_slides(self):
        # Act
        resposta = self.client.post(
            reverse("cursos_rh:aula_nova", args=[self.curso.id]),
            dados_aula(slides=[{"ordem": 0, "titulo": "Boas-vindas", "corpo": "<p>Olá</p>"},
                               {"ordem": 1, "titulo": "Riscos", "corpo": "Choque elétrico"}]))

        # Assert
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[self.curso.id]))
        aula = Aula.objects.get(curso=self.curso)
        self.assertEqual(aula.titulo, "Introdução")
        self.assertEqual(list(aula.slides.values_list("titulo", flat=True)),
                         ["Boas-vindas", "Riscos"])

    def test_deve_recusar_aula_com_ordem_repetida(self):
        # Arrange
        Aula.objects.create(curso=self.curso, ordem=1, titulo="Existente")

        # Act
        resposta = self.client.post(reverse("cursos_rh:aula_nova", args=[self.curso.id]),
                                    dados_aula(ordem=1, titulo="Outra"))

        # Assert
        self.assertContains(resposta, "Já existe uma aula com essa ordem neste curso.")
        self.assertEqual(self.curso.aulas.count(), 1)

    def test_deve_trocar_ordem_e_excluir_slides(self):
        # Arrange
        aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")
        primeiro = SlideAula.objects.create(aula=aula, ordem=0, titulo="Primeiro")
        segundo = SlideAula.objects.create(aula=aula, ordem=1, titulo="Segundo")
        terceiro = SlideAula.objects.create(aula=aula, ordem=2, titulo="Terceiro")

        # Act: troca a ordem dos dois primeiros e exclui o terceiro
        resposta = self.client.post(
            reverse("cursos_rh:aula_editar", args=[self.curso.id, aula.id]),
            dados_aula(iniciais=3, slides=[
                {"id": primeiro.id, "aula": aula.id, "ordem": 1, "titulo": "Primeiro"},
                {"id": segundo.id, "aula": aula.id, "ordem": 0, "titulo": "Segundo"},
                {"id": terceiro.id, "aula": aula.id, "ordem": 2, "titulo": "Terceiro",
                 "DELETE": "on"},
            ]))

        # Assert
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[self.curso.id]))
        self.assertEqual(list(aula.slides.values_list("titulo", "ordem")),
                         [("Segundo", 0), ("Primeiro", 1)])

    def test_deve_recusar_slides_com_ordem_repetida(self):
        # Act
        resposta = self.client.post(
            reverse("cursos_rh:aula_nova", args=[self.curso.id]),
            dados_aula(slides=[{"ordem": 0, "titulo": "A"}, {"ordem": 0, "titulo": "B"}]))

        # Assert
        self.assertContains(resposta, "Dois slides não podem ter a mesma ordem.")
        self.assertFalse(Aula.objects.filter(curso=self.curso).exists())

    def test_deve_excluir_aula_somente_via_post(self):
        # Arrange
        aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")
        url = reverse("cursos_rh:aula_excluir", args=[self.curso.id, aula.id])

        # Act
        self.client.get(url)
        existia_apos_get = Aula.objects.filter(pk=aula.pk).exists()
        resposta = self.client.post(url)

        # Assert
        self.assertTrue(existia_apos_get)
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[self.curso.id]))
        self.assertFalse(Aula.objects.filter(pk=aula.pk).exists())
        self.assertTrue(LogSistema.objects.filter(evento="Aula excluída").exists())


class CadastroQuestaoTest(GestaoCursosBase):

    def setUp(self):
        super().setUp()
        self.curso = self.criar_curso()

    def test_deve_criar_prova_e_questao_com_alternativa_correta(self):
        # Act
        resposta = self.client.post(reverse("cursos_rh:questao_nova", args=[self.curso.id]),
                                    dados_questao(correta="B", alt_C="Marcas"))

        # Assert
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[self.curso.id]))
        questao = Questao.objects.get(prova__curso=self.curso)
        self.assertEqual(list(questao.alternativas.values_list("letra", "correta")),
                         [("A", False), ("B", True), ("C", False)])

    def test_deve_recusar_alternativa_correta_em_branco(self):
        # Act
        resposta = self.client.post(reverse("cursos_rh:questao_nova", args=[self.curso.id]),
                                    dados_questao(correta="D"))

        # Assert
        self.assertContains(resposta, "A alternativa marcada como correta está em branco.")
        self.assertFalse(Prova.objects.filter(curso=self.curso).exists())

    def test_deve_exigir_ao_menos_duas_alternativas(self):
        # Act
        resposta = self.client.post(reverse("cursos_rh:questao_nova", args=[self.curso.id]),
                                    dados_questao(alt_B=""))

        # Assert
        self.assertContains(resposta, "Preencha pelo menos duas alternativas.")
        self.assertFalse(Questao.objects.exists())

    def test_deve_editar_questao_trocando_correta_e_removendo_alternativa(self):
        # Arrange
        prova = Prova.objects.create(curso=self.curso)
        questao = Questao.objects.create(prova=prova, ordem=1, enunciado="Antigo?")
        for letra, correta in (("A", True), ("B", False), ("C", False)):
            Alternativa.objects.create(questao=questao, letra=letra, texto=letra, correta=correta)

        # Act
        self.client.post(reverse("cursos_rh:questao_editar", args=[self.curso.id, questao.id]),
                         dados_questao(enunciado="Novo?", correta="B"))

        # Assert
        questao.refresh_from_db()
        self.assertEqual(questao.enunciado, "Novo?")
        self.assertEqual(list(questao.alternativas.values_list("letra", "correta")),
                         [("A", False), ("B", True)])

    def test_deve_retornar_404_para_questao_de_outro_curso(self):
        # Arrange
        outro = Curso.objects.create(nome="NR-35")
        questao = Questao.objects.create(prova=Prova.objects.create(curso=outro),
                                         ordem=1, enunciado="?")

        # Act
        resposta = self.client.get(
            reverse("cursos_rh:questao_editar", args=[self.curso.id, questao.id]))

        # Assert
        self.assertEqual(resposta.status_code, 404)


class PublicacaoPelasTelasTest(GestaoCursosBase):

    def test_curso_montado_pelas_telas_aparece_para_o_colaborador(self):
        # Arrange: cria curso, aula e questão só pelas telas do RH
        self.client.post(reverse("cursos_rh:novo"), dados_curso(departamentos=[self.vendas.id]))
        curso = Curso.objects.get(nome="LGPD na Prática")
        self.client.post(reverse("cursos_rh:aula_nova", args=[curso.id]),
                         dados_aula(slides=[{"ordem": 0, "titulo": "Boas-vindas"}]))
        self.client.post(reverse("cursos_rh:questao_nova", args=[curso.id]), dados_questao())

        # Act
        self.client.force_login(self.colaborador)
        resposta = self.client.get(reverse("treinamentos:inicio"))

        # Assert (RN-02 e RN-04)
        self.assertTrue(curso.publicado)
        self.assertContains(resposta, "LGPD na Prática")
