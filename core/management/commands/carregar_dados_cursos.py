"""Popula o banco com os cursos de demonstração - cenário Nortex Soluções Ltda.

O conteúdo vem de core/dados/cursos/ (cursos.json e imagens), gerado pelo comando
exportar_cursos a partir dos cursos cadastrados pela tela do RH. As imagens passam
pelo storage do Django: em produção vão para o storage configurado (Cloudinary).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from avaliacoes.models import Alternativa, Prova, Questao
from contas.models import Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, SlideAula
from treinamentos.seguranca import validar_imagem

DADOS = Path(__file__).resolve().parents[2] / "dados" / "cursos"


class Command(BaseCommand):
    help = "Cria os cursos de demonstração, com capa, aulas, slides, prova e questões."

    def handle(self, *args, **options):
        dados = json.loads((DADOS / "cursos.json").read_text(encoding="utf-8"))
        for curso in dados["cursos"]:
            self._criar_curso(curso)
        self.stdout.write(self.style.SUCCESS("Concluído."))

    @transaction.atomic
    def _criar_curso(self, dados):
        if Curso.objects.filter(nome=dados["nome"]).exists():
            self.stdout.write(f"Curso já existe, pulando: {dados['nome']}")
            return

        curso = Curso.objects.create(
            nome=dados["nome"],
            categoria=dados["categoria"],
            carga_horaria=dados["carga_horaria"],
            validade_meses=dados["validade_meses"],
            nota_minima=Decimal(dados["nota_minima"]),
            max_tentativas=dados["max_tentativas"],
            imagem_capa=self._imagem(dados["capa"]),
        )

        # get_or_create: funciona mesmo se este comando rodar antes do carregar_dados_colaboradores
        for nome in dados["departamentos"]:
            departamento, _ = Departamento.objects.get_or_create(nome=nome)
            CursoDepartamento.objects.create(curso=curso, departamento=departamento)

        for dados_aula in dados["aulas"]:
            aula = Aula.objects.create(curso=curso, ordem=dados_aula["ordem"], titulo=dados_aula["titulo"])
            for slide in dados_aula["slides"]:
                SlideAula.objects.create(aula=aula, ordem=slide["ordem"], titulo=slide["titulo"],
                                         corpo=slide["corpo"], imagem=self._imagem(slide["imagem"]))

        prova = Prova.objects.create(curso=curso)
        for dados_questao in dados["questoes"]:
            questao = Questao.objects.create(prova=prova, ordem=dados_questao["ordem"],
                                             enunciado=dados_questao["enunciado"])
            for alternativa in dados_questao["alternativas"]:
                Alternativa.objects.create(questao=questao, **alternativa)

        self.stdout.write(self.style.SUCCESS(f"Curso criado: {curso.nome}"))
        self.stdout.write(
            f"  {len(dados['aulas'])} aula(s), {len(dados['questoes'])} questão(ões), "
            f"{len(dados['departamentos'])} departamento(s) vinculado(s)")

    @staticmethod
    def _imagem(caminho):
        """Lê a imagem versionada e a valida como um upload do RH (RN-40).
        Ao salvar, o model a regrava com nome aleatório e sem metadados."""
        if not caminho:
            return None
        arquivo = ContentFile((DADOS / caminho).read_bytes(), name=Path(caminho).name)
        validar_imagem(arquivo)
        return arquivo
