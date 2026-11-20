"""Aba "Termo de uso" do painel do RH (RN-33).

O RH vê o histórico e a adesão e lança versões novas a partir do texto vigente, sempre
pré-visualizando antes de publicar. Publicar nunca altera a versão anterior.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag
from django.urls import reverse

from auditoria.models import LogSistema
from contas.forms import numero, proxima_versao
from contas.models import TermoUso

Usuario = get_user_model()
TEXTO = "1. Quem somos\nTexto revisado da política.\n\n| Dado | Prazo |\n| Nome | 5 anos |"


@tag("unitario")
class NumeracaoTest(SimpleTestCase):

    def test_compara_versoes_como_numeros(self):
        self.assertGreater(numero("1.10"), numero("1.9"))
        self.assertGreater(numero("2.0"), numero("1.11"))
        self.assertIsNone(numero("1.1-teste"))
        self.assertIsNone(numero(""))

    def test_sugere_a_proxima_versao(self):
        class V:
            def __init__(self, versao):
                self.versao = versao
        self.assertEqual(proxima_versao(V("1.1")), "1.2")
        self.assertEqual(proxima_versao(V("1.9")), "1.10")
        self.assertEqual(proxima_versao(V("2")), "2.1")
        self.assertEqual(proxima_versao(V("teste")), "1.0")
        self.assertEqual(proxima_versao(None), "1.0")


class CenarioTermoRh(TestCase):

    def setUp(self):
        self.rh = Usuario.objects.create_user(
            email="rh@exemplo.invalid", nome="Rita RH", password="x", grupo=Usuario.Grupo.RH,
            senha_provisoria=False, aceite_termo_vigente=True)
        self.ana = Usuario.objects.create_user(
            email="ana@exemplo.invalid", nome="Ana", password="x", senha_provisoria=False,
            aceite_termo_vigente=True)
        self.client.force_login(self.rh)

    def enviar(self, acao, versao="1.2", resumo="Inclusão do prazo de guarda.", conteudo=TEXTO):
        return self.client.post(reverse("termo_rh:nova"), {
            "acao": acao, "versao": versao, "resumo_alteracoes": resumo, "conteudo": conteudo})


class HistoricoTest(CenarioTermoRh):

    def test_lista_versoes_e_adesao(self):
        Usuario.objects.create_user(email="bia@exemplo.invalid", nome="Bia", password="x",
                                    senha_provisoria=False)   # ainda não aceitou

        resposta = self.client.get(reverse("termo_rh:lista"))

        self.assertContains(resposta, "Versão vigente")
        self.assertContains(resposta, "2 de 3 contas ativas já aceitaram")
        self.assertContains(resposta, "1 ainda vão ver o termo")
        for versao in ("1.0", "1.1"):
            self.assertContains(resposta, versao)

    def test_aba_aparece_no_menu_do_rh(self):
        resposta = self.client.get(reverse("core:rh_colaboradores"))
        self.assertContains(resposta, reverse("termo_rh:lista"))

    def test_ver_versao_mostra_o_texto_formatado_e_e_so_leitura(self):
        termo = TermoUso.objects.get(versao="1.0")
        resposta = self.client.get(reverse("termo_rh:ver", args=[termo.pk]))
        self.assertContains(resposta, "<h3>1. Quem somos e a quem esta política se aplica</h3>",
                            html=True)
        self.assertNotContains(resposta, 'name="conteudo"')


class NovaVersaoTest(CenarioTermoRh):

    def test_formulario_ja_vem_com_o_texto_vigente_e_o_proximo_numero(self):
        resposta = self.client.get(reverse("termo_rh:nova"))
        self.assertContains(resposta, 'value="1.2"')
        self.assertContains(resposta, "Esta é a versão 1.1.")

    def test_previsualizar_mostra_o_texto_e_nao_salva(self):
        resposta = self.enviar("previsualizar")

        self.assertContains(resposta, "Pré-visualização da versão 1.2")
        self.assertContains(resposta, "<th>Prazo</th>", html=True)
        self.assertContains(resposta, 'value="publicar"')
        self.assertContains(resposta, "data-confirmar=")
        self.assertEqual(TermoUso.vigente().versao, "1.1")

    def test_publicar_cria_a_versao_registra_e_aceita_pelo_autor(self):
        resposta = self.enviar("publicar")

        self.assertRedirects(resposta, reverse("termo_rh:lista"))
        termo = TermoUso.vigente()
        self.assertEqual((termo.versao, termo.publicado_por, termo.conteudo),
                         ("1.2", self.rh, TEXTO))
        self.assertTrue(LogSistema.objects.filter(
            evento="Nova versão do termo de uso publicada", nivel=LogSistema.Nivel.WARN,
            usuario=self.rh).exists())
        # o autor já aceitou e continua usando o sistema
        self.assertEqual(self.client.get(reverse("termo_rh:lista")).status_code, 200)

    def test_publicar_obriga_os_outros_a_aceitar(self):
        self.enviar("publicar")
        self.client.force_login(self.ana)
        resposta = self.client.get(reverse("contas:aceitar_termo"))
        self.assertContains(resposta, "O termo foi atualizado para a versão 1.2.")
        self.assertContains(resposta, "Inclusão do prazo de guarda.")

    def test_versao_anterior_nao_muda(self):
        anterior = TermoUso.objects.get(versao="1.1").conteudo
        self.enviar("publicar")
        self.assertEqual(TermoUso.objects.get(versao="1.1").conteudo, anterior)

    def test_voltar_e_editar_mantem_o_que_foi_digitado(self):
        resposta = self.enviar("editar")
        self.assertContains(resposta, "Texto revisado da política.")
        self.assertContains(resposta, 'value="1.2"')
        self.assertEqual(TermoUso.objects.count(), 2)

    def test_quebras_de_linha_chegam_intactas_na_publicacao(self):
        previa = self.enviar("previsualizar").content.decode()
        self.assertIn(TEXTO, previa.replace("&#x27;", "'"))


class RegrasDaVersaoTest(CenarioTermoRh):

    def test_versao_repetida_e_recusada(self):
        resposta = self.enviar("publicar", versao="1.1")
        self.assertContains(resposta, "A versão 1.1 já foi publicada.")
        self.assertEqual(TermoUso.objects.count(), 2)

    def test_versao_menor_que_a_vigente_e_recusada(self):
        resposta = self.enviar("publicar", versao="1.0.5")
        self.assertContains(resposta, "precisa ser maior que a vigente (1.1)")

    def test_numero_invalido_e_recusado(self):
        resposta = self.enviar("previsualizar", versao="2.0-final")
        self.assertContains(resposta, "Use só números separados por ponto")

    def test_texto_igual_ao_vigente_e_recusado(self):
        resposta = self.enviar("publicar", conteudo=TermoUso.vigente().conteudo)
        self.assertContains(resposta, "O texto está igual ao da versão vigente")

    def test_resumo_e_texto_sao_obrigatorios(self):
        resposta = self.enviar("publicar", resumo="", conteudo="")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(TermoUso.objects.count(), 2)

    def test_publicar_sem_post_nao_faz_nada(self):
        self.client.get(reverse("termo_rh:nova"), {"acao": "publicar", "versao": "1.2",
                                                    "conteudo": TEXTO, "resumo_alteracoes": "x"})
        self.assertEqual(TermoUso.objects.count(), 2)

    def test_texto_com_script_nao_executa_na_previa(self):
        resposta = self.enviar("previsualizar", conteudo="1. Título\n<script>alert(1)</script>")
        self.assertNotContains(resposta, "<script>alert(1)</script>")


class AcessoTest(CenarioTermoRh):

    def test_colaborador_nao_publica(self):
        self.client.force_login(self.ana)
        resposta = self.enviar("publicar")
        self.assertRedirects(resposta, reverse("treinamentos:inicio"))
        self.assertEqual(TermoUso.vigente().versao, "1.1")

    def test_colaborador_nao_ve_a_aba(self):
        self.client.force_login(self.ana)
        resposta = self.client.get(reverse("treinamentos:inicio"))
        self.assertNotContains(resposta, reverse("termo_rh:lista"))
