"""Verifica certificados próximos do vencimento e envia alerta por e-mail.
RF-09, RF-10, RN-11 (idempotencia), RN-12 (vencido não notifica de novo)."""
import time

from django.core.management.base import BaseCommand
from auditoria.models import ExecucaoRotina, LogSistema
from certificacao.models import Certificado, NotificacaoEnviada
from core.correio import enviar_alerta_vencimento
from core.services import registrar

MARCOS_DIAS = [30, 15, 7]

class Command(BaseCommand):
    help = "Verifica vencimentos e envia alertas nos marcos de 30/15/7 dias."

    def handle(self, *args, **options):
        inicio = time.monotonic()
        avaliados = notificados = ignorados = 0
        sucesso = True

        for cert in Certificado.objects.select_related("usuario", "curso"):
            avaliados += 1
            dias = cert.dias_para_vencer

            if dias < 0 or dias not in MARCOS_DIAS:
                continue   # RN-12 vencido não gera notificação nova

            if NotificacaoEnviada.objects.filter(certificado=cert, marco_dias=dias).exists():
                ignorados += 1   # RN-11 notificado nesse marco
                continue

            try:
                enviar_alerta_vencimento(cert.usuario, cert, dias)
                NotificacaoEnviada.objects.create(certificado=cert, marco_dias=dias)
                notificados += 1
            except Exception as exc:
                sucesso = False
                registrar(LogSistema.Nivel.ERRO, "Falha ao notificar vencimento",
                          f"{cert.usuario.email} — {cert.curso.nome} — {exc}"[:500])

        duracao = time.monotonic() - inicio
        ExecucaoRotina.objects.create(
            rotina="verificar_vencimentos", duracao_seg=round(duracao, 2),
            avaliados=avaliados, notificados=notificados,
            ignorados=ignorados, sucesso=sucesso,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Avaliados: {avaliados} | Notificados: {notificados} | Ignorados: {ignorados}"))