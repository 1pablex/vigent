"""
Envio de correspondência v1 (somente email sem template)
"""
from django.conf import settings
from django.core.mail import send_mail

from auditoria.models import EmailEnviado, LogSistema


def enviar_primeiro_acesso(usuario, senha_provisoria):
    """RN-32 — a credencial trafega apenas para o titular."""
    assunto = "Suas credenciais de acesso ao Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Sua conta no Vigent foi criada. Use as credenciais abaixo no "
        f"primeiro acesso:\n\n"
        f"Matrícula: {usuario.matricula}\n"
        f"E-mail: {usuario.email}\n"
        f"Senha provisória: {senha_provisoria}\n\n"
        f"Essa senha é de uso único — o sistema vai pedir que você defina "
        f"uma senha pessoal ao entrar."
    )
    registro = EmailEnviado(tipo="Primeiro acesso", destinatario=usuario.email,
                            assunto=assunto, corpo=corpo)
    try:
        send_mail(assunto, corpo, settings.DEFAULT_FROM_EMAIL or "nao-responda@vigent.local",
                  [usuario.email], fail_silently=False)
        registro.entregue = True
    except Exception as exc:
        registro.entregue = False
        registro.erro = str(exc)[:200]
        LogSistema.objects.create(
            nivel=LogSistema.Nivel.ERRO, evento="Falha no envio de e-mail",
            detalhe=f"{usuario.email} — {exc}"[:500])
    registro.save()
    return registro