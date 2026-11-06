"""Permissões da API REST do Vigent."""
from rest_framework.permissions import BasePermission


class SomenteRH(BasePermission):
    """Libera o acesso só para usuário autenticado do grupo RH.

    É a permissão padrão de toda a API (REST_FRAMEWORK em settings.py), o mesmo
    controle das telas do painel do RH, mas respondendo 403 em JSON em vez de
    redirecionar. A verificação acontece no back-end, nunca só na interface.
    """

    message = "Acesso restrito ao RH."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and usuario.is_authenticated and usuario.e_rh)
