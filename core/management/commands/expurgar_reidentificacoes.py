"""Exclui os dados originais de desligados após 90 dias no cofre (RN-29, LGPD art. 16)."""
import time

from django.core.management.base import BaseCommand

from auditoria.models import ExecucaoRotina, LogSistema
from core.services import expurgar_reidentificacoes, registrar


class Command(BaseCommand):
    help = "Expurga do cofre de reidentificação os registros com prazo de 90 dias vencido."

    def handle(self, *args, **options):
        inicio = time.monotonic()
        avaliados = expurgados = 0
        sucesso = True
        try:
            avaliados, expurgados = expurgar_reidentificacoes()
        except Exception as exc:
            sucesso = False
            registrar(LogSistema.Nivel.ERRO, "Falha no expurgo de reidentificação", str(exc)[:500])

        # Na tabela de rotinas: avaliados = registros no cofre; ignorados = ainda dentro do prazo.
        ExecucaoRotina.objects.create(
            rotina="expurgar_reidentificacoes",
            duracao_seg=round(time.monotonic() - inicio, 2),
            avaliados=avaliados, notificados=0,
            ignorados=avaliados - expurgados, sucesso=sucesso,
        )
        self.stdout.write(self.style.SUCCESS(
            f"No cofre: {avaliados} | Expurgados: {expurgados}"))
