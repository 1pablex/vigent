from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

"""avaliação de reação e prova de conhecimento."""

class AvaliacaoReacao(models.Model):
    """nível 1 do modelo de Kirkpatrick. RN-06:da o acesso à prova."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="reacoes")
    curso = models.ForeignKey("treinamentos.Curso", on_delete=models.CASCADE,
                              related_name="reacoes")
    nota_didatica = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)])
    nota_entendimento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)])
    comentario = models.TextField(blank=True)
    data_resposta = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-data_resposta"]
        verbose_name = "avaliação de reação"
        verbose_name_plural = "avaliações de reação"

    def __str__(self):
        return f"{self.usuario} — {self.curso}"

    @property
    def media(self):
        return (self.nota_didatica + self.nota_entendimento) / 2

class Prova(models.Model):
    curso = models.OneToOneField("treinamentos.Curso", on_delete=models.CASCADE,
                                 related_name="prova")

    def __str__(self):
        return f"Prova — {self.curso}"

    @property
    def total_questoes(self):
        return self.questoes.count()


class Questao(models.Model):
    prova = models.ForeignKey(Prova, on_delete=models.CASCADE, related_name="questoes")
    ordem = models.PositiveSmallIntegerField(default=1)   # RN-20 ordem fixa
    enunciado = models.TextField()

    class Meta:
        ordering = ["prova", "ordem"]
        verbose_name = "questão"
        verbose_name_plural = "questões"

    def __str__(self):
        return f"{self.prova.curso} — questão {self.ordem}"

class Alternativa(models.Model):
    LETRAS = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E")]

    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name="alternativas")
    letra = models.CharField(max_length=1, choices=LETRAS)
    texto = models.CharField(max_length=400)
    correta = models.BooleanField(default=False)

    class Meta:
        ordering = ["questao", "letra"]
        unique_together = [("questao", "letra")]

    def __str__(self):
        return f"{self.letra}) {self.texto[:50]}"


class RespostaProva(models.Model):
    """Cada tentativa gera um registro para o histórico(RN-09)."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="respostas")
    prova = models.ForeignKey(Prova, on_delete=models.CASCADE, related_name="respostas")
    numero_tentativa = models.PositiveSmallIntegerField()
    nota_obtida = models.DecimalField(max_digits=4, decimal_places=1)
    data_realizacao = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-data_realizacao"]
        verbose_name = "resposta de prova"
        verbose_name_plural = "respostas de prova"

    def __str__(self):
        return f"{self.usuario} — {self.prova.curso} (tentativa {self.numero_tentativa})"