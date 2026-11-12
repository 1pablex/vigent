"""IP de origem da requisição, usado no bloqueio de login por IP e na auditoria.

O cabeçalho X-Forwarded-For pode ser escrito pelo próprio cliente. Por isso ele só
é lido quando há proxies confiáveis na frente da aplicação (settings
VIGENT["PROXIES_CONFIAVEIS"]). Cada proxy acrescenta ao fim da lista o IP de quem
falou com ele; com N proxies, o IP do cliente é o N-ésimo a partir da direita.
O que vier antes dele foi escrito pelo cliente e é ignorado.
"""
import ipaddress
import os

from django.conf import settings


def _valido(valor):
    """Devolve o IP normalizado, ou None se o texto não for um IP."""
    try:
        return str(ipaddress.ip_address(valor.strip()))
    except (AttributeError, ValueError):
        return None


def ip_do_cliente(request):
    """IP de quem fez a requisição, ou None quando não for possível saber."""
    proxies = settings.VIGENT.get("PROXIES_CONFIAVEIS", 0)
    if proxies > 0:
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
        enderecos = [parte for parte in encaminhado.split(",") if parte.strip()]
        if len(enderecos) >= proxies:
            return _valido(enderecos[-proxies])
    return _valido(request.META.get("REMOTE_ADDR", ""))
