from django.contrib import admin

from .models import Alternativa, AvaliacaoReacao, Prova, Questao, RespostaProva


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 4
    max_num = 5


@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = ["prova", "ordem", "enunciado"]
    list_filter = ["prova__curso"]
    inlines = [AlternativaInline]


class QuestaoInline(admin.TabularInline):
    model = Questao
    extra = 1
    show_change_link = True
    fields = ["ordem", "enunciado"]


@admin.register(Prova)
class ProvaAdmin(admin.ModelAdmin):
    list_display = ["curso", "total_questoes"]
    inlines = [QuestaoInline]


@admin.register(AvaliacaoReacao)
class ReacaoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "curso", "nota_didatica", "nota_entendimento", "data_resposta"]
    list_filter = ["curso"]


@admin.register(RespostaProva)
class RespostaAdmin(admin.ModelAdmin):
    list_display = ["usuario", "prova", "numero_tentativa", "nota_obtida", "data_realizacao"]
    list_filter = ["prova__curso"]