from django.contrib import admin

from .models import EmailEnviado, ExecucaoRotina, LogSistema, RegistroAcesso


class SomenteLeitura(admin.ModelAdmin):
    """RN-24 — a trilha não pode ser editada nem removida."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogSistema)
class LogAdmin(SomenteLeitura):
    list_display = ["data_hora", "nivel", "evento", "usuario", "detalhe"]
    list_filter = ["nivel", "evento"]
    search_fields = ["evento", "detalhe"]


@admin.register(EmailEnviado)
class EmailAdmin(SomenteLeitura):
    list_display = ["data_hora", "tipo", "destinatario", "assunto", "entregue"]
    list_filter = ["tipo", "entregue"]


@admin.register(RegistroAcesso)
class AcessoAdmin(SomenteLeitura):
    list_display = ["data_hora", "identificacao", "evento", "resultado", "ip"]
    list_filter = ["resultado"]


@admin.register(ExecucaoRotina)
class ExecucaoAdmin(SomenteLeitura):
    list_display = ["data_hora", "rotina", "avaliados", "notificados", "ignorados", "sucesso"]