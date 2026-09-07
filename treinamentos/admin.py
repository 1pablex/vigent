from django.contrib import admin

from .models import (AtribuicaoManual, Aula, Curso, CursoDepartamento,
                     Presenca, ProgressoAula, SlideAula)


class SlideInline(admin.TabularInline):
    model = SlideAula
    extra = 1
    fields = ["ordem", "titulo", "corpo", "imagem"]


class AulaInline(admin.TabularInline):
    model = Aula
    extra = 1
    fields = ["ordem", "titulo"]
    show_change_link = True


class CursoDepInline(admin.TabularInline):
    model = CursoDepartamento
    extra = 1


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ["nome", "categoria", "carga_horaria", "validade_meses",
                    "nota_minima", "versao", "publicado"]
    list_filter = ["categoria"]
    search_fields = ["nome"]
    inlines = [AulaInline, CursoDepInline]

    @admin.display(boolean=True, description="Publicado")
    def publicado(self, obj):
        return obj.publicado


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ["curso", "ordem", "titulo"]
    list_filter = ["curso"]
    inlines = [SlideInline]


@admin.register(AtribuicaoManual)
class AtribuicaoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "curso", "atribuido_por", "data_atribuicao"]


@admin.register(CursoDepartamento)
class CursoDepAdmin(admin.ModelAdmin):
    list_display = ["curso", "departamento", "obrigatorio"]
    list_filter = ["departamento"]


admin.site.register([Presenca, ProgressoAula])