"""RN-33 - aceite do termo de uso versionado.

O texto de cada versão é publicado pelo superusuário no Django Admin. Mesmo vindo de quem
tem acesso total, o HTML é limpo na exibição: só formatação de texto, sem script, estilo
nem atributo de evento (defesa em profundidade junto da Content-Security-Policy).
"""
import nh3
from django.db import IntegrityError, transaction

from auditoria.models import LogSistema

from .models import AceiteTermo, TermoUso

TAGS_TERMO = {"h2", "h3", "h4", "p", "br", "ul", "ol", "li", "strong", "em", "b", "i",
              "table", "thead", "tbody", "tr", "th", "td", "a"}
ATRIBUTOS_TERMO = {"a": {"href"}}


def sanitizar_termo(html):
    return nh3.clean(html or "", tags=TAGS_TERMO, attributes=ATRIBUTOS_TERMO,
                     url_schemes={"https", "mailto"}, link_rel="noopener noreferrer")


def registrar_aceite(usuario, ip=None):
    """Grava o aceite da versão vigente. Devolve o aceite (o já existente, se houver)."""
    termo = TermoUso.vigente()
    if termo is None:
        return None
    anterior = usuario.ultimo_aceite
    try:
        with transaction.atomic():
            aceite = AceiteTermo.objects.create(usuario=usuario, termo=termo, ip=ip)
    except IntegrityError:   # dois envios simultâneos: o primeiro já registrou
        return AceiteTermo.objects.get(usuario=usuario, termo=termo)

    detalhe = f"Versão {termo.versao}"
    if anterior is not None:
        detalhe += f" (antes: versão {anterior.termo.versao})"
    LogSistema.objects.create(nivel=LogSistema.Nivel.INFO, evento="Termo de uso aceito",
                              detalhe=detalhe, usuario=usuario, ip=ip)
    return aceite
