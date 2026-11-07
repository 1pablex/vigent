"""Popula o banco com uma base grande de colaboradores para o dashboard de indicadores.

Cenário Nortex Soluções Ltda.: 60 colaboradores em 5 departamentos, com a situação de
cada treinamento distribuída entre em dia, vencendo, vencido e pendente. Cada
departamento tem um perfil diferente (acima da meta, na média, crítico), para que os
gráficos de conformidade contem uma história.

- Só roda com DEBUG=True: nunca popula o banco de produção com dados fictícios.
- Os e-mails usam o domínio reservado .invalid: nenhuma mensagem sai pelo Brevo.
- O sorteio usa semente fixa: os números do dashboard são os mesmos a cada execução.
- Rodar de novo recria a base; --limpar só remove. Os demais usuários não são tocados.
"""
import random
from datetime import datetime, time
from decimal import Decimal
from io import StringIO

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from avaliacoes.models import AvaliacaoReacao, RespostaProva
from certificacao.models import Certificado
from contas.models import Departamento, Usuario
from treinamentos.models import Curso, CursoDepartamento, ProgressoAula

DOMINIO = "exemplo.invalid"
SENHA = "123456"
SEMENTE = 2026
CURSOS_GERAIS = ["LGPD - Proteção de Dados", "Código de Conduta Ética"]
DEPARTAMENTOS_NOVOS = ["Financeiro", "TI"]

# departamento: (quantidade, cargos, pesos de em dia / vencendo / vencido / pendente)
PERFIS = {
    "Vendas": (14, ["Analista de Vendas", "Executivo de Contas", "Assistente Comercial"],
               (92, 6, 1, 1)),        # acima da meta
    "Financeiro": (10, ["Analista Financeiro", "Assistente Contábil", "Tesoureiro"],
                   (70, 18, 6, 6)),
    "TI": (12, ["Desenvolvedor", "Analista de Suporte", "Analista de Infraestrutura"],
           (52, 14, 16, 18)),
    "Operações": (14, ["Operador de Produção", "Supervisor de Turno", "Técnico de Manutenção"],
                  (50, 14, 18, 18)),
    "Sala Limpa": (10, ["Técnico de Sala Limpa", "Operador de Sala Limpa"],
                   (30, 15, 27, 28)),  # crítico
}

# curso: (média de didática, média de entendimento) - dá contraste ao gráfico de reação
REACAO_POR_CURSO = {
    "LGPD - Proteção de Dados": (8.6, 7.4),
    "Código de Conduta Ética": (7.8, 8.7),
    "Parametrização de Sala Limpa": (6.9, 6.1),
}

NOMES = ["Ana", "Bruno", "Camila", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique",
         "Isabela", "João", "Juliana", "Lucas", "Mariana", "Mateus", "Natália", "Otávio",
         "Patrícia", "Rafael", "Renata", "Rodrigo", "Sabrina", "Thiago", "Vanessa", "Vinícius",
         "Larissa", "Gustavo", "Letícia", "Diego", "Beatriz", "André"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves",
              "Pereira", "Gomes", "Martins", "Araújo", "Ribeiro", "Carvalho", "Rocha",
              "Almeida", "Nascimento", "Barbosa", "Moreira", "Cardoso", "Teixeira"]

SEM_ACENTO = str.maketrans("áâãàéêíóôõúçÁÉÍÓÚ", "aaaaeeiooouc" + "AEIOU")


