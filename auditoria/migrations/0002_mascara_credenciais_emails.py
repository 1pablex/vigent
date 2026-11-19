"""Mascara as credenciais já gravadas na auditoria de e-mails.

Até aqui o corpo de cada e-mail era registrado inteiro, inclusive o código de verificação
e a senha provisória do primeiro acesso. Os novos registros já saem mascarados
(core/correio.py); esta migração aplica a mesma máscara aos antigos. Só a credencial é
trocada por ******: o restante do registro (destinatário, assunto, data, entrega) fica igual.
"""
import re

from django.db import migrations
from django.db.models import Q

MASCARA = "******"
PADROES = [
    re.compile(r"(Senha provisória: )\S+"),
    re.compile(r"(código de (?:verificação|redefinição) é: )\d+"),
]


def mascarar(apps, schema_editor):
    EmailEnviado = apps.get_model("auditoria", "EmailEnviado")
    candidatos = EmailEnviado.objects.filter(
        Q(corpo__contains="Senha provisória: ") | Q(corpo__contains="código de verificação é: ")
        | Q(corpo__contains="código de redefinição é: "))
    alterados = []
    for registro in candidatos.iterator():
        novo = registro.corpo
        for padrao in PADROES:
            novo = padrao.sub(rf"\g<1>{MASCARA}", novo)
        if novo != registro.corpo:
            registro.corpo = novo
            alterados.append(registro)
    EmailEnviado.objects.bulk_update(alterados, ["corpo"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0001_initial"),
    ]

    # Sem volta: a credencial original não é recuperável, e é exatamente essa a intenção.
    operations = [
        migrations.RunPython(mascarar, migrations.RunPython.noop),
    ]
