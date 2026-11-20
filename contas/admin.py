from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import AceiteTermo, CodigoVerificacao, Departamento, Reidentificacao, TermoUso, Usuario
from .termos import formatar_termo


#registra Departamento no admin
@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    search_fields = ["nome"]

#registra Usuario no admin
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["matricula"]
    list_display = ["matricula", "nome", "email", "cargo", "departamento",
                    "grupo", "is_active", "senha_provisoria"]
    list_filter = ["grupo", "is_active", "departamento", "pseudonimizado"]
    search_fields = ["matricula", "nome", "email"]
    readonly_fields = ["matricula", "data_cadastro", "last_login"]
    fieldsets = (
        (None, {"fields": ("matricula", "email", "password")}),
        ("Dados funcionais", {"fields": ("nome", "cargo", "departamento", "grupo")}),
        ("Situação", {"fields": ("is_active", "senha_provisoria", "pseudonimizado")}),
        ("Permissões", {"classes": ("collapse",),
                        "fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("data_cadastro", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "nome", "cargo", "departamento", "grupo",
                           "password1", "password2")}),
    )

#registra Reidentificacao no admin
@admin.register(Reidentificacao)
class ReidentificacaoAdmin(admin.ModelAdmin):
    list_display = ["pseudonimo", "matricula", "data_desligamento", "data_exclusao"]
    readonly_fields = [f.name for f in Reidentificacao._meta.fields]

    def has_add_permission(self, request):
        return False

#regista CodigoVerificacao no admin
@admin.register(CodigoVerificacao)
class CodigoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "data_geracao", "data_expiracao", "utilizado"]


@admin.register(TermoUso)
class TermoUsoAdmin(admin.ModelAdmin):
    """RN-33 - somente consulta. Novas versões são lançadas pelo RH na aba "Termo de uso"
    do painel, com pré-visualização e numeração validada; versão publicada não muda."""
    list_display = ["versao", "publicado_em", "publicado_por", "total_aceites"]
    fields = ["versao", "publicado_em", "publicado_por", "resumo_alteracoes", "como_aparece"]
    readonly_fields = fields

    @admin.display(description="Aceites")
    def total_aceites(self, termo):
        return termo.aceites.count()

    @admin.display(description="Como aparece para o colaborador")
    def como_aparece(self, termo):
        return format_html('<div style="max-width:760px;border:1px solid #d7dbe3;'
                           'border-radius:8px;padding:12px 16px;background:#fff">{}</div>',
                           mark_safe(formatar_termo(termo.conteudo)))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AceiteTermo)
class AceiteTermoAdmin(admin.ModelAdmin):
    """Prova do aceite: somente leitura."""
    list_display = ["usuario", "termo", "data_hora", "ip"]
    list_filter = ["termo"]
    search_fields = ["usuario__matricula", "usuario__email"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
