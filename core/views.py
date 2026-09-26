from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.core.paginator import Paginator
from django.core.management import call_command
from django.contrib import messages
from django.shortcuts import get_object_or_404
from treinamentos.models import Curso

from contas.models import Departamento
from contas.models import Usuario
from auditoria.models import EmailEnviado, ExecucaoRotina, LogSistema, RegistroAcesso
from core.correio import enviar_notificacao_reciclagem
from core import services
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

@login_required
def rh_conformidade(request):
    if not request.user.e_rh:
        return redirect("treinamentos:inicio")

    if request.method == "POST" and "rodar_rotina" in request.POST:
        call_command("verificar_vencimentos")
        messages.success(request, "Rotina de verificação executada.")
        return redirect("core:rh_conformidade")

    linhas_completas = services.matriz_conformidade()

    busca = (request.GET.get("busca") or "").strip().lower()
    situacao_filtro = request.GET.get("situacao") or "TODOS"

    linhas = linhas_completas
    if busca:
        linhas = [l for l in linhas if busca in l["usuario"].nome.lower()
                 or busca in l["usuario"].matricula.lower()
                 or busca in l["curso"].nome.lower()]
    if situacao_filtro != "TODOS":
        linhas = [l for l in linhas if l["situacao"] == situacao_filtro]

    return render(request, "core/rh_conformidade.html", {
        "secao": "conformidade",
        "busca": request.GET.get("busca") or "",
        "situacao_selecionada": situacao_filtro,
        "linhas": linhas,
        "total_linhas": len(linhas),
        "kpis": services.kpis_conformidade(linhas_completas),
        "departamentos": services.conformidade_por_departamento(linhas_completas),
        "qualidade": services.qualidade_percebida(linhas_completas),
        "ultima_execucao": ExecucaoRotina.objects.order_by("-data_hora").first(),
    })

@login_required
def rh_solicitar_reciclagem(request, usuario_id, curso_id):
    if not request.user.e_rh:
        return redirect("treinamentos:inicio")
    if request.method != "POST":
        return redirect("core:rh_conformidade")

    usuario = get_object_or_404(Usuario, pk=usuario_id)
    curso = get_object_or_404(Curso, pk=curso_id)

    services.reciclar(usuario, curso)
    enviar_notificacao_reciclagem(usuario, curso)
    services.registrar(LogSistema.Nivel.INFO, "Reciclagem solicitada pelo RH",
              f"{usuario.nome} - {curso.nome} - progresso reiniciado, colaborador notificado",
              request.user)
    messages.success(request,
        f"{usuario.nome} foi notificado por e-mail, e o treinamento em {curso.nome} foi reiniciado.")
    return redirect("core:rh_conformidade")