"""Aba "Termo de uso" do painel do RH (RN-33).

O RH acompanha as versões e a adesão e lança versões novas. Uma versão publicada nunca é
alterada: "editar" é partir do texto vigente e publicar outra versão, que todos precisam
aceitar no próximo acesso. A publicação só acontece depois da pré-visualização.
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe

from auditoria.models import LogSistema
from core.services import registrar
from treinamentos.views_rh import rh_obrigatorio

from .forms import NovaVersaoTermoForm, proxima_versao
from .models import TermoUso, Usuario
from .rede import ip_do_cliente
from .termos import formatar_termo, registrar_aceite


def _contas_que_aceitam():
    """Quem precisa aceitar o termo: contas ativas que já passaram da senha provisória."""
    return Usuario.objects.filter(is_active=True, pseudonimizado=False, senha_provisoria=False)


@rh_obrigatorio
def lista(request):
    vigente = TermoUso.vigente()
    versoes = (TermoUso.objects.select_related("publicado_por")
               .annotate(total_aceites=Count("aceites")))
    contas = _contas_que_aceitam()
    aceitaram = contas.filter(aceites_termo__termo=vigente).count() if vigente else 0
    total = contas.count()
    return render(request, "contas/rh/termo_lista.html", {
        "vigente": vigente, "versoes": versoes,
        "aceitaram": aceitaram, "total_contas": total,
        "pendentes": total - aceitaram,
        "percentual": round(aceitaram / total * 100) if total else 0,
    })


@rh_obrigatorio
def ver(request, termo_id):
    termo = get_object_or_404(TermoUso.objects.select_related("publicado_por"), pk=termo_id)
    return render(request, "contas/rh/termo_ver.html", {
        "termo": termo, "vigente": TermoUso.vigente(),
        "conteudo": mark_safe(formatar_termo(termo.conteudo)),
    })


@rh_obrigatorio
def nova(request):
    vigente = TermoUso.vigente()
    acao = request.POST.get("acao") if request.method == "POST" else None

    if acao is None:   # abre já com o texto vigente, para o RH ajustar só o que muda
        form = NovaVersaoTermoForm(initial={
            "versao": proxima_versao(vigente),
            "conteudo": vigente.conteudo if vigente else ""})
        return _tela(request, form, vigente)

    form = NovaVersaoTermoForm(request.POST)
    if acao == "editar":   # voltou da pré-visualização: mantém o que foi digitado
        return _tela(request, NovaVersaoTermoForm(initial=request.POST.dict()), vigente)
    if not form.is_valid():
        return _tela(request, form, vigente)
    if acao == "previsualizar":
        return _tela(request, form, vigente, previa=formatar_termo(form.cleaned_data["conteudo"]))
    if acao != "publicar":
        return redirect("termo_rh:nova")

    with transaction.atomic():
        termo = TermoUso.objects.create(publicado_por=request.user, **form.cleaned_data)
        registrar(LogSistema.Nivel.WARN, "Nova versão do termo de uso publicada",
                  f"Versão {termo.versao}: todos precisam aceitar no próximo acesso",
                  request.user, ip_do_cliente(request))
    # quem publicou escreveu o texto: o aceite dele já fica registrado
    registrar_aceite(request.user, ip_do_cliente(request))
    messages.success(request, f"Versão {termo.versao} publicada. Os colaboradores verão o "
                              "termo atualizado no próximo acesso.")
    return redirect("termo_rh:lista")


def _tela(request, form, vigente, previa=None):
    return render(request, "contas/rh/termo_nova.html", {
        "form": form, "vigente": vigente,
        "previa": mark_safe(previa) if previa is not None else None,
    })
