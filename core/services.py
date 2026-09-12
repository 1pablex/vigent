"""
Regras de negócio centrais do Vigent para a entrega de 14/09.

Cobre apenas o necessário para login e para o fluxo de treinamento completo (conteúdo, avaliação de reação, prova, certificado).
"""
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from auditoria.models import LogSistema
from avaliacoes.models import AvaliacaoReacao, RespostaProva
from certificacao.models import Certificado
from treinamentos.models import Curso, Presenca, ProgressoAula


def registrar(nivel, evento, detalhe="", usuario=None, ip=None):
    return LogSistema.objects.create(
        nivel=nivel, evento=evento, detalhe=detalhe, usuario=usuario, ip=ip
    )


#RN-02/RN-04 visibilidade de cursos
def cursos_do_usuario(usuario):
    from django.db.models import Q
    por_departamento = Q(departamentos__departamento=usuario.departamento_id)
    individuais = Q(atribuicoes__usuario=usuario)
    return Curso.objects.filter(por_departamento | individuais).distinct()


def cursos_publicados_do_usuario(usuario):
    return [c for c in cursos_do_usuario(usuario) if c.publicado]


#RN-13/RN-14 situação de conformidade
def certificado_vigente(usuario, curso):
    return (Certificado.objects
            .filter(usuario=usuario, curso=curso)
            .order_by("-data_emissao", "-id")
            .first())


def situacao(usuario, curso):
    cert = certificado_vigente(usuario, curso)
    if cert is None:
        return "PENDENTE", None
    return cert.situacao, cert


#RN-05 presença
def registrar_presenca(usuario, curso):
    presenca, criada = Presenca.objects.get_or_create(usuario=usuario, curso=curso)
    if criada:
        registrar(LogSistema.Nivel.INFO, "Presença registrada",
                  f"Curso: {curso.nome}", usuario)
    return presenca, criada


#RN-23 progresso do conteudo
def progresso(usuario, aula):
    obj, _ = ProgressoAula.objects.get_or_create(usuario=usuario, aula=aula)
    return obj


def aula_concluida(usuario, aula):
    p = ProgressoAula.objects.filter(usuario=usuario, aula=aula).first()
    return bool(p and p.concluida)


def curso_concluido(usuario, curso):
    aulas = list(curso.aulas.all())
    return bool(aulas) and all(aula_concluida(usuario, a) for a in aulas)


def aula_liberada(usuario, aula):
    anterior = aula.curso.aulas.filter(ordem__lt=aula.ordem).order_by("-ordem").first()
    return anterior is None or aula_concluida(usuario, anterior)


#RN-06 reação obrigatória antes da prova
def tem_reacao(usuario, curso):
    return AvaliacaoReacao.objects.filter(usuario=usuario, curso=curso).exists()


def etapa_atual(usuario, curso):
    """1 conteúdo - 2 avaliação de reação - 3 prova."""
    if not curso_concluido(usuario, curso):
        return 1
    if not tem_reacao(usuario, curso):
        return 2
    return 3


#tentativas, reciclagem e certificado
def tentativas(usuario, curso):
    return RespostaProva.objects.filter(usuario=usuario, prova__curso=curso).count()


def reciclar(usuario, curso):
    """RN-19 que zera progresso, reação e tentativas; certificados anteriores ficam intactos."""
    ProgressoAula.objects.filter(usuario=usuario, aula__curso=curso).delete()
    AvaliacaoReacao.objects.filter(usuario=usuario, curso=curso).delete()
    RespostaProva.objects.filter(usuario=usuario, prova__curso=curso).delete()


def emitir_certificado(usuario, curso, nota):
    """RN-08/RN-21 que exige reação registrada e nota mínima e grava a versão vigente do curso."""
    if not tem_reacao(usuario, curso):
        raise ValueError("Certificado exige avaliação de reação registrada (RN-08).")
    if nota < curso.nota_minima:
        raise ValueError("Nota inferior à mínima exigida pelo curso (RN-08).")
    hoje = timezone.localdate()
    cert = Certificado.objects.create(
        usuario=usuario, curso=curso, nota_prova=nota, versao_curso=curso.versao,
        data_emissao=hoje,
        data_validade=hoje + relativedelta(months=curso.validade_meses),
    )
    registrar(LogSistema.Nivel.INFO, "Certificado emitido",
              f"{curso.nome} · nota {nota} · válido até {cert.data_validade:%d/%m/%Y}",
              usuario)
    return cert


def corrigir_prova(usuario, curso, marcadas):
    """RN-09/RN-19/RN-20 que corrige, grava a tentativa e devolve (nota, aprovado, reciclou)."""
    prova = curso.prova
    questoes = list(prova.questoes.prefetch_related("alternativas"))
    acertos = 0
    for q in questoes:
        escolhida = marcadas.get(str(q.id)) or marcadas.get(q.id)
        correta = next((a for a in q.alternativas.all() if a.correta), None)
        if correta and escolhida and int(escolhida) == correta.id:
            acertos += 1
    nota = round(acertos / len(questoes) * 10, 1) if questoes else 0

    tentativa = tentativas(usuario, curso) + 1
    RespostaProva.objects.create(usuario=usuario, prova=prova,
                                 numero_tentativa=tentativa, nota_obtida=nota)

    aprovado = nota >= float(curso.nota_minima)
    reciclou = False
    if not aprovado and tentativa >= curso.max_tentativas:
        reciclar(usuario, curso)
        reciclou = True
        registrar(LogSistema.Nivel.WARN, "Tentativas esgotadas",
                  f"{curso.nome} — curso reiniciado para reciclagem", usuario)
    return nota, aprovado, reciclou