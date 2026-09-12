"""Popula o banco com os cursos de demonstração — cenário Nortex Soluções Ltda."""
from django.core.management.base import BaseCommand

from avaliacoes.models import Alternativa, Prova, Questao
from contas.models import Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, SlideAula


class Command(BaseCommand):
    help = "Cria os cursos de demonstração, com aulas, slides, prova e questões."

    def handle(self, *args, **options):
        deps = self._obter_departamentos()
        self._criar_cursos(deps)
        self.stdout.write(self.style.SUCCESS("Concluído."))

    # ── departamentos ────────────────────────────────────────────
    def _obter_departamentos(self):
        """Usa get_or_create para funcionar mesmo se este comando rodar sozinho,
        antes do carregar_dados_colaboradores."""
        deps = {}
        for nome in ["Vendas", "Operações", "Sala Limpa"]:
            dep, criado = Departamento.objects.get_or_create(nome=nome)
            deps[nome] = dep
            if criado:
                self.stdout.write(f"Departamento criado: {nome}")
        return deps

    # ── cursos ───────────────────────────────────────────────────
    def _criar_cursos(self, deps):
        todos = [deps["Vendas"], deps["Operações"], deps["Sala Limpa"]]

        self._criar_curso(
            nome="LGPD — Proteção de Dados",
            categoria="Compliance",
            carga_horaria="2 horas",
            departamentos=todos,
            aulas=[
                ("Conceitos fundamentais da LGPD", [
                    ("O que é a LGPD",
                     "A Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018) "
                     "estabelece regras sobre coleta, uso e armazenamento de dados "
                     "pessoais no Brasil."),
                    ("Dados pessoais e dados sensíveis",
                     "Dados pessoais identificam uma pessoa; dados sensíveis (saúde, "
                     "biometria, origem racial, entre outros) exigem cuidado adicional "
                     "no tratamento."),
                    ("Responsabilidade de cada colaborador",
                     "Todo colaborador que acessa dados de clientes ou de outros "
                     "colaboradores é responsável por tratá-los apenas para a "
                     "finalidade autorizada."),
                ]),
            ],
            questoes=[
                ("O que a LGPD regula?", [
                    ("A", "Apenas dados de cartão de crédito", False),
                    ("B", "A coleta, o uso e o armazenamento de dados pessoais", True),
                    ("C", "Somente dados de empresas públicas", False),
                    ("D", "Apenas comunicação por e-mail corporativo", False),
                ]),
                ("São exemplos de dados sensíveis, EXCETO:", [
                    ("A", "Dados de saúde", False),
                    ("B", "Biometria", False),
                    ("C", "Cargo ocupado na empresa", True),
                    ("D", "Origem racial ou étnica", False),
                ]),
                ("Um colaborador que acessa dados de clientes deve:", [
                    ("A", "Usar os dados apenas para a finalidade autorizada", True),
                    ("B", "Compartilhar livremente com colegas de outras áreas", False),
                    ("C", "Salvar cópias em dispositivo pessoal", False),
                    ("D", "Ignorar a política de privacidade da empresa", False),
                ]),
            ],
        )

        self._criar_curso(
            nome="Parametrização de Sala Limpa",
            categoria="Operacional",
            carga_horaria="3 horas",
            departamentos=[deps["Sala Limpa"]],
            aulas=[
                ("Procedimentos de sala limpa", [
                    ("O que é uma sala limpa",
                     "Ambiente controlado que limita a presença de partículas, "
                     "contaminantes e microrganismos, essencial para processos "
                     "sensíveis de produção."),
                    ("Classificação e monitoramento",
                     "Salas limpas são classificadas pela quantidade máxima de "
                     "partículas por metro cúbico de ar, monitorada continuamente."),
                    ("Paramentação obrigatória",
                     "O uso correto de toucas, luvas, aventais e calçados específicos "
                     "é obrigatório antes de qualquer acesso à área controlada."),
                ]),
            ],
            questoes=[
                ("O principal objetivo de uma sala limpa é:", [
                    ("A", "Reduzir custos de energia", False),
                    ("B", "Controlar a quantidade de partículas e contaminantes no ambiente", True),
                    ("C", "Aumentar a velocidade de produção", False),
                    ("D", "Eliminar a necessidade de paramentação", False),
                ]),
                ("A paramentação antes de entrar na sala limpa é:", [
                    ("A", "Opcional, conforme o turno", False),
                    ("B", "Obrigatória para qualquer acesso à área controlada", True),
                    ("C", "Necessária apenas para visitantes", False),
                    ("D", "Dispensável para operações rápidas", False),
                ]),
                ("A classificação de uma sala limpa é baseada em:", [
                    ("A", "Número de colaboradores na área", False),
                    ("B", "Temperatura ambiente", False),
                    ("C", "Quantidade máxima de partículas por metro cúbico de ar", True),
                    ("D", "Quantidade de equipamentos instalados", False),
                ]),
            ],
        )

        self._criar_curso(
            nome="Código de Conduta Ética",
            categoria="Ético-legal",
            carga_horaria="2 horas",
            departamentos=todos,
            aulas=[
                ("Princípios do código de conduta", [
                    ("Por que existe um código",
                     "O código de conduta traduz os valores da organização em "
                     "orientações práticas de comportamento, oferecendo referência "
                     "para decisões em situações de ambiguidade."),
                    ("Conflito de interesse",
                     "Ocorre quando interesses pessoais podem influenciar decisões "
                     "profissionais — deve ser sempre declarado à liderança ou ao "
                     "compliance."),
                    ("Canal de denúncias",
                     "Permite relato, inclusive anônimo, de condutas que violem o "
                     "código, com vedação expressa a qualquer retaliação contra quem "
                     "denuncia de boa-fé."),
                ]),
            ],
            questoes=[
                ("Identificado possível conflito de interesse com fornecedor, a conduta correta é:", [
                    ("A", "Resolver a situação por conta própria, sem informar ninguém", False),
                    ("B", "Reportar o conflito ao canal de compliance antes de prosseguir", True),
                    ("C", "Prosseguir normalmente, já que não há prova de irregularidade", False),
                    ("D", "Repassar a negociação a um colega sem justificar o motivo", False),
                ]),
                ("Sobre o canal de denúncias, é correto afirmar:", [
                    ("A", "Exige sempre identificação do denunciante", False),
                    ("B", "Permite relato anônimo e veda retaliação a quem relata de boa-fé", True),
                    ("C", "Destina-se exclusivamente a questões financeiras", False),
                    ("D", "É administrado pela liderança direta do denunciante", False),
                ]),
                ("Constitui exemplo de conflito de interesse:", [
                    ("A", "Solicitar férias no mesmo período que um colega", False),
                    ("B", "Contratar fornecedor com vínculo familiar sem declarar a relação", True),
                    ("C", "Discordar publicamente de uma decisão da liderança", False),
                    ("D", "Recusar participação em projeto por sobrecarga", False),
                ]),
                ("A retaliação contra quem relata de boa-fé:", [
                    ("A", "É tolerada quando o relato se mostra improcedente", False),
                    ("B", "Constitui, por si só, violação do código de conduta", True),
                    ("C", "Depende de avaliação da liderança envolvida", False),
                    ("D", "Só é vedada em relatos identificados", False),
                ]),
                ("O código de conduta serve principalmente para:", [
                    ("A", "Substituir a legislação trabalhista aplicável", False),
                    ("B", "Traduzir os valores da organização em orientações práticas de comportamento", True),
                    ("C", "Definir metas de desempenho por área", False),
                    ("D", "Regular a política de remuneração variável", False),
                ]),
            ],
        )

    def _criar_curso(self, nome, categoria, carga_horaria, departamentos, aulas, questoes):
        curso, criado = Curso.objects.get_or_create(
            nome=nome,
            defaults={"categoria": categoria, "carga_horaria": carga_horaria},
        )
        if not criado:
            self.stdout.write(f"Curso já existe, pulando: {nome}")
            return
        self.stdout.write(self.style.SUCCESS(f"Curso criado: {nome}"))

        for dep in departamentos:
            CursoDepartamento.objects.get_or_create(curso=curso, departamento=dep)

        for ordem, (titulo_aula, slides) in enumerate(aulas, start=1):
            aula = Aula.objects.create(curso=curso, ordem=ordem, titulo=titulo_aula)
            for s_ordem, (titulo_slide, corpo) in enumerate(slides):
                SlideAula.objects.create(
                    aula=aula, ordem=s_ordem, titulo=titulo_slide, corpo=corpo)

        prova = Prova.objects.create(curso=curso)
        for q_ordem, (enunciado, alternativas) in enumerate(questoes, start=1):
            questao = Questao.objects.create(
                prova=prova, ordem=q_ordem, enunciado=enunciado)
            for letra, texto, correta in alternativas:
                Alternativa.objects.create(
                    questao=questao, letra=letra, texto=texto, correta=correta)

        self.stdout.write(
            f"  {len(aulas)} aula(s), {len(questoes)} questão(ões), "
            f"{len(departamentos)} departamento(s) vinculado(s)")