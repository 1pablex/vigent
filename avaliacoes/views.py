from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from auditoria.models import LogSistema
from avaliacoes.models import AvaliacaoReacao
from core import services
from treinamentos.models import Curso

"""Avaliação de reação e prova de conhecimento."""

@login_required
def reacao(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if curso not in services.cursos_do_usuario(request.user):
        return redirect("treinamentos:inicio")

    # RN-23 — só abre com todas as aulas concluídas
    if not services.curso_concluido(request.user, curso):
        messages.warning(request, "Conclua todas as aulas antes da avaliação de reação.")
        return redirect("treinamentos:curso", curso_id=curso.id)
    if services.tem_reacao(request.user, curso):
        return redirect("avaliacoes:prova", curso_id=curso.id)

    erro = None
    if request.method == "POST":
        try:
            didatica = int(request.POST.get("didatica") or 0)
            entendimento = int(request.POST.get("entendimento") or 0)
        except ValueError:
            didatica = entendimento = 0
        if not (1 <= didatica <= 10) or not (1 <= entendimento <= 10):
            erro = "Responda as duas questões para continuar."
        else:
            AvaliacaoReacao.objects.create(
                usuario=request.user, curso=curso, nota_didatica=didatica,
                nota_entendimento=entendimento,
                comentario=(request.POST.get("comentario") or "").strip(),
            )
            services.registrar(
                LogSistema.Nivel.INFO, "Avaliação de reação registrada",
                f"{curso.nome} · didática {didatica} · entendimento {entendimento}",
                request.user)
            return redirect("avaliacoes:prova", curso_id=curso.id)

    return render(request, "avaliacoes/reacao.html",
                  {"curso": curso, "erro": erro, "etapa": 2, "escala": range(1, 11)})

@login_required
def prova(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if curso not in services.cursos_do_usuario(request.user):
        return redirect("treinamentos:inicio")

    # RN-06 — a prova exige avaliação de reação registrada
    if not services.tem_reacao(request.user, curso):
        messages.warning(request, "Responda a avaliação de reação antes da prova.")
        return redirect("avaliacoes:reacao", curso_id=curso.id)

    prova = getattr(curso, "prova", None)
    if prova is None or not prova.questoes.exists():
        messages.error(request, "Este curso ainda não possui prova cadastrada.")
        return redirect("treinamentos:inicio")

    questoes = list(prova.questoes.prefetch_related("alternativas"))

    if request.method == "POST":
        marcadas = {str(q.id): request.POST.get(f"q{q.id}") for q in questoes}
        if any(v is None for v in marcadas.values()):
            return render(request, "avaliacoes/prova.html", {
                "curso": curso, "questoes": questoes, "etapa": 3,
                "tentativa": services.tentativas(request.user, curso) + 1,
                "erro": "Responda todas as questões antes de finalizar.",
                "marcadas": marcadas,
            })
        nota, aprovado, reciclou = services.corrigir_prova(request.user, curso, marcadas)
        certificado = None
        if aprovado:
            certificado = services.emitir_certificado(request.user, curso, nota)
        return render(request, "avaliacoes/resultado.html", {
            "curso": curso, "nota": nota, "aprovado": aprovado, "reciclou": reciclou,
            "certificado": certificado,
            "restantes": max(0, curso.max_tentativas - services.tentativas(request.user, curso)),
            "etapa": 3,
        })

    return render(request, "avaliacoes/prova.html", {
        "curso": curso, "questoes": questoes, "etapa": 3,
        "tentativa": services.tentativas(request.user, curso) + 1,
        "marcadas": {},
    })