"""RNF-13 - sessão única por conta: o último login vale, as sessões anteriores são encerradas."""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


def marcar_sessao_ativa(request, usuario):
    """Grava a sessão atual como a única válida da conta."""
    if not request.session.session_key:
        request.session.save()
    usuario.sessao_ativa = request.session.session_key
    usuario.save(update_fields=["sessao_ativa"])


@receiver(user_logged_in)
def _ao_fazer_login(sender, request, user, **kwargs):
    # Vale para todo login: tela do sistema, admin e testes (force_login).
    if request is not None and hasattr(request, "session"):
        marcar_sessao_ativa(request, user)