class Command(BaseCommand):
    help = "Cria 60 colaboradores fictícios com treinamentos em dia, vencendo, vencidos e pendentes."

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true",
                            help="Só remove os colaboradores criados por este comando.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Seed de demonstração bloqueada: só roda com DEBUG=True, "
                               "para não popular o banco de produção com dados fictícios.")

        removidos = self._limpar()
        if options["limpar"]:
            self.stdout.write(self.style.SUCCESS(f"Removidos {removidos} colaboradores de demonstração."))
            return

        call_command("carregar_dados_colaboradores", stdout=self._silencio())
        call_command("carregar_dados_cursos", stdout=self._silencio())
        resumo = self._popular(random.Random(SEMENTE))

        self.stdout.write(self.style.SUCCESS(
            f"Criados {resumo['colaboradores']} colaboradores em {len(PERFIS)} departamentos."))
        self.stdout.write("Pares colaborador x curso: " + " | ".join(
            f"{k}: {v}" for k, v in resumo["situacoes"].items()))
        self.stdout.write(f"Login de qualquer um: <nome.sobrenome>@{DOMINIO} / senha {SENHA}")

    @staticmethod
    def _silencio():
        return StringIO()

    # ── limpeza ──────────────────────────────────────────────────
    @transaction.atomic
    def _limpar(self):
        seed = Usuario.objects.filter(email__endswith=f"@{DOMINIO}")
        quantidade = seed.count()
        seed.delete()   # certificados, reações, provas e progresso vão junto (CASCADE)
        for nome in DEPARTAMENTOS_NOVOS:
            dep = Departamento.objects.filter(nome=nome).first()
            if dep and not dep.colaboradores.exists():
                CursoDepartamento.objects.filter(departamento=dep).delete()
                dep.delete()
        return quantidade

    # ── criação ──────────────────────────────────────────────────
    @transaction.atomic
    def _popular(self, rng):
        hoje = timezone.localdate()
        cursos = {c.nome: c for c in Curso.objects.prefetch_related("aulas__slides", "prova")}
        faltando = [n for n in REACAO_POR_CURSO if n not in cursos]
        if faltando:
            raise CommandError(f"Cursos não encontrados: {', '.join(faltando)}")

        for nome in DEPARTAMENTOS_NOVOS:
            dep, _ = Departamento.objects.get_or_create(nome=nome)
            for curso in CURSOS_GERAIS:   # cursos gerais valem para todos os departamentos
                CursoDepartamento.objects.get_or_create(curso=cursos[curso], departamento=dep)

        nomes = self._nomes_unicos(rng, sum(p[0] for p in PERFIS.values()))
        situacoes = {"EM DIA": 0, "VENCENDO": 0, "VENCIDO": 0, "PENDENTE": 0}
        criados = 0

        for dep_nome, (quantidade, cargos, pesos) in PERFIS.items():
            dep = Departamento.objects.get(nome=dep_nome)
            cursos_dep = [cursos[cd.curso.nome] for cd in
                          CursoDepartamento.objects.filter(departamento=dep).select_related("curso")
                          if cd.curso.nome in cursos]
            for _ in range(quantidade):
                nome = nomes.pop()
                usuario = Usuario.objects.create_user(
                    email=self._email(nome), nome=nome, password=SENHA,
                    cargo=rng.choice(cargos), departamento=dep,
                    senha_provisoria=False, aceitou_termos=True,
                    data_aceite_termos=timezone.now())
                criados += 1
                for curso in cursos_dep:
                    situacao = rng.choices(list(situacoes), weights=pesos)[0]
                    situacoes[situacao] += 1
                    self._registrar_treinamento(rng, usuario, curso, situacao, hoje)

        return {"colaboradores": criados, "situacoes": situacoes}

    def _registrar_treinamento(self, rng, usuario, curso, situacao, hoje):
        aulas = list(curso.aulas.all())
        if situacao == "PENDENTE":
            if aulas and rng.random() < 0.5:   # metade começou e parou no meio
                slides = [s.ordem for s in aulas[0].slides.all()]
                ProgressoAula.objects.create(usuario=usuario, aula=aulas[0],
                                             slides_vistos=slides[:max(1, len(slides) // 2)])
            return

        dias_para_vencer = {
            "EM DIA": rng.randint(31, 330),    # cobre também as faixas de 31-60 e 61-90
            "VENCENDO": rng.randint(0, 30),
            "VENCIDO": -rng.randint(1, 200),
        }[situacao]
        validade = hoje + relativedelta(days=dias_para_vencer)
        emissao = validade - relativedelta(months=curso.validade_meses)
        momento = timezone.make_aware(datetime.combine(emissao, time(rng.randint(8, 17))))

        for aula in aulas:
            ProgressoAula.objects.create(
                usuario=usuario, aula=aula, concluida=True, data_conclusao=momento,
                slides_vistos=[s.ordem for s in aula.slides.all()])

        didatica, entendimento = REACAO_POR_CURSO[curso.nome]
        AvaliacaoReacao.objects.create(
            usuario=usuario, curso=curso, data_resposta=momento,
            nota_didatica=self._nota(rng, didatica), nota_entendimento=self._nota(rng, entendimento))

        nota = self._nota_prova(rng, curso.nota_minima)
        if rng.random() < 0.25:   # um quarto reprovou na primeira tentativa
            RespostaProva.objects.create(usuario=usuario, prova=curso.prova, numero_tentativa=1,
                                         nota_obtida=curso.nota_minima - Decimal("1.5"),
                                         data_realizacao=momento - relativedelta(days=1))
            tentativa = 2
        else:
            tentativa = 1
        RespostaProva.objects.create(usuario=usuario, prova=curso.prova, numero_tentativa=tentativa,
                                     nota_obtida=nota, data_realizacao=momento)
        Certificado.objects.create(usuario=usuario, curso=curso, nota_prova=nota,
                                   versao_curso=curso.versao, data_emissao=emissao,
                                   data_validade=validade)

    # ── auxiliares ───────────────────────────────────────────────
    @staticmethod
    def _nomes_unicos(rng, quantidade):
        combinacoes = [f"{n} {s}" for n in NOMES for s in SOBRENOMES]
        return rng.sample(combinacoes, quantidade)

    @staticmethod
    def _email(nome):
        return nome.translate(SEM_ACENTO).lower().replace(" ", ".") + f"@{DOMINIO}"

    @staticmethod
    def _nota(rng, media):
        return max(1, min(10, round(rng.gauss(media, 1.2))))

    @staticmethod
    def _nota_prova(rng, minima):
        passos = int((Decimal("10") - minima) / Decimal("0.5"))
        return minima + Decimal("0.5") * rng.randint(0, passos)
