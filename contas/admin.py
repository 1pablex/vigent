from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CodigoVerificacao, Departamento, Reidentificacao, Usuario

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