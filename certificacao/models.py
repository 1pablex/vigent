from django.conf import settings
from django.db import models
from django.utils import timezone


class Certificado(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="certificados")
    curso = models.ForeignKey("treinamentos.Curso", on_delete=models.PROTECT,
                              related_name="certificados")
    nota_prova = models.DecimalField(max_digits=4, decimal_places=1)
    versao_curso = models.PositiveIntegerField()
    data_emissao = models.DateField()
    data_validade = models.DateField()

    class Meta:
        ordering = ["-data_emissao"]

    def __str__(self):
        return f"{self.usuario} — {self.curso} ({self.data_emissao:%d/%m/%Y})"

    @property
    def dias_para_vencer(self):
        return (self.data_validade - timezone.localdate()).days

    @property
    def situacao(self):
        """RN-13 — calculada na consulta, nunca armazenada."""
        d = self.dias_para_vencer
        if d < 0:
            return "VENCIDO"
        if d <= 30:
            return "VENCENDO"
        return "EM DIA"

class NotificacaoEnviada(models.Model):
    """RN-11 trava de idempotencia: um e-mail por marco, nunca repetido."""

    certificado = models.ForeignKey(Certificado, on_delete=models.CASCADE, related_name="notificacoes")
    marco_dias = models.PositiveSmallIntegerField()
    data_envio = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("certificado", "marco_dias")]
        verbose_name = "notificação enviada"
        verbose_name_plural = "notificações enviadas"

    def __str__(self):
        return f"{self.certificado} — {self.marco_dias} dias"