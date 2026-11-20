"""Termo de uso versionado (RN-33).

Cria TermoUso e AceiteTermo, registra o texto que estava no sistema como versão 1.0
(publicada em 24/09/2026) e converte os aceites existentes em aceites da 1.0, com a data
original. Só depois remove os campos antigos do Usuario. Ninguém precisa aceitar de novo
por causa da migração.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

PUBLICACAO_V1 = datetime(2026, 9, 24, tzinfo=ZoneInfo("America/Sao_Paulo"))

CONTEUDO_V1 = (
    '<h3>1. Quem somos e a quem esta política se aplica</h3>\n'
    '<p>O Vigent é o sistema utilizado por NORTEX LTDA para gerenciar os treinamentos obrigatórios de seus colaboradores. Esta política explica quais dados pessoais o sistema trata, para que os utiliza, com quem os compartilha, por quanto tempo os mantém e quais são os seus direitos.</p>\n'
    '<p>A NORTEX LTDA é a controladora desses dados, ou seja, é quem decide porque e como eles são tratados. Esta política se aplica a todos os colaboradores com conta ativa no sistema e aos registros de colaboradores já desligados, enquanto eles precisarem ser mantidos.</p>\n'
    '<h3>2. Que dados tratamos</h3>\n'
    '<p>Tratamos apenas os dados necessários para que o sistema funcione. Não coletamos CPF, RG, endereço residencial, data de nascimento, telefone pessoal, fotografia, dados de saúde, dados financeiros, biometria, voz ou imagem.</p>\n'
    '<h3>3. Por que tratamos esses dados</h3>\n'
    '<p>Cada dado é utilizado para uma finalidade específica, amparada em uma base legal prevista na Lei nº 13.709/2018 (LGPD).</p>\n'
    '<table>\n'
    '<thead><tr><th>Para que usamos</th><th>Base legal</th></tr></thead>\n'
    '<tbody>\n'
    '<tr><td>Identificar você e definir quais treinamentos obrigatórios se aplicam ao seu cargo e à sua área</td><td>Cumprimento de obrigação legal do empregador (art. 7º, II)</td></tr>\n'
    '<tr><td>Registrar sua participação, seu desempenho e sua certificação, de modo a comprovar o treinamento perante fiscalização</td><td>Cumprimento de obrigação legal (art. 7º, II) e exercício regular de direitos (art. 7º, VI)</td></tr>\n'
    '<tr><td>Avisar você por e-mail quando um certificado estiver próximo do vencimento</td><td>Cumprimento de obrigação legal (art. 7º, II)</td></tr>\n'
    '<tr><td>Avaliar a qualidade dos treinamentos oferecidos, a partir das notas e comentários</td><td>Legítimo interesse (art. 7º, IX)</td></tr>\n'
    '<tr><td>Proteger o sistema contra acessos indevidos e manter trilha de auditoria</td><td>Legítimo interesse (art. 7º, IX)</td></tr>\n'
    '</tbody>\n'
    '</table>\n'
    '<p><strong>Por que não pedimos o seu consentimento?</strong> O treinamento obrigatório decorre de exigência legal aplicável ao empregador e não depende de autorização sua para existir. Além disso, em uma relação de trabalho, um consentimento pedido pelo empregador dificilmente seria livre, como a lei exige. Por isso, utilizamos as bases legais acima, e não o consentimento. Isso não reduz os seus direitos, descritos no item 7.</p>\n'
    '<h3>4. Com quem compartilhamos</h3>\n'
    '<p>Não vendemos, alugamos nem cedemos seus dados. Não há publicidade, criação de perfis de consumo ou compartilhamento com terceiros para finalidades próprias deles. Os dados são acessíveis a:</p>\n'
    '<p>Você, quanto aos seus próprios cursos, notas e certificados.<br>\n'
    'A equipe de RH, para gerir os treinamentos e acompanhar a conformidade da organização.<br>\n'
    'Autoridades públicas, quando houver requisição legal ou fiscalização.</p>\n'
    '<p>Os dados são armazenados em servidores localizados nos Estados Unidos. Essa transferência internacional ocorre com base em cláusulas contratuais firmadas com o prestador, que impõem obrigações de proteção equivalentes às da legislação brasileira.</p>\n'
    '<h3>5. Cookies</h3>\n'
    '<p>O Vigent utiliza apenas cookies estritamente necessários ao funcionamento, destinados a manter você autenticado durante a sessão e a proteger os formulários contra requisições fraudulentas. Não utilizamos cookies de publicidade, de análise de comportamento ou de terceiros, e por isso não exibimos banner de escolha de cookies.</p>\n'
    '<h3>6. Por quanto tempo guardamos</h3>\n'
    '<table>\n'
    '<thead><tr><th>Dados</th><th>Prazo</th></tr></thead>\n'
    '<tbody>\n'
    '<tr><td>Cadastro e histórico de treinamento</td><td>Enquanto durar o seu vínculo com a organização</td></tr>\n'
    '<tr><td>Dados de identificação após o desligamento</td><td>Substituídos por um código, mantidos em área restrita por 90 dias e depois excluídos</td></tr>\n'
    '<tr><td>Certificados</td><td>Mantidos por 5 anos após o desligamento, para comprovação em fiscalização ou processo</td></tr>\n'
    '<tr><td>Registros de acesso e trilha de auditoria</td><td>90 dias</td></tr>\n'
    '<tr><td>Códigos de verificação</td><td>Até a utilização ou a expiração</td></tr>\n'
    '</tbody>\n'
    '</table>\n'
    '<p>Quando você é desligado da organização, seus dados de identificação deixam de ser exibidos no sistema e são substituídos por um código. O histórico de treinamento permanece, sem identificação direta, porque a organização precisa comprovar que a capacitação foi realizada. A recomposição da identidade só é possível para a equipe autorizada e apenas em caso de fiscalização ou processo.</p>\n'
    '<h3>7. Seus direitos</h3>\n'
    '<p>A LGPD garante a você o direito de saber se tratamos seus dados, acessá-los, corrigi-los, solicitar a eliminação dos que forem desnecessários, opor-se a determinados tratamentos, solicitar a portabilidade e pedir informações sobre compartilhamentos.</p>\n'
    '<p>No Vigent, você consulta a qualquer momento, na própria interface, seus cursos atribuídos, suas notas e seus certificados. Para os demais pedidos, entre em contato pelo canal indicado no item 10. Responderemos no prazo legal.</p>\n'
    '<p><strong>Limite à exclusão:</strong> os registros de treinamento obrigatório e os certificados não podem ser apagados a pedido, porque a organização tem o dever legal de comprovar a capacitação. A LGPD prevê essa exceção no art. 16, I. Os demais dados são eliminados conforme os prazos do item 6.</p>\n'
    '<h3>8. Decisões automatizadas</h3>\n'
    '<p>O sistema corrige sua prova automaticamente, compara a nota com o mínimo exigido pelo curso e, a partir desse resultado, emite ou não o certificado e classifica sua situação como conforme ou pendente. Essa decisão é tomada sem intervenção humana.</p>\n'
    '<p>Você pode solicitar a revisão dessa decisão pelo canal do item 10. Todas as suas tentativas ficam registradas, o que permite conferir a correção questão a questão.</p>\n'
    '<h3>9. Como protegemos seus dados</h3>\n'
    '<p>Adotamos medidas técnicas e administrativas para proteger seus dados, entre elas: senhas armazenadas de forma cifrada, nunca em texto legível; acesso ao sistema somente por conexão segura (HTTPS); controle de permissões por perfil, verificado a cada operação no servidor; limitação de tentativas de login e bloqueio temporário após excessos; registro de eventos relevantes em trilha de auditoria que não pode ser alterada.</p>\n'
    '<h3>10. Contato</h3>\n'
    '<p>Para exercer seus direitos ou esclarecer dúvidas sobre esta política, entre em contato com o departamento de Recursos Humanos pelo e-mail rh@nortex.com.br</p>\n'
    '<h3>11. Alterações desta política</h3>\n'
    '<p>Esta é a versão 1.0, publicada em 24/09/2026. Caso haja alteração relevante, publicaremos a nova versão no sistema e comunicaremos você por e-mail antes que ela entre em vigor. As versões anteriores ficam disponíveis mediante solicitação.</p>\n'
)


def criar_versao_1_e_converter_aceites(apps, schema_editor):
    Usuario = apps.get_model("contas", "Usuario")
    TermoUso = apps.get_model("contas", "TermoUso")
    AceiteTermo = apps.get_model("contas", "AceiteTermo")

    termo = TermoUso.objects.create(versao="1.0", conteudo=CONTEUDO_V1,
                                    resumo_alteracoes="Versão inicial.",
                                    publicado_em=PUBLICACAO_V1)
    AceiteTermo.objects.bulk_create(
        AceiteTermo(usuario=u, termo=termo,
                    data_hora=u.data_aceite_termos or u.data_cadastro)
        for u in Usuario.objects.filter(aceitou_termos=True))


def voltar_aceites(apps, schema_editor):
    Usuario = apps.get_model("contas", "Usuario")
    AceiteTermo = apps.get_model("contas", "AceiteTermo")
    for aceite in AceiteTermo.objects.all():
        Usuario.objects.filter(pk=aceite.usuario_id).update(
            aceitou_termos=True, data_aceite_termos=aceite.data_hora)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0005_codigo_somente_hmac"),
    ]

    operations = [
        migrations.CreateModel(
            name="TermoUso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("versao", models.CharField(help_text="Ex.: 1.1", max_length=10, unique=True)),
                ("conteudo", models.TextField(
                    help_text="Texto completo em HTML simples: títulos (h3), parágrafos, listas "
                              "e tabelas.")),
                ("resumo_alteracoes", models.TextField(
                    blank=True, help_text="O que mudou em relação à versão anterior. Aparece "
                                          "para quem precisa aceitar de novo.")),
                ("publicado_em", models.DateTimeField(default=django.utils.timezone.now,
                                                      editable=False)),
                ("publicado_por", models.ForeignKey(
                    blank=True, editable=False, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="termos_publicados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "termo de uso",
                "verbose_name_plural": "termos de uso",
                "ordering": ["-publicado_em", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AceiteTermo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("data_hora", models.DateTimeField(default=django.utils.timezone.now,
                                                   editable=False)),
                ("ip", models.GenericIPAddressField(blank=True, editable=False, null=True)),
                ("termo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name="aceites", to="contas.termouso")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="aceites_termo",
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "aceite do termo",
                "verbose_name_plural": "aceites do termo",
                "ordering": ["-data_hora"],
                "unique_together": {("usuario", "termo")},
            },
        ),
        migrations.RunPython(criar_versao_1_e_converter_aceites, voltar_aceites),
        migrations.RemoveField(model_name="usuario", name="aceitou_termos"),
        migrations.RemoveField(model_name="usuario", name="data_aceite_termos"),
    ]
