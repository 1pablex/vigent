"""Exporta cursos do banco para os arquivos que o carregar_dados_cursos lê.

Uso: python manage.py exportar_cursos 5 6 7 8   (sem ids, exporta todos os cursos)

Gera core/dados/cursos/cursos.json com o conteúdo (aulas, slides, prova, questões e
departamentos) e copia as imagens para core/dados/cursos/imagens/. Assim um curso
cadastrado pela tela do RH vira carga de dados versionada, que recria o mesmo curso
em outro banco, inclusive em produção.
"""
import json
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from treinamentos.models import Curso

DADOS = Path(__file__).resolve().parents[2] / "dados" / "cursos"


class Command(BaseCommand):
    help = "Exporta cursos do banco para core/dados/cursos (conteúdo em JSON e imagens)."

    def add_arguments(self, parser):
        parser.add_argument("ids", nargs="*", type=int, help="Ids dos cursos. Sem ids, exporta todos.")

    def handle(self, *args, **options):
        cursos = Curso.objects.prefetch_related(
            "departamentos__departamento", "aulas__slides", "prova__questoes__alternativas")
        if options["ids"]:
            cursos = cursos.filter(id__in=options["ids"])
            faltando = set(options["ids"]) - {c.id for c in cursos}
            if faltando:
                raise CommandError(f"Cursos não encontrados: {sorted(faltando)}")

        imagens = DADOS / "imagens"
        shutil.rmtree(imagens, ignore_errors=True)   # imagem de curso que saiu não fica para trás
        imagens.mkdir(parents=True)

        exportados = [self._curso(curso, imagens) for curso in cursos]
        conteudo = json.dumps({"cursos": exportados}, ensure_ascii=False, indent=2)
        (DADOS / "cursos.json").write_text(conteudo + "\n", encoding="utf-8")

        for curso in exportados:
            self.stdout.write(f"Exportado: {curso['nome']}")
        self.stdout.write(self.style.SUCCESS(f"{len(exportados)} curso(s) em {DADOS}"))

    def _curso(self, curso, imagens):
        pasta = slugify(curso.nome)
        prova = getattr(curso, "prova", None)
        return {
            "nome": curso.nome,
            "categoria": curso.categoria,
            "carga_horaria": curso.carga_horaria,
            "validade_meses": curso.validade_meses,
            "nota_minima": str(curso.nota_minima),
            "max_tentativas": curso.max_tentativas,
            "capa": self._copiar(curso.imagem_capa, imagens, pasta, "capa"),
            "departamentos": sorted(cd.departamento.nome for cd in curso.departamentos.all()),
            "aulas": [{
                "ordem": aula.ordem,
                "titulo": aula.titulo,
                "slides": [{
                    "ordem": slide.ordem,
                    "titulo": slide.titulo,
                    "corpo": slide.corpo,
                    "imagem": self._copiar(slide.imagem, imagens, pasta,
                                           f"aula-{aula.ordem}-slide-{slide.ordem}"),
                } for slide in aula.slides.all()],
            } for aula in curso.aulas.all()],
            "questoes": [{
                "ordem": questao.ordem,
                "enunciado": questao.enunciado,
                "alternativas": [{"letra": a.letra, "texto": a.texto, "correta": a.correta}
                                 for a in questao.alternativas.all()],
            } for questao in (prova.questoes.all() if prova else [])],
        }

    @staticmethod
    def _copiar(campo, imagens, pasta, nome):
        """Copia a imagem pelo storage (vale para disco ou nuvem) e devolve o caminho relativo."""
        if not campo:
            return None
        destino = imagens / pasta / f"{nome}{Path(campo.name).suffix.lower()}"
        destino.parent.mkdir(exist_ok=True)
        with campo.open("rb") as origem:
            destino.write_bytes(origem.read())
        return destino.relative_to(DADOS).as_posix()
