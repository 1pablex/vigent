"""Testes de integração da avaliação de reação e da prova (RN-06, RN-09, RN-19, RN-23).

Views, services e banco de teste são reais; nada é mockado.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import LogSistema
from avaliacoes.models import Alternativa, AvaliacaoReacao, Prova, Questao, RespostaProva
from certificacao.models import Certificado
from contas.models import Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, ProgressoAula

Usuario = get_user_model()


class CenarioCursoMixin:
    """Colaborador de Vendas com um curso publicado (1 aula + prova de 2 questões)."""

    def setUp(self):
        self.departamento = Departamento.objects.create(nome="Vendas")
        self.colaborador = Usuario.objects.create_user(
            email="colab@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            departamento=self.departamento, senha_provisoria=False, aceitou_termos=True,
        )
        self.curso = Curso.objects.create(
            nome="LGPD na Prática", categoria="Compliance",
            nota_minima=7, max_tentativas=2, validade_meses=12,
        )
        CursoDepartamento.objects.create(curso=self.curso, departamento=self.departamento)
        self.aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")

        prova = Prova.objects.create(curso=self.curso)
        self.respostas_certas, self.respostas_erradas = {}, {}
        for ordem in (1, 2):
            questao = Questao.objects.create(prova=prova, ordem=ordem, enunciado=f"Q{ordem}?")
            certa = Alternativa.objects.create(questao=questao, letra="A", texto="Certa",
                                               correta=True)
            errada = Alternativa.objects.create(questao=questao, letra="B", texto="Errada")
            self.respostas_certas[f"q{questao.id}"] = str(certa.id)
            self.respostas_erradas[f"q{questao.id}"] = str(errada.id)

        self.client.force_login(self.colaborador)

    def concluir_conteudo(self):
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula, concluida=True)

    def responder_reacao(self):
        AvaliacaoReacao.objects.create(usuario=self.colaborador, curso=self.curso,
                                       nota_didatica=9, nota_entendimento=8)


class AvaliacaoReacaoIntegracaoTest(CenarioCursoMixin, TestCase):

    def test_deve_redirecionar_para_login_quando_nao_autenticado(self):
        # Arrange
        self.client.logout()
        url = reverse("avaliacoes:reacao", args=[self.curso.id])

        # Act
        resposta = self.client.get(url)

        # Assert
        self.assertRedirects(resposta, f"{reverse('contas:login')}?next={url}")

    def test_deve_retornar_404_para_curso_inexistente(self):
        # Act
        resposta = self.client.get(reverse("avaliacoes:reacao", args=[999999]))

        # Assert
        self.assertEqual(resposta.status_code, 404)

    def test_deve_bloquear_curso_de_outro_departamento(self):
        # Arrange: curso atribuído apenas ao departamento Financeiro (RN-02)
        outro = Curso.objects.create(nome="NR-35", categoria="Segurança")
        CursoDepartamento.objects.create(
            curso=outro, departamento=Departamento.objects.create(nome="Financeiro"))

        # Act
        resposta = self.client.get(reverse("avaliacoes:reacao", args=[outro.id]))

        # Assert
        self.assertRedirects(resposta, reverse("treinamentos:inicio"))

    def test_deve_exigir_conteudo_concluido_antes_da_reacao(self):
        # Act (RN-23: aula ainda não concluída)
        resposta = self.client.post(reverse("avaliacoes:reacao", args=[self.curso.id]),
                                    {"didatica": 9, "entendimento": 8})

        # Assert
        self.assertRedirects(resposta, reverse("treinamentos:curso", args=[self.curso.id]),
                             fetch_redirect_response=False)
        self.assertFalse(AvaliacaoReacao.objects.filter(usuario=self.colaborador).exists())

    def test_deve_gravar_reacao_e_liberar_prova(self):
        # Arrange
        self.concluir_conteudo()

        # Act
        resposta = self.client.post(reverse("avaliacoes:reacao", args=[self.curso.id]),
                                    {"didatica": 9, "entendimento": 7, "comentario": "  Ótimo "})

        # Assert
        self.assertRedirects(resposta, reverse("avaliacoes:prova", args=[self.curso.id]))
        reacao = AvaliacaoReacao.objects.get(usuario=self.colaborador, curso=self.curso)
        self.assertEqual((reacao.nota_didatica, reacao.nota_entendimento), (9, 7))
        self.assertEqual(reacao.comentario, "Ótimo")
        self.assertTrue(LogSistema.objects.filter(
            evento="Avaliação de reação registrada", usuario=self.colaborador).exists())

    def test_deve_rejeitar_nota_fora_da_escala(self):
        # Arrange
        self.concluir_conteudo()

        # Act
        resposta = self.client.post(reverse("avaliacoes:reacao", args=[self.curso.id]),
                                    {"didatica": 11, "entendimento": 8})

        # Assert
        self.assertContains(resposta, "Responda as duas questões para continuar.")
        self.assertFalse(AvaliacaoReacao.objects.filter(usuario=self.colaborador).exists())


class ProvaIntegracaoTest(CenarioCursoMixin, TestCase):

    def test_deve_exigir_reacao_antes_da_prova(self):
        # Arrange (RN-06)
        self.concluir_conteudo()

        # Act
        resposta = self.client.post(reverse("avaliacoes:prova", args=[self.curso.id]),
                                    self.respostas_certas)

        # Assert
        self.assertRedirects(resposta, reverse("avaliacoes:reacao", args=[self.curso.id]))
        self.assertFalse(RespostaProva.objects.filter(usuario=self.colaborador).exists())

    def test_deve_recusar_prova_com_questao_em_branco(self):
        # Arrange
        self.concluir_conteudo()
        self.responder_reacao()
        uma_resposta = dict(list(self.respostas_certas.items())[:1])

        # Act
        resposta = self.client.post(reverse("avaliacoes:prova", args=[self.curso.id]),
                                    uma_resposta)

        # Assert
        self.assertContains(resposta, "Responda todas as questões antes de finalizar.")
        self.assertFalse(RespostaProva.objects.filter(usuario=self.colaborador).exists())

    def test_deve_registrar_tentativa_reprovada_sem_emitir_certificado(self):
        # Arrange
        self.concluir_conteudo()
        self.responder_reacao()

        # Act
        resposta = self.client.post(reverse("avaliacoes:prova", args=[self.curso.id]),
                                    self.respostas_erradas)

        # Assert (RN-09)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context["aprovado"])
        self.assertEqual(resposta.context["restantes"], 1)
        tentativa = RespostaProva.objects.get(usuario=self.colaborador)
        self.assertEqual((tentativa.numero_tentativa, float(tentativa.nota_obtida)), (1, 0.0))
        self.assertFalse(Certificado.objects.filter(usuario=self.colaborador).exists())

    def test_deve_reiniciar_curso_ao_esgotar_tentativas(self):
        # Arrange: max_tentativas=2, primeira tentativa já reprovada
        self.concluir_conteudo()
        self.responder_reacao()
        self.client.post(reverse("avaliacoes:prova", args=[self.curso.id]),
                         self.respostas_erradas)

        # Act
        resposta = self.client.post(reverse("avaliacoes:prova", args=[self.curso.id]),
                                    self.respostas_erradas)

        # Assert (RN-19: progresso, reação e tentativas zerados)
        self.assertTrue(resposta.context["reciclou"])
        self.assertFalse(ProgressoAula.objects.filter(usuario=self.colaborador).exists())
        self.assertFalse(AvaliacaoReacao.objects.filter(usuario=self.colaborador).exists())
        self.assertFalse(RespostaProva.objects.filter(usuario=self.colaborador).exists())
        self.assertTrue(LogSistema.objects.filter(evento="Tentativas esgotadas").exists())
