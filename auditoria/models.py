from django.conf import settings
from django.db import models

"""Trilha de eventos da plataforma (RN-24, RN-25)."""
class LogSistema(models.Model):
    class Nivel(models.TextChoices):
        INFO = "INFO", "Informação"
        OK = "OK", "Sucesso"
        WARN = "WARN", "Alerta"
        ERRO = "ERRO", "Erro"

    data_hora = models.DateTimeField(auto_now_add=True)
    nivel = models.CharField(max_length=5, choices=Nivel.choices, default=Nivel.INFO)
    evento = models.CharField(max_length=80)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="eventos")
    detalhe = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "registro do sistema"
        verbose_name_plural = "registros do sistema"

    def __str__(self):
        return f"[{self.nivel}] {self.evento}"


class EmailEnviado(models.Model):
    """Correspondência disparada, com o conteúdo preservado para consulta (RF-25)."""

    data_hora = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=40)
    destinatario = models.EmailField()
    assunto = models.CharField(max_length=200)
    corpo = models.TextField(blank=True)
    entregue = models.BooleanField(default=True)
    erro = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "mensagem enviada"
        verbose_name_plural = "mensagens enviadas"

    def __str__(self):
        return f"{self.tipo} → {self.destinatario}"


class RegistroAcesso(models.Model):
    """Tentativas de autenticação e acessos negados (RF-26)."""

    data_hora = models.DateTimeField(auto_now_add=True)
    identificacao = models.CharField(max_length=150)
    evento = models.CharField(max_length=80)
    grupo = models.CharField(max_length=20, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    resultado = models.CharField(max_length=40)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "registro de acesso"
        verbose_name_plural = "registros de acesso"

    def __str__(self):
        return f"{self.identificacao} — {self.resultado}"


class ExecucaoRotina(models.Model):
    """Resultado de cada execução do verificador de vencimentos."""

    data_hora = models.DateTimeField(auto_now_add=True)
    rotina = models.CharField(max_length=60, default="verificar_vencimentos")
    duracao_seg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    avaliados = models.PositiveIntegerField(default=0)
    notificados = models.PositiveIntegerField(default=0)
    ignorados = models.PositiveIntegerField(default=0)
    sucesso = models.BooleanField(default=True)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "execução de rotina"
        verbose_name_plural = "execuções de rotina"

    def __str__(self):
        return f"{self.rotina} — {self.data_hora:%d/%m/%Y}"