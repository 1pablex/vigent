"""RN-27 — enquanto a senha provisória não for substituída, apenas a tela
de definição de senha permanece acessível."""
from django.shortcuts import redirect
from django.urls import reverse

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
                return redirect("contas:definir_senha")
        return self.get_response(request)

class TermoAceiteMiddleware:
    """Bloqueia acesso até o aceite do termo de uso, exceto para RH/colaborador     ainda em processo de definir a senha"""
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
                return redirect("contas:aceitar_termo")
        return self.get_response(request)