"""RN-33 - aceite do termo de uso versionado.

O texto de cada versão é publicado pelo superusuário no Django Admin. Mesmo vindo de quem
tem acesso total, o HTML é limpo na exibição: só formatação de texto, sem script, estilo
nem atributo de evento (defesa em profundidade junto da Content-Security-Policy).
"""
import re
from html import escape

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


# --- Texto puro: quem publica pode digitar o termo sem HTML -------------------------------
TEM_HTML = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
TITULO = re.compile(r"^\d+(\.\d+)*\.?\s+\S")            # "1. Quem somos", "2.1 Prazos"
SEPARADOR_TABELA = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


def formatar_termo(conteudo):
    """HTML pronto para exibir. Conteúdo com HTML segue como está (versões 1.0 e 1.1);
    texto puro é convertido. Nos dois casos o resultado passa pela limpeza do nh3.

    No texto puro: linha em branco separa blocos; "1. Título" sozinho na linha vira título
    de seção; linhas com "- " viram lista; linhas com "|" viram tabela (a primeira linha é
    o cabeçalho e "|---|---|" é opcional); o resto vira parágrafo. Tudo o que foi digitado
    é escapado: "<script>" aparece como texto.
    """
    conteudo = (conteudo or "").replace("\r\n", "\n").strip()
    if TEM_HTML.search(conteudo):
        return sanitizar_termo(conteudo)
    blocos = [b.strip("\n") for b in re.split(r"\n\s*\n", conteudo) if b.strip()]
    return sanitizar_termo("\n".join(_bloco([linha.strip() for linha in b.split("\n")])
                                     for b in blocos))


def _bloco(linhas):
    if len(linhas) > 1 and TITULO.match(linhas[0]) and not linhas[0].startswith(("-", "|")):
        return f"<h3>{escape(linhas[0])}</h3>\n" + _bloco(linhas[1:])
    if all(linha.startswith("|") for linha in linhas):
        return _tabela(linhas)
    if all(linha.startswith("- ") for linha in linhas):
        itens = "".join(f"<li>{escape(linha[2:].strip())}</li>" for linha in linhas)
        return f"<ul>{itens}</ul>"
    if len(linhas) == 1 and TITULO.match(linhas[0]):
        return f"<h3>{escape(linhas[0])}</h3>"
    return "<p>" + "<br>".join(escape(linha) for linha in linhas) + "</p>"


def _tabela(linhas):
    def celulas(linha):
        return [c.strip() for c in linha.strip().strip("|").split("|")]

    linhas = [linha for linha in linhas if not SEPARADOR_TABELA.match(linha)]
    cabecalho, corpo = celulas(linhas[0]), [celulas(linha) for linha in linhas[1:]]
    thead = "".join(f"<th>{escape(c)}</th>" for c in cabecalho)
    tbody = "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in linha) + "</tr>"
                    for linha in corpo)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


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
