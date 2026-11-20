"""Cabeçalhos HTTP de segurança: CSP, Permissions-Policy e HSTS.

A CSP (script-src 'self') só funciona se nenhum template tiver script inline nem atributo
on...=. Os testes de templates garantem isso daqui para a frente: quem colocar código
solto num HTML vê o teste falhar, em vez de ver o botão parar de funcionar em produção.
"""
import os
import re
import runpy
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase, tag
from django.urls import reverse

from core.middleware import CSP, PERMISSIONS_POLICY

Usuario = get_user_model()

SCRIPT_INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)
EVENTO_INLINE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


def templates():
    return sorted(Path(settings.BASE_DIR, "templates").rglob("*.html"))


@tag("unitario")
class PoliticaCspTest(SimpleTestCase):

    def test_scripts_so_do_proprio_vigent(self):
        diretivas = dict(d.strip().split(" ", 1) for d in CSP.split(";"))
        self.assertEqual(diretivas["script-src"], "'self'")
        self.assertNotIn("unsafe-inline", diretivas["script-src"])
        self.assertNotIn("unsafe-eval", CSP)

    def test_bloqueia_iframe_plugins_e_troca_de_base(self):
        self.assertIn("frame-ancestors 'none'", CSP)
        self.assertIn("object-src 'none'", CSP)
        self.assertIn("base-uri 'self'", CSP)
        self.assertIn("form-action 'self'", CSP)

    def test_permissions_policy_desliga_recursos_nao_usados(self):
        for recurso in ("camera=()", "microphone=()", "geolocation=()", "payment=()"):
            self.assertIn(recurso, PERMISSIONS_POLICY)


@tag("unitario")
class TemplatesSemCodigoInlineTest(SimpleTestCase):

    def test_nenhum_template_tem_script_inline(self):
        com_script = [str(t) for t in templates() if SCRIPT_INLINE.search(t.read_text("utf-8"))]
        self.assertEqual(com_script, [], "Mova o script para static/js/ (CSP: script-src 'self').")

    def test_nenhum_template_tem_evento_on(self):
        com_evento = [str(t) for t in templates() if EVENTO_INLINE.search(t.read_text("utf-8"))]
        self.assertEqual(com_evento, [], "Use data-envio-automatico, data-confirmar ou "
                                         "data-imprimir (static/js/vigent.js).")

    def test_scripts_das_telas_existem(self):
        for arquivo in ("js/vigent.js", "js/dashboard.js"):
            self.assertIsNotNone(finders.find(arquivo), arquivo)


@tag("unitario")
class HstsEmProducaoTest(SimpleTestCase):
    """Lê o settings.py como em produção (HTTPS=True), sem mudar a configuração dos testes."""

    def configuracao(self, https):
        with patch.dict(os.environ, {"HTTPS": https}):
            return runpy.run_path(str(Path(settings.BASE_DIR, "config", "settings.py")))

    def test_hsts_de_um_ano_com_subdominios_e_preload(self):
        producao = self.configuracao("True")
        self.assertEqual(producao["SECURE_HSTS_SECONDS"], 31536000)
        self.assertTrue(producao["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertTrue(producao["SECURE_HSTS_PRELOAD"])
        self.assertTrue(producao["SECURE_SSL_REDIRECT"])

    def test_sem_https_nao_liga_hsts(self):
        self.assertNotIn("SECURE_HSTS_SECONDS", self.configuracao("False"))


class CabecalhosNasRespostasTest(TestCase):

    def setUp(self):
        self.rh = Usuario.objects.create_user(
            email="rh@exemplo.invalid", nome="RH Teste", password="x",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceite_termo_vigente=True)

    def assert_cabecalhos(self, resposta):
        self.assertEqual(resposta["Content-Security-Policy"], CSP)
        self.assertEqual(resposta["Permissions-Policy"], PERMISSIONS_POLICY)

    def test_tela_publica(self):
        self.assert_cabecalhos(self.client.get(reverse("contas:login")))

    def test_tela_do_rh(self):
        self.client.force_login(self.rh)
        self.assert_cabecalhos(self.client.get(reverse("core:rh_colaboradores")))

    def test_api_e_recusa_da_api(self):
        self.assert_cabecalhos(self.client.get(reverse("api:conformidade")))   # 403 sem login
        self.client.force_login(self.rh)
        self.assert_cabecalhos(self.client.get(reverse("api:conformidade")))

    def test_pagina_de_erro_e_redirecionamento(self):
        self.assert_cabecalhos(self.client.get("/rota-que-nao-existe/"))
        self.assert_cabecalhos(self.client.get(reverse("core:rh_colaboradores")))   # redirect

    def test_telas_do_rh_carregam_o_vigent_js_e_usam_atributos_data(self):
        self.client.force_login(self.rh)
        Usuario.objects.create_user(email="colab@exemplo.invalid", nome="Colab Teste", password="x")

        html = self.client.get(reverse("core:rh_colaboradores")).content.decode()

        self.assertIn("/static/js/vigent.js", html)
        self.assertIn("data-envio-automatico", html)
        self.assertIn('data-confirmar="Remover a matrícula', html)

    def test_dashboard_carrega_o_script_em_arquivo(self):
        self.client.force_login(self.rh)
        html = self.client.get(reverse("core:rh_dashboard")).content.decode()
        self.assertIn("/static/js/dashboard.js", html)
        self.assertIsNone(SCRIPT_INLINE.search(re.sub(
            r'<script id="dash-endpoints" type="application/json">.*?</script>', "", html, flags=re.S)))


class SwaggerSemCdnTest(TestCase):
    """Swagger com arquivos servidos pelo Vigent (sidecar) e sem script inline."""

    def setUp(self):
        rh = Usuario.objects.create_user(
            email="rh@exemplo.invalid", nome="RH Teste", password="x",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceite_termo_vigente=True)
        self.client.force_login(rh)

    def test_pagina_do_swagger_so_usa_arquivos_locais(self):
        resposta = self.client.get(reverse("api:docs"))
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertIsNone(SCRIPT_INLINE.search(html))
        self.assertIn("/static/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js", html)

    def test_script_de_inicializacao_vem_em_requisicao_separada(self):
        resposta = self.client.get(reverse("api:docs") + "?script")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("javascript", resposta["Content-Type"])

    def test_arquivos_do_swagger_existem_localmente(self):
        self.assertIsNotNone(finders.find("drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js"))
