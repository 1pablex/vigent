from django.conf import settings
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)

from auditoria.models import EmailEnviado, LogSistema
from brevo.core.api_error import ApiError


def _enviar(destinatario, assunto, corpo_texto, tipo):
    registro = EmailEnviado(tipo=tipo, destinatario=destinatario,
                            assunto=assunto, corpo=corpo_texto)
    try:
        cliente = Brevo(api_key=settings.BREVO_API_KEY)
        cliente.transactional_emails.send_transac_email(
            subject=assunto,
            html_content=(
                f"<pre style='font-family:inherit;white-space:pre-wrap'>"
                f"{corpo_texto}</pre>"
            ),
            sender=SendTransacEmailRequestSender(
                name="Vigent", email=settings.DEFAULT_FROM_EMAIL),
            to=[SendTransacEmailRequestToItem(email=destinatario)],
        )
        registro.entregue = True
    except ApiError as exc:
        registro.entregue = False
        registro.erro = f"[{exc.status_code}] {exc.body}"[:500]
        LogSistema.objects.create(
            nivel=LogSistema.Nivel.ERRO, evento="Falha no envio de e-mail",
            detalhe=f"{destinatario} — [{exc.status_code}] {exc.body}"[:500])
    except Exception as exc:
        registro.entregue = False
        registro.erro = str(exc)[:500]
        LogSistema.objects.create(
            nivel=LogSistema.Nivel.ERRO, evento="Falha no envio de e-mail",
            detalhe=f"{destinatario} — {exc}"[:500])
    registro.save()
    return registro


def enviar_primeiro_acesso(usuario, senha_provisoria):
    """RN-19 — a credencial trafega apenas para o titular."""
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
    return _enviar(usuario.email, assunto, corpo, "Primeiro acesso")


def enviar_codigo_verificacao(usuario, codigo_obj):
    """RN-18 — segundo fator de autenticação."""
    assunto = "Seu código de verificação Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Seu código de verificação é: {codigo_obj.codigo}\n\n"
        f"Ele é válido por 5 minutos e só pode ser usado uma vez. Se você não "
        f"tentou entrar no Vigent agora, ignore este e-mail."
    )
    return _enviar(usuario.email, assunto, corpo, "Código de verificação")