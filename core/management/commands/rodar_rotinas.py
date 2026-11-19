"""Rotinas diárias do Cron Job, com aviso ao monitor externo (RF-12, RN-35).

Roda a verificação de vencimentos e o expurgo do cofre de reidentificação e avisa o monitor
(core/monitor.py) no início, no sucesso ou na falha. Se o Cron Job deixar de rodar, o aviso
de sucesso não chega e o monitor alerta por e-mail.

Cada rotina registra a própria execução (ExecucaoRotina). Uma falha numa delas não impede a
outra; no fim, se alguma falhou, o comando avisa falha e termina com erro, para o Render
também marcar a execução como falha.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auditoria.models import ExecucaoRotina
from core import monitor

ROTINAS = ["verificar_vencimentos", "expurgar_reidentificacoes"]


class Command(BaseCommand):
    help = "Roda as rotinas diárias e avisa o monitor externo (Healthchecks.io)."

    def handle(self, *args, **options):
        inicio = timezone.now()
        monitor.avisar("inicio")

        problemas = []
        for rotina in ROTINAS:
            try:
                call_command(rotina, stdout=self.stdout)
            except Exception as exc:
                problemas.append(f"{rotina}: {type(exc).__name__}: {exc}"[:300])

        execucoes = ExecucaoRotina.objects.filter(data_hora__gte=inicio)
        for rotina in ROTINAS:
            ultima = execucoes.filter(rotina=rotina).order_by("-data_hora").first()
            if ultima is None:
                if not any(p.startswith(rotina) for p in problemas):
                    problemas.append(f"{rotina}: execução não registrada")
            elif not ultima.sucesso:
                problemas.append(f"{rotina}: terminou com falha (ver Registros e auditoria)")

        resumo = "\n".join(
            f"{e.rotina}: avaliados {e.avaliados}, notificados {e.notificados}, "
            f"ignorados {e.ignorados}, sucesso {e.sucesso}"
            for e in execucoes.order_by("data_hora"))

        if problemas:
            monitor.avisar("falha", "\n".join(problemas + [resumo]))
            raise CommandError("Rotinas com falha: " + "; ".join(problemas))

        monitor.avisar("sucesso", resumo)
        self.stdout.write(self.style.SUCCESS("Rotinas concluídas e monitor avisado."))
