"""Termo de uso versionado (RN-33).

Cada versão publicada fica registrada; quem aceitou só uma versão anterior volta a ver o
termo e não usa o sistema até aceitar a vigente. Versão publicada não muda nem some.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogSistema
from contas.models import AceiteTermo, TermoUso
from contas.termos import registrar_aceite, sanitizar_termo

Usuario = get_user_model()


def publicar(versao, resumo="", conteudo="<h3>Texto</h3><p>Conteúdo da versão.</p>"):
    """Publica uma versão um instante depois da vigente, como faria o Admin."""
    atual = TermoUso.vigente()
    quando = (atual.publicado_em if atual else timezone.now()) + timedelta(seconds=1)
    return TermoUso.objects.create(versao=versao, conteudo=conteudo,
                                   resumo_alteracoes=resumo, publicado_em=quando)


class VersaoInicialTest(TestCase):

    def test_texto_que_estava_no_sistema_e_a_versao_1_0(self):
        termo = TermoUso.objects.get(versao="1.0")
        self.assertEqual(termo.versao, "1.0")
        self.assertEqual(timezone.localtime(termo.publicado_em).date().isoformat(), "2026-09-24")
        self.assertIn("1. Quem somos e a quem esta política se aplica", termo.conteudo)
        self.assertIn("comunicaremos você por e-mail", termo.conteudo)   # aceito como era

    def test_versao_1_1_e_a_vigente_e_nao_promete_e_mail(self):
        v1_0, v1_1 = TermoUso.objects.get(versao="1.0"), TermoUso.vigente()
        self.assertEqual(v1_1.versao, "1.1")
        self.assertNotIn("e-mail antes que ela entre em vigor", v1_1.conteudo)
        self.assertIn("no seu próximo acesso, você verá o aviso de atualização", v1_1.conteudo)
        self.assertIn("aviso por e-mail", v1_1.resumo_alteracoes)
        # o resto do texto é idêntico ao da 1.0
        self.assertEqual(v1_0.conteudo.split("<p>Esta é a versão")[0],
                         v1_1.conteudo.split("<p>Esta é a versão")[0])

    def test_quem_aceitou_so_a_1_0_precisa_aceitar_a_1_1(self):
        ana = Usuario.objects.create_user(email="ana@exemplo.invalid", nome="Ana",
                                          password="x", senha_provisoria=False)
        AceiteTermo.objects.create(usuario=ana, termo=TermoUso.objects.get(versao="1.0"))
        self.client.force_login(ana)
        resposta = self.client.get(reverse("contas:aceitar_termo"))
        self.assertContains(resposta, "O termo foi atualizado para a versão 1.1.")
        self.assertContains(resposta, "aviso por e-mail")


class NovaVersaoExigeNovoAceiteTest(TestCase):

    def setUp(self):
        self.ana = Usuario.objects.create_user(
            email="ana@exemplo.invalid", nome="Ana Colaboradora", password="x",
            senha_provisoria=False, aceite_termo_vigente=True)
        self.client.force_login(self.ana)

    def test_com_a_versao_vigente_aceita_usa_o_sistema(self):
        self.assertEqual(self.client.get(reverse("treinamentos:inicio")).status_code, 200)

    def test_nova_versao_bloqueia_ate_aceitar(self):
        publicar("2.0", resumo="Novo prazo de retenção dos registros de acesso.")

        self.assertRedirects(self.client.get(reverse("treinamentos:inicio")),
                             reverse("contas:aceitar_termo"))
        self.assertRedirects(self.client.get(reverse("certificacao:meus")),
                             reverse("contas:aceitar_termo"))
        self.assertRedirects(self.client.get(reverse("contas:meus_dados")),
                             reverse("contas:aceitar_termo"))

    def test_tela_mostra_que_o_termo_foi_atualizado_e_o_que_mudou(self):
        publicar("2.0", resumo="Novo prazo de retenção dos registros de acesso.")

        resposta = self.client.get(reverse("contas:aceitar_termo"))

        self.assertContains(resposta, "O termo foi atualizado para a versão 2.0.")
        self.assertContains(resposta, "Você aceitou a versão 1.1")
        self.assertContains(resposta, "Novo prazo de retenção dos registros de acesso.")
        self.assertContains(resposta, 'name="versao" value="2.0"')

    def test_aceitar_a_nova_versao_libera_e_mantem_o_historico(self):
        publicar("2.0")

        resposta = self.client.post(reverse("contas:aceitar_termo"),
                                    {"aceito": "on", "versao": "2.0"}, REMOTE_ADDR="10.0.0.7")

        self.assertRedirects(resposta, reverse("core:inicio"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("treinamentos:inicio")).status_code, 200)
        self.assertEqual(sorted(self.ana.aceites_termo.values_list("termo__versao", flat=True)),
                         ["1.1", "2.0"])
        self.assertEqual(self.ana.aceite_vigente.ip, "10.0.0.7")
        log = LogSistema.objects.filter(evento="Termo de uso aceito").latest("data_hora")
        self.assertEqual(log.detalhe, "Versão 2.0 (antes: versão 1.1)")

    def test_aceite_de_texto_desatualizado_nao_vale(self):
        publicar("2.0")

        # o formulário foi aberto na 2.0, mas a 2.1 saiu antes do envio
        publicar("2.1")
        resposta = self.client.post(reverse("contas:aceitar_termo"),
                                    {"aceito": "on", "versao": "2.0"})

        self.assertContains(resposta, "O termo foi atualizado enquanto você lia.")
        self.assertFalse(self.ana.aceites_termo.filter(termo__versao__in=["2.0", "2.1"]).exists())

    def test_sem_marcar_o_aceite_continua_bloqueado(self):
        publicar("2.0")
        resposta = self.client.post(reverse("contas:aceitar_termo"), {"versao": "2.0"})
        self.assertContains(resposta, "É necessário marcar a caixa de aceite para continuar.")
        self.assertIsNone(self.ana.aceite_vigente)

    def test_sem_aceitar_ainda_consegue_sair(self):
        publicar("2.0")
        self.assertRedirects(self.client.get(reverse("contas:logout")), reverse("contas:login"))

    def test_api_responde_403_ate_aceitar(self):
        rh = Usuario.objects.create_user(
            email="rh@exemplo.invalid", nome="RH Teste", password="x", grupo=Usuario.Grupo.RH,
            senha_provisoria=False, aceite_termo_vigente=True)
        self.client.force_login(rh)
        publicar("2.0")

        resposta = self.client.get(reverse("api:conformidade"))

        self.assertEqual(resposta.status_code, 403)
        self.assertIn("termo", resposta.json()["detail"])

    def test_rh_tambem_precisa_aceitar(self):
        rh = Usuario.objects.create_user(
            email="rh@exemplo.invalid", nome="RH Teste", password="x", grupo=Usuario.Grupo.RH,
            senha_provisoria=False, aceite_termo_vigente=True)
        self.client.force_login(rh)
        publicar("2.0")
        self.assertRedirects(self.client.get(reverse("core:rh_colaboradores")),
                             reverse("contas:aceitar_termo"))

    def test_meus_dados_mostra_a_versao_aceita(self):
        resposta = self.client.get(reverse("contas:meus_dados"))
        self.assertContains(resposta, "Versão 1.1, aceita em")

    def test_aceite_repetido_nao_duplica_registro(self):
        publicar("2.0")
        registrar_aceite(self.ana)
        registrar_aceite(self.ana)
        self.assertEqual(self.ana.aceites_termo.filter(termo__versao="2.0").count(), 1)


class VersaoPublicadaImutavelTest(TestCase):

    def test_nao_pode_ser_alterada(self):
        termo = TermoUso.vigente()
        termo.conteudo = "<p>Texto trocado depois do aceite.</p>"
        with self.assertRaises(ValueError):
            termo.save()
        self.assertIn("Quem somos", TermoUso.vigente().conteudo)

    def test_nao_pode_ser_apagada(self):
        with self.assertRaises(ValueError):
            TermoUso.vigente().delete()


class PublicacaoPeloAdminTest(TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            email="admin@exemplo.invalid", nome="Administrador", password="x",
            aceite_termo_vigente=True)
        self.client.force_login(self.admin)

    def test_superusuario_publica_versao_nova(self):
        resposta = self.client.post(reverse("admin:contas_termouso_add"), {
            "versao": "2.0", "resumo_alteracoes": "Ajuste no prazo.",
            "conteudo": "<h3>1. Quem somos</h3><p>Texto novo.</p>"})

        self.assertEqual(resposta.status_code, 302)
        termo = TermoUso.vigente()
        self.assertEqual((termo.versao, termo.publicado_por), ("2.0", self.admin))
        self.assertTrue(LogSistema.objects.filter(
            evento="Nova versão do termo de uso publicada", nivel=LogSistema.Nivel.WARN).exists())

    def test_versao_publicada_aparece_so_para_leitura_e_sem_excluir(self):
        termo = TermoUso.vigente()
        resposta = self.client.get(reverse("admin:contas_termouso_change", args=[termo.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'name="_save"')

        resposta = self.client.post(reverse("admin:contas_termouso_change", args=[termo.pk]),
                                    {"versao": "9.9", "conteudo": "<p>x</p>"})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(self.client.get(
            reverse("admin:contas_termouso_delete", args=[termo.pk])).status_code, 403)

    def test_aceites_sao_somente_leitura(self):
        aceite = AceiteTermo.objects.get(usuario=self.admin)
        self.assertEqual(self.client.get(reverse("admin:contas_aceitetermo_add")).status_code, 403)
        self.assertEqual(self.client.get(
            reverse("admin:contas_aceitetermo_delete", args=[aceite.pk])).status_code, 403)

    def test_versao_repetida_e_recusada(self):
        resposta = self.client.post(reverse("admin:contas_termouso_add"),
                                    {"versao": "1.0", "conteudo": "<p>x</p>"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(TermoUso.objects.count(), 2)


class ConteudoSeguroTest(TestCase):

    def test_html_perigoso_e_removido_na_exibicao(self):
        limpo = sanitizar_termo('<h3 onclick="x()">Título</h3><script>alert(1)</script>'
                                '<a href="javascript:alert(1)">link</a><p style="color:red">ok</p>')
        self.assertNotIn("<script", limpo)
        self.assertNotIn("onclick", limpo)
        self.assertNotIn("javascript:", limpo)
        self.assertNotIn("style=", limpo)
        self.assertIn("<h3>Título</h3>", limpo)

    def test_pagina_publica_mostra_a_versao_vigente(self):
        publicar("2.0", conteudo="<h3>Política revisada</h3>")
        resposta = self.client.get(reverse("contas:politica_privacidade"))
        self.assertContains(resposta, "Versão 2.0")
        self.assertContains(resposta, "<h3>Política revisada</h3>", html=True)


class MigracaoDosAceitesAntigosTest(TransactionTestCase):
    """Quem tinha aceitado antes da mudança ganha o aceite da 1.0, com a data original."""

    # Volta os dados criados pelas migrações (a versão 1.0) depois do teste, para os
    # testes seguintes encontrarem o banco como antes.
    serialized_rollback = True
    antes = [("contas", "0005_codigo_somente_hmac")]
    depois = [("contas", "0006_termo_versionado")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_converte_aceite_antigo_em_aceite_da_versao_1_0(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.antes)
        antigos = executor.loader.project_state(self.antes).apps
        usuario_antigo = antigos.get_model("contas", "Usuario")
        quando = timezone.now() - timedelta(days=30)
        aceitou = usuario_antigo.objects.create(email="a@exemplo.invalid", nome="A", matricula="9001",
                                               aceitou_termos=True, data_aceite_termos=quando)
        usuario_antigo.objects.create(email="b@exemplo.invalid", nome="B", matricula="9002",
                                     aceitou_termos=False)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.depois)
        novos = executor.loader.project_state(self.depois).apps
        aceite_modelo = novos.get_model("contas", "AceiteTermo")

        aceites = list(aceite_modelo.objects.select_related("termo", "usuario"))
        self.assertEqual([(a.usuario.email, a.termo.versao) for a in aceites],
                         [("a@exemplo.invalid", "1.0")])
        self.assertEqual(aceites[0].data_hora, quando)
        self.assertEqual(aceites[0].usuario_id, aceitou.pk)
