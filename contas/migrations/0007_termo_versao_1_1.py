"""Publica a versão 1.1 do termo de uso (RN-33).

A versão 1.0 prometia aviso por e-mail antes de uma nova versão entrar em vigor, o que o
sistema não faz. A 1.0 não é alterada, porque é o texto que as pessoas aceitaram: a 1.1 é
uma cópia dela com o parágrafo final corrigido. Por ser uma versão nova, todos precisam
aceitá-la no próximo acesso.
"""
from django.db import migrations
from django.utils import timezone

PARAGRAFO_V1_0 = (
    "<p>Esta é a versão 1.0, publicada em 24/09/2026. Caso haja alteração relevante, "
    "publicaremos a nova versão no sistema e comunicaremos você por e-mail antes que ela "
    "entre em vigor. As versões anteriores ficam disponíveis mediante solicitação.</p>"
)
PARAGRAFO_V1_1 = (
    "<p>Esta é a versão 1.1. Caso haja alteração relevante, publicaremos uma nova versão no "
    "sistema; no seu próximo acesso, você verá o aviso de atualização e precisará ler e "
    "aceitar o novo texto para continuar usando o Vigent. As versões anteriores ficam "
    "disponíveis mediante solicitação.</p>"
)
RESUMO = (
    "A política deixa de prometer aviso por e-mail antes de uma nova versão entrar em vigor. "
    "Uma nova versão passa a valer quando é publicada, e o aviso de atualização aparece no "
    "seu próximo acesso ao Vigent."
)


def publicar_1_1(apps, schema_editor):
    TermoUso = apps.get_model("contas", "TermoUso")
    v1_0 = TermoUso.objects.filter(versao="1.0").first()
    if v1_0 is None or TermoUso.objects.filter(versao="1.1").exists():
        return
    assert PARAGRAFO_V1_0 in v1_0.conteudo, "texto da versão 1.0 diferente do esperado"
    TermoUso.objects.create(versao="1.1", conteudo=v1_0.conteudo.replace(PARAGRAFO_V1_0,
                                                                          PARAGRAFO_V1_1),
                            resumo_alteracoes=RESUMO, publicado_em=timezone.now())


def remover_1_1(apps, schema_editor):
    TermoUso = apps.get_model("contas", "TermoUso")
    AceiteTermo = apps.get_model("contas", "AceiteTermo")
    AceiteTermo.objects.filter(termo__versao="1.1").delete()
    TermoUso.objects.filter(versao="1.1").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0006_termo_versionado"),
    ]

    operations = [
        migrations.RunPython(publicar_1_1, remover_1_1),
    ]
