"""Comando carregar_dados_cursos: recria os cursos versionados em core/dados/cursos."""
import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.management.commands.carregar_dados_cursos import DADOS
from treinamentos.models import Curso, SlideAula

ESPERADO = json.loads((DADOS / "cursos.json").read_text(encoding="utf-8"))["cursos"]


def rodar():
    call_command("carregar_dados_cursos", stdout=StringIO())


class CargaDeCursosTest(TestCase):

    @classmethod
    def setUpClass(cls):
        media = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, media, ignore_errors=True)
        configuracao = override_settings(MEDIA_ROOT=media)
        configuracao.enable()
        cls.addClassCleanup(configuracao.disable)
        super().setUpClass()

    @classmethod
    def setUpTestData(cls):
        rodar()

    def test_cria_cada_curso_do_arquivo_com_o_mesmo_conteudo(self):
        self.assertEqual(Curso.objects.count(), len(ESPERADO))
        for dados in ESPERADO:
            with self.subTest(curso=dados["nome"]):
                curso = Curso.objects.get(nome=dados["nome"])
                self.assertTrue(curso.publicado)   # RN-04: aula e questão cadastradas
                self.assertEqual(curso.aulas.count(), len(dados["aulas"]))
                self.assertEqual(curso.total_slides, sum(len(a["slides"]) for a in dados["aulas"]))
                self.assertEqual(curso.prova.questoes.count(), len(dados["questoes"]))
                self.assertEqual(
                    sorted(curso.departamentos.values_list("departamento__nome", flat=True)),
                    dados["departamentos"])

    def test_toda_questao_tem_uma_unica_alternativa_correta(self):
        for dados in ESPERADO:
            for questao in dados["questoes"]:
                with self.subTest(curso=dados["nome"], questao=questao["ordem"]):
                    self.assertEqual(sum(a["correta"] for a in questao["alternativas"]), 1)

    def test_imagens_passam_pela_regravacao_do_upload(self):
        # RN-40: mesma regra do upload pelo RH, com nome aleatório no storage.
        curso = Curso.objects.exclude(imagem_capa="").first()
        self.assertIsNotNone(curso)
        for campo in [curso.imagem_capa] + [s.imagem for s in SlideAula.objects.exclude(imagem="")]:
            with self.subTest(imagem=campo.name):
                self.assertEqual(len(Path(campo.name).stem), 32)
                self.assertTrue(campo.storage.exists(campo.name))

    def test_rodar_de_novo_nao_duplica(self):
        rodar()
        self.assertEqual(Curso.objects.count(), len(ESPERADO))
