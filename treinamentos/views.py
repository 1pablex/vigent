"""Fluxo do colaborador: lista de treinamentos e percurso do curso."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from relatorios import services
from treinamentos.models import Aula, Curso


@login_required
def meus_treinamentos(request):
    usuario = request.user
    itens = []
    for curso in services.cursos_publicados_do_usuario(usuario):
        sit, cert = services.situacao(usuario, curso)
        iniciado = curso.presencas.filter(usuario=usuario).exists()
        itens.append({
            "curso": curso, "situacao": sit, "certificado": cert,
            "em_andamento": iniciado and sit == "PENDENTE",
        })
    ordem = {"VENCIDO": 0, "VENCENDO": 1, "PENDENTE": 2, "EM DIA": 3}
    itens.sort(key=lambda i: ordem[i["situacao"]])
    return render(request, "treinamentos/inicio.html", {"itens": itens})


@login_required
def abrir_curso(request, curso_id):
    """Registra a presença (RN-05) e leva para a etapa correta do curso."""
    curso = get_object_or_404(Curso, pk=curso_id)
    if curso not in services.cursos_do_usuario(request.user):
        return redirect("treinamentos:inicio")      # RN-02

    services.registrar_presenca(request.user, curso)
    return redirect("treinamentos:curso", curso_id=curso.id)

#check-in para saber se o usuario ja deveria estar nessa etapa
@login_required
def curso(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if curso not in services.cursos_do_usuario(request.user):
        return redirect("treinamentos:inicio")

    etapa = services.etapa_atual(request.user, curso)
    if etapa == 2:
        return redirect("avaliacoes:reacao", curso_id=curso.id)
    if etapa == 3:
        return redirect("avaliacoes:prova", curso_id=curso.id)

    aulas = list(curso.aulas.prefetch_related("slides"))
    atual = next((a for a in aulas if not services.aula_concluida(request.user, a)), aulas[-1])
    if request.GET.get("aula"):
        pedida = next((a for a in aulas if str(a.id) == request.GET["aula"]), None)
        if pedida and services.aula_liberada(request.user, pedida):
            atual = pedida

    prog = services.progresso(request.user, atual)
    slides = list(atual.slides.all())

    #o colaborador pode revisitar o que já viu e avançar um slide por vez
    vistos_ate_agora = prog.slides_vistos or []
    permitidos = set(vistos_ate_agora)
    permitidos.add(max(vistos_ate_agora) + 1 if vistos_ate_agora else 0)

    indice = max(vistos_ate_agora) if vistos_ate_agora else 0
    if request.GET.get("slide"):
        try:
            pedido = int(request.GET["slide"])
            if pedido in permitidos:
                indice = max(0, min(pedido, len(slides) - 1))
        except ValueError:
            pass
    prog.registrar_slide(indice)

    vistos = prog.slides_vistos or []
    proxima = curso.aulas.filter(ordem__gt=atual.ordem).order_by("ordem").first()

    navegacao = [{
        "aula": a,
        "atual": a.id == atual.id,
        "concluida": services.aula_concluida(request.user, a),
        "liberada": services.aula_liberada(request.user, a),
    } for a in aulas]

    marcadores = [{"ordem": n, "visto": n in vistos, "atual": n == indice}
                  for n in range(len(slides))]

    return render(request, "treinamentos/curso.html", {
        "curso": curso, "aula": atual, "total_aulas": len(aulas),
        "navegacao": navegacao, "marcadores": marcadores,
        "slide": slides[indice] if slides else None,
        "indice": indice, "posicao": indice + 1, "total_slides": len(slides),
        "anterior": indice - 1 if indice > 0 else None,
        "seguinte": indice + 1 if indice < len(slides) - 1 else None,
        "percentual": round(len(vistos) / len(slides) * 100) if slides else 0,
        "concluida": services.aula_concluida(request.user, atual),
        "curso_concluido": services.curso_concluido(request.user, curso),
        "proxima": proxima,
        "presenca": curso.presencas.filter(usuario=request.user).first(),
        "etapa": 1,
    })