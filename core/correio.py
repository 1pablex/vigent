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
            detalhe=f"{destinatario} - [{exc.status_code}] {exc.body}"[:500])
    except Exception as exc:
        registro.entregue = False
        registro.erro = str(exc)[:500]
        LogSistema.objects.create(
            nivel=LogSistema.Nivel.ERRO, evento="Falha no envio de e-mail",
            detalhe=f"{destinatario} - {exc}"[:500])
    registro.save()
    return registro


def enviar_primeiro_acesso(usuario, senha_provisoria):
    """RN-19 - a credencial trafega apenas para o titular."""
    assunto = "Suas credenciais de acesso ao Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Sua conta no Vigent foi criada. Use as credenciais abaixo no "
        f"primeiro acesso:\n\n"
        f"Matrícula: {usuario.matricula}\n"
        f"E-mail: {usuario.email}\n"
        f"Senha provisória: {senha_provisoria}\n\n"
        f"Essa senha é de uso único - o sistema vai pedir que você defina "
        f"uma senha pessoal ao entrar."
    )
    return _enviar(usuario.email, assunto, corpo, "Primeiro acesso")


def enviar_codigo_verificacao(usuario, codigo_obj):
    """RN-18 - segundo fator de autenticação."""
    assunto = "Seu código de verificação Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Seu código de verificação é: {codigo_obj.codigo}\n\n"
        f"Ele é válido por 5 minutos e só pode ser usado uma vez. Se você não "
        f"tentou entrar no Vigent agora, ignore este e-mail."
    )
    return _enviar(usuario.email, assunto, corpo, "Código de verificação")

def enviar_codigo_redefinicao(usuario, codigo_obj):
    """Redefinição de senha - código enviado por e-mail."""
    assunto = "Redefinição de senha Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Recebemos uma solicitação para redefinir sua senha no Vigent.\n\n"
        f"Seu código de redefinição é: {codigo_obj.codigo}\n\n"
        f"Ele é válido por 5 minutos e só pode ser usado uma vez. Se você não "
        f"solicitou essa redefinição, ignore este e-mail: sua senha continuará a mesma."
    )
    return _enviar(usuario.email, assunto, corpo, "Redefinição de senha")

def enviar_alerta_vencimento(usuario, certificado, dias):
    """RF-10 - alerta nos marcos de 30, 15 e 7 dias antes do vencimento."""
    assunto = f"Seu certificado vence em {dias} dias - Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Seu certificado do curso \"{certificado.curso.nome}\" vence em {dias} dias, "
        f"em {certificado.data_validade.strftime('%d/%m/%Y')}.\n\n"
        f"Acesse o Vigent para renovar o treinamento antes do vencimento."
    )
    return _enviar(usuario.email, assunto, corpo, "Alerta de vencimento")

def enviar_notificacao_reciclagem(usuario, curso):
    assunto = f"Treinamento vencido: {curso.nome} - Vigent"
    corpo = (
        f"Olá, {usuario.get_short_name()}.\n\n"
        f"Seu certificado do curso \"{curso.nome}\" venceu e precisa ser refeito.\n\n"
        f"Acesse o Vigent e conclua o treinamento novamente o quanto antes, "
        f"para manter sua conformidade em dia."
    )
    return _enviar(usuario.email, assunto, corpo, "Reciclagem solicitada")