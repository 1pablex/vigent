"""Cursos, conteúdo, atribuição e progresso do colaborador."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Curso(models.Model):
    nome = models.CharField(max_length=140)
    categoria = models.CharField(max_length=60)
    imagem_capa = models.ImageField(upload_to="capas/", blank=True, null=True)
    carga_horaria = models.CharField(max_length=30, default="4 horas")
    validade_meses = models.PositiveSmallIntegerField(default=12)
    nota_minima = models.DecimalField(max_digits=3, decimal_places=1, default=7)
    max_tentativas = models.PositiveSmallIntegerField(default=3)      # RN-19
    versao = models.PositiveIntegerField(default=1)                   # RN-21

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def publicado(self):
        """RN-04 — exige ao menos uma aula e uma questão cadastradas."""
        return self.aulas.exists() and Questao_existe(self)

    @property
    def total_slides(self):
        return SlideAula.objects.filter(aula__curso=self).count()


def Questao_existe(curso):
    from avaliacoes.models import Questao
    return Questao.objects.filter(prova__curso=curso).exists()

#aula do curso, com ordem e título
class Aula(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="aulas")
    ordem = models.PositiveSmallIntegerField()
    titulo = models.CharField(max_length=140)

    class Meta:
        ordering = ["curso", "ordem"]
        unique_together = [("curso", "ordem")]

    def __str__(self):
        return f"{self.curso} — aula {self.ordem}"

#conteudo em slides
class SlideAula(models.Model):
    """Conteúdo em slides. A imagem é opcional para permitir slides textuais."""

    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name="slides")
    ordem = models.PositiveSmallIntegerField()
    titulo = models.CharField(max_length=140)
    corpo = models.TextField(blank=True, help_text="Aceita HTML simples: parágrafos e listas.")
    imagem = models.ImageField(upload_to="slides/", blank=True, null=True)

    class Meta:
        ordering = ["aula", "ordem"]
        unique_together = [("aula", "ordem")]
        verbose_name = "slide"

    def __str__(self):
        return f"{self.aula} — slide {self.ordem}"


class CursoDepartamento(models.Model):
    """RN-02 — obrigatoriedade por setor."""

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="departamentos")
    departamento = models.ForeignKey("contas.Departamento", on_delete=models.CASCADE,
                                     related_name="cursos")
    obrigatorio = models.BooleanField(default=True)

    class Meta:
        unique_together = [("curso", "departamento")]
        verbose_name = "curso por departamento"
        verbose_name_plural = "cursos por departamento"

    def __str__(self):
        return f"{self.curso} → {self.departamento}"


class AtribuicaoManual(models.Model):
    """RN-02 — exceção individual à regra do departamento."""

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="atribuicoes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="atribuicoes")
    atribuido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      related_name="atribuicoes_feitas")
    data_atribuicao = models.DateField(default=timezone.localdate)

    class Meta:
        unique_together = [("curso", "usuario")]
        verbose_name = "atribuição individual"
        verbose_name_plural = "atribuições individuais"

    def __str__(self):
        return f"{self.usuario} → {self.curso}"

class Presenca(models.Model):
    """RN-05 — registrada uma única vez, no primeiro acesso ao curso."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="presencas")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="presencas")
    data_hora_acesso = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("usuario", "curso")]
        verbose_name = "presença"
        verbose_name_plural = "presenças"

    def __str__(self):
        return f"{self.usuario} em {self.curso}"


class ProgressoAula(models.Model):
    """RN-23 — a aula conclui quando todos os slides são percorridos."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="progressos")
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name="progressos")
    slides_vistos = models.JSONField(default=list)
    concluida = models.BooleanField(default=False)
    data_conclusao = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("usuario", "aula")]
        verbose_name = "progresso de aula"
        verbose_name_plural = "progressos de aula"

    def registrar_slide(self, ordem):
        vistos = set(self.slides_vistos or [])
        vistos.add(int(ordem))
        self.slides_vistos = sorted(vistos)
        total = self.aula.slides.count()
        if total and len(self.slides_vistos) >= total and not self.concluida:
            self.concluida = True
            self.data_conclusao = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.usuario} — {self.aula}"