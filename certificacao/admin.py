from django.contrib import admin

from .models import Certificado, NotificacaoEnviada


@admin.register(Certificado)
class CertificadoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "curso", "nota_prova", "versao_curso",
                    "data_emissao", "data_validade"]
    list_filter = ["curso"]
    search_fields = ["usuario__nome", "usuario__matricula"]
    readonly_fields = ["usuario", "curso", "nota_prova", "versao_curso",
                      "data_emissao", "data_validade"]

    def has_add_permission(self, request):
        return False
    
@admin.register(NotificacaoEnviada)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ["certificado", "marco_dias", "data_envio"]

    def has_add_permission(self, request):
        return False