"""Gestão de cursos pelo RH: dados do curso, aulas com slides e questões da prova."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from auditoria.models import LogSistema
from avaliacoes.models import Questao
from core import services
from treinamentos.forms import AulaForm, CursoForm, QuestaoForm, SlideFormSet
from treinamentos.models import Aula, Curso


def rh_obrigatorio(view):
    @login_required
    @wraps(view)
    def _view(request, *args, **kwargs):
        if not request.user.e_rh:
            return redirect("treinamentos:inicio")
        return view(request, *args, **kwargs)
    return _view


@rh_obrigatorio
def lista(request):
    busca = (request.GET.get("busca") or "").strip()
    cursos = (Curso.objects
              .annotate(total_aulas=Count("aulas", distinct=True),
                        total_questoes=Count("prova__questoes", distinct=True))
              .prefetch_related("departamentos__departamento"))
    if busca:
        cursos = cursos.filter(Q(nome__icontains=busca) | Q(categoria__icontains=busca))
    return render(request, "treinamentos/rh/lista.html", {"cursos": cursos, "busca": busca})


@rh_obrigatorio
def novo(request):
    form = CursoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        curso = form.save()
        services.registrar(LogSistema.Nivel.INFO, "Curso cadastrado", curso.nome, request.user)
        messages.success(request, "Curso criado. Agora cadastre as aulas e as questões da prova.")
        return redirect("cursos_rh:editar", curso_id=curso.id)
    return render(request, "treinamentos/rh/curso_form.html", {"form": form, "curso": None})


@rh_obrigatorio
def editar(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    form = CursoForm(request.POST or None, request.FILES or None, instance=curso)
    if request.method == "POST" and form.is_valid():
        form.save()
        services.registrar(LogSistema.Nivel.INFO, "Curso alterado", curso.nome, request.user)
        messages.success(request, "Dados do curso salvos.")
        return redirect("cursos_rh:editar", curso_id=curso.id)

    prova = getattr(curso, "prova", None)
    return render(request, "treinamentos/rh/curso_form.html", {
        "form": form, "curso": curso,
        "aulas": curso.aulas.annotate(total_slides=Count("slides")),
        "questoes": prova.questoes.prefetch_related("alternativas") if prova else [],
    })


def _salvar_aula(request, curso, aula):
    form = AulaForm(request.POST or None, instance=aula, curso=curso)
    slides = SlideFormSet(request.POST or None, request.FILES or None,
                          instance=aula or Aula(curso=curso), prefix="slides")
    if request.method == "POST" and form.is_valid() and slides.is_valid():
        aula = form.save()
        slides.instance = aula
        slides.save()
        services.registrar(LogSistema.Nivel.INFO, "Aula salva",
                           f"{curso.nome} - aula {aula.ordem}: {aula.titulo}", request.user)
        messages.success(request, f"Aula {aula.ordem} salva.")
        if "continuar" in request.POST:
            return redirect("cursos_rh:aula_editar", curso_id=curso.id, aula_id=aula.id)
        return redirect("cursos_rh:editar", curso_id=curso.id)
    return render(request, "treinamentos/rh/aula_form.html",
                  {"curso": curso, "aula": aula, "form": form, "slides": slides})


@rh_obrigatorio
def aula_nova(request, curso_id):
    return _salvar_aula(request, get_object_or_404(Curso, pk=curso_id), None)


@rh_obrigatorio
def aula_editar(request, curso_id, aula_id):
    aula = get_object_or_404(Aula, pk=aula_id, curso_id=curso_id)
    return _salvar_aula(request, aula.curso, aula)


@rh_obrigatorio
def aula_excluir(request, curso_id, aula_id):
    aula = get_object_or_404(Aula, pk=aula_id, curso_id=curso_id)
    if request.method == "POST":
        aula.delete()
        services.registrar(LogSistema.Nivel.WARN, "Aula excluída",
                           f"{aula.curso.nome} - aula {aula.ordem}: {aula.titulo}", request.user)
        messages.success(request, f"Aula {aula.ordem} excluída.")
    return redirect("cursos_rh:editar", curso_id=curso_id)


def _salvar_questao(request, curso, questao):
    form = QuestaoForm(request.POST or None, prova=getattr(curso, "prova", None),
                       questao=questao)
    if request.method == "POST" and form.is_valid():
        questao = form.save(curso)
        services.registrar(LogSistema.Nivel.INFO, "Questão salva",
                           f"{curso.nome} - questão {questao.ordem}", request.user)
        messages.success(request, f"Questão {questao.ordem} salva.")
        if "outra" in request.POST:
            return redirect("cursos_rh:questao_nova", curso_id=curso.id)
        return redirect("cursos_rh:editar", curso_id=curso.id)
    return render(request, "treinamentos/rh/questao_form.html",
                  {"curso": curso, "questao": questao, "form": form})


@rh_obrigatorio
def questao_nova(request, curso_id):
    return _salvar_questao(request, get_object_or_404(Curso, pk=curso_id), None)


@rh_obrigatorio
def questao_editar(request, curso_id, questao_id):
    questao = get_object_or_404(Questao, pk=questao_id, prova__curso_id=curso_id)
    return _salvar_questao(request, questao.prova.curso, questao)


@rh_obrigatorio
def questao_excluir(request, curso_id, questao_id):
    questao = get_object_or_404(Questao, pk=questao_id, prova__curso_id=curso_id)
    if request.method == "POST":
        questao.delete()
        services.registrar(LogSistema.Nivel.WARN, "Questão excluída",
                           f"{questao.prova.curso.nome} - questão {questao.ordem}", request.user)
        messages.success(request, f"Questão {questao.ordem} excluída.")
    return redirect("cursos_rh:editar", curso_id=curso_id)
