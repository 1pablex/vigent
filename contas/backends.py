"""Autenticação por endereço de correio eletrônico, com normalização (RN-17)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        modelo_usuario = get_user_model()
        email = (username or kwargs.get("email") or "").strip().lower()
        if not email or password is None:
            return None
        try:
            usuario = modelo_usuario.objects.get(email=email)
        except modelo_usuario.DoesNotExist:
            modelo_usuario().set_password(password)   # evita medir tempo de resposta
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
