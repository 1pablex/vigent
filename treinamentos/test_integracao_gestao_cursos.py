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


def dados_aula(ordem=1, titulo="Introdução"):
    return {"ordem": ordem, "titulo": titulo}


def dados_slide(ordem=0, titulo="Boas-vindas", corpo="", **extra):
    dados = {"ordem": ordem, "titulo": titulo, "corpo": corpo}
    dados.update(extra)
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

    def test_deve_criar_aula_e_abrir_a_tela_de_slides(self):
        # Act
        resposta = self.client.post(reverse("cursos_rh:aula_nova", args=[self.curso.id]),
                                    dados_aula())

        # Assert
        aula = Aula.objects.get(curso=self.curso)
        self.assertRedirects(resposta, reverse("cursos_rh:aula_editar",
                                               args=[self.curso.id, aula.id]))
        self.assertEqual(aula.titulo, "Introdução")

    def test_deve_editar_aula_e_voltar_ao_curso(self):
        # Arrange
        aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")

        # Act
        resposta = self.client.post(
            reverse("cursos_rh:aula_editar", args=[self.curso.id, aula.id]),
            dados_aula(titulo="Abertura"))

        # Assert
        self.assertRedirects(resposta, reverse("cursos_rh:editar", args=[self.curso.id]))
        aula.refresh_from_db()
        self.assertEqual(aula.titulo, "Abertura")

    def test_tela_da_aula_lista_os_slides_sem_formulario_de_cada_um(self):
        # Arrange
        aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")
        SlideAula.objects.create(aula=aula, ordem=0, titulo="Primeiro")
        SlideAula.objects.create(aula=aula, ordem=1, titulo="Segundo")

        # Act
        resposta = self.client.get(reverse("cursos_rh:aula_editar", args=[self.curso.id, aula.id]))

        # Assert
        self.assertContains(resposta, "Primeiro")
        self.assertContains(resposta, "Segundo")
        self.assertContains(resposta, reverse("cursos_rh:slide_novo", args=[self.curso.id, aula.id]))
        self.assertNotContains(resposta, 'name="corpo"')

    def test_deve_recusar_aula_com_ordem_repetida(self):
        # Arrange
        Aula.objects.create(curso=self.curso, ordem=1, titulo="Existente")

        # Act
        resposta = self.client.post(reverse("cursos_rh:aula_nova", args=[self.curso.id]),
                                    dados_aula(ordem=1, titulo="Outra"))

        # Assert
        self.assertContains(resposta, "Já existe uma aula com essa ordem neste curso.")
        self.assertEqual(self.curso.aulas.count(), 1)

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


class CadastroSlideTest(GestaoCursosBase):

    def setUp(self):
        super().setUp()
        self.curso = self.criar_curso()
        self.aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")
        self.url_aula = reverse("cursos_rh:aula_editar", args=[self.curso.id, self.aula.id])
        self.url_novo = reverse("cursos_rh:slide_novo", args=[self.curso.id, self.aula.id])

    def test_deve_criar_slide_e_voltar_para_a_aula(self):
        # Act
        resposta = self.client.post(self.url_novo, dados_slide(corpo="<p>Olá</p>"))

        # Assert
        self.assertRedirects(resposta, self.url_aula)
        slide = self.aula.slides.get()
        self.assertEqual((slide.ordem, slide.titulo, slide.corpo), (0, "Boas-vindas", "<p>Olá</p>"))
        self.assertTrue(LogSistema.objects.filter(evento="Slide salvo").exists())

    def test_salvar_e_cadastrar_outro_abre_slide_em_branco_com_a_proxima_ordem(self):
        # Act
        resposta = self.client.post(self.url_novo, dados_slide(outro="1"))
        nova_tela = self.client.get(self.url_novo)

        # Assert
        self.assertRedirects(resposta, self.url_novo)
        self.assertEqual(nova_tela.context["form"].initial["ordem"], 1)

    def test_primeiro_slide_sugere_ordem_zero(self):
        resposta = self.client.get(self.url_novo)
        self.assertEqual(resposta.context["form"].initial["ordem"], 0)

    def test_deve_recusar_slide_com_ordem_repetida(self):
        # Arrange
        SlideAula.objects.create(aula=self.aula, ordem=0, titulo="Existente")

        # Act
        resposta = self.client.post(self.url_novo, dados_slide(ordem=0, titulo="Outro"))

        # Assert
        self.assertContains(resposta, "Já existe um slide com essa ordem nesta aula.")
        self.assertEqual(self.aula.slides.count(), 1)

    def test_deve_editar_slide_mantendo_a_propria_ordem(self):
        # Arrange
        slide = SlideAula.objects.create(aula=self.aula, ordem=0, titulo="Antigo")

        # Act
        resposta = self.client.post(
            reverse("cursos_rh:slide_editar", args=[self.curso.id, self.aula.id, slide.id]),
            dados_slide(ordem=0, titulo="Novo"))

        # Assert
        self.assertRedirects(resposta, self.url_aula)
        slide.refresh_from_db()
        self.assertEqual(slide.titulo, "Novo")

    def test_deve_excluir_slide_somente_via_post(self):
        # Arrange
        slide = SlideAula.objects.create(aula=self.aula, ordem=0, titulo="Boas-vindas")
        url = reverse("cursos_rh:slide_excluir", args=[self.curso.id, self.aula.id, slide.id])

        # Act
        self.client.get(url)
        existia_apos_get = SlideAula.objects.filter(pk=slide.pk).exists()
        resposta = self.client.post(url)

        # Assert
        self.assertTrue(existia_apos_get)
        self.assertRedirects(resposta, self.url_aula)
        self.assertFalse(SlideAula.objects.filter(pk=slide.pk).exists())
        self.assertTrue(LogSistema.objects.filter(evento="Slide excluído").exists())

    def test_deve_retornar_404_para_slide_de_outra_aula(self):
        # Arrange
        outra_aula = Aula.objects.create(curso=self.curso, ordem=2, titulo="Outra")
        slide = SlideAula.objects.create(aula=outra_aula, ordem=0, titulo="De outra aula")

        # Act
        resposta = self.client.post(
            reverse("cursos_rh:slide_excluir", args=[self.curso.id, self.aula.id, slide.id]))

        # Assert
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(SlideAula.objects.filter(pk=slide.pk).exists())


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
        self.client.post(reverse("cursos_rh:aula_nova", args=[curso.id]), dados_aula())
        aula = curso.aulas.get()
        self.client.post(reverse("cursos_rh:slide_novo", args=[curso.id, aula.id]), dados_slide())
        self.client.post(reverse("cursos_rh:questao_nova", args=[curso.id]), dados_questao())

        # Act
        self.client.force_login(self.colaborador)
        resposta = self.client.get(reverse("treinamentos:inicio"))

        # Assert (RN-02 e RN-04)
        self.assertTrue(curso.publicado)
        self.assertContains(resposta, "LGPD na Prática")
