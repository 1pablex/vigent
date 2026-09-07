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