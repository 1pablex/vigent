"""Termo digitado em texto puro no Django Admin (RN-33).

Sem HTML: parágrafos, títulos "1. ...", listas "- " e tabelas com "|". Com HTML (versões
1.0 e 1.1), o conteúdo segue como antes. Em qualquer caso, nada digitado vira script.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag
from django.urls import reverse

from contas.models import TermoUso
from contas.termos import formatar_termo

Usuario = get_user_model()

TEXTO = """1. Quem somos
O Vigent é o sistema de treinamentos da empresa.
Esta política explica como tratamos seus dados.

2. Que dados tratamos

- Nome e e-mail corporativo
- Matrícula e departamento

| Para que usamos | Base legal |
|---|---|
| Identificar você | Obrigação legal (art. 7º, II) |
| Avaliar os treinamentos | Legítimo interesse (art. 7º, IX) |

Esta é a versão 2.0."""


@tag("unitario")
class FormatarTextoPuroTest(SimpleTestCase):

    def test_titulos_paragrafos_listas_e_tabela(self):
        html = formatar_termo(TEXTO)

        self.assertInHTML("<h3>1. Quem somos</h3>", html)
        self.assertInHTML("<h3>2. Que dados tratamos</h3>", html)
        self.assertInHTML("<p>O Vigent é o sistema de treinamentos da empresa.<br>"
                          "Esta política explica como tratamos seus dados.</p>", html)
        self.assertInHTML("<ul><li>Nome e e-mail corporativo</li>"
                          "<li>Matrícula e departamento</li></ul>", html)
        self.assertInHTML("<p>Esta é a versão 2.0.</p>", html)

    def test_tabela_com_cabecalho_e_sem_a_linha_separadora(self):
        html = formatar_termo(TEXTO)

        self.assertInHTML(
            "<table><thead><tr><th>Para que usamos</th><th>Base legal</th></tr></thead>"
            "<tbody><tr><td>Identificar você</td><td>Obrigação legal (art. 7º, II)</td></tr>"
            "<tr><td>Avaliar os treinamentos</td><td>Legítimo interesse (art. 7º, IX)</td></tr>"
            "</tbody></table>", html)
        self.assertNotIn("---", html)

    def test_tabela_sem_linha_separadora_tambem_funciona(self):
        html = formatar_termo("| Dado | Prazo |\n| Nome | 5 anos |")
        self.assertInHTML("<table><thead><tr><th>Dado</th><th>Prazo</th></tr></thead>"
                          "<tbody><tr><td>Nome</td><td>5 anos</td></tr></tbody></table>", html)

    def test_quebra_de_linha_do_windows(self):
        html = formatar_termo("1. Título\r\nPrimeira linha\r\n\r\nSegundo parágrafo")
        self.assertInHTML("<h3>1. Título</h3>", html)
        self.assertInHTML("<p>Segundo parágrafo</p>", html)

    def test_texto_digitado_nunca_vira_codigo(self):
        html = formatar_termo("1. Título\nTexto & mais <b>negrito?</b> fim\n\n"
                              "| <script>x()</script> | ok |")
        # tem "<b>", então segue como HTML e passa pela limpeza
        self.assertNotIn("<script", html)

        puro = formatar_termo("Texto com 2 < 3 e a & b\n\n- item com > sinal")
        self.assertIn("2 &lt; 3 e a &amp; b", puro)
        self.assertIn("item com &gt; sinal", puro)

    def test_script_digitado_em_texto_puro_aparece_como_texto(self):
        html = formatar_termo("Olá alert(1) e javascript:x\n\n| a | b |")
        self.assertNotIn("<script", html)
        self.assertIn("javascript:x", html)   # só texto, sem link

    def test_conteudo_em_html_continua_como_antes(self):
        html = formatar_termo("<h3>1. Quem somos</h3>\n<p>Texto.</p>")
        self.assertInHTML("<h3>1. Quem somos</h3>", html)
        self.assertInHTML("<p>Texto.</p>", html)
        self.assertNotIn("&lt;h3&gt;", html)

    def test_numero_no_meio_de_um_paragrafo_nao_vira_titulo(self):
        html = formatar_termo("O prazo é de 5 anos.\n2026 é o ano de referência.")
        self.assertNotIn("<h3>", html)


class VersoesExistentesNaoMudamTest(TestCase):

    def test_versoes_1_0_e_1_1_aparecem_iguais(self):
        for termo in TermoUso.objects.filter(versao__in=["1.0", "1.1"]):
            html = formatar_termo(termo.conteudo)
            self.assertInHTML("<h3>1. Quem somos e a quem esta política se aplica</h3>", html)
            self.assertIn("<table>", html)
            self.assertNotIn("&lt;", html)


class TermoTextoPuroNaTelaTest(TestCase):

    def test_colaborador_ve_o_termo_formatado(self):
        TermoUso.objects.create(versao="2.0", conteudo=TEXTO, resumo_alteracoes="Texto revisado.")
        ana = Usuario.objects.create_user(email="ana@exemplo.invalid", nome="Ana", password="x",
                                          senha_provisoria=False)
        self.client.force_login(ana)

        resposta = self.client.get(reverse("contas:aceitar_termo"))

        self.assertContains(resposta, "<h3>1. Quem somos</h3>", html=True)
        self.assertContains(resposta, "<th>Base legal</th>", html=True)

    def test_admin_mostra_como_a_versao_aparece(self):
        admin = Usuario.objects.create_superuser(
            email="admin@exemplo.invalid", nome="Admin", password="x", aceite_termo_vigente=True)
        termo = TermoUso.objects.create(versao="2.0", conteudo=TEXTO)
        self.client.force_login(admin)
        admin.aceites_termo.create(termo=termo)

        resposta = self.client.get(reverse("admin:contas_termouso_change", args=[termo.pk]))

        self.assertContains(resposta, "Como aparece para o colaborador")
        self.assertContains(resposta, "<th>Base legal</th>", html=True)

    def test_formulario_do_admin_explica_o_formato(self):
        admin = Usuario.objects.create_superuser(
            email="admin@exemplo.invalid", nome="Admin", password="x", aceite_termo_vigente=True)
        self.client.force_login(admin)
        resposta = self.client.get(reverse("admin:contas_termouso_add"))
        self.assertContains(resposta, "Pode ser digitado em texto puro, sem HTML")
