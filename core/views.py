from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.core.paginator import Paginator

from contas.models import Departamento
from contas.models import Usuario
from auditoria.models import EmailEnviado, ExecucaoRotina, LogSistema, RegistroAcesso
"""apos login (tela de inicio) """
@login_required
def inicio(request):
    if request.user.e_rh:
        return redirect("core:rh_colaboradores")
    return redirect("treinamentos:inicio")

@login_required
def rh_colaboradores(request):
    if not request.user.e_rh:
        return redirect("treinamentos:inicio")

    busca = (request.GET.get("busca") or "").strip()
    departamento_id = request.GET.get("departamento") or "TODOS"

    colaboradores = Usuario.objects.select_related("departamento").order_by("matricula")
    if busca:
        colaboradores = colaboradores.filter(
            Q(matricula__icontains=busca) | Q(nome__icontains=busca) | Q(email__icontains=busca)
        )
    if departamento_id != "TODOS":
        colaboradores = colaboradores.filter(departamento_id=departamento_id)

    return render(request, "core/rh_colaboradores.html", {
        "secao": "colaboradores",
        "colaboradores": colaboradores,
        "departamentos": Departamento.objects.all(),
        "departamento_selecionado": departamento_id,
        "busca": busca,
        "total_ativos": Usuario.objects.filter(is_active=True).count(),
        "total_desligados": Usuario.objects.filter(is_active=False).count(),
    })

@login_required
def rh_auditoria(request):
    if not request.user.e_rh:
        return redirect("treinamentos:inicio")

    busca = (request.GET.get("busca") or "").strip()
    nivel = request.GET.get("nivel") or "TODOS"
    por_pagina = request.GET.get("por_pagina") or "10"
    if por_pagina not in ("10", "15", "20"):
        por_pagina = "10"
    n = int(por_pagina)

    logs_qs = LogSistema.objects.all()
    if busca:
        logs_qs = logs_qs.filter(Q(evento__icontains=busca) | Q(detalhe__icontains=busca))
    if nivel != "TODOS":
        logs_qs = logs_qs.filter(nivel=nivel)

    pagina_logs = Paginator(logs_qs, n).get_page(request.GET.get("pagina_logs") or 1)
    pagina_jobs = Paginator(ExecucaoRotina.objects.all(), n).get_page(request.GET.get("pagina_jobs") or 1)
    pagina_email = Paginator(EmailEnviado.objects.all(), n).get_page(request.GET.get("pagina_email") or 1)
    pagina_acesso = Paginator(RegistroAcesso.objects.all(), n).get_page(request.GET.get("pagina_acesso") or 1)

    return render(request, "core/rh_auditoria.html", {
        "secao": "auditoria",
        "busca": busca,
        "nivel_selecionado": nivel,
        "por_pagina": por_pagina,
        "pagina_logs": pagina_logs,
        "pagina_jobs": pagina_jobs,
        "pagina_email": pagina_email,
        "pagina_acesso": pagina_acesso,
        "total_logs": LogSistema.objects.count(),
        "total_warn": LogSistema.objects.filter(nivel=LogSistema.Nivel.WARN).count(),
        "total_erro": LogSistema.objects.filter(nivel=LogSistema.Nivel.ERRO).count(),
    })