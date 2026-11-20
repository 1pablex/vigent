"""O código de verificação deixa de ser gravado em texto: fica só o HMAC dele.

Os códigos pendentes ficam com hash vazio e não conferem com nenhum valor digitado:
o usuário pede outro. Isso não causa perda real, porque cada código vale só 5 minutos.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0004_usuario_sessao_ativa"),
    ]

    operations = [
        migrations.AddField(
            model_name="codigoverificacao",
            name="codigo_hash",
            field=models.CharField(default="", editable=False, max_length=64),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name="codigoverificacao",
            name="codigo",
        ),
    ]
