"""Aviso das rotinas diárias a um monitor externo (Healthchecks.io).

O monitor sabe que as rotinas devem rodar todo dia. Se o aviso de sucesso não chegar no
horário, ou se chegar um aviso de falha, ele alerta por e-mail. Assim uma falha do Cron Job
do Render não passa despercebida, e os dados do cofre de reidentificação (RN-35) não ficam
guardados além dos 90 dias sem ninguém saber.

O endereço de aviso (MONITOR_ROTINAS_URL) é secreto: quem o tiver consegue mandar avisos
falsos. Fica só no painel do Render. Sem ele (desenvolvimento e testes), nada é enviado.

O aviso nunca impede a rotina: se o monitor estiver fora do ar, a falha só é registrada.
"""
import urllib.request

from django.conf import settings

from auditoria.models import LogSistema

# Healthchecks.io: o endereço base indica sucesso; /start e /fail indicam início e falha.
SUFIXOS = {"inicio": "/start", "sucesso": "", "falha": "/fail"}
TEMPO_LIMITE_SEG = 10


def avisar(estado, resumo=""):
    """Envia o estado ("inicio", "sucesso" ou "falha") ao monitor. Devolve True se enviou."""
    base = (getattr(settings, "MONITOR_ROTINAS_URL", "") or "").rstrip("/")
    if not base:
        return False
    if not base.startswith("https://"):
        _registrar_falha("MONITOR_ROTINAS_URL precisa começar com https://")
        return False

    pedido = urllib.request.Request(
        base + SUFIXOS[estado], data=resumo.encode("utf-8")[:10_000], method="POST",
        headers={"User-Agent": "vigent-rotinas"})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_SEG) as resposta:
            return 200 <= resposta.status < 300
    except Exception as exc:   # o monitor fora do ar não pode derrubar a rotina
        _registrar_falha(f"{type(exc).__name__}: {exc}"[:300])
        return False


def _registrar_falha(detalhe):
    # O endereço não entra no log: ele é o segredo que autentica os avisos.
    LogSistema.objects.create(nivel=LogSistema.Nivel.WARN,
                              evento="Falha ao avisar o monitor das rotinas", detalhe=detalhe)
