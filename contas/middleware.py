"""RN-18 - enquanto a senha provisória não for substituída, apenas a tela
de definição de senha permanece acessível."""
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def _bloquear(request, destino, motivo):
    """Telas são redirecionadas; a API (/api/) recebe 403 em JSON, sem redirect."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": motivo}, status=403)
    return redirect(destino)

"""enquanto o colaborador não trocar a senha provisória, ele não pode acessar nada"""
class SenhaProvisoriaMiddleware:
    LIBERADAS = ("contas:definir_senha", "contas:logout")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and usuario.senha_provisoria:
            liberadas = [reverse(n) for n in self.LIBERADAS]
            if request.path not in liberadas and not request.path.startswith("/static/"):
                return _bloquear(request, "contas:definir_senha",
                                 "Defina a senha definitiva antes de usar o sistema.")
        return self.get_response(request)

class TermoAceiteMiddleware:
    """RN-33 - bloqueia acesso até o aceite do termo de uso.

    Exceto para RH e para o colaborador ainda em processo de definir a senha.
    """
    LIBERADAS = ("contas:aceitar_termo", "contas:logout", "contas:definir_senha")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (usuario is not None and usuario.is_authenticated
                and not usuario.senha_provisoria and not usuario.aceitou_termos):
            liberadas = [reverse(n) for n in self.LIBERADAS]
            if (request.path not in liberadas
                    and not request.path.startswith("/static/")
                    and not request.path.startswith("/media/")):
                return _bloquear(request, "contas:aceitar_termo",
                                 "Aceite o termo de uso antes de usar o sistema.")
        return self.get_response(request)


class SessaoUnicaMiddleware:
    """
    RNF-13 - sessão única por conta. Se a conta fez login em outro dispositivo, a sessão
    antiga não vale mais: é encerrada e a pessoa volta ao login com um aviso.
    """

    MENSAGEM = ("Sua sessão foi encerrada porque sua conta foi acessada "
                "em outro dispositivo.")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (usuario is not None and usuario.is_authenticated and usuario.sessao_ativa
                and request.session.session_key != usuario.sessao_ativa):
            from auditoria.models import LogSistema
            from core.services import registrar
            registrar(LogSistema.Nivel.WARN, "Sessão encerrada por novo login",
                      f"{usuario.email} entrou em outro dispositivo", usuario)
            logout(request)
            if request.path.startswith("/api/"):
                return JsonResponse({"detail": self.MENSAGEM}, status=401)
            messages.warning(request, self.MENSAGEM)
            return redirect("contas:login")
        return self.get_response(request)
